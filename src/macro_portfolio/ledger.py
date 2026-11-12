"""Append-only run ledger: every successful run's model holdings, trades and
headline numbers, kept under ``ledger/`` and tracked in git.

Why: the live pipeline recomputes everything each run and only keeps the
latest snapshot pointer. The ledger is the permanent record that lets you
measure a forward (paper) track record — what the model held, at what price,
and what it actually returned until the next run — and compare it with what
you really executed (``ledger/actual_holdings.csv``).

Files (all UTF-8 CSV / JSON, safe to commit):

    ledger/runs.csv                one row per run: KPIs, regime, readiness
    ledger/holdings_history.csv    one row per (run, ticker) with weight > 0
    ledger/trades_history.csv      one row per proposed trade
    ledger/track_record.csv        period returns between consecutive runs
    ledger/snapshots/<run>.json    compact payload the dashboards read
    ledger/actual_holdings.csv     YOUR real positions (edit by hand)

Every write is idempotent per run_id, so re-recording a run replaces it.

CLI:
    python -m macro_portfolio.ledger backfill     # record every archived run
    python -m macro_portfolio.ledger record <run_dir>
    python -m macro_portfolio.ledger push         # git add/commit/push ledger/
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

LEDGER_VERSION = "1.0.0"

# Weights below this are optimizer residue, not positions (mirrors
# portfolio.min_position_weight in settings.yaml; overridable via record_run).
DEFAULT_MIN_POSITION_WEIGHT = 0.005

TRADE_ACTIONS = {"BUY", "SELL", "TRIM", "ADD"}
NOISE_TRIGGER_TYPES = {"SNAPSHOT_CHANGE"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load(run_dir: Path, name: str):
    pq = run_dir / f"{name}.parquet"
    js = run_dir / f"{name}.json"
    if pq.exists():
        return pd.read_parquet(pq)
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    return None


def _df(obj) -> pd.DataFrame:
    return obj if isinstance(obj, pd.DataFrame) else pd.DataFrame()


def _row(df: pd.DataFrame) -> dict:
    return {} if df.empty else df.iloc[0].to_dict()


def _clean(v):
    """JSON-safe scalar."""
    if v is None:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v if isinstance(v, (str, int)) else str(v)


def _records(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    if df.empty:
        return []
    keep = [c for c in cols if c in df.columns]
    return [{k: _clean(v) for k, v in r.items()} for r in df[keep].to_dict(orient="records")]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def ledger_dir(project_root: Path) -> Path:
    d = Path(project_root) / "ledger"
    (d / "snapshots").mkdir(parents=True, exist_ok=True)
    return d


def _price_file(project_root: Path, ticker: str) -> Path:
    sym = str(ticker).upper().replace(".", "-")
    stock = Path(project_root) / "data" / "raw" / "stocks" / "prices" / f"{sym}.parquet"
    if stock.exists():
        return stock
    return Path(project_root) / "data" / "raw" / "market" / f"{sym}.parquet"


def price_on(project_root: Path, ticker: str, session, field: str = "adj_close"):
    """Last close on or before ``session`` from the local price cache."""
    p = _price_file(project_root, ticker)
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p, columns=["date", field])
    except Exception:
        try:
            df = pd.read_parquet(p, columns=["date", "close"]).rename(columns={"close": field})
        except Exception:
            return None
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df[df["date"] <= pd.Timestamp(session)].dropna(subset=[field])
    if df.empty:
        return None
    return float(df.iloc[-1][field])


def _upsert_csv(path: Path, new: pd.DataFrame, key: str = "run_id") -> pd.DataFrame:
    if path.exists():
        old = pd.read_csv(path)
        if key in old.columns and not new.empty:
            old = old[~old[key].isin(set(new[key]))]
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    sort_cols = [c for c in ["market_session", "run_id", "ticker"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, kind="stable")
    out.to_csv(path, index=False)
    return out


def _not_traded(not_traded: pd.DataFrame, residue: pd.DataFrame, min_weight: float) -> pd.DataFrame:
    frames = []
    if not not_traded.empty:
        frames.append(not_traded.assign(reason=f"below {min_weight:.1%} minimum position"))
    if not residue.empty:
        frames.append(residue.assign(reason="optimizer residue"))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["target_weight"] = _num(out, "target_weight").fillna(0.0)
    out.loc[out["target_weight"] < 1e-4, "reason"] = "optimizer residue"
    return out.sort_values("target_weight", ascending=False).drop_duplicates("ticker")


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

def build_snapshot(project_root: Path, run_dir: Path, min_weight: float = DEFAULT_MIN_POSITION_WEIGHT) -> dict:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")) if (run_dir / "manifest.json").exists() else {}
    session = manifest.get("market_session") or run_dir.parent.name
    run_id = manifest.get("run_id") or run_dir.name

    port = _df(_load(run_dir, "G_FINAL_PORTFOLIO_WEIGHTS"))
    trades = _df(_load(run_dir, "G_FINAL_TRADE_PLAN"))
    psum = _row(_df(_load(run_dir, "G_FINAL_PORTFOLIO_SUMMARY")))
    ready = _row(_df(_load(run_dir, "K2_READINESS")))
    regime = _row(_df(_load(run_dir, "LIVE_REGIME_SUMMARY")))
    probs = _df(_load(run_dir, "ECONOMIC_REGIME_PROBABILITIES"))
    sectors = _df(_load(run_dir, "FINAL_SECTOR_SIGNAL_DASHBOARD"))
    val = _df(_load(run_dir, "F_FINAL_VALUATION_HANDOFF"))
    alerts = _df(_load(run_dir, "H_FINAL_ALERTS"))
    mon = _df(_load(run_dir, "H_FINAL_MONITORING_SNAPSHOT"))
    mc = _row(_df(_load(run_dir, "G9_PATH_MC_SUMMARY")))
    daily = _row(_df(_load(run_dir, "I_FINAL_DAILY_SUMMARY")))

    # ---- holdings (model) --------------------------------------------------
    vcols = ["ticker", "company_name", "current_price", "expected_intrinsic_value", "mos_price_threshold",
             "expected_upside_pct", "valuation_review_severity", "valuation_anomaly_reason", "valuation_confidence"]
    v = val[[c for c in vcols if c in val.columns]] if not val.empty else pd.DataFrame(columns=["ticker"])
    hold = pd.DataFrame()
    if not port.empty:
        p = port.copy()
        p["target_weight"] = _num(p, "target_weight").fillna(0.0)
        p["previous_weight"] = _num(p, "previous_weight").fillna(0.0)
        p["is_cash"] = p["ticker"].astype(str).str.upper() == "CASH"
        stocks = p[~p["is_cash"]].copy()
        stocks["residue"] = (stocks["target_weight"] > 0) & (stocks["target_weight"] < min_weight)
        hold = stocks[stocks["target_weight"] >= min_weight]
        hold = hold.merge(v.drop(columns=[c for c in ["company_name"] if c in v.columns and "company_name" in hold.columns]),
                          on="ticker", how="left")
        hold = hold.sort_values("target_weight", ascending=False)
        residue = stocks[stocks["residue"]]
    else:
        residue = pd.DataFrame()

    invested = float(hold["target_weight"].sum()) if not hold.empty else 0.0

    # ---- trades -------------------------------------------------------------
    t = trades.copy()
    if not t.empty:
        t["target_weight"] = _num(t, "target_weight").fillna(0.0)
        t["previous_weight"] = _num(t, "previous_weight").fillna(0.0)
        t["trade_notional"] = _num(t, "trade_notional")
        side = np.where(t["target_weight"] > t["previous_weight"], "BUY", "SELL")
        side = np.where((side == "SELL") & (t["target_weight"] >= min_weight), "TRIM", side)
        side = np.where((side == "BUY") & (t["previous_weight"] >= min_weight), "ADD", side)
        t["side"] = side
        act = t.get("action", pd.Series("", index=t.index)).astype(str).str.upper()
        executable = act.isin(["BUY", "SELL"]) & (t["ticker"].astype(str).str.upper() != "CASH")
        # Residue / below-min-size buys are not real trades.
        executable &= ~((t["side"] == "BUY") & (t["target_weight"] < min_weight))
        t["executable"] = executable
        t = t.merge(v[[c for c in ["ticker", "mos_price_threshold", "valuation_review_severity"] if c in v.columns]],
                    on="ticker", how="left")
        t["below_buy_price_pct"] = np.where(
            _num(t, "mos_price_threshold") > 0,
            1.0 - _num(t, "current_price") / _num(t, "mos_price_threshold"), np.nan)
        trade_rows = t[t["executable"]].copy()
        trade_rows["abs_n"] = trade_rows["trade_notional"].abs()
        trade_rows = trade_rows.sort_values(["side", "abs_n"], ascending=[True, False])
        not_traded = t[(~t["executable"]) & (t["target_weight"] > 0) & (t["ticker"].astype(str).str.upper() != "CASH")
                       & (t["previous_weight"] < min_weight)]
    else:
        trade_rows = not_traded = pd.DataFrame()

    # ---- flags (things that need a human) -----------------------------------
    flags = []
    held = set(hold["ticker"]) if not hold.empty else set()
    buys = set(trade_rows.loc[trade_rows["side"].isin(["BUY", "ADD"]), "ticker"]) if not trade_rows.empty else set()
    if not v.empty and "valuation_review_severity" in v.columns:
        rev = v[v["valuation_review_severity"].isin(["REVIEW", "CRITICAL_REVIEW"]) & v["ticker"].isin(held | buys)]
        for _, r in rev.iterrows():
            flags.append({"severity": "WARNING", "type": "VALUATION_REVIEW", "ticker": r["ticker"],
                          "message": f"{r['ticker']} is in the target portfolio but its valuation is flagged "
                                     f"{str(r['valuation_review_severity']).replace('_', ' ').lower()}"
                                     + (f" ({r['valuation_anomaly_reason']})" if isinstance(r.get("valuation_anomaly_reason"), str) and r.get("valuation_anomaly_reason") else "")})
    if not alerts.empty:
        for _, r in alerts.iterrows():
            at = str(r.get("alert_type", ""))
            if at in NOISE_TRIGGER_TYPES or at == "VALUATION_REVIEW":
                continue  # valuation review rebuilt above without residue names
            flags.append({"severity": _clean(r.get("severity")), "type": at,
                          "ticker": _clean(r.get("ticker")), "message": _clean(r.get("message"))})
    blocked = val[val.get("valuation_critical_block", pd.Series(False, index=val.index)).fillna(False).astype(bool)] if not val.empty else pd.DataFrame()

    # ---- watchlist: closest names to their buy price, not held ---------------
    watch = pd.DataFrame()
    if not mon.empty and "distance_to_mos_pct" in mon.columns:
        w = mon.copy()
        w["distance_to_mos_pct"] = _num(w, "distance_to_mos_pct")
        w = w[~w["ticker"].isin(held) & w["distance_to_mos_pct"].notna()]
        w = w[w["distance_to_mos_pct"] > 0].sort_values("distance_to_mos_pct").head(10)
        watch = w

    # ---- sectors ------------------------------------------------------------
    sec = sectors.copy()
    if not sec.empty:
        sec = sec.sort_values("combined_rank") if "combined_rank" in sec.columns else sec
        sector_weights = hold.groupby("sector_ticker")["target_weight"].sum().to_dict() if not hold.empty and "sector_ticker" in hold.columns else {}
        sec["model_weight"] = sec["ticker"].map(sector_weights).fillna(0.0)
        # pipeline stores relative returns in percent units; ledger uses fractions
        if "relative_3m" in sec.columns:
            sec["relative_3m"] = _num(sec, "relative_3m") / 100.0

    # ---- prices for track record ---------------------------------------------
    price_tickers = set(hold["ticker"]) if not hold.empty else set()
    if not t.empty:
        price_tickers |= set(t.loc[t["previous_weight"] > 0, "ticker"])
    # Also price the previous recorded run's holdings so the forward track record
    # can mark them at this run even if they are no longer in the trade plan.
    try:
        prior = sorted(p for p in (Path(project_root) / "ledger" / "snapshots").glob("*.json")
                       if p.name[:10] < str(session)[:10])
        if prior:
            price_tickers |= {h["ticker"] for h in json.loads(prior[-1].read_text(encoding="utf-8")).get("holdings", [])}
    except Exception:
        pass
    price_tickers.discard("CASH")
    prices = {}
    for tk in sorted(price_tickers):
        px = price_on(project_root, tk, session)
        if px is None and not t.empty and tk in set(t["ticker"]):
            px = _clean(t.loc[t["ticker"] == tk, "current_price"].iloc[0])
        prices[tk] = px
    benchmark_px = price_on(project_root, "SPY", session)
    if not trade_rows.empty:
        trade_rows["current_price"] = _num(trade_rows, "current_price").fillna(trade_rows["ticker"].map(
            lambda tk: price_on(project_root, tk, session, field="close")))

    snap = {
        "ledger_version": LEDGER_VERSION,
        "run_id": run_id,
        "market_session": str(session)[:10],
        "created_at": manifest.get("created_at"),
        "system_version": manifest.get("system_version"),
        "state": {
            "portfolio_state_mode": _clean(ready.get("portfolio_state_mode")),
            "portfolio_state_is_actual": _clean(ready.get("portfolio_state_is_actual")),
            "real_money_execution_ready": _clean(ready.get("real_money_execution_ready")),
            "pipeline_operational_ready": _clean(ready.get("pipeline_operational_ready")),
            "pit_backtest_ready": _clean(ready.get("pit_backtest_ready")),
            "critical_alerts": _clean(ready.get("critical_alerts")),
            "liquidity_failures": _clean(ready.get("liquidity_failures")),
            "previous_snapshot": _clean(daily.get("previous_snapshot")),
        },
        "kpis": {
            "nav": _clean(psum.get("portfolio_nav")),
            "invested": round(invested, 6),
            "cash": round(1.0 - invested, 6),
            "positions": int(len(hold)),
            "expected_return": _clean(psum.get("expected_return_net_first_year", psum.get("expected_return_gross"))),
            "expected_volatility": _clean(psum.get("expected_volatility")),
            "expected_sharpe": _clean(psum.get("expected_sharpe")),
            "prob_loss_1y": _clean(mc.get("probability_of_loss", psum.get("monte_carlo_probability_of_loss"))),
            "var_99_1y": _clean(mc.get("var_99", psum.get("monte_carlo_var_99"))),
            "median_max_drawdown": _clean(mc.get("median_max_drawdown")),
            "turnover": _clean(psum.get("turnover")),
            "transaction_cost": _clean(psum.get("transaction_cost")),
            "largest_sector_weight": _clean(psum.get("largest_sector_weight")),
            "portfolio_beta": _clean(daily.get("portfolio_beta")),
            "trades": int(len(trade_rows)),
        },
        "regime": {
            "label": _clean(regime.get("economic_regime")),
            # Use the published probability table so header and bars agree
            # (LIVE_REGIME_SUMMARY.top_probability is a different, unnormalised figure).
            "top_candidate": _clean(probs.sort_values("probability").iloc[-1]["regime"]) if not probs.empty else _clean(regime.get("top_regime_candidate")),
            "top_probability": _clean(probs["probability"].max()) if not probs.empty else _clean(regime.get("top_probability")),
            "growth": _clean(regime.get("growth_axis_label")),
            "inflation": _clean(regime.get("inflation_axis_label")),
            "financial_conditions": _clean(regime.get("financial_conditions")),
            "probabilities": _records(probs, ["regime", "probability"]),
        },
        "sectors": _records(sec, ["ticker", "sector", "combined_rank", "combined_signal", "macro_market_alignment",
                                  "hard_conflict", "relative_3m", "model_weight"]),
        "holdings": _records(hold, ["ticker", "company_name", "sector_ticker", "previous_weight", "target_weight",
                                    "expected_total_return_annual", "risk_contribution_share", "current_price",
                                    "expected_intrinsic_value", "mos_price_threshold", "valuation_review_severity"]),
        "trades": _records(trade_rows, ["ticker", "company_name", "sector_ticker", "side", "previous_weight",
                                        "target_weight", "trade_notional", "trade_shares_est", "current_price",
                                        "below_buy_price_pct", "valuation_review_severity", "liquidity_check"]),
        "not_traded": _records(_not_traded(not_traded, residue, min_weight),
                               ["ticker", "target_weight", "reason"]),
        "flags": flags,
        "blocked": _records(blocked, ["ticker", "company_name", "valuation_anomaly_reason", "iv_price_ratio"]),
        "watchlist": _records(watch, ["ticker", "company_name", "sector_ticker", "current_price",
                                      "mos_price_threshold", "distance_to_mos_pct"]),
        "prices": {k: _clean(v) for k, v in prices.items()},
        "benchmark": {"ticker": "SPY", "price": _clean(benchmark_px)},
    }
    return snap


# ---------------------------------------------------------------------------
# record + track record
# ---------------------------------------------------------------------------

def record_run(project_root: Path, run_dir: Path, min_weight: float = DEFAULT_MIN_POSITION_WEIGHT) -> dict:
    project_root = Path(project_root)
    d = ledger_dir(project_root)
    snap = build_snapshot(project_root, run_dir, min_weight=min_weight)
    rid, sess = snap["run_id"], snap["market_session"]
    try:
        from .paper import summary as paper_summary
        paper = paper_summary(project_root)
        if paper:
            snap["paper"] = paper
    except Exception:
        pass
    # v1.0.14: institutional risk / limits panel and per-holding valuation sheets
    try:
        from .paper import load_config
        from .risk_panel import build_risk_panel
        cfg = load_config(project_root)
        review = [h["ticker"] for h in snap["holdings"] if h.get("valuation_review_severity") in ("REVIEW", "CRITICAL_REVIEW")]
        snap["risk"] = build_risk_panel(project_root, snap["holdings"], sess, cfg, float(snap["kpis"].get("nav") or 1_000_000),
                                        blocked=[b["ticker"] for b in snap.get("blocked", [])], review=review)
    except Exception as exc:
        snap["risk"] = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    try:
        from .paper import load_config
        from .valuation_sheet import build_sheets
        names = [h["ticker"] for h in snap["holdings"]] + [t["ticker"] for t in snap["trades"] if t["side"] in ("BUY", "ADD")]
        snap["valuation_sheets"] = build_sheets(project_root, run_dir, list(dict.fromkeys(names)), load_config(project_root))
    except Exception as exc:
        snap["valuation_sheets"] = {}
        snap.setdefault("warnings", []).append(f"valuation sheets: {type(exc).__name__}: {exc}")

    (d / "snapshots" / f"{sess}_{rid}.json").write_text(json.dumps(snap, indent=1), encoding="utf-8")

    k, r, s = snap["kpis"], snap["regime"], snap["state"]
    runs_row = pd.DataFrame([{
        "market_session": sess, "run_id": rid, "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "system_version": snap["system_version"], "state_mode": s["portfolio_state_mode"],
        "real_money_ready": s["real_money_execution_ready"], "positions": k["positions"],
        "invested": k["invested"], "cash": k["cash"], "expected_return": k["expected_return"],
        "expected_volatility": k["expected_volatility"], "expected_sharpe": k["expected_sharpe"],
        "prob_loss_1y": k["prob_loss_1y"], "turnover": k["turnover"], "trades": k["trades"],
        "regime": r["label"], "regime_top": r["top_candidate"], "regime_top_prob": r["top_probability"],
        "financial_conditions": r["financial_conditions"],
        "top_sectors": "|".join(x["ticker"] for x in snap["sectors"][:3]),
        "spy_price": snap["benchmark"]["price"],
    }])
    _upsert_csv(d / "runs.csv", runs_row)

    hold = pd.DataFrame(snap["holdings"])
    if not hold.empty:
        hold.insert(0, "run_id", rid)
        hold.insert(0, "market_session", sess)
        hold["ledger_price"] = hold["ticker"].map(snap["prices"])
        hold["source"] = "MODEL"
    else:
        hold = pd.DataFrame([{"market_session": sess, "run_id": rid, "ticker": "CASH", "target_weight": 1.0, "source": "MODEL"}])
    _upsert_csv(d / "holdings_history.csv", hold)

    tr = pd.DataFrame(snap["trades"])
    if tr.empty:
        tr = pd.DataFrame(columns=["ticker"])
    tr.insert(0, "run_id", rid)
    tr.insert(0, "market_session", sess)
    _upsert_csv(d / "trades_history.csv", tr)

    actual = d / "actual_holdings.csv"
    if not actual.exists():
        actual.write_text(
            "date,ticker,shares,avg_cost,note\n"
            "# Add one row per position you ACTUALLY hold after you trade. Example:\n"
            "# 2026-11-13,MO,1290,77.40,bought after 11 Nov run\n",
            encoding="utf-8")

    build_track_record(project_root)
    return snap


def build_track_record(project_root: Path) -> pd.DataFrame:
    """Forward (paper) returns of the MODEL portfolio between consecutive runs.

    Holdings set at run t are marked to market at run t+1 using adjusted closes
    from the local price cache (falls back to the ledger's recorded price).
    Cash earns 0 here; this is deliberately conservative and simple.
    """
    d = ledger_dir(project_root)
    snaps = []
    for p in sorted((d / "snapshots").glob("*.json")):
        try:
            snaps.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    snaps.sort(key=lambda s: (s["market_session"], s["run_id"]))
    # one snapshot per session (latest run of the day wins)
    by_session = {}
    for s in snaps:
        by_session[s["market_session"]] = s
    snaps = [by_session[k] for k in sorted(by_session)]

    rows, cum, cum_spy = [], 1.0, 1.0
    for a, b in zip(snaps, snaps[1:]):
        t0, t1 = a["market_session"], b["market_session"]
        contrib, missing = 0.0, []
        for h in a["holdings"]:
            tk, w = h["ticker"], float(h.get("target_weight") or 0)
            p0 = price_on(project_root, tk, t0) or a["prices"].get(tk)
            p1 = price_on(project_root, tk, t1) or b["prices"].get(tk)
            if not p0 or not p1:
                missing.append(tk)
                continue
            contrib += w * (p1 / p0 - 1.0)
        s0 = price_on(project_root, "SPY", t0) or a["benchmark"].get("price")
        s1 = price_on(project_root, "SPY", t1) or b["benchmark"].get("price")
        spy = (s1 / s0 - 1.0) if (s0 and s1) else None
        days = (pd.Timestamp(t1) - pd.Timestamp(t0)).days
        exp = a["kpis"].get("expected_return")
        exp_period = ((1 + exp) ** (days / 365.0) - 1) if exp is not None else None
        cum *= 1 + contrib
        if spy is not None:
            cum_spy *= 1 + spy
        rows.append({
            "from_session": t0, "to_session": t1, "days": days,
            "from_run_id": a["run_id"], "invested": a["kpis"].get("invested"),
            "model_return": round(contrib, 6),
            "expected_return_for_period": None if exp_period is None else round(exp_period, 6),
            "spy_return": None if spy is None else round(spy, 6),
            "excess_vs_spy": None if spy is None else round(contrib - spy, 6),
            "cumulative_model": round(cum - 1, 6), "cumulative_spy": round(cum_spy - 1, 6),
            "missing_prices": "|".join(missing),
        })
    out = pd.DataFrame(rows)
    out.to_csv(d / "track_record.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------

def git_push_ledger(project_root: Path, message: str | None = None) -> str:
    """Commit and push ledger/ only. Never stages anything else (e.g. .env)."""
    root = Path(project_root)
    if not (root / ".git").exists():
        return "SKIPPED: project folder is not a git clone"

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=120)

    git("add", "--", "ledger")
    if git("diff", "--cached", "--quiet", "--", "ledger").returncode == 0:
        return "NO_CHANGES"
    msg = message or f"ledger: record run {datetime.now():%Y-%m-%d %H:%M}"
    c = git("commit", "-m", msg, "--", "ledger")
    if c.returncode != 0:
        return f"COMMIT_FAILED: {c.stderr.strip()[:300]}"
    p = git("push")
    if p.returncode != 0:
        return f"PUSH_FAILED (committed locally): {p.stderr.strip()[:300]}"
    return "PUSHED"


def backfill(project_root: Path, min_weight: float = DEFAULT_MIN_POSITION_WEIGHT) -> list[str]:
    root = Path(project_root)
    done = []
    for run_dir in sorted((root / "outputs" / "runs").glob("*/*")):
        if (run_dir / "G_FINAL_PORTFOLIO_WEIGHTS.parquet").exists():
            record_run(root, run_dir, min_weight=min_weight)
            done.append(run_dir.name)
    return done


def _main(argv):
    from .runtime import repository_root  # local import: CLI convenience only
    root = repository_root()
    cmd = argv[1] if len(argv) > 1 else "backfill"
    if cmd == "backfill":
        print("Recorded:", ", ".join(backfill(root)) or "nothing")
    elif cmd == "record":
        record_run(root, Path(argv[2]))
        print("Recorded", argv[2])
    elif cmd == "push":
        print(git_push_ledger(root))
    else:
        print(__doc__)


if __name__ == "__main__":
    _main(sys.argv)
