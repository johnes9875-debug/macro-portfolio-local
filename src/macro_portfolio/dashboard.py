from __future__ import annotations

import json
from pathlib import Path

import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
OPS_DB_PATH = PROJECT_ROOT / "data" / "operations.sqlite3"

st.set_page_config(page_title="Macro Portfolio Local", layout="wide")


def latest_pointer():
    p = STATE_DIR / "latest_run.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_df(run_dir: Path, name: str):
    p = run_dir / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def load_obj(run_dir: Path, name: str):
    pq = run_dir / f"{name}.parquet"
    js = run_dir / f"{name}.json"
    if pq.exists():
        return pd.read_parquet(pq)
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    return None


def metric_from_df(df, names, default="—"):
    if df.empty:
        return default
    for n in names:
        if n in df.columns:
            v = df.iloc[0][n]
            if isinstance(v, float):
                return f"{v:,.3f}"
            return str(v)
    return default


st.title("Macro Portfolio — Local Trading System")
ptr = latest_pointer()
if not ptr:
    st.warning("No successful local production run yet. Run `scripts\\run_once.bat` first.")
    st.stop()
run_dir = Path(ptr["run_dir"])

# If a newer attempt failed, keep showing the last successful snapshot but make the failure obvious.
if OPS_DB_PATH.exists():
    try:
        _con = sqlite3.connect(OPS_DB_PATH)
        _last_attempt = pd.read_sql_query(
            "SELECT * FROM local_pipeline_runs ORDER BY started_at DESC LIMIT 1", _con
        )
        _con.close()
        if not _last_attempt.empty and str(_last_attempt.iloc[0]["status"]).upper() == "FAILED":
            st.error(
                f"Latest attempted production run FAILED: {_last_attempt.iloc[0]['run_id']}. "
                "Dashboard remains pinned to the last successful run."
            )
    except Exception:
        pass

c1, c2, c3 = st.columns(3)
c1.metric("Latest NYSE session", ptr.get("market_session", "—"))
c2.metric("Run ID", ptr.get("run_id", "—"))
c3.metric("Storage", "LOCAL")

brief = run_dir / "daily_brief.md"
if brief.exists():
    with st.expander("What changed since the prior successful run", expanded=True):
        st.markdown(brief.read_text(encoding="utf-8"))

readiness = load_df(run_dir, "K2_READINESS")
portfolio = load_df(run_dir, "G_FINAL_PORTFOLIO_WEIGHTS")
trades = load_df(run_dir, "G_FINAL_TRADE_PLAN")
risk = load_df(run_dir, "G9_PATH_MC_SUMMARY")
alerts = load_df(run_dir, "H_FINAL_ALERTS")
sectors = load_df(run_dir, "FINAL_SECTOR_SIGNAL_DASHBOARD")
valuation = load_df(run_dir, "F_FINAL_VALUATION_HANDOFF")
actions = load_df(run_dir, "I_FINAL_ACTION_BOOK")
alpha = load_df(run_dir, "G1_FINAL_ALPHA_HANDOFF")
changes = pd.read_parquet(run_dir / "daily_changes.parquet") if (run_dir / "daily_changes.parquet").exists() else pd.DataFrame()
regime_prob = load_obj(run_dir, "ECONOMIC_REGIME_PROBABILITIES")
regime_summary = load_obj(run_dir, "LIVE_REGIME_SUMMARY")

# Readiness strip
st.subheader("Readiness")
if not readiness.empty:
    cols = st.columns(min(5, len(readiness.columns)))
    important = [
        "pipeline_operational_ready", "live_model_portfolio_ready",
        "real_money_execution_ready", "liquidity_failures", "critical_alerts"
    ]
    for col, name in zip(cols, [x for x in important if x in readiness.columns]):
        col.metric(name.replace("_", " ").title(), str(readiness.iloc[0][name]))
else:
    st.info("K2 readiness snapshot unavailable.")

tabs = st.tabs(["Overview", "Macro & Sectors", "Stocks & Valuation", "Portfolio & Trades", "Risk", "Alerts & Changes", "System"])

with tabs[0]:
    # Operator KPIs
    _cash = None
    _risky = None
    _action_count = 0
    key = next((c for c in ["ticker", "symbol"] if c in portfolio.columns), None) if not portfolio.empty else None
    weight = next((c for c in ["target_weight", "portfolio_weight", "weight"] if c in portfolio.columns), None) if not portfolio.empty else None
    if key and weight:
        _p = portfolio.copy()
        _p[weight] = pd.to_numeric(_p[weight], errors="coerce").fillna(0.0)
        _cash_rows = _p[_p[key].astype(str).str.upper() == "CASH"]
        _cash = float(_cash_rows[weight].sum()) if len(_cash_rows) else max(0.0, 1.0 - float(_p[weight].sum()))
        _risky = max(0.0, 1.0 - _cash)
    if not trades.empty and "trade_required" in trades.columns:
        _action_count = int(trades["trade_required"].fillna(False).astype(bool).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Risky exposure", "—" if _risky is None else f"{_risky:.1%}")
    k2.metric("Cash", "—" if _cash is None else f"{_cash:.1%}")
    k3.metric("Trades required", str(_action_count))
    _prob_loss = "—"
    if not risk.empty and "probability_of_loss" in risk.columns:
        try: _prob_loss = f"{float(risk.iloc[0]['probability_of_loss']):.1%}"
        except Exception: pass
    k4.metric("MC probability of loss", _prob_loss)

    if regime_prob is not None:
        st.subheader("Current regime probabilities")
        if isinstance(regime_prob, pd.DataFrame):
            st.dataframe(regime_prob, use_container_width=True, hide_index=True)
        elif isinstance(regime_prob, dict):
            _rdf = pd.DataFrame({"regime": list(regime_prob.keys()), "probability": list(regime_prob.values())})
            _rdf["probability"] = pd.to_numeric(_rdf["probability"], errors="coerce")
            st.plotly_chart(px.bar(_rdf, x="regime", y="probability"), use_container_width=True)
        else:
            st.write(regime_prob)

    st.subheader("Current portfolio")
    if not portfolio.empty:
        if key and weight:
            p = portfolio.copy()
            p[weight] = pd.to_numeric(p[weight], errors="coerce")
            fig = px.bar(p.sort_values(weight, ascending=False), x=key, y=weight, title="Target weights")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(portfolio, use_container_width=True, hide_index=True)
    st.subheader("Today's action book")
    st.dataframe(actions, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Sector signal dashboard")
    st.dataframe(sectors, use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Master alpha")
    st.dataframe(alpha, use_container_width=True, hide_index=True)
    st.subheader("Valuation")
    st.dataframe(valuation, use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Portfolio weights")
    st.dataframe(portfolio, use_container_width=True, hide_index=True)
    st.subheader("Trade plan")
    st.dataframe(trades, use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Empirical path Monte Carlo")
    st.dataframe(risk, use_container_width=True, hide_index=True)
    html = run_dir / "execution_cockpit.html"
    if html.exists():
        st.download_button("Download execution cockpit HTML", html.read_bytes(), file_name="execution_cockpit.html", mime="text/html")

with tabs[5]:
    st.subheader("Alerts")
    st.dataframe(alerts, use_container_width=True, hide_index=True)
    st.subheader("Tracked changes")
    st.dataframe(changes, use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Run history")
    if OPS_DB_PATH.exists():
        con = sqlite3.connect(OPS_DB_PATH)
        try:
            hist = pd.read_sql_query("SELECT * FROM local_pipeline_runs ORDER BY started_at DESC LIMIT 100", con)
            st.dataframe(hist, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(str(exc))
        finally:
            con.close()
    st.caption(f"Latest snapshot directory: {run_dir}")
