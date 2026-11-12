"""Ex-ante risk, limits and stress tests for the cockpit.

Inputs: the run's target weights and the local daily price cache. Everything
here is computed transparently from those two inputs so each number can be
traced:

  * covariance: Ledoit-Wolf shrinkage on up to 3 years of daily returns
    (the same family the optimizer uses), annualised x252
  * beta / tracking error: against SPY (benchmark fully invested)
  * VaR / CVaR: 1-day 99% historical simulation of today's weights
  * risk contribution: w_i (Sigma w)_i / sigma_p^2
  * liquidity: position value vs 20-day average dollar volume
  * stress: (a) historical replays of crisis windows via each holding's
    beta to its sector ETF (stock histories are only ~3y, ETFs go back
    to 2000); (b) single-factor shocks via 3y betas to SPY, TLT, oil
  * limits: every configured constraint as PASS / WARN / FAIL
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS = 252

EPISODES = [
    ("Global financial crisis", "2008-09-12", "2009-03-09"),
    ("US downgrade / euro crisis", "2011-07-22", "2011-10-03"),
    ("Q4 2018 selloff", "2018-09-20", "2018-12-24"),
    ("COVID crash", "2020-02-19", "2020-03-23"),
    ("2022 rate shock", "2022-01-03", "2022-10-12"),
]

SHOCKS = [
    ("Equity market −20%", "SPY", -0.20),
    ("Long Treasuries −10% (rates up ~1pp)", "TLT", -0.10),
    ("Oil −30%", "CL_F", -0.30),
]


def _series(root: Path, ticker: str, field: str = "adj_close") -> pd.Series | None:
    sym = str(ticker).upper().replace(".", "-")
    for p in (Path(root) / "data/raw/stocks/prices" / f"{sym}.parquet",
              Path(root) / "data/raw/market" / f"{sym}.parquet"):
        if p.exists():
            df = pd.read_parquet(p, columns=["date", field] if field != "volume" else ["date", "volume", "close"])
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
            df = df.drop_duplicates("date", keep="last").set_index("date").sort_index()
            if field == "volume":
                return df
            return pd.to_numeric(df[field], errors="coerce").dropna()
    return None


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _status(value, limit, warn_ratio=0.9, higher_is_bad=True):
    if value is None or limit is None:
        return "N/A"
    if higher_is_bad:
        return "FAIL" if value > limit + 1e-9 else ("WARN" if value > warn_ratio * limit else "PASS")
    return "FAIL" if value < limit - 1e-9 else "PASS"


def build_risk_panel(root: Path, holdings: list[dict], session, config: dict, nav: float,
                     blocked: list[str] | None = None, review: list[str] | None = None) -> dict:
    root = Path(root)
    session = pd.Timestamp(session)
    hold = [h for h in holdings if (h.get("target_weight") or 0) > 0]
    if not hold:
        return {"available": False, "reason": "no holdings"}
    tickers = [h["ticker"] for h in hold]
    w = np.array([float(h["target_weight"]) for h in hold])
    sectors = {h["ticker"]: h.get("sector_ticker") for h in hold}

    prices = {}
    for t in tickers + ["SPY"]:
        s = _series(root, t)
        if s is not None:
            prices[t] = s[s.index <= session]
    missing = [t for t in tickers if t not in prices]
    px = pd.DataFrame(prices).dropna(how="all")
    px = px[px.index > session - pd.Timedelta(days=int(365 * 3.05))]
    rets = px.pct_change().dropna(how="all").iloc[1:]
    rets = rets.dropna(axis=0, how="any")
    cols = [t for t in tickers if t in rets.columns]
    wv = np.array([float(h["target_weight"]) for h in hold if h["ticker"] in cols])
    out = {"available": True, "as_of": str(session.date()), "observations": int(len(rets)),
           "missing_prices": missing, "nav": nav}
    if len(rets) < 120 or not cols:
        out.update({"available": False, "reason": "not enough overlapping price history"})
        return out

    try:
        from sklearn.covariance import LedoitWolf
        cov = LedoitWolf().fit(rets[cols + ["SPY"]].values).covariance_ * TRADING_DAYS
    except Exception:
        cov = rets[cols + ["SPY"]].cov().values * TRADING_DAYS
    n = len(cols)
    S = cov[:n, :n]
    s_spy = cov[:n, n]
    var_spy = cov[n, n]
    port_var = float(wv @ S @ wv)
    port_vol = math.sqrt(max(port_var, 0.0))
    beta = float(wv @ s_spy / var_spy)
    active_var = port_var - 2 * float(wv @ s_spy) + var_spy
    te = math.sqrt(max(active_var, 0.0))
    mctr = S @ wv
    contrib = wv * mctr / port_var if port_var > 0 else np.zeros(n)

    corr = rets[cols].corr().values
    avg_corr = float((corr.sum() - n) / (n * (n - 1))) if n > 1 else None

    port_hist = rets[cols].values @ wv
    q = np.quantile(port_hist, 0.01)
    var99 = -float(q)
    cvar99 = -float(port_hist[port_hist <= q].mean())
    spy_hist = rets["SPY"].values
    max_dd = None
    eq = np.cumprod(1 + port_hist)
    if len(eq):
        max_dd = float((eq / np.maximum.accumulate(eq) - 1).min())

    risky = wv.sum()
    rel = wv / risky if risky > 0 else wv
    eff_n = float(1.0 / np.sum(rel ** 2)) if risky > 0 else None
    top5 = float(np.sort(wv)[::-1][:5].sum())

    # liquidity
    liq_rows = []
    for t, wt in zip(cols, wv):
        vol = _series(root, t, "volume")
        if vol is None or vol.empty:
            continue
        vol = vol[vol.index <= session].tail(20)
        adv_usd = float((pd.to_numeric(vol["volume"], errors="coerce") * pd.to_numeric(vol["close"], errors="coerce")).mean())
        pos_usd = wt * nav
        liq_rows.append({"ticker": t, "position_usd": pos_usd, "adv_usd": adv_usd,
                         "pct_adv": pos_usd / adv_usd if adv_usd else None,
                         "days_to_exit_20pct": pos_usd / (0.2 * adv_usd) if adv_usd else None})

    # stress: historical replays via sector ETF beta
    sec_beta = {}
    for t in cols:
        etf = sectors.get(t) or "SPY"
        es = _series(root, etf)
        if es is None:
            etf, es = "SPY", _series(root, "SPY")
        er = es.pct_change()
        j = pd.concat([rets[t], er], axis=1, join="inner").dropna()
        b = float(np.cov(j.iloc[:, 0], j.iloc[:, 1])[0, 1] / np.var(j.iloc[:, 1], ddof=1)) if len(j) > 60 else 1.0
        sec_beta[t] = (etf, b)
    stress = []
    spy = _series(root, "SPY")
    for name, a, b in EPISODES:
        if spy is None or spy.index.min() > pd.Timestamp(a) or spy.index.max() < pd.Timestamp(b):
            continue  # price history does not cover this window
        spy_ret = float(spy[:b].iloc[-1] / spy[:a].iloc[-1] - 1)
        total, detail = 0.0, []
        for t, wt in zip(cols, wv):
            etf, beta_t = sec_beta[t]
            es = _series(root, etf)
            proxy = etf
            if es is None or es.index.min() > pd.Timestamp(a):
                es, proxy = spy, "SPY"
                beta_t = float(s_spy[cols.index(t)] / var_spy)
            r = float(es[:b].iloc[-1] / es[:a].iloc[-1] - 1) * beta_t
            r = max(r, -1.0)
            total += wt * r
            detail.append({"ticker": t, "proxy": proxy, "beta": beta_t, "shocked_return": r})
        stress.append({"scenario": name, "window": f"{a} to {b}", "portfolio_return": total,
                       "portfolio_pnl": total * nav, "spy_return": spy_ret, "detail": detail})
    for name, factor, shock in SHOCKS:
        fs = _series(root, factor)
        if fs is None:
            continue
        fr = fs.pct_change()
        total = 0.0
        for t, wt in zip(cols, wv):
            j = pd.concat([rets[t], fr], axis=1, join="inner").dropna()
            bt = float(np.cov(j.iloc[:, 0], j.iloc[:, 1])[0, 1] / np.var(j.iloc[:, 1], ddof=1)) if len(j) > 60 else 0.0
            total += wt * bt * shock
        stress.append({"scenario": name, "window": "hypothetical, 3y betas", "portfolio_return": total,
                       "portfolio_pnl": total * nav, "spy_return": shock if factor == "SPY" else None, "detail": []})

    # limits
    pcfg = config.get("portfolio", {}) or {}
    ecfg = config.get("execution", {}) or {}
    max_stock = float(pcfg.get("max_stock_weight", 0.10))
    max_sector = float(pcfg.get("max_sector_weight", 0.30))
    min_pos = float(pcfg.get("optimizer_weight_epsilon", 0.005))
    max_adv = float(ecfg.get("max_adv_participation", 0.10))
    sec_w = {}
    for h in hold:
        sec_w[h.get("sector_ticker") or "?"] = sec_w.get(h.get("sector_ticker") or "?", 0.0) + float(h["target_weight"])
    top_sector, top_sector_w = max(sec_w.items(), key=lambda kv: kv[1])
    largest = max(hold, key=lambda h: h["target_weight"])
    smallest = min(hold, key=lambda h: h["target_weight"])
    worst_adv = max(liq_rows, key=lambda r: r["pct_adv"] or 0) if liq_rows else None
    cash = 1.0 - float(sum(h["target_weight"] for h in hold))
    held_blocked = sorted(set(blocked or []) & set(tickers))
    held_review = sorted(set(review or []) & set(tickers))
    limits = [
        {"limit": "Largest single stock", "value": largest["target_weight"], "limit_value": max_stock, "unit": "weight",
         "detail": largest["ticker"], "status": _status(largest["target_weight"], max_stock)},
        {"limit": "Largest sector", "value": top_sector_w, "limit_value": max_sector, "unit": "weight",
         "detail": top_sector, "status": _status(top_sector_w, max_sector)},
        {"limit": "Smallest position (minimum size)", "value": smallest["target_weight"], "limit_value": min_pos, "unit": "weight",
         "detail": smallest["ticker"], "status": _status(smallest["target_weight"], min_pos, higher_is_bad=False)},
        {"limit": "Position vs 20-day volume", "value": worst_adv["pct_adv"] if worst_adv else None, "limit_value": max_adv,
         "unit": "weight", "detail": worst_adv["ticker"] if worst_adv else "", "status": _status(worst_adv["pct_adv"] if worst_adv else None, max_adv)},
        {"limit": "Cash not negative", "value": cash, "limit_value": float(pcfg.get("min_cash_weight", 0.0)), "unit": "weight",
         "detail": "", "status": _status(cash, float(pcfg.get("min_cash_weight", 0.0)), higher_is_bad=False)},
        {"limit": "No critically flagged valuations held", "value": len(held_blocked), "limit_value": 0, "unit": "count",
         "detail": ", ".join(held_blocked), "status": "FAIL" if held_blocked else "PASS"},
        {"limit": "Holdings with valuation under review", "value": len(held_review), "limit_value": 0, "unit": "count",
         "detail": ", ".join(held_review), "status": "WARN" if held_review else "PASS"},
        {"limit": "Price data present for every holding", "value": len(missing), "limit_value": 0, "unit": "count",
         "detail": ", ".join(missing), "status": "FAIL" if missing else "PASS"},
    ]

    out.update({
        "ex_ante_volatility": port_vol,
        "beta": beta,
        "tracking_error": te,
        "var_99_1d": var99, "cvar_99_1d": cvar99,
        "var_99_1d_usd": var99 * nav, "cvar_99_1d_usd": cvar99 * nav,
        "historical_max_drawdown": max_dd,
        "average_correlation": avg_corr,
        "effective_positions": eff_n,
        "top5_weight": top5,
        "invested": float(risky),
        "risk_contributions": [{"ticker": t, "weight": float(wt), "risk_share": float(c),
                                "standalone_vol": float(math.sqrt(S[i, i]))}
                               for i, (t, wt, c) in enumerate(zip(cols, wv, contrib))],
        "sector_weights": [{"sector": k, "weight": v} for k, v in sorted(sec_w.items(), key=lambda kv: -kv[1])],
        "liquidity": liq_rows,
        "stress": stress,
        "limits": limits,
        "limits_summary": {s: sum(1 for x in limits if x["status"] == s) for s in ("PASS", "WARN", "FAIL")},
    })

    def deep(o):
        if isinstance(o, dict):
            return {k: deep(v) for k, v in o.items()}
        if isinstance(o, list):
            return [deep(v) for v in o]
        return _clean(o)
    return deep(out)
