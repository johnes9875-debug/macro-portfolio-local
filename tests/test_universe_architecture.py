from pathlib import Path

import pandas as pd
import yaml

from macro_portfolio.universe import (
    _parse_ishares_csv,
    _parse_stockanalysis_soxx_html,
    combine_current_universes,
)

ROOT = Path(__file__).resolve().parents[1]


def test_master_universe_deduplicates_and_preserves_membership_flags():
    sp = pd.DataFrame([
        {"ticker":"NVDA","company_name":"Nvidia","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors"},
        {"ticker":"JPM","company_name":"JPMorgan","gics_sector":"Financials","gics_sub_industry":"Diversified Banks"},
    ])
    ndx = pd.DataFrame([
        {"ticker":"NVDA","company_name":"Nvidia","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors"},
        {"ticker":"CRWD","company_name":"CrowdStrike","gics_sector":"Information Technology","gics_sub_industry":"Systems Software"},
    ])
    soxx = pd.DataFrame([
        {"ticker":"NVDA","company_name":"Nvidia","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors & Semiconductor Equipment"},
        {"ticker":"TSM","company_name":"TSMC","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors & Semiconductor Equipment"},
    ])
    out = combine_current_universes(sp, ndx, soxx, pd.Timestamp("2026-10-01"))
    assert set(out.ticker) == {"NVDA","JPM","CRWD","TSM"}
    nvda = out.set_index("ticker").loc["NVDA"]
    assert bool(nvda.member_sp500) and bool(nvda.member_nasdaq100) and bool(nvda.member_soxx)
    assert nvda.universe_source_count == 3
    assert out.set_index("ticker").loc["TSM","sector_ticker"] == "XLK"


def test_config_declares_three_layer_universe_and_funnel():
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    u = cfg["universe"]
    assert u["sources"]["sp500"]["role"] == "CORE"
    assert u["sources"]["nasdaq100"]["role"] == "GROWTH_OVERLAY"
    assert u["sources"]["soxx"]["role"] == "SEMICONDUCTOR_SPECIALIST_OVERLAY"
    assert u["research_funnel"]["deep_valuation_max_total"] == 60
    assert u["research_funnel"]["deep_valuation_target_min"] == 30


def test_section_e_uses_dynamic_master_and_deep_valuation_pool():
    text = (ROOT / "src" / "macro_portfolio" / "engine" / "sections" / "section_e.py").read_text(encoding="utf-8")
    assert "fetch_sp500" in text
    assert "fetch_nasdaq100" in text
    assert "fetch_soxx" in text
    assert "combine_current_universes" in text
    assert "DEEP_VALUATION_UNIVERSE" in text
    assert "STOCK_MIN_ADV20_DOLLAR" in text
    assert "E7_SOXX_SPECIALIST_FLOOR" in text


def test_section_f_consumes_deep_valuation_pool():
    text = (ROOT / "src" / "macro_portfolio" / "engine" / "sections" / "section_f.py").read_text(encoding="utf-8")
    assert '"DEEP_VALUATION_UNIVERSE"' in text
    assert "VALUATION_SECURITY_UNIVERSE = (\n\n    DEEP_VALUATION_UNIVERSE" in text


def test_ishares_csv_parser_accepts_metadata_and_quoted_header():
    rows = [
        'iShares Semiconductor ETF',
        'Fund Holdings as of,"Sep 30, 2026"',
        '',
        '"Ticker","Name","Sector","Asset Class","Weight (%)"',
    ]
    for i in range(20):
        rows.append(f'"T{i:02d}","Company {i}","Information Technology","Equity","{5-i*0.1:.2f}"')
    rows.append('"USD","USD CASH","Cash and/or Derivatives","Cash","0.1"')
    out = _parse_ishares_csv("\n".join(rows))
    assert len(out) == 20
    assert set(out["membership_source_detail"]) == {"ISHARES_HOLDINGS_CSV"}
    assert out["ticker"].iloc[0] == "T00"




def test_master_universe_marks_secondary_soxx_membership_non_exact():
    sp = pd.DataFrame([{"ticker":"NVDA","company_name":"Nvidia","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors"}])
    ndx = sp.copy()
    soxx = pd.DataFrame([
        {"ticker":"NVDA","company_name":"Nvidia","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors","membership_source_detail":"STOCKANALYSIS_SOXX_HOLDINGS"},
        {"ticker":"TSM","company_name":"TSMC","gics_sector":"Information Technology","gics_sub_industry":"Semiconductors","membership_source_detail":"STOCKANALYSIS_SOXX_HOLDINGS"},
    ])
    out = combine_current_universes(sp, ndx, soxx, pd.Timestamp("2026-10-01")).set_index("ticker")
    assert out.loc["NVDA", "soxx_membership_source"] == "STOCKANALYSIS_SOXX_HOLDINGS"
    assert not bool(out.loc["NVDA", "soxx_membership_exact"])
    assert out.loc["NVDA", "soxx_membership_quality"] == "SECONDARY_LIVE"


def test_sector_aliases_normalize_to_canonical_gics():
    from macro_portfolio.universe import canonicalize_gics_sector, GICS_TO_SECTOR_ETF
    cases = {
        "Technology": "Information Technology",
        "Healthcare": "Health Care",
        "Financial Services": "Financials",
        "Consumer Cyclical": "Consumer Discretionary",
        "Consumer Defensive": "Consumer Staples",
        "Basic Materials": "Materials",
        "Communication Services": "Communication Services",
        "Industrials": "Industrials",
        "Energy": "Energy",
        "Utilities": "Utilities",
        "Real Estate": "Real Estate",
    }
    for raw, expected in cases.items():
        got = canonicalize_gics_sector(raw)
        assert got == expected
        assert got in GICS_TO_SECTOR_ETF


def test_soxx_members_are_forced_to_information_technology():
    sp = pd.DataFrame([{"ticker":"JPM","company_name":"JPMorgan","gics_sector":"Financial Services"}])
    ndx = pd.DataFrame([{"ticker":"NVDA","company_name":"Nvidia","gics_sector":None}])
    soxx = pd.DataFrame([{"ticker":"NVDA","company_name":"Nvidia","gics_sector":None,"membership_source_detail":"BUNDLED_SOXX_LAST_KNOWN_GOOD"}])
    out = combine_current_universes(sp, ndx, soxx, pd.Timestamp("2026-10-01")).set_index("ticker")
    assert out.loc["NVDA", "gics_sector"] == "Information Technology"
    assert out.loc["NVDA", "sector_ticker"] == "XLK"
    assert out.loc["JPM", "gics_sector"] == "Financials"
    assert out.loc["JPM", "sector_ticker"] == "XLF"


def test_company_level_sector_enrichment_guarantees_100pct_coverage(tmp_path):
    from macro_portfolio.universe import enrich_gics_sector_coverage
    master = pd.DataFrame([
        {"ticker":"NVDA","company_name":"Nvidia","gics_sector":None,"gics_sub_industry":None,"member_soxx":True,"universe_memberships":"NASDAQ100+SOXX"},
        {"ticker":"MELI","company_name":"MercadoLibre","gics_sector":None,"gics_sub_industry":None,"member_soxx":False,"universe_memberships":"NASDAQ100"},
        {"ticker":"JPM","company_name":"JPMorgan","gics_sector":"Financial Services","gics_sub_industry":"Banks","member_soxx":False,"universe_memberships":"SP500"},
    ])
    fake = {
        "MELI": {"sector":"Consumer Cyclical","industry":"Internet Retail","longName":"MercadoLibre"},
    }
    def fetcher(ticker):
        return fake[ticker]
    out = enrich_gics_sector_coverage(
        master,
        curated_dir=tmp_path,
        snapshot_date=pd.Timestamp("2026-10-01"),
        yahoo_fetcher=fetcher,
    )
    assert out["sector_ticker"].notna().all()
    assert out["gics_sector"].isin({
        "Information Technology","Financials","Communication Services","Consumer Discretionary",
        "Health Care","Industrials","Consumer Staples","Energy","Utilities","Materials","Real Estate"
    }).all()
    x = out.set_index("ticker")
    assert x.loc["NVDA","gics_sector"] == "Information Technology"
    assert x.loc["MELI","gics_sector"] == "Consumer Discretionary"
    assert x.loc["JPM","gics_sector"] == "Financials"
