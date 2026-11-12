"""Per-holding valuation sheets for the cockpit.

For each ticker: the BASE-case DCF bridge (PV of 5-year cash flows + PV of
terminal value = enterprise value - net debt = equity / shares), the cost of
capital build-up, scenario values, consensus, margin-of-safety price, what the
price implies, and a discount-rate x terminal-growth sensitivity grid.

The grid is recomputed from the engine's own BASE forecast cash flows with the
same formulas as F5 (end-year discounting; terminal value = Gordon/exit-multiple
blend). Each sheet reports whether the recomputation reproduces the engine's
value at the base inputs (`reconciles`), so a reader can trust the grid.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


def _load(run_dir: Path, name: str) -> pd.DataFrame:
    p = Path(run_dir) / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def _per_share(fcff, ebitda_final, r, g, exit_multiple, w_gordon, net_debt, shares, fx):
    if r - g <= 0.005:
        return None
    pv = sum(cf / (1 + r) ** (t + 1) for t, cf in enumerate(fcff))
    gordon = fcff[-1] * (1 + g) / (r - g)
    exit_tv = ebitda_final * exit_multiple
    tv = w_gordon * gordon + (1 - w_gordon) * exit_tv
    ev = pv + tv / (1 + r) ** len(fcff)
    return (ev - net_debt) / shares * fx


def build_sheets(root: Path, run_dir: Path, tickers: list[str], config: dict) -> dict:
    run_dir = Path(run_dir)
    val = _load(run_dir, "F_FINAL_VALUATION_HANDOFF")
    scen = _load(run_dir, "F5_FINAL_SCENARIO_VALUATIONS")
    if scen.empty:
        scen = _load(run_dir, "F5_SCENARIO_VALUATIONS")
    cfs = _load(run_dir, "F5_FINAL_FORECAST_CASHFLOWS")
    if cfs.empty:
        cfs = _load(run_dir, "F5_FORECAST_CASHFLOWS")
    coc = _load(run_dir, "F4_COST_OF_CAPITAL")
    if val.empty:
        return {}
    w_gordon = float(((config.get("valuation") or {}).get("gordon_growth_weight", 0.7)))
    out = {}
    for t in tickers:
        v = val[val["ticker"] == t]
        if v.empty:
            continue
        v = v.iloc[0]
        sheet = {
            "ticker": t, "company_name": v.get("company_name"), "model": v.get("execution_model"),
            "price": _f(v.get("current_price")),
            "scenarios": {"bear": _f(v.get("bear_intrinsic_value")), "base": _f(v.get("base_intrinsic_value")),
                          "bull": _f(v.get("bull_intrinsic_value")), "expected": _f(v.get("expected_intrinsic_value"))},
            "consensus_target": _f(v.get("consensus_target_mean")),
            "mos_price": _f(v.get("mos_price_threshold")),
            "mos_met": bool(v.get("mos_threshold_met")) if pd.notna(v.get("mos_threshold_met")) else None,
            "review": v.get("valuation_review_severity"),
            "review_reason": v.get("valuation_anomaly_reason") if isinstance(v.get("valuation_anomaly_reason"), str) else "",
            "confidence": _f(v.get("valuation_confidence")),
            "implied": {"driver": v.get("market_implied_driver"), "market_implied": _f(v.get("market_implied_driver_level")),
                        "model_base": _f(v.get("base_driver_level"))},
            "multiples": {"metric": v.get("terminal_multiple_metric"), "current": _f(v.get("current_trading_multiple")),
                          "exit_base": _f(v.get("base_exit_multiple")),
                          "market_implied_exit": _f(v.get("market_implied_exit_multiple"))},
        }
        # 52-week range from the local cache
        sym = str(t).upper().replace(".", "-")
        pp = Path(root) / "data/raw/stocks/prices" / f"{sym}.parquet"
        if pp.exists():
            px = pd.read_parquet(pp, columns=["date", "close"])
            px["date"] = pd.to_datetime(px["date"]).dt.tz_localize(None)
            last = px["date"].max()
            yr = px[px["date"] > last - pd.Timedelta(days=365)]["close"]
            sheet["range_52w"] = {"low": _f(yr.min()), "high": _f(yr.max())}
        c = coc[coc["ticker"] == t] if not coc.empty else pd.DataFrame()
        if not c.empty:
            c = c.iloc[0]
            sheet["cost_of_capital"] = {k: _f(c.get(k)) for k in
                                        ["raw_beta", "valuation_beta", "cost_of_equity", "after_tax_cost_of_debt",
                                         "equity_weight", "debt_weight", "wacc", "discount_rate", "terminal_growth"]}
            sheet["cost_of_capital"]["beta_source"] = c.get("beta_source")
        s = scen[(scen["ticker"] == t) & (scen["scenario"] == "BASE")] if not scen.empty else pd.DataFrame()
        if not s.empty:
            s = s.iloc[0]
            sheet["bridge"] = {k: _f(s.get(k)) for k in
                               ["pv_explicit_cash_flows", "pv_terminal_value", "enterprise_value", "net_debt",
                                "equity_value", "valuation_share_units", "intrinsic_value_per_share",
                                "terminal_value_share", "gordon_terminal_value", "exit_terminal_value",
                                "discount_rate", "terminal_growth", "exit_multiple", "financial_to_price_fx"]}
            sheet["bridge"]["basis"] = s.get("valuation_basis")
        cf = cfs[(cfs["ticker"] == t) & (cfs["scenario"] == "BASE")].sort_values("forecast_year") if not cfs.empty else pd.DataFrame()
        if not cf.empty and "bridge" in sheet and str(sheet["bridge"].get("basis", "")).startswith("FCFF"):
            sheet["forecast"] = [{k: _f(r.get(k)) for k in ["forecast_year", "revenue", "revenue_growth", "ebit_margin",
                                                             "nopat", "capex_outflow", "nwc_investment", "fcff"]}
                                 for _, r in cf.iterrows()]
            b = sheet["bridge"]
            fcff = [float(x) for x in cf["fcff"]]
            ebitda_final = float(cf["ebitda"].iloc[-1])
            fx = b.get("financial_to_price_fx") or 1.0
            shares = b.get("valuation_share_units")
            r0, g0, xm = b.get("discount_rate"), b.get("terminal_growth"), b.get("exit_multiple")
            if all(x is not None for x in [shares, r0, g0, xm, b.get("net_debt")]) and shares:
                base_check = _per_share(fcff, ebitda_final, r0, g0, xm, w_gordon, b["net_debt"], shares, fx)
                eng = b.get("intrinsic_value_per_share")
                sheet["reconciles"] = bool(base_check and eng and abs(base_check / eng - 1) < 0.005)
                rs = [r0 - 0.01, r0 - 0.005, r0, r0 + 0.005, r0 + 0.01]
                gs = [g0 - 0.01, g0 - 0.005, g0, g0 + 0.005, g0 + 0.01]
                sheet["sensitivity"] = {
                    "discount_rates": rs, "terminal_growth": gs,
                    "values": [[_f(_per_share(fcff, ebitda_final, r, g, xm, w_gordon, b["net_debt"], shares, fx))
                                for g in gs] for r in rs],
                }
        out[t] = sheet
    return out
