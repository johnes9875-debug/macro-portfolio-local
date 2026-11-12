import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from macro_portfolio.valuation_sheet import _per_share

ROOT = Path(__file__).resolve().parents[1]


def test_fixes_are_configured_and_switchable():
    cfg = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    fx = cfg["valuation"]["fixes"]
    assert fx["nwc_on_incremental_revenue"] is True
    assert 0.0 <= fx["exit_multiple_own_weight"] <= 1.0
    assert fx["min_valuation_beta"] >= 0.5


def test_section_f_reads_every_fix_switch():
    src = (ROOT / "src/macro_portfolio/engine/sections/section_f.py").read_text(encoding="utf-8")
    for key in ("nwc_on_incremental_revenue", "exit_multiple_own_weight", "min_valuation_beta"):
        assert key in src
    # all three beta stages use the configurable floor
    assert src.count('.get("min_valuation_beta", 0.50)') == 3
    # NWC fix applied at both FCFF projection sites (F5 valuation and F6 reverse DCF)
    assert src.count("f5_nwc_incremental_intensity(") == 3  # definition + 2 call sites


def test_k_allows_holding_but_not_adding_to_blocked_names():
    src = (ROOT / "src/macro_portfolio/engine/sections/section_k.py").read_text(encoding="utf-8")
    assert "only BUYING MORE of a non-eligible name is a violation" in src


def test_dcf_recompute_matches_closed_form():
    fcff = [100.0, 104.0, 108.0, 112.0, 116.0]
    r, g, xm, wg, nd, sh = 0.08, 0.025, 12.0, 0.7, 200.0, 10.0
    ebitda = 150.0
    pv = sum(cf / (1 + r) ** (t + 1) for t, cf in enumerate(fcff))
    tv = wg * fcff[-1] * (1 + g) / (r - g) + (1 - wg) * ebitda * xm
    expected = (pv + tv / (1 + r) ** 5 - nd) / sh
    assert math.isclose(_per_share(fcff, ebitda, r, g, xm, wg, nd, sh, 1.0), expected, rel_tol=1e-12)
    # higher discount rate -> lower value; higher growth -> higher value
    assert _per_share(fcff, ebitda, r + 0.01, g, xm, wg, nd, sh, 1.0) < expected
    assert _per_share(fcff, ebitda, r, g + 0.005, xm, wg, nd, sh, 1.0) > expected
    # r - g too small is refused rather than exploding
    assert _per_share(fcff, ebitda, 0.03, 0.028, xm, wg, nd, sh, 1.0) is None


def test_risk_panel_on_synthetic_prices(tmp_path):
    from macro_portfolio.risk_panel import build_risk_panel
    (tmp_path / "data/raw/stocks/prices").mkdir(parents=True)
    (tmp_path / "data/raw/market").mkdir(parents=True)
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2023-01-02", "2026-11-11")
    mkt = rng.normal(0.0004, 0.01, len(dates))
    def write(path, rets, vol=1e6):
        px = 100 * np.cumprod(1 + rets)
        pd.DataFrame({"date": dates, "adj_close": px, "close": px, "volume": vol}).to_parquet(path, index=False)
    write(tmp_path / "data/raw/market/SPY.parquet", mkt)
    write(tmp_path / "data/raw/market/XLP.parquet", 0.6 * mkt + rng.normal(0, 0.006, len(dates)))
    write(tmp_path / "data/raw/stocks/prices/AAA.parquet", 0.5 * mkt + rng.normal(0, 0.01, len(dates)))
    write(tmp_path / "data/raw/stocks/prices/BBB.parquet", 1.2 * mkt + rng.normal(0, 0.012, len(dates)))
    hold = [{"ticker": "AAA", "sector_ticker": "XLP", "target_weight": 0.3},
            {"ticker": "BBB", "sector_ticker": "XLK", "target_weight": 0.2}]   # XLK missing -> SPY proxy
    cfg = {"portfolio": {"max_stock_weight": 0.25, "max_sector_weight": 0.3, "optimizer_weight_epsilon": 0.005},
           "execution": {"max_adv_participation": 0.1}}
    r = build_risk_panel(tmp_path, hold, "2026-11-11", cfg, 1_000_000)
    assert r["available"]
    assert 0.3 < r["beta"] < 0.7                                  # 0.3*0.5 + 0.2*1.2 = 0.39
    assert math.isclose(sum(x["risk_share"] for x in r["risk_contributions"]), 1.0, rel_tol=1e-6)
    lim = {l["limit"]: l["status"] for l in r["limits"]}
    assert lim["Largest single stock"] == "FAIL"                  # 30% > 25%
    assert lim["Largest sector"] == "WARN"                        # 30% at the 30% limit
    assert r["var_99_1d"] > 0 and r["cvar_99_1d"] >= r["var_99_1d"]
    assert any(s["scenario"] == "Equity market −20%" for s in r["stress"])
