"""Valuation and execution guardrails for the live macro portfolio engine.

These helpers are deliberately small and deterministic so they can be unit-tested
separately from the large research sections.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Optional


def _finite_positive(value: Any) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return isfinite(x) and x > 0.0


def classify_valuation_anomaly(
    *,
    expected_intrinsic_value: Any,
    current_price: Any,
    consensus_target_mean: Any = None,
    currency_reconciliation_ready: bool = True,
    iv_price_ratio_min: float = 0.20,
    iv_price_ratio_max: float = 3.00,
    consensus_review_divergence: float = 0.40,
    consensus_critical_divergence: float = 0.75,
) -> Dict[str, Any]:
    """Classify model-risk severity without changing the valuation itself.

    CRITICAL means the name must not be opened as a new position until reviewed.
    REVIEW means it remains research/ranking eligible but requires analyst review.
    NORMAL means none of the configured anomaly checks fired.
    """
    iv_price_ratio: Optional[float] = None
    consensus_divergence_abs: Optional[float] = None
    reasons = []
    critical = False
    review = False

    if not bool(currency_reconciliation_ready):
        critical = True
        reasons.append("CURRENCY_OR_LISTED_UNIT_RECONCILIATION_NOT_READY")

    if _finite_positive(expected_intrinsic_value) and _finite_positive(current_price):
        iv_price_ratio = float(expected_intrinsic_value) / float(current_price)
        if iv_price_ratio < float(iv_price_ratio_min):
            critical = True
            reasons.append("IV_PRICE_RATIO_BELOW_CRITICAL_BOUND")
        elif iv_price_ratio > float(iv_price_ratio_max):
            critical = True
            reasons.append("IV_PRICE_RATIO_ABOVE_CRITICAL_BOUND")
    else:
        critical = True
        reasons.append("INVALID_IV_OR_PRICE")

    if _finite_positive(consensus_target_mean) and _finite_positive(expected_intrinsic_value):
        consensus_divergence_abs = abs(
            float(expected_intrinsic_value) / float(consensus_target_mean) - 1.0
        )
        if consensus_divergence_abs > float(consensus_critical_divergence):
            critical = True
            reasons.append("MODEL_CONSENSUS_DIVERGENCE_CRITICAL")
        elif consensus_divergence_abs > float(consensus_review_divergence):
            review = True
            reasons.append("MODEL_CONSENSUS_DIVERGENCE_REVIEW")

    if critical:
        severity = "CRITICAL_REVIEW"
    elif review:
        severity = "REVIEW"
    else:
        severity = "NORMAL"

    return {
        "iv_price_ratio": iv_price_ratio,
        "consensus_divergence_abs": consensus_divergence_abs,
        "valuation_review_severity": severity,
        "valuation_critical_block": bool(critical),
        "valuation_anomaly_reason": ";".join(reasons),
    }


def clean_optimizer_weight(weight: Any, epsilon: float = 1e-8) -> float:
    """Remove numerical QP residue without changing economically meaningful weights."""
    try:
        w = float(weight)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not isfinite(w) or abs(w) < float(epsilon):
        return 0.0
    return w


def choose_listed_unit_count(
    *,
    cross_currency: bool,
    market_cap_implied_units: Any,
    economic_units: Any,
    economic_source: str = "",
    security_type: str = "COMMON",
    underlying_per_listed_unit: Any = None,
) -> Dict[str, Any]:
    """Choose the denominator matching the actually traded security.

    For cross-currency ADR/GDR listings, market_cap/current_price is preferred
    because both values refer to the quoted listed security. If it is absent,
    a known depositary-receipt ratio can translate an underlying statement
    share count into listed receipt units.
    """
    if bool(cross_currency) and _finite_positive(market_cap_implied_units):
        return {
            "valuation_share_units": float(market_cap_implied_units),
            "valuation_share_unit_source": "MARKET_CAP_IMPLIED_LISTED_UNITS",
        }

    if not _finite_positive(economic_units):
        return {
            "valuation_share_units": None,
            "valuation_share_unit_source": "MISSING",
        }

    units = float(economic_units)
    source = str(economic_source or "ECONOMIC_DILUTED_SHARES")
    stype = str(security_type or "COMMON").upper()

    if (
        stype in {"ADR", "GDR", "DEPOSITARY_RECEIPT"}
        and _finite_positive(underlying_per_listed_unit)
        and source in {"STATEMENT_DILUTED_SHARES", "STATEMENT_ORDINARY_SHARES"}
    ):
        units /= float(underlying_per_listed_unit)
        source = f"{source}_ADJUSTED_FOR_RECEIPT_RATIO"

    return {
        "valuation_share_units": units,
        "valuation_share_unit_source": source,
    }


def intrinsic_value_per_listed_unit(
    *,
    equity_value_financial_currency: Any,
    financial_to_price_fx: Any,
    listed_units: Any,
) -> float:
    """Translate total equity value to the traded security's per-unit value."""
    if not _finite_positive(financial_to_price_fx):
        raise ValueError("financial_to_price_fx must be positive and finite")
    if not _finite_positive(listed_units):
        raise ValueError("listed_units must be positive and finite")
    try:
        equity = float(equity_value_financial_currency)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("equity value must be numeric") from exc
    if not isfinite(equity):
        raise ValueError("equity value must be finite")
    return equity * float(financial_to_price_fx) / float(listed_units)
