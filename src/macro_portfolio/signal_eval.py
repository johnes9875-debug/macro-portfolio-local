"""Do the signals work? Record every run's signals, then score them against
what actually happened.

Idea borrowed from Trading-R1's labelling (volatility-normalised forward
returns mapped to five classes, with false bullish calls penalised more), used
here to EVALUATE this system's signals, not to train anything.

Recorded each run (ledger/signals_history.csv):
  stock rows : master alpha, sector / company / valuation components, model
               expected upside, consensus upside, MOS flag, entry eligibility,
               target weight, price
  sector rows: combined sector score/rank and model weight

Scored (ledger/signal_quality.csv, summary in the snapshot):
  outcome z  = (stock return - SPY return over h sessions)
               / (stock daily vol over the 63 sessions before the run * sqrt(h))
  label      = strong buy  z >= 1 | buy 0.25..1 | hold -0.25..0.25 |
               sell -1..-0.25 | strong sell <= -1
  metrics    = rank IC (Spearman of signal vs z), top-minus-bottom quintile z,
               hit rate of the model's buys (z > 0), and an asymmetric score for
               buys: +1 if label is buy/strong buy, -1.5 if sell/strong sell
               (a false buy costs more than a missed one), 0 otherwise
  horizons   = 21 and 63 sessions (about 1 and 3 months)

Also scores the macro sector layer historically from Section L's monthly
target weights (tilt vs equal weight against next-month sector ETF returns).
Small samples are labelled as such; nothing here is significant until there
are many runs.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (21, 63)
VOL_WINDOW = 63
LABELS = [(1.0, "strong buy"), (0.25, "buy"), (-0.25, "hold"), (-1.0, "sell")]
STOCK_SIGNALS = {
    "master_alpha_score": "Master alpha (what the model ranks on)",
    "sector_signal": "Sector component",
    "company_selection_signal": "Company component",
    "valuation_signal_normalized": "Valuation component",
    "expected_upside_pct": "Model expected upside",
    "consensus_upside_pct": "Analyst consensus upside (benchmark)",
}


def label(z: float) -> str:
    for cut, name in LABELS:
        if z >= cut:
            return name
    return "strong sell"


def _px(root: Path, ticker: str) -> pd.Series | None:
    sym = str(ticker).upper().replace(".", "-")
    for p in (Path(root) / "data/raw/stocks/prices" / f"{sym}.parquet", Path(root) / "data/raw/market" / f"{sym}.parquet"):
        if p.exists():
            d = pd.read_parquet(p, columns=["date", "adj_close"])
            d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None).dt.normalize()
            return pd.to_numeric(d.drop_duplicates("date").set_index("date").sort_index()["adj_close"], errors="coerce").dropna()
    return None


# ---------------------------------------------------------------------------
# recording
# ---------------------------------------------------------------------------

def record_signals(root: Path, run_dir: Path, session: str, run_id: str) -> pd.DataFrame:
    run_dir = Path(run_dir)
    led = Path(root) / "ledger"
    led.mkdir(exist_ok=True)
    rows = []
    g1p, fp = run_dir / "G1_FINAL_ALPHA_HANDOFF.parquet", run_dir / "F_FINAL_VALUATION_HANDOFF.parquet"
    if g1p.exists():
        g = pd.read_parquet(g1p)
        f = pd.read_parquet(fp)[["ticker", "consensus_upside_pct"]] if fp.exists() else pd.DataFrame(columns=["ticker"])
        w = pd.read_parquet(run_dir / "G_FINAL_PORTFOLIO_WEIGHTS.parquet")[["ticker", "target_weight"]] \
            if (run_dir / "G_FINAL_PORTFOLIO_WEIGHTS.parquet").exists() else pd.DataFrame(columns=["ticker", "target_weight"])
        g = g.merge(f, on="ticker", how="left").merge(w, on="ticker", how="left")
        keep = ["ticker", "sector_ticker", "master_alpha_score", "master_alpha_rank", "sector_signal",
                "company_selection_signal", "valuation_signal_normalized", "expected_upside_pct",
                "consensus_upside_pct", "mos_threshold_met", "entry_eligible_now", "valuation_review_severity",
                "target_weight", "current_price"]
        g = g[[c for c in keep if c in g.columns]].copy()
        g["target_weight"] = pd.to_numeric(g.get("target_weight"), errors="coerce").fillna(0.0)
        g.insert(0, "kind", "stock")
        rows.append(g)
    sp = run_dir / "FINAL_SECTOR_SIGNAL_DASHBOARD.parquet"
    if sp.exists():
        s = pd.read_parquet(sp)
        s = s[[c for c in ["ticker", "combined_score_z", "combined_rank", "macro_rank", "market_rank"] if c in s.columns]].copy()
        s.insert(0, "kind", "sector")
        rows.append(s)
    if not rows:
        return pd.DataFrame()
    new = pd.concat(rows, ignore_index=True)
    new.insert(0, "run_id", run_id)
    new.insert(0, "market_session", str(session)[:10])
    path = led / "signals_history.csv"
    if path.exists():
        old = pd.read_csv(path)
        old = old[old["run_id"] != run_id]
        new = pd.concat([old, new], ignore_index=True)
    new.sort_values(["market_session", "run_id", "kind", "ticker"]).to_csv(path, index=False)
    return new


# ---------------------------------------------------------------------------
# outcomes
# ---------------------------------------------------------------------------

def outcome(root: Path, ticker: str, session, h: int, spy: pd.Series, cache: dict) -> dict | None:
    px = cache.get(ticker)
    if px is None:
        px = cache[ticker] = _px(root, ticker)
    if px is None:
        return None
    s = pd.Timestamp(session)
    past = px[px.index <= s]
    fut = px[px.index > s]
    if len(past) < VOL_WINDOW + 1 or len(fut) < h:
        return None
    p0, p1 = float(past.iloc[-1]), float(fut.iloc[h - 1])
    end = fut.index[h - 1]
    sp0, sp1 = float(spy[spy.index <= s].iloc[-1]), float(spy[spy.index <= end].iloc[-1])
    vol = float(past.pct_change().iloc[-VOL_WINDOW:].std())
    if not vol or math.isnan(vol):
        return None
    excess = (p1 / p0 - 1) - (sp1 / sp0 - 1)
    z = excess / (vol * math.sqrt(h))
    return {"end": str(end.date()), "return": p1 / p0 - 1, "excess": excess, "z": z, "label": label(z)}


def _spearman(a, b):
    a, b = pd.Series(a).rank(), pd.Series(b).rank()
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def evaluate(root: Path) -> dict:
    root = Path(root)
    led = root / "ledger"
    path = led / "signals_history.csv"
    if not path.exists():
        return {}
    hist = pd.read_csv(path)
    hist = hist.sort_values(["market_session", "run_id"]).groupby(["market_session", "kind", "ticker"], as_index=False).last()
    spy = _px(root, "SPY")
    cache: dict = {}
    detail, per_run = [], []
    for (sess, kind), grp in hist.groupby(["market_session", "kind"]):
        for h in HORIZONS:
            outs = []
            for _, r in grp.iterrows():
                o = outcome(root, r["ticker"], sess, h, spy, cache)
                if o:
                    outs.append({**r.to_dict(), **o, "horizon": h})
            if len(outs) < 5:
                continue
            d = pd.DataFrame(outs)
            detail.append(d)
            sigs = STOCK_SIGNALS if kind == "stock" else {"combined_score_z": "Sector combined signal"}
            for col, name in sigs.items():
                if col not in d.columns:
                    continue
                x = pd.to_numeric(d[col], errors="coerce")
                ok = x.notna()
                if ok.sum() < 5:
                    continue
                ic = _spearman(x[ok], d.loc[ok, "z"])
                q = pd.qcut(x[ok].rank(method="first"), 5, labels=False) if ok.sum() >= 10 else None
                spread = None
                if q is not None:
                    zz = d.loc[ok, "z"].values
                    spread = float(zz[q.values == 4].mean() - zz[q.values == 0].mean())
                per_run.append({"market_session": sess, "kind": kind, "horizon": h, "signal": col, "signal_name": name,
                                "n": int(ok.sum()), "rank_ic": ic, "top_minus_bottom_quintile_z": spread})
            if kind == "stock" and "target_weight" in d.columns:
                buys = d[pd.to_numeric(d["target_weight"], errors="coerce").fillna(0) > 0]
                if len(buys):
                    score = buys["label"].map(lambda l: 1.0 if l in ("buy", "strong buy") else (-1.5 if l in ("sell", "strong sell") else 0.0))
                    per_run.append({"market_session": sess, "kind": "portfolio", "horizon": h, "signal": "model_buys",
                                    "signal_name": "Stocks the model held/bought", "n": int(len(buys)),
                                    "hit_rate": float((buys["z"] > 0).mean()), "asymmetric_score": float(score.mean()),
                                    "mean_z": float(buys["z"].mean())})
    runs = pd.DataFrame(per_run)
    det = pd.concat(detail, ignore_index=True) if detail else pd.DataFrame()
    if not det.empty:
        det.to_csv(led / "signal_outcomes.csv", index=False)
    if not runs.empty:
        runs.to_csv(led / "signal_quality.csv", index=False)

    summary = {"sessions_recorded": int(hist["market_session"].nunique()), "horizons": list(HORIZONS), "signals": []}
    if not runs.empty:
        for (sig, h), g in runs[runs["kind"] != "portfolio"].groupby(["signal", "horizon"]):
            ics = g["rank_ic"].dropna()
            summary["signals"].append({
                "signal": sig, "name": g["signal_name"].iloc[0], "horizon": int(h), "runs_scored": int(len(ics)),
                "mean_ic": float(ics.mean()) if len(ics) else None,
                "ic_t_stat": float(ics.mean() / ics.std() * math.sqrt(len(ics))) if len(ics) > 2 and ics.std() > 0 else None,
                "mean_quintile_spread_z": float(g["top_minus_bottom_quintile_z"].dropna().mean()) if g["top_minus_bottom_quintile_z"].notna().any() else None,
            })
        pb = runs[runs["kind"] == "portfolio"]
        summary["model_buys"] = [{"horizon": int(h), "runs_scored": int(len(g)), "hit_rate": float(g["hit_rate"].mean()),
                                  "asymmetric_score": float(g["asymmetric_score"].mean()), "mean_z": float(g["mean_z"].mean()),
                                  "positions_scored": int(g["n"].sum())} for h, g in pb.groupby("horizon")]
    summary["sector_layer_history"] = evaluate_section_l(root)
    summary["note"] = ("Fewer than 12 scored runs: treat every number as anecdotal."
                       if max([s["runs_scored"] for s in summary["signals"]] + [0]) < 12 else "")
    (led / "signal_quality_summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    return summary


def evaluate_section_l(root: Path) -> dict:
    """Historical check of the macro sector layer from Section L's monthly target weights."""
    src = Path(root) / "models" / "regime" / "l_regime_sector_backtest_target_weights.parquet"
    if not src.exists():
        return {}
    w = pd.read_parquet(src)
    if "date" in w.columns:
        w = w.set_index("date")
    w.index = pd.to_datetime(w.index)
    tilt = w.sub(w.mean(axis=1), axis=0)
    px = {}
    for etf in w.columns:
        s = _px(root, etf)
        if s is not None:
            px[etf] = s.resample("ME").last()
    if not px:
        return {}
    m = pd.DataFrame(px)
    fwd = m.pct_change().shift(-1)
    ics = []
    for d in tilt.index:
        me = d + pd.offsets.MonthEnd(0)
        if me not in fwd.index:
            continue
        f = fwd.loc[me].reindex(tilt.columns)
        t = tilt.loc[d]
        ok = f.notna() & t.notna()
        if ok.sum() >= 6 and t[ok].std() > 0:
            ics.append(_spearman(t[ok], f[ok]))
    ics = pd.Series([x for x in ics if x is not None])
    if ics.empty:
        return {}
    return {"months": int(len(ics)), "mean_ic": float(ics.mean()),
            "ic_t_stat": float(ics.mean() / ics.std() * math.sqrt(len(ics))) if ics.std() > 0 else None,
            "share_positive": float((ics > 0).mean()),
            "from": str(tilt.index.min().date()), "to": str(tilt.index.max().date())}
