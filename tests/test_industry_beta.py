import numpy as np
import pandas as pd
import pytest

from macro_portfolio.industry_beta import apply_industry_betas


@pytest.fixture()
def root(tmp_path):
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2015-01-02", "2026-11-11")
    (tmp_path / "data/raw/market").mkdir(parents=True)
    (tmp_path / "data/raw/stocks/prices").mkdir(parents=True)
    (tmp_path / "data/curated/stocks/fundamentals").mkdir(parents=True)
    (tmp_path / "out").mkdir()
    mkt = rng.normal(0.0004, 0.01, len(dates))

    def write(path, rets, start=None):
        idx = dates if start is None else dates[dates >= pd.Timestamp(start)]
        r = rets[-len(idx):]
        pd.DataFrame({"date": idx, "adj_close": 100 * np.cumprod(1 + r)}).to_parquet(path, index=False)

    # sector ETF with a true long-run beta of 0.6
    write(tmp_path / "data/raw/market/SPY.parquet", mkt)
    write(tmp_path / "data/raw/market/XLP.parquet", 0.6 * mkt + rng.normal(0, 0.004, len(dates)))
    write(tmp_path / "data/raw/market/XLF.parquet", 1.0 * mkt + rng.normal(0, 0.004, len(dates)))
    uni = []
    # sub-industry A (high beta within staples) and B (low beta); 3y of stock history
    for i in range(5):
        write(tmp_path / f"data/raw/stocks/prices/A{i}.parquet", 0.9 * mkt + rng.normal(0, 0.01, len(dates)), "2023-11-01")
        uni.append({"ticker": f"A{i}", "yahoo_ticker": f"A{i}", "gics_sub_industry": "Sub A", "sector_ticker": "XLP"})
    for i in range(5):
        write(tmp_path / f"data/raw/stocks/prices/B{i}.parquet", 0.3 * mkt + rng.normal(0, 0.01, len(dates)), "2023-11-01")
        uni.append({"ticker": f"B{i}", "yahoo_ticker": f"B{i}", "gics_sub_industry": "Sub B", "sector_ticker": "XLP"})
    pd.DataFrame(uni).to_csv(tmp_path / "out/master_current_stock_universe.csv", index=False)
    pd.DataFrame({"ticker": [u["ticker"] for u in uni], "market_cap": 100.0, "total_debt": 20.0,
                  "market_data_as_of": "2026-11-11"}).to_parquet(tmp_path / "data/curated/stocks/fundamentals/f.parquet")
    return tmp_path


def _coc(rows):
    base = {"equity_weight": 0.9, "debt_weight": 0.1, "after_tax_cost_of_debt": 0.04, "terminal_growth": 0.025,
            "wacc_tax_rate": 0.25, "valuation_beta": 0.7, "discount_rate": 0.08, "equity_market_value": 100.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_level_tilt_and_relevering(root):
    coc = _coc([
        {"ticker": "A0", "sector_ticker": "XLP", "discount_rate_type": "WACC", "gross_debt": 20.0},
        {"ticker": "B0", "sector_ticker": "XLP", "discount_rate_type": "WACC", "gross_debt": 20.0},
        {"ticker": "A1", "sector_ticker": "XLP", "discount_rate_type": "WACC", "gross_debt": 80.0},
    ])
    out, audit, table = apply_industry_betas(coc, root, root / "out", 0.045, 0.05, "2026-11-11", {"anchor_years": 10})
    a = audit.set_index("ticker")
    level = float(table.set_index("sector_ticker").loc["XLP", "beta_long_run"])
    assert 0.5 < level < 0.7                                  # true 0.6
    assert a.loc["A0", "tilt"] > 0 > a.loc["B0", "tilt"]      # within-sector ordering kept
    assert abs(a.loc["A0", "tilt"]) <= 0.35 + 1e-12
    # same peers, more debt -> higher relevered beta
    assert a.loc["A1", "final_beta"] > a.loc["A0", "final_beta"]
    # unlever/relever round trip at peer leverage returns the levered industry beta
    assert a.loc["A0", "final_beta"] == pytest.approx(a.loc["A0", "levered_industry_beta"], rel=1e-9)
    o = out.set_index("ticker")
    assert o.loc["A0", "cost_of_equity"] == pytest.approx(0.045 + a.loc["A0", "final_beta"] * 0.05)
    assert o.loc["A0", "discount_rate"] == pytest.approx(0.9 * o.loc["A0", "cost_of_equity"] + 0.1 * 0.04)
    assert (o["beta_source"] == "BOTTOM_UP_INDUSTRY").all()


def test_financials_use_levered_industry_beta_and_cost_of_equity(root):
    coc = _coc([{"ticker": "BANK", "sector_ticker": "XLF", "discount_rate_type": "COST_OF_EQUITY", "gross_debt": 900.0}])
    out, audit, _ = apply_industry_betas(coc, root, root / "out", 0.045, 0.05, "2026-11-11", {})
    a = audit.iloc[0]
    assert a["method"] == "LEVERED_INDUSTRY_FINANCIAL"
    assert a["final_beta"] == pytest.approx(a["levered_industry_beta"])
    assert out.iloc[0]["discount_rate"] == pytest.approx(out.iloc[0]["cost_of_equity"])


def test_bounds_respected(root):
    coc = _coc([{"ticker": "B0", "sector_ticker": "XLP", "discount_rate_type": "WACC", "gross_debt": 0.0}])
    out, audit, _ = apply_industry_betas(coc, root, root / "out", 0.045, 0.05, "2026-11-11", {"min_beta": 0.9})
    assert audit.iloc[0]["final_beta"] == pytest.approx(0.9)
