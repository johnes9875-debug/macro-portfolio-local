"""Bottom-up (industry) betas for the valuation discount rate.

Why: single-stock betas from 2-3 years of weekly data are noisy, and the
2023-2026 window is unusual: technology dominated SPY, so every defensive
sector's recent beta collapsed (staples ETF 3y beta 0.19 vs 0.56 over 10y,
energy 0.29 vs 0.90). Discounting staples at almost the risk-free rate is
not defensible.

Method (all from the local price cache and fundamentals snapshots):

1. Sector level  - weekly beta of the company's sector ETF vs SPY over
                   `anchor_years` (default 10). ETF history goes back to
                   2000, so this spans several cycles.
2. Industry tilt - equal-weighted weekly return portfolios of every universe
                   stock in the company's GICS sub-industry and in its sector,
                   over `relative_years` (default 3, all the stock history we
                   have). tilt = beta(sub-industry portfolio) -
                   beta(sector portfolio), shrunk toward 0 by n / (n + k)
                   (n = peers, k = `tilt_shrinkage_k`) and clipped to
                   +/- `max_abs_tilt`. Needs at least `min_peers` stocks with
                   enough history; else tilt = 0. Additive, not a ratio: the
                   recent sector betas of staples/energy are ~0.2, and dividing
                   by them amplifies noise. The tilt keeps within-sector
                   differences (e.g. life-science tools vs pharma) while the
                   level comes from step 1.
3. Levered industry beta = sector level + tilt.
4. Operating companies: unlever with the peer group's median debt/equity
   (sub-industry if >= `min_leverage_peers` have data, else sector),
   beta_u = beta_L / (1 + (1 - t) D/E), then relever with the company's own
   D/E and tax rate. Financial models (discount rate = cost of equity) use
   the levered industry beta directly: for banks and insurers debt is an
   operating input, not financing.
5. Optional blend with the company's own (F4B) beta:
   final = (1 - w) x industry + w x company, w = `company_beta_weight`.
6. Clip to [min_beta, max_beta]; recompute cost of equity, WACC and the
   discount rate with the engine's own identities.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DEFAULTS = {
    "anchor_years": 10,
    "relative_years": 3,
    "min_peers": 4,
    "min_leverage_peers": 3,
    "min_weekly_obs": 100,
    "tilt_shrinkage_k": 4,
    "max_abs_tilt": 0.35,
    "company_beta_weight": 0.0,
    "min_beta": 0.40,
    "max_beta": 2.50,
    "max_debt_to_equity": 3.0,
}


def _weekly(series: pd.Series) -> pd.Series:
    return series.resample("W-FRI").last().pct_change().dropna()


def _load_px(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    df = pd.read_parquet(path, columns=["date", "adj_close"])
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return pd.to_numeric(df.drop_duplicates("date").set_index("date").sort_index()["adj_close"], errors="coerce").dropna()


def _beta(y: pd.Series, x: pd.Series, min_obs: int) -> tuple[float | None, int]:
    j = pd.concat([y, x], axis=1, join="inner").dropna()
    if len(j) < min_obs:
        return None, len(j)
    # winsorise weekly returns at 1%/99% to limit single-week shocks
    lo, hi = j.quantile(0.01), j.quantile(0.99)
    j = j.clip(lo, hi, axis=1)
    v = float(np.var(j.iloc[:, 1], ddof=1))
    return (float(np.cov(j.iloc[:, 0], j.iloc[:, 1])[0, 1] / v) if v > 0 else None), len(j)


def _leverage_table(root: Path) -> pd.DataFrame:
    """Latest market cap and total debt per ticker from the fundamentals snapshots."""
    frames = []
    for p in sorted((Path(root) / "data" / "curated" / "stocks" / "fundamentals").glob("*.parquet")):
        try:
            d = pd.read_parquet(p, columns=["ticker", "market_cap", "total_debt", "market_data_as_of"])
            d["_src"] = p.name
            frames.append(d)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["ticker", "debt_to_equity"])
    d = pd.concat(frames, ignore_index=True)
    d["market_cap"] = pd.to_numeric(d["market_cap"], errors="coerce")
    d["total_debt"] = pd.to_numeric(d["total_debt"], errors="coerce")
    d = d[(d["market_cap"] > 0) & d["total_debt"].notna()]
    d = d.sort_values(["ticker", "market_data_as_of", "_src"]).drop_duplicates("ticker", keep="last")
    d["debt_to_equity"] = d["total_debt"].clip(lower=0) / d["market_cap"]
    return d[["ticker", "debt_to_equity"]]


def apply_industry_betas(coc: pd.DataFrame, root, stock_output_dir, risk_free: float, erp: float,
                         as_of, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    c = {**DEFAULTS, **(cfg or {})}
    root = Path(root)
    as_of = pd.Timestamp(as_of).tz_localize(None) if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of)
    universe = pd.read_csv(Path(stock_output_dir) / "master_current_stock_universe.csv",
                           usecols=["ticker", "yahoo_ticker", "gics_sub_industry", "sector_ticker"])
    lev = _leverage_table(root)
    universe = universe.merge(lev, on="ticker", how="left")

    spy = _load_px(root / "data/raw/market/SPY.parquet")
    spy = spy[spy.index <= as_of]
    spy_w = _weekly(spy)
    rel_start = as_of - pd.DateOffset(years=int(c["relative_years"]))
    anc_start = as_of - pd.DateOffset(years=int(c["anchor_years"]))

    # 1. sector ETF long-run level
    sector_level = {}
    for etf in sorted(set(coc["sector_ticker"].dropna()) | set(universe["sector_ticker"].dropna())):
        px = _load_px(root / f"data/raw/market/{etf}.parquet")
        if px is None:
            continue
        w = _weekly(px[px.index <= as_of])
        b, n = _beta(w[w.index > anc_start], spy_w[spy_w.index > anc_start], 150)
        if b is not None:
            sector_level[etf] = {"beta": b, "weeks": n}

    # 2. equal-weighted peer portfolios (3y)
    rets = {}
    for _, r in universe.iterrows():
        sym = str(r["yahoo_ticker"] if isinstance(r["yahoo_ticker"], str) else r["ticker"]).upper().replace(".", "-")
        px = _load_px(root / f"data/raw/stocks/prices/{sym}.parquet")
        if px is None:
            continue
        w = _weekly(px[(px.index <= as_of) & (px.index > rel_start - pd.Timedelta(days=10))])
        if len(w) >= int(c["min_weekly_obs"]):
            rets[r["ticker"]] = w
    spy_rel = spy_w[spy_w.index > rel_start]

    def port_beta(tickers):
        cols = [rets[t] for t in tickers if t in rets]
        if len(cols) < int(c["min_peers"]):
            return None, len(cols)
        port = pd.concat(cols, axis=1).mean(axis=1, skipna=True)
        b, _ = _beta(port[port.index > rel_start], spy_rel, int(c["min_weekly_obs"]))
        return b, len(cols)

    sector_port = {s: port_beta(list(g["ticker"])) for s, g in universe.groupby("sector_ticker")}
    sub_port = {s: port_beta(list(g["ticker"])) for s, g in universe.groupby("gics_sub_industry")}

    def med_de(tickers):
        v = universe.loc[universe["ticker"].isin(tickers), "debt_to_equity"].dropna()
        v = v.clip(upper=float(c["max_debt_to_equity"]))
        return (float(v.median()), int(len(v))) if len(v) else (None, 0)

    sub_of = dict(zip(universe["ticker"], universe["gics_sub_industry"]))
    rows = []
    out = coc.copy()
    for i, r in out.iterrows():
        t, sec = r["ticker"], r["sector_ticker"]
        sub = sub_of.get(t)
        level = (sector_level.get(sec) or {}).get("beta")
        sec_b, sec_n = sector_port.get(sec, (None, 0))
        sub_b, sub_n = sub_port.get(sub, (None, 0)) if isinstance(sub, str) else (None, 0)
        tilt, tilt_src = 0.0, "SECTOR_ONLY"
        if sub_b is not None and sec_b is not None:
            k = float(c["tilt_shrinkage_k"])
            m = float(c["max_abs_tilt"])
            tilt = float(np.clip((sub_b - sec_b) * sub_n / (sub_n + k), -m, m))
            tilt_src = "SUB_INDUSTRY"
        if level is None:
            rows.append({"ticker": t, "status": "NO_SECTOR_LEVEL_KEEP_F4B"})
            continue
        levered_ind = level + tilt
        financial = str(r.get("discount_rate_type")) == "COST_OF_EQUITY"
        peers = list(universe.loc[universe["gics_sub_industry"] == sub, "ticker"]) if isinstance(sub, str) else []
        de_grp, n_de = med_de(peers)
        de_src = "SUB_INDUSTRY"
        if de_grp is None or n_de < int(c["min_leverage_peers"]):
            de_grp, n_de = med_de(list(universe.loc[universe["sector_ticker"] == sec, "ticker"]))
            de_src = "SECTOR"
        tax = float(r.get("wacc_tax_rate") or 0.21)
        eq = float(r.get("equity_market_value") or 0)
        de_co = min(float(r.get("gross_debt") or 0) / eq, float(c["max_debt_to_equity"])) if eq > 0 else 0.0
        if financial or de_grp is None:
            unlevered = None
            industry_beta = levered_ind
            method = "LEVERED_INDUSTRY_FINANCIAL" if financial else "LEVERED_INDUSTRY_NO_LEVERAGE_DATA"
        else:
            unlevered = levered_ind / (1 + (1 - tax) * de_grp)
            industry_beta = unlevered * (1 + (1 - tax) * de_co)
            method = "UNLEVERED_RELEVERED"
        w = float(c["company_beta_weight"])
        company_beta = float(r["valuation_beta"])
        final = (1 - w) * industry_beta + w * company_beta
        final = float(np.clip(final, float(c["min_beta"]), float(c["max_beta"])))

        coe = risk_free + final * erp
        wacc = float(r["equity_weight"]) * coe + float(r["debt_weight"]) * float(r["after_tax_cost_of_debt"])
        dr = coe if financial else wacc
        out.at[i, "f4b_valuation_beta"] = company_beta
        out.at[i, "f4b_discount_rate"] = float(r["discount_rate"])
        out.at[i, "valuation_beta"] = final
        out.at[i, "cost_of_equity"] = coe
        out.at[i, "wacc"] = wacc
        out.at[i, "discount_rate"] = dr
        out.at[i, "terminal_safety_spread"] = dr - float(r["terminal_growth"])
        out.at[i, "beta_source"] = "BOTTOM_UP_INDUSTRY"
        rows.append({
            "ticker": t, "status": "APPLIED", "sector_ticker": sec, "gics_sub_industry": sub,
            "sector_level_beta": level, "sector_level_years": int(c["anchor_years"]),
            "sector_portfolio_beta_3y": sec_b, "sector_portfolio_n": sec_n,
            "sub_industry_portfolio_beta_3y": sub_b, "sub_industry_portfolio_n": sub_n,
            "tilt": tilt, "tilt_source": tilt_src, "levered_industry_beta": levered_ind,
            "peer_median_debt_to_equity": de_grp, "peer_leverage_n": n_de, "peer_leverage_source": de_src,
            "unlevered_industry_beta": unlevered, "company_debt_to_equity": de_co, "tax_rate": tax,
            "industry_beta": industry_beta, "company_beta_f4b": company_beta, "company_beta_weight": w,
            "final_beta": final, "method": method,
            "discount_rate_before": float(r["discount_rate"]), "discount_rate_after": dr,
        })
    audit = pd.DataFrame(rows)
    table = pd.DataFrame([
        {"sector_ticker": s, "beta_long_run": v["beta"], "weeks": v["weeks"],
         "sector_portfolio_beta_3y": sector_port.get(s, (None, 0))[0], "sector_portfolio_n": sector_port.get(s, (None, 0))[1]}
        for s, v in sorted(sector_level.items())
    ])
    return out, audit, table
