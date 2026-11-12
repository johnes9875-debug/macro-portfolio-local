from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from macro_portfolio.cockpit import render_cockpit
from macro_portfolio.ledger import build_snapshot, build_track_record, git_push_ledger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
LEDGER = PROJECT_ROOT / "ledger"
OPS_DB_PATH = PROJECT_ROOT / "data" / "operations.sqlite3"

st.set_page_config(page_title="Macro Portfolio", layout="wide")


def latest_pointer():
    p = STATE_DIR / "latest_run.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def read_csv(name: str) -> pd.DataFrame:
    p = LEDGER / name
    if not p.exists() or p.stat().st_size < 5:
        return pd.DataFrame()
    return pd.read_csv(p, comment="#")


def load_df(run_dir: Path, name: str) -> pd.DataFrame:
    p = run_dir / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def snapshot_for(run_dir: Path, run_id: str, session: str) -> dict:
    p = LEDGER / "snapshots" / f"{session}_{run_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return build_snapshot(PROJECT_ROOT, run_dir)


# ---------------------------------------------------------------- header
ptr = latest_pointer()
if not ptr:
    st.warning("No successful run yet. Run RUN_ME.ipynb (or scripts\\run_once.bat) first.")
    st.stop()

if OPS_DB_PATH.exists():
    try:
        with sqlite3.connect(OPS_DB_PATH) as con:
            last = pd.read_sql_query("SELECT * FROM local_pipeline_runs ORDER BY started_at DESC LIMIT 1", con)
        if not last.empty and str(last.iloc[0]["status"]).upper() == "FAILED":
            st.error(f"Latest attempted run FAILED ({last.iloc[0]['run_id']}). Showing the last successful run.")
    except Exception:
        pass

runs = read_csv("runs.csv")
run_options = {f"{r.market_session} · {r.run_id}": r for r in runs.itertuples()} if not runs.empty else {}
latest_label = f"{ptr['market_session']} · {ptr['run_id']}"
labels = list(reversed(list(run_options))) or [latest_label]
choice = st.sidebar.selectbox("Run", labels, index=labels.index(latest_label) if latest_label in labels else 0)
if choice == latest_label or choice not in run_options:
    run_dir, session, run_id = Path(ptr["run_dir"]), str(ptr["market_session"]), ptr["run_id"]
else:
    sel = run_options[choice]
    session, run_id = str(sel.market_session), sel.run_id
    run_dir = next((PROJECT_ROOT / "outputs" / "runs").glob(f"*/{run_id}"), Path(ptr["run_dir"]))

snap = snapshot_for(run_dir, run_id, session)
track = read_csv("track_record.csv")

tab_today, tab_history, tab_actual, tab_detail, tab_system = st.tabs(
    ["Today", "History and track record", "My actual holdings", "Detail tables", "System"])

# ---------------------------------------------------------------- today
with tab_today:
    t = track[track["to_session"] <= session] if not track.empty else None
    components.html(render_cockpit(snap, t, runs if not runs.empty else None), height=2600, scrolling=True)
    brief = run_dir / "daily_brief.md"
    if brief.exists():
        with st.expander("What changed since the previous run"):
            st.markdown(brief.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- history
with tab_history:
    if runs.empty:
        st.info("No ledger yet. Run `python -m macro_portfolio.ledger backfill`.")
    else:
        c1, c2 = st.columns(2)
        h = runs.copy()
        h["market_session"] = pd.to_datetime(h["market_session"])
        c1.plotly_chart(px.line(h, x="market_session", y=["invested", "expected_return", "prob_loss_1y"],
                                markers=True, title="Invested, expected return, chance of loss"), use_container_width=True)
        hold = read_csv("holdings_history.csv")
        if not hold.empty:
            hold = hold[hold["ticker"] != "CASH"]
            c2.plotly_chart(px.bar(hold, x="market_session", y="target_weight", color="ticker",
                                   title="Model holdings by run"), use_container_width=True)
        st.subheader("Track record (model, forward)")
        if track.empty:
            st.caption("Starts after the second recorded run.")
        else:
            tr = track.copy()
            tr["to_session"] = pd.to_datetime(tr["to_session"])
            st.plotly_chart(px.line(tr, x="to_session", y=["cumulative_model", "cumulative_spy"], markers=True,
                                    title="Cumulative return: model vs SPY"), use_container_width=True)
            st.dataframe(track, use_container_width=True, hide_index=True)
        st.subheader("Runs")
        st.dataframe(runs.sort_values("market_session", ascending=False), use_container_width=True, hide_index=True)
        st.subheader("Proposed trades")
        st.dataframe(read_csv("trades_history.csv").sort_values("market_session", ascending=False),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- actual holdings
with tab_actual:
    st.caption("Record what you actually bought after each run. Saved to ledger/actual_holdings.csv "
               "and pushed to GitHub with the ledger.")
    actual = read_csv("actual_holdings.csv")
    if actual.empty:
        actual = pd.DataFrame(columns=["date", "ticker", "shares", "avg_cost", "note"])
    edited = st.data_editor(actual, num_rows="dynamic", use_container_width=True, key="actual_editor")
    a, b = st.columns(2)
    if a.button("Save"):
        LEDGER.mkdir(exist_ok=True)
        edited.to_csv(LEDGER / "actual_holdings.csv", index=False)
        st.success("Saved")
    if b.button("Save and push to GitHub"):
        edited.to_csv(LEDGER / "actual_holdings.csv", index=False)
        st.info(git_push_ledger(PROJECT_ROOT, "ledger: update actual holdings"))

# ---------------------------------------------------------------- detail
with tab_detail:
    specs = {
        "Valuation": ("F_FINAL_VALUATION_HANDOFF", ["ticker", "company_name", "sector_ticker", "current_price",
                       "expected_intrinsic_value", "mos_price_threshold", "expected_upside_pct", "valuation_confidence",
                       "valuation_review_severity", "valuation_anomaly_reason", "valuation_entry_eligible"]),
        "Alpha ranking": ("G1_FINAL_ALPHA_HANDOFF", ["master_alpha_rank", "ticker", "company_name", "sector_ticker",
                          "master_alpha_score", "research_confidence", "mos_threshold_met", "entry_eligible_now", "research_status"]),
        "Action book": ("I_FINAL_ACTION_BOOK", ["ticker", "decision_category", "current_price", "buy_trigger_price",
                        "price_change_required_to_buy", "target_weight", "trade_required", "master_alpha_rank"]),
        "Sector signals": ("FINAL_SECTOR_SIGNAL_DASHBOARD", ["combined_rank", "ticker", "sector", "combined_signal",
                           "macro_rank", "market_rank", "macro_market_alignment", "hard_conflict", "risk_bucket"]),
        "Monte Carlo": ("G9_PATH_MC_SUMMARY", None),
        "Readiness": ("K2_READINESS", None),
    }
    for title, (obj, cols) in specs.items():
        df = load_df(run_dir, obj)
        with st.expander(title, expanded=(title == "Valuation")):
            if df.empty:
                st.caption("Not available for this run.")
                continue
            show = df[[c for c in cols if c in df.columns]] if cols else df
            st.dataframe(show, use_container_width=True, hide_index=True)
            with st.popover("All columns"):
                st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- system
with tab_system:
    if st.button("Rebuild track record"):
        build_track_record(PROJECT_ROOT)
        st.success("Rebuilt")
    if OPS_DB_PATH.exists():
        with sqlite3.connect(OPS_DB_PATH) as con:
            try:
                st.dataframe(pd.read_sql_query(
                    "SELECT * FROM local_pipeline_runs ORDER BY started_at DESC LIMIT 100", con),
                    use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(str(exc))
    st.caption(f"Snapshot directory: {run_dir}")
