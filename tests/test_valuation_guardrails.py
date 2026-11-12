from pathlib import Path
import math
import yaml

from macro_portfolio.valuation_controls import (
    choose_listed_unit_count,
    classify_valuation_anomaly,
    clean_optimizer_weight,
    intrinsic_value_per_listed_unit,
)

ROOT = Path(__file__).resolve().parents[1]


def test_tsm_adr_listed_unit_reconciliation_prefers_market_cap_implied_units():
    # TSM's issuer statement share count is ordinary shares (~25.9bn), while
    # the NYSE ADR quote has ~5.19bn listed-equivalent units (5 ord : 1 ADR).
    out = choose_listed_unit_count(
        cross_currency=True,
        market_cap_implied_units=5.19e9,
        economic_units=25.95e9,
        economic_source="STATEMENT_DILUTED_SHARES",
        security_type="ADR",
        underlying_per_listed_unit=5.0,
    )
    assert math.isclose(out["valuation_share_units"], 5.19e9)
    assert out["valuation_share_unit_source"] == "MARKET_CAP_IMPLIED_LISTED_UNITS"


def test_tsm_currency_translation_converts_twd_total_equity_to_usd_adr_value():
    # If the old model produced ~NT$10,491 per ADR-equivalent unit, translating
    # at about NT$31.6/USD should produce about US$332, not US$10,491.
    listed_units = 5.19e9
    twd_per_adr_equivalent = 10491.3725
    equity_twd = twd_per_adr_equivalent * listed_units
    iv_usd = intrinsic_value_per_listed_unit(
        equity_value_financial_currency=equity_twd,
        financial_to_price_fx=1.0 / 31.6,
        listed_units=listed_units,
    )
    assert 330.0 < iv_usd < 335.0


def test_pre_fix_tsm_output_is_critical_anomaly():
    out = classify_valuation_anomaly(
        expected_intrinsic_value=10491.3725,
        current_price=456.19,
        consensus_target_mean=552.2594,
        currency_reconciliation_ready=True,
    )
    assert out["valuation_critical_block"] is True
    assert out["valuation_review_severity"] == "CRITICAL_REVIEW"


def test_reasonable_model_consensus_difference_is_not_critical():
    out = classify_valuation_anomaly(
        expected_intrinsic_value=294.47,
        current_price=221.10,
        consensus_target_mean=250.0,
        currency_reconciliation_ready=True,
    )
    assert out["valuation_critical_block"] is False
    assert out["valuation_review_severity"] == "NORMAL"


def test_currency_reconciliation_failure_blocks_entry():
    out = classify_valuation_anomaly(
        expected_intrinsic_value=150,
        current_price=120,
        consensus_target_mean=145,
        currency_reconciliation_ready=False,
    )
    assert out["valuation_critical_block"] is True
    assert "CURRENCY_OR_LISTED_UNIT_RECONCILIATION_NOT_READY" in out["valuation_anomaly_reason"]


def test_optimizer_residue_is_zeroed():
    assert clean_optimizer_weight(5.7e-9, epsilon=1e-8) == 0.0
    assert clean_optimizer_weight(0.025, epsilon=1e-8) == 0.025


def test_config_contains_tsm_adr_and_anomaly_governance():
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())
    tsm = cfg["valuation"]["security_overrides"]["TSM"]
    assert tsm["security_type"] == "ADR"
    assert float(tsm["underlying_per_listed_unit"]) == 5.0
    assert tsm["expected_financial_currency"] == "TWD"
    assert tsm["expected_price_currency"] == "USD"
    gate = cfg["valuation"]["anomaly_gate"]
    assert float(gate["iv_price_ratio_max"]) == 3.0
    assert bool(gate["block_critical_new_entries"]) is True


def test_section_f_and_g_wire_guardrails_into_production_flow():
    f = (ROOT / "src" / "macro_portfolio" / "engine" / "sections" / "section_f.py").read_text()
    g = (ROOT / "src" / "macro_portfolio" / "engine" / "sections" / "section_g.py").read_text()
    assert "financial_to_price_fx" in f
    assert "valuation_share_units" in f
    assert "valuation_critical_block" in f
    assert "valuation_entry_eligible" in f
    # Reverse DCF / implied-multiple logic must use the same listed-unit + FX
    # lineage as the forward intrinsic valuation.
    assert "market_equity_value_price_currency" in f
    assert "target_equity_value = (" in f
    assert "valuation_fx" in f
    assert 'G1_MASTER["valuation_entry_eligible"]' in g
    assert '"VALUATION_CRITICAL_BLOCKED"' in g
    assert 'action = "DEFER_SMALL"' in g
