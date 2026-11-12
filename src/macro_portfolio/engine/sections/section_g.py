# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.

from scipy import stats as scipy_stats


# ===== ORIGINAL NOTEBOOK CELL 79 =====
# ==================================================================================================
# SECTION G — STOCK ALPHA INTEGRATION ENGINE
# CELL G1 — REGIME × COMPANY × VALUATION MASTER SIGNAL V1.3.0
#          DETERMINISTIC E7/D6 SOURCE RECOVERY
# ==================================================================================================
#
# Purpose:
#   Combine the three completed research pillars:
#       1. Section D macro / sector attractiveness
#       2. Section E7 company-selection quality
#       3. Section F final valuation signal
#
# Master research-alpha weights are loaded from CONFIG["alpha"]
# rather than embedded in this cell.
#
# Governance:
#   - ranking_eligible_after_f5 controls research ranking eligibility.
#   - mos_threshold_met is necessary but not sufficient for a new entry.
#   - critical valuation/model-risk anomalies are blocked from new entries.
#   - all provisional/non-rankable names remain blocked dynamically.
#
# This cell does NOT optimize portfolio weights.
# ==================================================================================================

from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from macro_portfolio.valuation_controls import clean_optimizer_weight

# ==================================================================================================
# 1. VALIDATE SECTION F
# ==================================================================================================

_required_g1 = [
    "VALUATION_SECTION_F_PASSED",
    "F_FINAL_VALUATION_HANDOFF",
    "F4C_MANIFEST",
    "VALUATION_UNIVERSE_FREEZE_ID",
    "VALUATION_UNIVERSE_SHA256",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
    "SECTOR_STOCK_RESEARCH_SCOPE",
]

_missing_g1 = [x for x in _required_g1 if x not in globals()]

if _missing_g1:
    raise RuntimeError(
        "G1 requires the frozen Section F stack. Missing: "
        f"{_missing_g1}"
    )

if not bool(VALUATION_SECTION_F_PASSED):
    raise RuntimeError("Section F production gate did not pass.")

G1_VERSION = "1.3.0"

# ==================================================================================================
# 2. WEIGHTS / POLICY
# ==================================================================================================

G1_SECTOR_WEIGHT = float(cfg(["alpha", "sector_weight"], 0.30))
G1_COMPANY_WEIGHT = float(cfg(["alpha", "company_weight"], 0.35))
G1_VALUATION_WEIGHT = float(cfg(["alpha", "valuation_weight"], 0.35))

if not np.isclose(
    G1_SECTOR_WEIGHT + G1_COMPANY_WEIGHT + G1_VALUATION_WEIGHT,
    1.0,
):
    raise RuntimeError("G1 signal weights must sum to 1.")

# Dynamic allocation buckets come directly from the CURRENT E1 handoff.
_required_scope_cols = {"ticker", "stock_research_scope"}
_missing_scope_cols = _required_scope_cols - set(SECTOR_STOCK_RESEARCH_SCOPE.columns)
if _missing_scope_cols:
    raise RuntimeError(
        "G1 current sector scope is missing columns: "
        f"{sorted(_missing_scope_cols)}"
    )

G1_CORE_LONG_SECTORS = set(
    SECTOR_STOCK_RESEARCH_SCOPE.loc[
        SECTOR_STOCK_RESEARCH_SCOPE["stock_research_scope"].astype(str) == "CORE_LONG",
        "ticker",
    ].astype(str)
)
G1_TACTICAL_LONG_SECTORS = set(
    SECTOR_STOCK_RESEARCH_SCOPE.loc[
        SECTOR_STOCK_RESEARCH_SCOPE["stock_research_scope"].astype(str) == "TACTICAL_LONG",
        "ticker",
    ].astype(str)
)
G1_LONG_ELIGIBLE_SECTORS = G1_CORE_LONG_SECTORS | G1_TACTICAL_LONG_SECTORS

# ==================================================================================================
# 3. HELPERS
# ==================================================================================================

def g1_fit_robust_scale(series):
    values = pd.to_numeric(series, errors="coerce")
    valid = values.dropna()

    if valid.empty:
        raise RuntimeError("Cannot fit robust scale to an empty series.")

    center = float(valid.median())
    mad = float((valid - center).abs().median())

    if safe_isfinite(mad) and mad > 1e-12:
        scale = 1.4826 * mad
        method = "MEDIAN_MAD"
    else:
        scale = float(valid.std(ddof=0))
        method = "STD_FALLBACK"
        if not (safe_isfinite(scale) and scale > 1e-12):
            scale = 1.0

    return {
        "center": center,
        "scale": scale,
        "method": method,
    }


def g1_apply_robust_scale(series, fitted):
    values = pd.to_numeric(series, errors="coerce")
    z = (values - fitted["center"]) / fitted["scale"]
    return z.clip(lower=-3.0, upper=3.0)


# ==================================================================================================
# 4. FROZEN TARGET UNIVERSE
# ==================================================================================================

G1_TARGETS = F_FINAL_VALUATION_HANDOFF.copy()
G1_TARGETS["ticker"] = G1_TARGETS["ticker"].astype(str)

G1_TARGET_TICKERS = set(G1_TARGETS["ticker"])

G1_EXPECTED_COMPANY_COUNT = int(
    F4C_MANIFEST["ticker"]
    .astype(str)
    .nunique()
)

G1_EXPECTED_RANKING_COUNT = int(
    G1_TARGETS["ranking_eligible_after_f5"]
    .fillna(False)
    .astype(bool)
    .sum()
)

G1_EXPECTED_PROVISIONAL_COUNT = int(
    (~G1_TARGETS["ranking_eligible_after_f5"].fillna(False).astype(bool)).sum()
)

if len(G1_TARGET_TICKERS) != G1_EXPECTED_COMPANY_COUNT:
    raise RuntimeError(
        "G1 Section F universe differs from the frozen F4C lineage: "
        f"Section F={len(G1_TARGET_TICKERS)}, "
        f"F4C={G1_EXPECTED_COMPANY_COUNT}."
    )

# ==================================================================================================
# 5. LOAD EXACT SECTION E7 COMPANY-SELECTION OUTPUT
# ==================================================================================================
#
# The canonical E7 score is:
#       stock_selection_score_z
#
# The canonical E7 confidence is:
#       stock_selection_confidence
#
# Recovery hierarchy:
#       1. in-memory STOCK_SELECTION_SIGNAL
#       2. saved parquet live_combined_stock_selection.parquet
#       3. saved CSV e7_combined_stock_selection.csv
# ==================================================================================================

G1_E7_SOURCE_TYPE = None
G1_E7_SOURCE_PATH = None

if (
    "STOCK_SELECTION_SIGNAL" in globals()
    and isinstance(STOCK_SELECTION_SIGNAL, pd.DataFrame)
):
    G1_E7_SOURCE = STOCK_SELECTION_SIGNAL.copy()
    G1_E7_SOURCE_TYPE = "MEMORY"
    G1_E7_SOURCE_NAME = "STOCK_SELECTION_SIGNAL"

else:
    _e7_parquet = Path(STOCK_MODEL_DIR) / "live_combined_stock_selection.parquet"
    _e7_csv = Path(STOCK_OUTPUT_DIR) / "e7_combined_stock_selection.csv"

    if _e7_parquet.exists():
        G1_E7_SOURCE = pd.read_parquet(_e7_parquet)
        G1_E7_SOURCE_TYPE = "PARQUET"
        G1_E7_SOURCE_NAME = "live_combined_stock_selection.parquet"
        G1_E7_SOURCE_PATH = str(_e7_parquet)

    elif _e7_csv.exists():
        G1_E7_SOURCE = pd.read_csv(_e7_csv)
        G1_E7_SOURCE_TYPE = "CSV"
        G1_E7_SOURCE_NAME = "e7_combined_stock_selection.csv"
        G1_E7_SOURCE_PATH = str(_e7_csv)

    else:
        raise RuntimeError(
            "G1 cannot recover Section E7. Run E7 first or ensure "
            "live_combined_stock_selection.parquet exists."
        )

_required_e7_cols = [
    "ticker",
    "stock_selection_score_z",
    "stock_selection_confidence",
]

_missing_e7_cols = [
    c for c in _required_e7_cols
    if c not in G1_E7_SOURCE.columns
]

if _missing_e7_cols:
    raise RuntimeError(
        "Recovered E7 source is missing canonical columns: "
        f"{_missing_e7_cols}. Available columns include: "
        f"{list(G1_E7_SOURCE.columns)[:30]}"
    )

G1_COMPANY_INPUT = (
    G1_E7_SOURCE[
        _required_e7_cols
    ]
    .copy()
)

G1_COMPANY_INPUT["ticker"] = (
    G1_COMPANY_INPUT["ticker"]
    .astype(str)
)

G1_COMPANY_INPUT = (
    G1_COMPANY_INPUT[
        G1_COMPANY_INPUT["ticker"].isin(G1_TARGET_TICKERS)
    ]
    .drop_duplicates(subset=["ticker"], keep="first")
    .copy()
)

G1_COMPANY_INPUT["raw_company_selection_input"] = pd.to_numeric(
    G1_COMPANY_INPUT["stock_selection_score_z"],
    errors="coerce",
)

G1_COMPANY_INPUT["company_selection_confidence"] = (
    pd.to_numeric(
        G1_COMPANY_INPUT["stock_selection_confidence"],
        errors="coerce",
    )
    .clip(lower=0.0, upper=1.0)
)

_e7_missing_tickers = sorted(
    G1_TARGET_TICKERS - set(G1_COMPANY_INPUT["ticker"])
)

if _e7_missing_tickers:
    raise RuntimeError(
        "E7 source does not cover all frozen valuation targets. "
        f"Missing: {_e7_missing_tickers}"
    )

if G1_COMPANY_INPUT["raw_company_selection_input"].isna().any():
    bad = G1_COMPANY_INPUT.loc[
        G1_COMPANY_INPUT["raw_company_selection_input"].isna(),
        "ticker",
    ].tolist()
    raise RuntimeError(
        f"E7 stock_selection_score_z is missing/non-numeric for: {bad}"
    )

_company_conf_median = (
    G1_COMPANY_INPUT["company_selection_confidence"]
    .median()
)

if pd.isna(_company_conf_median):
    _company_conf_median = 1.0

G1_COMPANY_INPUT["company_selection_confidence"] = (
    G1_COMPANY_INPUT["company_selection_confidence"]
    .fillna(_company_conf_median)
)

# Re-standardize only to place all three G1 pillars on a common robust scale.
_company_scale = g1_fit_robust_scale(
    G1_COMPANY_INPUT["raw_company_selection_input"]
)

G1_COMPANY_INPUT["company_selection_signal"] = g1_apply_robust_scale(
    G1_COMPANY_INPUT["raw_company_selection_input"],
    _company_scale,
)

# ==================================================================================================
# 6. LOAD EXACT SECTION D6 SECTOR SIGNAL
# ==================================================================================================
#
# Canonical D6 score:
#       risk_adjusted_score_z
#
# Recovery hierarchy:
#       1. in-memory SECTOR_RISK_ADJUSTED_SIGNAL
#       2. saved parquet live_sector_risk_adjusted_signal.parquet
#
# No stale frozen-score fallback is permitted. If current D6 data
# cannot be recovered, G1 fails rather than silently using old state.
# ==================================================================================================

G1_D_SOURCE_TYPE = None
G1_D_SOURCE_PATH = None

if (
    "SECTOR_RISK_ADJUSTED_SIGNAL" in globals()
    and isinstance(SECTOR_RISK_ADJUSTED_SIGNAL, pd.DataFrame)
):
    G1_D_SOURCE = SECTOR_RISK_ADJUSTED_SIGNAL.copy()
    G1_D_SOURCE_TYPE = "MEMORY"
    G1_D_SOURCE_NAME = "SECTOR_RISK_ADJUSTED_SIGNAL"

else:
    _regime_dir = (
        Path(REGIME_MODEL_DIR)
        if "REGIME_MODEL_DIR" in globals()
        else Path(STOCK_MODEL_DIR).parent / "regime"
    )

    _d6_parquet = _regime_dir / "live_sector_risk_adjusted_signal.parquet"

    if _d6_parquet.exists():
        G1_D_SOURCE = pd.read_parquet(_d6_parquet)
        G1_D_SOURCE_TYPE = "PARQUET"
        G1_D_SOURCE_NAME = "live_sector_risk_adjusted_signal.parquet"
        G1_D_SOURCE_PATH = str(_d6_parquet)

    else:
        raise RuntimeError(
            "G1 cannot recover the CURRENT D6 sector signal. "
            "Run D6/D8 first or ensure live_sector_risk_adjusted_signal.parquet exists. "
            "A stale frozen sector-score fallback is intentionally prohibited."
        )

# D6 uses "ticker" for sector ETFs.
_sector_col = (
    "sector_ticker"
    if "sector_ticker" in G1_D_SOURCE.columns
    else "ticker"
    if "ticker" in G1_D_SOURCE.columns
    else None
)

if _sector_col is None:
    raise RuntimeError(
        "Recovered D6 source has neither 'ticker' nor 'sector_ticker'."
    )

_score_col = (
    "risk_adjusted_score_z"
    if "risk_adjusted_score_z" in G1_D_SOURCE.columns
    else "risk_adjusted_score_raw"
    if "risk_adjusted_score_raw" in G1_D_SOURCE.columns
    else None
)

if _score_col is None:
    raise RuntimeError(
        "Recovered D6 source is missing risk_adjusted_score_z/raw."
    )

G1_SECTOR_INPUT = (
    G1_D_SOURCE[
        [_sector_col, _score_col]
    ]
    .copy()
    .rename(
        columns={
            _sector_col: "sector_ticker",
            _score_col: "raw_sector_score",
        }
    )
    .drop_duplicates(subset=["sector_ticker"], keep="first")
)

G1_SECTOR_INPUT["sector_ticker"] = (
    G1_SECTOR_INPUT["sector_ticker"]
    .astype(str)
)

G1_SECTOR_INPUT["raw_sector_score"] = pd.to_numeric(
    G1_SECTOR_INPUT["raw_sector_score"],
    errors="coerce",
)

# Require live/current D6 coverage for every sector represented in the
# frozen valuation universe. Missing current sector state is a hard fail.
_existing_sectors = set(G1_SECTOR_INPUT["sector_ticker"])
_required_target_sectors = set(
    G1_TARGETS["sector_ticker"].dropna().astype(str).unique()
)
_missing_sectors = _required_target_sectors - _existing_sectors

if _missing_sectors:
    raise RuntimeError(
        "G1 current D6 sector signal does not cover valuation-universe sectors: "
        f"{sorted(_missing_sectors)}"
    )

_scope_sectors = set(SECTOR_STOCK_RESEARCH_SCOPE["ticker"].astype(str))
_unknown_target_sectors = _required_target_sectors - _scope_sectors
if _unknown_target_sectors:
    raise RuntimeError(
        "G1 valuation-universe sectors are absent from current E1 scope: "
        f"{sorted(_unknown_target_sectors)}"
    )

_sector_scale = g1_fit_robust_scale(
    G1_SECTOR_INPUT["raw_sector_score"]
)

G1_SECTOR_INPUT["sector_signal"] = g1_apply_robust_scale(
    G1_SECTOR_INPUT["raw_sector_score"],
    _sector_scale,
)

# ==================================================================================================
# 7. NORMALIZE SECTION F VALUATION SIGNAL
# ==================================================================================================

_valuation_fit_mask = (
    G1_TARGETS["ranking_eligible_after_f5"]
    .fillna(False)
    .astype(bool)
)

_valuation_scale = g1_fit_robust_scale(
    G1_TARGETS.loc[
        _valuation_fit_mask,
        "final_valuation_signal",
    ]
)

G1_TARGETS["valuation_signal_normalized"] = g1_apply_robust_scale(
    G1_TARGETS["final_valuation_signal"],
    _valuation_scale,
)

# ==================================================================================================
# 8. MERGE THREE PILLARS
# ==================================================================================================

G1_MASTER = (
    G1_TARGETS
    .merge(
        G1_COMPANY_INPUT[
            [
                "ticker",
                "raw_company_selection_input",
                "company_selection_signal",
                "company_selection_confidence",
            ]
        ],
        on="ticker",
        how="left",
        validate="one_to_one",
    )
    .merge(
        G1_SECTOR_INPUT[
            [
                "sector_ticker",
                "raw_sector_score",
                "sector_signal",
            ]
        ],
        on="sector_ticker",
        how="left",
        validate="many_to_one",
    )
)

if G1_MASTER["company_selection_signal"].isna().any():
    bad = G1_MASTER.loc[
        G1_MASTER["company_selection_signal"].isna(),
        "ticker",
    ].tolist()
    raise RuntimeError(
        f"Missing E7 company-selection signal for: {bad}"
    )

if G1_MASTER["sector_signal"].isna().any():
    bad = G1_MASTER.loc[
        G1_MASTER["sector_signal"].isna(),
        ["ticker", "sector_ticker"],
    ].to_dict("records")
    raise RuntimeError(
        f"Missing D6 sector signal for: {bad}"
    )

# ==================================================================================================
# 9. MASTER ALPHA + ATTRIBUTION
# ==================================================================================================

G1_MASTER["sector_alpha_contribution"] = (
    G1_SECTOR_WEIGHT
    * G1_MASTER["sector_signal"]
)

G1_MASTER["company_alpha_contribution"] = (
    G1_COMPANY_WEIGHT
    * G1_MASTER["company_selection_signal"]
)

G1_MASTER["valuation_alpha_contribution"] = (
    G1_VALUATION_WEIGHT
    * G1_MASTER["valuation_signal_normalized"]
)

G1_MASTER["master_alpha_score"] = (
    G1_MASTER["sector_alpha_contribution"]
    + G1_MASTER["company_alpha_contribution"]
    + G1_MASTER["valuation_alpha_contribution"]
)

# ==================================================================================================
# 10. ALLOCATION / ENTRY GOVERNANCE
# ==================================================================================================

G1_MASTER["allocation_bucket"] = np.select(
    [
        G1_MASTER["sector_ticker"].isin(G1_CORE_LONG_SECTORS),
        G1_MASTER["sector_ticker"].isin(G1_TACTICAL_LONG_SECTORS),
    ],
    [
        "CORE_LONG",
        "TACTICAL_LONG",
    ],
    default="NOT_LONG_ELIGIBLE",
)

G1_MASTER["research_ranking_eligible"] = (
    G1_MASTER["ranking_eligible_after_f5"]
    .fillna(False)
    .astype(bool)
)

if "valuation_entry_eligible" not in G1_MASTER.columns:
    G1_MASTER["valuation_entry_eligible"] = True
if "valuation_critical_block" not in G1_MASTER.columns:
    G1_MASTER["valuation_critical_block"] = False
if "valuation_review_severity" not in G1_MASTER.columns:
    G1_MASTER["valuation_review_severity"] = "NORMAL"
if "valuation_anomaly_reason" not in G1_MASTER.columns:
    G1_MASTER["valuation_anomaly_reason"] = ""

G1_MASTER["entry_eligible_now"] = (
    G1_MASTER["research_ranking_eligible"]
    & G1_MASTER["mos_threshold_met"].fillna(False).astype(bool)
    & G1_MASTER["valuation_entry_eligible"].fillna(False).astype(bool)
)

G1_MASTER["research_status"] = np.select(
    [
        ~G1_MASTER["research_ranking_eligible"],
        G1_MASTER["valuation_critical_block"].fillna(False).astype(bool),
        G1_MASTER["entry_eligible_now"],
    ],
    [
        "PROVISIONAL_BLOCKED",
        "VALUATION_CRITICAL_BLOCKED",
        "ENTRY_CANDIDATE",
    ],
    default="WATCHLIST",
)

# ==================================================================================================
# 11. RANK / PERCENTILE / LABEL
# ==================================================================================================

G1_MASTER["master_alpha_rank"] = np.nan

_eligible_alpha = (
    G1_MASTER[
        G1_MASTER["research_ranking_eligible"]
    ]
    .copy()
    .sort_values(
        ["master_alpha_score", "valuation_confidence"],
        ascending=[False, False],
    )
    .reset_index(drop=True)
)

_eligible_alpha["master_alpha_rank"] = np.arange(
    1,
    len(_eligible_alpha) + 1,
)

_rank_map = (
    _eligible_alpha
    .set_index("ticker")["master_alpha_rank"]
    .to_dict()
)

G1_MASTER["master_alpha_rank"] = (
    G1_MASTER["ticker"].map(_rank_map)
)

_percentile_map = (
    G1_MASTER[
        G1_MASTER["research_ranking_eligible"]
    ][["ticker", "master_alpha_score"]]
    .assign(
        master_alpha_percentile=lambda x:
            100.0
            * x["master_alpha_score"].rank(
                pct=True,
                method="average",
            )
    )
    .set_index("ticker")["master_alpha_percentile"]
    .to_dict()
)

G1_MASTER["master_alpha_percentile"] = (
    G1_MASTER["ticker"].map(_percentile_map)
)


def g1_alpha_status(score):
    if pd.isna(score):
        return "UNAVAILABLE"
    if score >= 1.00:
        return "STRONG_POSITIVE_ALPHA"
    if score >= 0.35:
        return "POSITIVE_ALPHA"
    if score > -0.35:
        return "NEUTRAL_ALPHA"
    if score > -1.00:
        return "NEGATIVE_ALPHA"
    return "STRONG_NEGATIVE_ALPHA"


G1_MASTER["master_alpha_status"] = (
    G1_MASTER["master_alpha_score"]
    .map(g1_alpha_status)
)

# ==================================================================================================
# 12. RESEARCH CONFIDENCE
# ==================================================================================================

G1_MASTER["research_confidence"] = np.sqrt(
    G1_MASTER["company_selection_confidence"].clip(0.0, 1.0)
    * pd.to_numeric(
        G1_MASTER["valuation_confidence"],
        errors="coerce",
    ).clip(0.0, 1.0)
)

G1_MASTER["confidence_adjusted_master_alpha"] = (
    G1_MASTER["master_alpha_score"]
    * G1_MASTER["research_confidence"]
)

# ==================================================================================================
# 13. OUTPUT BUCKETS
# ==================================================================================================

G1_ENTRY_CANDIDATES = (
    G1_MASTER[
        G1_MASTER["entry_eligible_now"]
    ]
    .copy()
    .sort_values(
        [
            "confidence_adjusted_master_alpha",
            "master_alpha_score",
        ],
        ascending=[False, False],
    )
    .reset_index(drop=True)
)

G1_ENTRY_CANDIDATES["entry_priority_rank"] = np.arange(
    1,
    len(G1_ENTRY_CANDIDATES) + 1,
)

G1_WATCHLIST = (
    G1_MASTER[
        G1_MASTER["research_status"] == "WATCHLIST"
    ]
    .copy()
    .sort_values(
        "master_alpha_score",
        ascending=False,
    )
    .reset_index(drop=True)
)

G1_PROVISIONAL = (
    G1_MASTER[
        G1_MASTER["research_status"] == "PROVISIONAL_BLOCKED"
    ]
    .copy()
    .sort_values("ticker")
    .reset_index(drop=True)
)

# ==================================================================================================
# 14. FINAL G1 HANDOFF
# ==================================================================================================

G1_FINAL_ALPHA_HANDOFF = (
    G1_MASTER[
        [
            "ticker",
            "company_name",
            "sector_ticker",
            "allocation_bucket",

            "raw_sector_score",
            "sector_signal",

            "raw_company_selection_input",
            "company_selection_signal",
            "company_selection_confidence",

            "current_price",
            "expected_intrinsic_value",
            "expected_upside_pct",
            "mos_price_threshold",
            "mos_threshold_met",

            "final_valuation_signal",
            "valuation_signal_normalized",
            "valuation_confidence",

            "sector_alpha_contribution",
            "company_alpha_contribution",
            "valuation_alpha_contribution",

            "master_alpha_score",
            "master_alpha_rank",
            "master_alpha_percentile",
            "master_alpha_status",

            "research_confidence",
            "confidence_adjusted_master_alpha",

            "research_ranking_eligible",
            "valuation_entry_eligible",
            "valuation_critical_block",
            "valuation_review_severity",
            "valuation_anomaly_reason",
            "entry_eligible_now",
            "research_status",

            "valuation_review_required",
            "specialist_completion_status",
        ]
    ]
    .copy()
)

# ==================================================================================================
# 15. HEALTH
# ==================================================================================================

G1_COMPANY_COUNT = len(G1_FINAL_ALPHA_HANDOFF)

G1_RANKING_ELIGIBLE_COUNT = int(
    G1_FINAL_ALPHA_HANDOFF["research_ranking_eligible"].sum()
)

G1_ENTRY_COUNT = int(
    G1_FINAL_ALPHA_HANDOFF["entry_eligible_now"].sum()
)

G1_PROVISIONAL_COUNT = len(G1_PROVISIONAL)

G1_FINITE_ALPHA_COUNT = int(
    safe_isfinite(
        G1_FINAL_ALPHA_HANDOFF["master_alpha_score"]
    ).sum()
)

G1_MOS_RULE_VALID = bool(
    G1_FINAL_ALPHA_HANDOFF.loc[
        G1_FINAL_ALPHA_HANDOFF["entry_eligible_now"],
        "mos_threshold_met",
    ]
    .fillna(False)
    .all()
)

G1_PROVISIONAL_ENTRY_VIOLATIONS = int(
    (
        G1_FINAL_ALPHA_HANDOFF["entry_eligible_now"]
        & ~G1_FINAL_ALPHA_HANDOFF["research_ranking_eligible"]
    ).sum()
)

G1_CRITICAL_ENTRY_VIOLATIONS = int(
    (
        G1_FINAL_ALPHA_HANDOFF["entry_eligible_now"]
        & G1_FINAL_ALPHA_HANDOFF["valuation_critical_block"].fillna(False).astype(bool)
    ).sum()
)

G1_ALPHA_RANK_UNIQUE = bool(
    G1_FINAL_ALPHA_HANDOFF.loc[
        G1_FINAL_ALPHA_HANDOFF["research_ranking_eligible"],
        "master_alpha_rank",
    ].nunique()
    == G1_RANKING_ELIGIBLE_COUNT
)

G1_HEALTH = pd.DataFrame(
    [
        {
            "check": "Frozen research universe preserved",
            "passed": G1_COMPANY_COUNT == G1_EXPECTED_COMPANY_COUNT,
            "required": True,
            "detail": f"companies={G1_COMPANY_COUNT}/{G1_EXPECTED_COMPANY_COUNT}",
        },
        {
            "check": "Canonical Section E7 company-selection source recovered",
            "passed": len(G1_COMPANY_INPUT) == G1_EXPECTED_COMPANY_COUNT,
            "required": True,
            "detail": (
                f"coverage={len(G1_COMPANY_INPUT)}/{G1_EXPECTED_COMPANY_COUNT}; "
                f"source={G1_E7_SOURCE_NAME}; "
                f"type={G1_E7_SOURCE_TYPE}; "
                "score=stock_selection_score_z"
            ),
        },
        {
            "check": "Section D6 sector-signal coverage is complete",
            "passed": G1_FINAL_ALPHA_HANDOFF["sector_signal"].notna().all(),
            "required": True,
            "detail": (
                f"source={G1_D_SOURCE_NAME}; "
                f"type={G1_D_SOURCE_TYPE}"
            ),
        },
        {
            "check": "Every company receives finite master alpha score",
            "passed": G1_FINITE_ALPHA_COUNT == G1_EXPECTED_COMPANY_COUNT,
            "required": True,
            "detail": f"coverage={G1_FINITE_ALPHA_COUNT}/{G1_EXPECTED_COMPANY_COUNT}",
        },
        {
            "check": "Research-ranking eligibility matches Section F governance",
            "passed": G1_RANKING_ELIGIBLE_COUNT == G1_EXPECTED_RANKING_COUNT,
            "required": True,
            "detail": f"eligible={G1_RANKING_ELIGIBLE_COUNT}/{G1_EXPECTED_RANKING_COUNT}",
        },
        {
            "check": "Section F provisional / blocked count is preserved",
            "passed": G1_PROVISIONAL_COUNT == G1_EXPECTED_PROVISIONAL_COUNT,
            "required": True,
            "detail": (
                f"provisional={G1_PROVISIONAL_COUNT}/"
                f"{G1_EXPECTED_PROVISIONAL_COUNT}"
            ),
        },
        {
            "check": "Entry eligibility obeys margin-of-safety rule",
            "passed": G1_MOS_RULE_VALID,
            "required": True,
            "detail": f"entry_candidates={G1_ENTRY_COUNT}",
        },
        {
            "check": "No provisional company is entry eligible",
            "passed": G1_PROVISIONAL_ENTRY_VIOLATIONS == 0,
            "required": True,
            "detail": (
                f"violations={G1_PROVISIONAL_ENTRY_VIOLATIONS}"
            ),
        },
        {
            "check": "No critical valuation anomaly is entry eligible",
            "passed": G1_CRITICAL_ENTRY_VIOLATIONS == 0,
            "required": True,
            "detail": (
                f"violations={G1_CRITICAL_ENTRY_VIOLATIONS}"
            ),
        },
        {
            "check": "Eligible master-alpha ranks are unique",
            "passed": G1_ALPHA_RANK_UNIQUE,
            "required": True,
            "detail": (
                f"unique_ranks={G1_RANKING_ELIGIBLE_COUNT}"
            ),
        },
        {
            "check": "Historical stock-selection backtest remains blocked",
            "passed": True,
            "required": True,
            "detail": (
                "current membership / valuation stack is not PIT-ready"
            ),
        },
    ]
)

G1_HEALTH["status"] = np.where(
    G1_HEALTH["passed"],
    "✓ PASS",
    "✗ FAIL",
)

G1_REQUIRED_FAILURES = G1_HEALTH[
    G1_HEALTH["required"]
    & ~G1_HEALTH["passed"]
]

G1_PASSED = G1_REQUIRED_FAILURES.empty

# ==================================================================================================
# 16. HASH / SUMMARY / SAVE
# ==================================================================================================

_G1_HASH_FRAME = (
    G1_FINAL_ALPHA_HANDOFF[
        [
            "ticker",
            "sector_signal",
            "company_selection_signal",
            "valuation_signal_normalized",
            "master_alpha_score",
            "research_confidence",
            "confidence_adjusted_master_alpha",
            "research_ranking_eligible",
            "entry_eligible_now",
        ]
    ]
    .sort_values("ticker")
    .reset_index(drop=True)
)

G1_ALPHA_SHA256 = hashlib.sha256(
    pd.util.hash_pandas_object(
        _G1_HASH_FRAME,
        index=False,
    )
    .values
    .tobytes()
).hexdigest()

G1_SUMMARY = pd.DataFrame(
    [
        {
            "g1_version": G1_VERSION,
            "valuation_universe_freeze_id": VALUATION_UNIVERSE_FREEZE_ID,
            "alpha_sha256": G1_ALPHA_SHA256,
            "companies": G1_COMPANY_COUNT,
            "research_ranking_eligible": G1_RANKING_ELIGIBLE_COUNT,
            "entry_candidates_now": G1_ENTRY_COUNT,
            "watchlist": len(G1_WATCHLIST),
            "provisional_blocked": G1_PROVISIONAL_COUNT,
            "core_long_count": int(
                (
                    G1_FINAL_ALPHA_HANDOFF["allocation_bucket"]
                    == "CORE_LONG"
                ).sum()
            ),
            "tactical_long_count": int(
                (
                    G1_FINAL_ALPHA_HANDOFF["allocation_bucket"]
                    == "TACTICAL_LONG"
                ).sum()
            ),
            "sector_weight": G1_SECTOR_WEIGHT,
            "company_weight": G1_COMPANY_WEIGHT,
            "valuation_weight": G1_VALUATION_WEIGHT,
            "e7_source": G1_E7_SOURCE_NAME,
            "e7_source_type": G1_E7_SOURCE_TYPE,
            "sector_source": G1_D_SOURCE_NAME,
            "sector_source_type": G1_D_SOURCE_TYPE,
            "historical_backtest_eligible": False,
            "g1_passed": G1_PASSED,
        }
    ]
)

G1_FINAL_ALPHA_HANDOFF.to_parquet(
    Path(STOCK_MODEL_DIR) / "g1_master_alpha_handoff.parquet",
    index=False,
)

G1_ENTRY_CANDIDATES.to_parquet(
    Path(STOCK_MODEL_DIR) / "g1_entry_candidates.parquet",
    index=False,
)

G1_FINAL_ALPHA_HANDOFF.to_csv(
    Path(STOCK_OUTPUT_DIR) / "g1_master_alpha_handoff.csv",
    index=False,
)

G1_ENTRY_CANDIDATES.to_csv(
    Path(STOCK_OUTPUT_DIR) / "g1_entry_candidates.csv",
    index=False,
)

G1_WATCHLIST.to_csv(
    Path(STOCK_OUTPUT_DIR) / "g1_watchlist.csv",
    index=False,
)

G1_PROVISIONAL.to_csv(
    Path(STOCK_OUTPUT_DIR) / "g1_provisional_blocked.csv",
    index=False,
)

G1_HEALTH.to_csv(
    Path(STOCK_OUTPUT_DIR) / "g1_health.csv",
    index=False,
)

G1_SUMMARY.to_csv(
    Path(STOCK_OUTPUT_DIR) / "g1_summary.csv",
    index=False,
)

# ==================================================================================================
# 17. DISPLAY / PRODUCTION GATE
# ==================================================================================================

print("=" * 145)
print("G1 — REGIME × COMPANY × VALUATION MASTER SIGNAL V1.3.0")
print("=" * 145)

print(f"E7 source:                        {G1_E7_SOURCE_NAME} ({G1_E7_SOURCE_TYPE})")
print(f"Sector source:                    {G1_D_SOURCE_NAME} ({G1_D_SOURCE_TYPE})")
print(f"Companies:                        {G1_COMPANY_COUNT}")
print(f"Research-ranking eligible:        {G1_RANKING_ELIGIBLE_COUNT}")
print(f"Entry candidates now:             {G1_ENTRY_COUNT}")
print(f"Watchlist:                        {len(G1_WATCHLIST)}")
print(f"Provisional / blocked:            {G1_PROVISIONAL_COUNT}")
print(f"Master alpha SHA256:              {G1_ALPHA_SHA256}")

print("\nMASTER research-alpha ranking:")

display(
    G1_FINAL_ALPHA_HANDOFF[
        G1_FINAL_ALPHA_HANDOFF["research_ranking_eligible"]
    ][
        [
            "master_alpha_rank",
            "ticker",
            "company_name",
            "sector_ticker",
            "allocation_bucket",
            "sector_signal",
            "company_selection_signal",
            "valuation_signal_normalized",
            "sector_alpha_contribution",
            "company_alpha_contribution",
            "valuation_alpha_contribution",
            "master_alpha_score",
            "research_confidence",
            "confidence_adjusted_master_alpha",
            "master_alpha_percentile",
            "master_alpha_status",
            "mos_threshold_met",
            "research_status",
        ]
    ]
    .sort_values("master_alpha_rank")
)

print(f"\nENTRY candidates — ranking eligible AND current MOS policy satisfied (base={float(cfg(['valuation', 'mos_base'], 0.15)):.0%}):")

if G1_ENTRY_CANDIDATES.empty:
    print("None.")
else:
    display(
        G1_ENTRY_CANDIDATES[
            [
                "entry_priority_rank",
                "ticker",
                "company_name",
                "sector_ticker",
                "allocation_bucket",
                "current_price",
                "expected_intrinsic_value",
                "mos_price_threshold",
                "master_alpha_rank",
                "master_alpha_score",
                "research_confidence",
                "confidence_adjusted_master_alpha",
                "valuation_review_required",
            ]
        ]
    )

print("\nHighest-ranked WATCHLIST names:")

display(
    G1_WATCHLIST[
        [
            "master_alpha_rank",
            "ticker",
            "company_name",
            "sector_ticker",
            "master_alpha_score",
            "research_confidence",
            "confidence_adjusted_master_alpha",
            "current_price",
            "mos_price_threshold",
        ]
    ].head(15)
)

print("\nG1 health:")
display(G1_HEALTH)

print("\nG1 summary:")
display(G1_SUMMARY)

if not G1_PASSED:
    display(G1_REQUIRED_FAILURES)
    raise RuntimeError(
        "G1 PRODUCTION GATE FAILED. "
        "Do not build expected returns yet."
    )

print("\n" + "=" * 145)
print("✓ G1 COMPLETE — macro, company selection, and valuation integrated.")
print("✓ Canonical E7 stock_selection_score_z is used.")
print("✓ E7 and D6 can be recovered from saved artifacts after a runtime restart.")
print("✓ Section D sector signal receives 30% weight.")
print(f"✓ Section E7 company-selection signal receives {G1_COMPANY_WEIGHT:.0%} weight.")
print(f"✓ Section F valuation signal receives {G1_VALUATION_WEIGHT:.0%} weight.")
print("✓ MOS and critical valuation-model-risk gates are enforced separately from research ranking.")
print(f"✓ {G1_PROVISIONAL_COUNT} provisional / non-rankable names remain blocked from research ranking.")
print("✓ G1_FINAL_ALPHA_HANDOFF is the master stock-selection object for G2.")
print("=" * 145)


# ===== ORIGINAL NOTEBOOK CELL 80 =====
# ==================================================================================================
# SECTION G — STOCK ALPHA INTEGRATION ENGINE
# CELL G2 — POLICY-CALIBRATED ANNUALIZED EXPECTED RETURN ENGINE V1.0.0
# ==================================================================================================
#
# PURPOSE
# -------
#
# Translate the stock-selection signal from G1 into an annualized
# expected EQUITY return usable by the later portfolio optimizer.
#
#
# IMPORTANT GOVERNANCE
# --------------------
#
# We DO NOT yet have a valid historical PIT stock-selection backtest.
#
# Therefore G2 DOES NOT estimate:
#
#       realized IC
#       signal-return regression
#       historical alpha coefficient
#
# from the current notebook.
#
#
# Instead, G2 uses:
#
#       Expected equity return
#
#           =
#           CAPM required equity return
#           +
#           conservative policy-calibrated alpha overlay
#
#
# CAPM baseline:
#
#       Ke_i = Rf + Beta_i × ERP
#
#
# Alpha overlay:
#
#       Alpha_i
#           =
#           5% × confidence-adjusted master alpha
#
# bounded to:
#
#       [-10%, +10%] annually
#
#
# The mapping is intentionally conservative and EXPLICITLY labeled
# POLICY_CALIBRATED rather than empirically fitted.
#
#
# OUTPUTS
# -------
#
# For each stock:
#
#       cost_of_equity
#       CAPM market-required return
#       annualized alpha overlay
#       annualized total expected return
#       active expected return vs SPY
#       entry / watchlist / provisional governance
#
#
# G2 does NOT:
#
#       calculate covariance
#       optimize weights
#       override MOS
#       change valuation
#       change G1 ranking
#
#
# Next:
#
#       G3 = covariance / stock risk model
# ==================================================================================================


# ==================================================================================================
# 1. IMPORTS
# ==================================================================================================

from pathlib import Path

import hashlib

import numpy as np
import pandas as pd


# ==================================================================================================
# 2. VALIDATE UPSTREAM
# ==================================================================================================

required_g2_objects = [

    "G1_PASSED",
    "G1_FINAL_ALPHA_HANDOFF",

    "F4C_MANIFEST",

    "F4_RISK_FREE_RATE",
    "F4_EQUITY_RISK_PREMIUM",

    "VALUATION_UNIVERSE_FREEZE_ID",

    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",

]


missing_g2_objects = [

    obj

    for obj in required_g2_objects

    if obj not in globals()

]


if missing_g2_objects:

    raise RuntimeError(

        "G2 requires completed G1/F4 objects. Missing: "
        f"{missing_g2_objects}"

    )


if not bool(
    G1_PASSED
):

    raise RuntimeError(

        "G1 production gate did not pass."

    )


# ==================================================================================================
# 3. VERSION
# ==================================================================================================

G2_VERSION = "1.0.0"


# ==================================================================================================
# 4. POLICY-CALIBRATION PARAMETERS
# ==================================================================================================
#
# A +1.0 confidence-adjusted G1 signal receives +5% annual alpha.
#
# Example:
#
#       +0.80 signal -> +4.0% expected annual alpha
#       -0.60 signal -> -3.0% expected annual alpha
#
# Alpha is capped at +/-10%.
# ==================================================================================================

G2_ALPHA_RETURN_PER_SIGNAL = float(cfg(["alpha", "alpha_return_per_signal"], 0.05))

G2_MAX_ABS_ANNUAL_ALPHA = float(cfg(["alpha", "max_abs_annual_alpha"], 0.10))


# ------------------------------------------------------------
# Sanity bounds for expected TOTAL equity return.
#
# These are diagnostic policy bounds, not optimization bounds.
# ------------------------------------------------------------

G2_MIN_REASONABLE_EXPECTED_RETURN = float(cfg(["alpha", "min_reasonable_expected_return"], -0.10))

G2_MAX_REASONABLE_EXPECTED_RETURN = float(cfg(["alpha", "max_reasonable_expected_return"], 0.35))


# ==================================================================================================
# 5. GLOBAL MARKET ASSUMPTIONS
# ==================================================================================================

G2_RISK_FREE_RATE = float(

    F4_RISK_FREE_RATE

)


G2_EQUITY_RISK_PREMIUM = float(

    F4_EQUITY_RISK_PREMIUM

)


G2_MARKET_EXPECTED_RETURN = (

    G2_RISK_FREE_RATE

    +

    G2_EQUITY_RISK_PREMIUM

)


if not (

    0.0
    <=
    G2_RISK_FREE_RATE
    <=
    0.15

):

    raise RuntimeError(

        f"Invalid G2 risk-free rate: "
        f"{G2_RISK_FREE_RATE:.3%}"

    )


if not (

    0.0
    <
    G2_EQUITY_RISK_PREMIUM
    <=
    0.15

):

    raise RuntimeError(

        f"Invalid G2 ERP: "
        f"{G2_EQUITY_RISK_PREMIUM:.3%}"

    )


# ==================================================================================================
# 6. WORKING UNIVERSE
# ==================================================================================================

G2_ALPHA = (

    G1_FINAL_ALPHA_HANDOFF
    .copy()

)


G2_ALPHA[
    "ticker"
] = (

    G2_ALPHA[
        "ticker"
    ]
    .astype(str)

)


G2_EXPECTED_COMPANY_COUNT = len(

    G2_ALPHA

)


G2_EXPECTED_RANKING_COUNT = int(

    G2_ALPHA[
        "research_ranking_eligible"
    ]
    .fillna(False)
    .sum()

)


G2_EXPECTED_ENTRY_COUNT = int(

    G2_ALPHA[
        "entry_eligible_now"
    ]
    .fillna(False)
    .sum()

)


# ==================================================================================================
# 7. COST-OF-EQUITY INPUT FROM F4C
# ==================================================================================================

required_cost_columns = [

    "ticker",
    "valuation_beta",
    "cost_of_equity",

]


missing_cost_columns = [

    column

    for column
    in required_cost_columns

    if column not in F4C_MANIFEST.columns

]


if missing_cost_columns:

    raise RuntimeError(

        "F4C_MANIFEST is missing G2 cost-of-equity fields: "
        f"{missing_cost_columns}"

    )


G2_COST_INPUT = (

    F4C_MANIFEST[
        [
            column

            for column in [

                "ticker",

                "valuation_beta",
                "cost_of_equity",

                "beta_estimation_confidence",
                "discount_rate_confidence",

                "discount_rate_type",
                "discount_rate",

            ]

            if column in F4C_MANIFEST.columns

        ]
    ]

    .copy()

    .drop_duplicates(
        subset=[
            "ticker"
        ]
    )

)


G2_COST_INPUT[
    "ticker"
] = (

    G2_COST_INPUT[
        "ticker"
    ]
    .astype(str)

)


# ==================================================================================================
# 8. MERGE COST-OF-EQUITY INPUT
# ==================================================================================================

G2_EXPECTED_RETURNS = (

    G2_ALPHA

    .merge(

        G2_COST_INPUT,

        on="ticker",

        how="left",

        validate="one_to_one",

    )

)


# ==================================================================================================
# 9. NUMERIC NORMALIZATION
# ==================================================================================================

for column in [

    "valuation_beta",
    "cost_of_equity",

    "confidence_adjusted_master_alpha",
    "master_alpha_score",

    "research_confidence",
    "valuation_confidence",

]:

    if column in G2_EXPECTED_RETURNS.columns:

        G2_EXPECTED_RETURNS[
            column
        ] = pd.to_numeric(

            G2_EXPECTED_RETURNS[
                column
            ],

            errors="coerce",

        )


# ==================================================================================================
# 10. CAPM REQUIRED EQUITY RETURN — INDEPENDENT RECOMPUTATION
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "capm_required_return"
] = (

    G2_RISK_FREE_RATE

    +

    G2_EXPECTED_RETURNS[
        "valuation_beta"
    ]

    *
    G2_EQUITY_RISK_PREMIUM

)


# ==================================================================================================
# 11. VERIFY F4 COST-OF-EQUITY IDENTITY
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "cost_of_equity_reproduction_error"
] = (

    G2_EXPECTED_RETURNS[
        "cost_of_equity"
    ]

    -

    G2_EXPECTED_RETURNS[
        "capm_required_return"
    ]

)


G2_EXPECTED_RETURNS[
    "cost_of_equity_reproduction_valid"
] = (

    G2_EXPECTED_RETURNS[
        "cost_of_equity_reproduction_error"
    ]
    .abs()

    <=
    1e-10

)


# ==================================================================================================
# 12. POLICY-CALIBRATED ANNUAL ALPHA
# ==================================================================================================
#
# G1 already confidence-adjusted the master signal using:
#
#       research confidence
#
# Therefore we do NOT multiply by confidence again here.
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "raw_annual_alpha_overlay"
] = (

    G2_ALPHA_RETURN_PER_SIGNAL

    *
    G2_EXPECTED_RETURNS[
        "confidence_adjusted_master_alpha"
    ]

)


G2_EXPECTED_RETURNS[
    "annual_alpha_overlay"
] = (

    G2_EXPECTED_RETURNS[
        "raw_annual_alpha_overlay"
    ]

    .clip(

        lower=
            -G2_MAX_ABS_ANNUAL_ALPHA,

        upper=
            G2_MAX_ABS_ANNUAL_ALPHA,

    )

)


# ==================================================================================================
# 13. ALPHA CAP DIAGNOSTIC
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "alpha_overlay_capped"
] = (

    ~

    np.isclose(

        G2_EXPECTED_RETURNS[
            "raw_annual_alpha_overlay"
        ],

        G2_EXPECTED_RETURNS[
            "annual_alpha_overlay"
        ],

        rtol=1e-12,
        atol=1e-12,

    )

)


# ==================================================================================================
# 14. FINAL ANNUALIZED EXPECTED TOTAL RETURN
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "expected_total_return_annual"
] = (

    G2_EXPECTED_RETURNS[
        "capm_required_return"
    ]

    +

    G2_EXPECTED_RETURNS[
        "annual_alpha_overlay"
    ]

)


# ==================================================================================================
# 15. EXPECTED ACTIVE RETURN VS MARKET
# ==================================================================================================
#
# Market expected return:
#
#       Rf + ERP
#
#
# Therefore:
#
#       stock expected return - market expected return
#
#       =
#
#       (beta - 1) * ERP
#       +
#       stock alpha
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "expected_active_return_vs_market"
] = (

    G2_EXPECTED_RETURNS[
        "expected_total_return_annual"
    ]

    -
    G2_MARKET_EXPECTED_RETURN

)


G2_EXPECTED_RETURNS[
    "systematic_active_return_component"
] = (

    (

        G2_EXPECTED_RETURNS[
            "valuation_beta"
        ]

        -
        1.0

    )

    *
    G2_EQUITY_RISK_PREMIUM

)


G2_EXPECTED_RETURNS[
    "alpha_active_return_component"
] = (

    G2_EXPECTED_RETURNS[
        "annual_alpha_overlay"
    ]

)


# ==================================================================================================
# 16. EXPECTED EXCESS RETURN OVER CASH
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "expected_excess_return_over_cash"
] = (

    G2_EXPECTED_RETURNS[
        "expected_total_return_annual"
    ]

    -
    G2_RISK_FREE_RATE

)


# ==================================================================================================
# 17. SIGNAL CONTRIBUTION IN RETURN UNITS
# ==================================================================================================
#
# Translate each G1 research pillar into annual alpha units
# without changing the total master-alpha methodology.
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "sector_alpha_return_contribution"
] = (

    G2_ALPHA_RETURN_PER_SIGNAL

    *
    G2_EXPECTED_RETURNS[
        "sector_alpha_contribution"
    ]

    *
    G2_EXPECTED_RETURNS[
        "research_confidence"
    ]

)


G2_EXPECTED_RETURNS[
    "company_alpha_return_contribution"
] = (

    G2_ALPHA_RETURN_PER_SIGNAL

    *
    G2_EXPECTED_RETURNS[
        "company_alpha_contribution"
    ]

    *
    G2_EXPECTED_RETURNS[
        "research_confidence"
    ]

)


G2_EXPECTED_RETURNS[
    "valuation_alpha_return_contribution"
] = (

    G2_ALPHA_RETURN_PER_SIGNAL

    *
    G2_EXPECTED_RETURNS[
        "valuation_alpha_contribution"
    ]

    *
    G2_EXPECTED_RETURNS[
        "research_confidence"
    ]

)


# ==================================================================================================
# 18. RETURN ATTRIBUTION RECONCILIATION
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "reconstructed_alpha_overlay"
] = (

    G2_EXPECTED_RETURNS[
        "sector_alpha_return_contribution"
    ]

    +

    G2_EXPECTED_RETURNS[
        "company_alpha_return_contribution"
    ]

    +

    G2_EXPECTED_RETURNS[
        "valuation_alpha_return_contribution"
    ]

)


G2_EXPECTED_RETURNS[
    "alpha_attribution_error"
] = (

    G2_EXPECTED_RETURNS[
        "annual_alpha_overlay"
    ]

    -
    G2_EXPECTED_RETURNS[
        "reconstructed_alpha_overlay"
    ]

)


# ==================================================================================================
# 19. EXPECTED-RETURN CONFIDENCE
# ==================================================================================================
#
# Research confidence carries:
#
#       company-selection confidence
#       valuation confidence
#
# Cost-of-capital confidence is included if available.
# ==================================================================================================

if (

    "discount_rate_confidence"
    in
    G2_EXPECTED_RETURNS.columns

):

    cost_confidence = (

        pd.to_numeric(

            G2_EXPECTED_RETURNS[
                "discount_rate_confidence"
            ],

            errors="coerce",

        )

        .clip(
            lower=0.0,
            upper=1.0,
        )

        .fillna(
            1.0
        )

    )


else:

    cost_confidence = pd.Series(

        1.0,

        index=
            G2_EXPECTED_RETURNS.index,

    )


G2_EXPECTED_RETURNS[
    "expected_return_confidence"
] = np.sqrt(

    G2_EXPECTED_RETURNS[
        "research_confidence"
    ]

    *
    cost_confidence

)


# ==================================================================================================
# 20. POLICY-CALIBRATION LABEL
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "expected_return_method"
] = (

    "CAPM_BASELINE_PLUS_POLICY_ALPHA"

)


G2_EXPECTED_RETURNS[
    "alpha_calibration_type"
] = (

    "POLICY_CALIBRATED_NOT_PIT_BACKTESTED"

)


# ==================================================================================================
# 21. CURRENT OPTIMIZATION ELIGIBILITY
# ==================================================================================================
#
# This preserves the current CONFIG-driven MOS rule from G1.
#
# WATCHLIST names still receive expected returns because:
#
#       - we may need them for monitoring
#       - existing holdings may later require hold/sell decisions
#
# But they are NOT new-entry candidates today.
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "new_entry_optimizer_eligible"
] = (

    G2_EXPECTED_RETURNS[
        "entry_eligible_now"
    ]
    .fillna(False)
    .astype(bool)

)


G2_EXPECTED_RETURNS[
    "research_optimizer_eligible"
] = (

    G2_EXPECTED_RETURNS[
        "research_ranking_eligible"
    ]
    .fillna(False)
    .astype(bool)

)


# ==================================================================================================
# 22. EXPECTED-RETURN SANITY FLAG
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "expected_return_outside_policy_range"
] = (

    (

        G2_EXPECTED_RETURNS[
            "expected_total_return_annual"
        ]

        <
        G2_MIN_REASONABLE_EXPECTED_RETURN

    )

    |

    (

        G2_EXPECTED_RETURNS[
            "expected_total_return_annual"
        ]

        >
        G2_MAX_REASONABLE_EXPECTED_RETURN

    )

)


# ==================================================================================================
# 23. EXPECTED-RETURN STATUS
# ==================================================================================================

def g2_return_status(
    active_return
):

    if pd.isna(
        active_return
    ):

        return "UNAVAILABLE"


    if active_return >= 0.05:

        return (
            "STRONG_POSITIVE_ACTIVE_RETURN"
        )


    if active_return >= 0.015:

        return (
            "POSITIVE_ACTIVE_RETURN"
        )


    if active_return > -0.015:

        return (
            "NEAR_MARKET_EXPECTED_RETURN"
        )


    if active_return > -0.05:

        return (
            "NEGATIVE_ACTIVE_RETURN"
        )


    return (
        "STRONG_NEGATIVE_ACTIVE_RETURN"
    )


G2_EXPECTED_RETURNS[
    "expected_return_status"
] = (

    G2_EXPECTED_RETURNS[
        "expected_active_return_vs_market"
    ]

    .map(
        g2_return_status
    )

)


# ==================================================================================================
# 24. EXPECTED-RETURN RANK
# ==================================================================================================

G2_EXPECTED_RETURNS[
    "expected_return_rank"
] = np.nan


rankable_return_table = (

    G2_EXPECTED_RETURNS[

        G2_EXPECTED_RETURNS[
            "research_optimizer_eligible"
        ]

    ]

    .copy()

    .sort_values(

        [
            "expected_total_return_annual",
            "expected_return_confidence",
        ],

        ascending=[
            False,
            False,
        ],

    )

    .reset_index(
        drop=True
    )

)


rankable_return_table[
    "expected_return_rank"
] = np.arange(

    1,

    len(
        rankable_return_table
    )
    +
    1,

)


return_rank_map = (

    rankable_return_table

    .set_index(
        "ticker"
    )[
        "expected_return_rank"
    ]

    .to_dict()

)


G2_EXPECTED_RETURNS[
    "expected_return_rank"
] = (

    G2_EXPECTED_RETURNS[
        "ticker"
    ]

    .map(
        return_rank_map
    )

)


# ==================================================================================================
# 25. OPTIMIZER EXPECTED-RETURN HANDOFF
# ==================================================================================================

G2_OPTIMIZER_EXPECTED_RETURNS = (

    G2_EXPECTED_RETURNS[
        [
            "ticker",
            "company_name",

            "sector_ticker",
            "allocation_bucket",

            "valuation_beta",

            "cost_of_equity",
            "capm_required_return",

            "annual_alpha_overlay",

            "expected_total_return_annual",

            "expected_excess_return_over_cash",

            "expected_active_return_vs_market",

            "expected_return_confidence",

            "expected_return_rank",
            "expected_return_status",

            "research_optimizer_eligible",
            "new_entry_optimizer_eligible",

            "research_status",

            "mos_threshold_met",

            "valuation_review_required",

            "specialist_completion_status",
        ]
    ]

    .copy()

)


# ==================================================================================================
# 26. CURRENT NEW-ENTRY TABLE
# ==================================================================================================

G2_CURRENT_ENTRY_RETURNS = (

    G2_OPTIMIZER_EXPECTED_RETURNS[

        G2_OPTIMIZER_EXPECTED_RETURNS[
            "new_entry_optimizer_eligible"
        ]

    ]

    .copy()

    .sort_values(

        "expected_total_return_annual",

        ascending=False,

    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# 27. HEALTH CHECKS
# ==================================================================================================

G2_COMPANY_COUNT = len(

    G2_EXPECTED_RETURNS

)


G2_COST_COVERAGE_COUNT = int(

    (

        G2_EXPECTED_RETURNS[
            "valuation_beta"
        ]
        .notna()

        &

        G2_EXPECTED_RETURNS[
            "cost_of_equity"
        ]
        .notna()

    )
    .sum()

)


G2_EXPECTED_RETURN_FINITE_COUNT = int(

    safe_isfinite(

        G2_EXPECTED_RETURNS[
            "expected_total_return_annual"
        ]

    )
    .sum()

)


G2_CAPM_IDENTITY_VALID = bool(

    G2_EXPECTED_RETURNS[
        "cost_of_equity_reproduction_valid"
    ]
    .all()

)


G2_ALPHA_BOUND_VALID = bool(

    (

        G2_EXPECTED_RETURNS[
            "annual_alpha_overlay"
        ]
        .abs()

        <=

        G2_MAX_ABS_ANNUAL_ALPHA
        +
        1e-12

    )
    .all()

)


G2_PROVISIONAL_ENTRY_VIOLATIONS = int(

    (

        G2_EXPECTED_RETURNS[
            "new_entry_optimizer_eligible"
        ]

        &

        ~
        G2_EXPECTED_RETURNS[
            "research_optimizer_eligible"
        ]

    )
    .sum()

)


G2_ENTRY_COUNT = int(

    G2_EXPECTED_RETURNS[
        "new_entry_optimizer_eligible"
    ]
    .sum()

)


G2_OUTSIDE_POLICY_RANGE_COUNT = int(

    G2_EXPECTED_RETURNS[
        "expected_return_outside_policy_range"
    ]
    .sum()

)


# ==================================================================================================
# 28. HEALTH TABLE
# ==================================================================================================

G2_HEALTH = pd.DataFrame([

    {

        "check":
            "G1 frozen company universe preserved",

        "passed":
            G2_COMPANY_COUNT
            ==
            G2_EXPECTED_COMPANY_COUNT,

        "required":
            True,

        "detail":
            (
                f"companies="
                f"{G2_COMPANY_COUNT}/"
                f"{G2_EXPECTED_COMPANY_COUNT}"
            ),

    },

    {

        "check":
            "F4 equity beta / cost-of-equity coverage is complete",

        "passed":
            G2_COST_COVERAGE_COUNT
            ==
            G2_EXPECTED_COMPANY_COUNT,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{G2_COST_COVERAGE_COUNT}/"
                f"{G2_EXPECTED_COMPANY_COUNT}"
            ),

    },

    {

        "check":
            "F4 cost of equity exactly reproduces CAPM identity",

        "passed":
            G2_CAPM_IDENTITY_VALID,

        "required":
            True,

        "detail":
            (
                f"Rf={G2_RISK_FREE_RATE:.3%}, "
                f"ERP={G2_EQUITY_RISK_PREMIUM:.3%}"
            ),

    },

    {

        "check":
            "Every company receives finite annual expected return",

        "passed":
            G2_EXPECTED_RETURN_FINITE_COUNT
            ==
            G2_EXPECTED_COMPANY_COUNT,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{G2_EXPECTED_RETURN_FINITE_COUNT}/"
                f"{G2_EXPECTED_COMPANY_COUNT}"
            ),

    },

    {

        "check":
            "Policy-calibrated annual alpha obeys hard bounds",

        "passed":
            G2_ALPHA_BOUND_VALID,

        "required":
            True,

        "detail":
            (
                f"bound=+/-"
                f"{G2_MAX_ABS_ANNUAL_ALPHA:.1%}"
            ),

    },

    {

        "check":
            "Research-ranking eligibility remains unchanged",

        "passed":
            int(

                G2_EXPECTED_RETURNS[
                    "research_optimizer_eligible"
                ]
                .sum()

            )
            ==
            G2_EXPECTED_RANKING_COUNT,

        "required":
            True,

        "detail":
            (
                f"eligible="
                f"{int(G2_EXPECTED_RETURNS['research_optimizer_eligible'].sum())}/"
                f"{G2_EXPECTED_RANKING_COUNT}"
            ),

    },

    {

        "check":
            "New-entry eligibility remains exactly the G1 MOS set",

        "passed":
            G2_ENTRY_COUNT
            ==
            G2_EXPECTED_ENTRY_COUNT,

        "required":
            True,

        "detail":
            (
                f"entry_candidates="
                f"{G2_ENTRY_COUNT}/"
                f"{G2_EXPECTED_ENTRY_COUNT}"
            ),

    },

    {

        "check":
            "No provisional company becomes optimizer entry eligible",

        "passed":
            G2_PROVISIONAL_ENTRY_VIOLATIONS
            ==
            0,

        "required":
            True,

        "detail":
            (
                f"violations="
                f"{G2_PROVISIONAL_ENTRY_VIOLATIONS}"
            ),

    },

    {

        "check":
            "Expected returns outside policy sanity range disclosed",

        "passed":
            True,

        "required":
            False,

        "detail":
            (
                f"outside "
                f"[{G2_MIN_REASONABLE_EXPECTED_RETURN:.0%}, "
                f"{G2_MAX_REASONABLE_EXPECTED_RETURN:.0%}]="
                f"{G2_OUTSIDE_POLICY_RANGE_COUNT}"
            ),

    },

    {

        "check":
            "Expected-return calibration explicitly remains non-backtested",

        "passed":
            True,

        "required":
            True,

        "detail":
            "POLICY_CALIBRATED_NOT_PIT_BACKTESTED",

    },

])


G2_HEALTH[
    "status"
] = np.where(

    G2_HEALTH[
        "passed"
    ],

    "✓ PASS",

    np.where(

        G2_HEALTH[
            "required"
        ],

        "✗ FAIL",

        "⚠ WARN",

    )

)


G2_REQUIRED_FAILURES = (

    G2_HEALTH[

        G2_HEALTH[
            "required"
        ]

        &

        ~
        G2_HEALTH[
            "passed"
        ]

    ]

)


G2_PASSED = (

    G2_REQUIRED_FAILURES.empty

)


# ==================================================================================================
# 29. HASH
# ==================================================================================================

G2_HASH_FRAME = (

    G2_OPTIMIZER_EXPECTED_RETURNS[
        [
            "ticker",

            "valuation_beta",

            "capm_required_return",

            "annual_alpha_overlay",

            "expected_total_return_annual",

            "expected_active_return_vs_market",

            "expected_return_confidence",

            "research_optimizer_eligible",

            "new_entry_optimizer_eligible",
        ]
    ]

    .copy()

    .sort_values(
        "ticker"
    )

    .reset_index(
        drop=True
    )

)


G2_EXPECTED_RETURN_SHA256 = (

    hashlib.sha256(

        pd.util.hash_pandas_object(

            G2_HASH_FRAME,
            index=False,

        )
        .values
        .tobytes()

    )

    .hexdigest()

)


# ==================================================================================================
# 30. SUMMARY
# ==================================================================================================

G2_SUMMARY = pd.DataFrame([{

    "g2_version":
        G2_VERSION,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "expected_return_sha256":
        G2_EXPECTED_RETURN_SHA256,

    "companies":
        G2_COMPANY_COUNT,

    "research_optimizer_eligible":
        int(

            G2_EXPECTED_RETURNS[
                "research_optimizer_eligible"
            ]
            .sum()

        ),

    "new_entry_optimizer_eligible":
        G2_ENTRY_COUNT,

    "risk_free_rate":
        G2_RISK_FREE_RATE,

    "equity_risk_premium":
        G2_EQUITY_RISK_PREMIUM,

    "market_expected_return":
        G2_MARKET_EXPECTED_RETURN,

    "alpha_return_per_signal":
        G2_ALPHA_RETURN_PER_SIGNAL,

    "maximum_absolute_alpha":
        G2_MAX_ABS_ANNUAL_ALPHA,

    "mean_expected_return":
        float(

            G2_EXPECTED_RETURNS.loc[

                G2_EXPECTED_RETURNS[
                    "research_optimizer_eligible"
                ],

                "expected_total_return_annual",

            ]
            .mean()

        ),

    "median_expected_return":
        float(

            G2_EXPECTED_RETURNS.loc[

                G2_EXPECTED_RETURNS[
                    "research_optimizer_eligible"
                ],

                "expected_total_return_annual",

            ]
            .median()

        ),

    "mean_expected_active_return_vs_market":
        float(

            G2_EXPECTED_RETURNS.loc[

                G2_EXPECTED_RETURNS[
                    "research_optimizer_eligible"
                ],

                "expected_active_return_vs_market",

            ]
            .mean()

        ),

    "alpha_overlay_cap_hits":
        int(

            G2_EXPECTED_RETURNS[
                "alpha_overlay_capped"
            ]
            .sum()

        ),

    "historical_backtest_eligible":
        False,

    "g2_passed":
        G2_PASSED,

}])


# ==================================================================================================
# 31. SAVE
# ==================================================================================================

G2_EXPECTED_RETURNS.to_parquet(

    STOCK_MODEL_DIR
    /
    "g2_expected_returns_full.parquet",

    index=False,

)


G2_OPTIMIZER_EXPECTED_RETURNS.to_parquet(

    STOCK_MODEL_DIR
    /
    "g2_optimizer_expected_returns.parquet",

    index=False,

)


G2_EXPECTED_RETURNS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g2_expected_returns_full.csv",

    index=False,

)


G2_OPTIMIZER_EXPECTED_RETURNS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g2_optimizer_expected_returns.csv",

    index=False,

)


G2_CURRENT_ENTRY_RETURNS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g2_current_entry_expected_returns.csv",

    index=False,

)


G2_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g2_health.csv",

    index=False,

)


G2_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g2_summary.csv",

    index=False,

)


# ==================================================================================================
# 32. DISPLAY HEADER
# ==================================================================================================

print(
    "=" * 145
)

print(
    "G2 — POLICY-CALIBRATED ANNUALIZED EXPECTED RETURN ENGINE V1.0.0"
)

print(
    "=" * 145
)


print(
    f"Companies:                         "
    f"{G2_COMPANY_COUNT}"
)


print(
    f"Research optimizer eligible:       "
    f"{int(G2_EXPECTED_RETURNS['research_optimizer_eligible'].sum())}"
)


print(
    f"New-entry optimizer eligible:      "
    f"{G2_ENTRY_COUNT}"
)


print(
    f"Risk-free rate:                    "
    f"{G2_RISK_FREE_RATE:.2%}"
)


print(
    f"Equity risk premium:               "
    f"{G2_EQUITY_RISK_PREMIUM:.2%}"
)


print(
    f"Market expected return:            "
    f"{G2_MARKET_EXPECTED_RETURN:.2%}"
)


print(
    f"Alpha calibration:                 "
    f"{G2_ALPHA_RETURN_PER_SIGNAL:.1%} per signal unit"
)


print(
    f"Maximum annual alpha:              "
    f"+/-{G2_MAX_ABS_ANNUAL_ALPHA:.1%}"
)


print(
    f"Expected-return SHA256:            "
    f"{G2_EXPECTED_RETURN_SHA256}"
)


# ==================================================================================================
# 33. RANKING-ELIGIBLE EXPECTED RETURNS
# ==================================================================================================

print(
    "\nRanking-eligible annualized expected returns:"
)


display(

    G2_EXPECTED_RETURNS[

        G2_EXPECTED_RETURNS[
            "research_optimizer_eligible"
        ]

    ][
        [
            "expected_return_rank",

            "ticker",
            "company_name",

            "sector_ticker",
            "allocation_bucket",

            "valuation_beta",

            "capm_required_return",

            "annual_alpha_overlay",

            "expected_total_return_annual",

            "expected_excess_return_over_cash",

            "expected_active_return_vs_market",

            "expected_return_confidence",

            "expected_return_status",

            "mos_threshold_met",
            "research_status",
        ]
    ]

    .sort_values(
        "expected_return_rank"
    )

)


# ==================================================================================================
# 34. CURRENT ENTRY CANDIDATES
# ==================================================================================================

print(
    "\nCurrent MOS-qualified entry candidates:"
)


if G2_CURRENT_ENTRY_RETURNS.empty:

    print(
        "None."
    )


else:

    display(

        G2_CURRENT_ENTRY_RETURNS[
            [
                "ticker",
                "company_name",

                "sector_ticker",
                "allocation_bucket",

                "valuation_beta",

                "capm_required_return",

                "annual_alpha_overlay",

                "expected_total_return_annual",

                "expected_active_return_vs_market",

                "expected_return_confidence",

                "valuation_review_required",
            ]
        ]

    )


# ==================================================================================================
# 35. EXPECTED RETURN ATTRIBUTION
# ==================================================================================================

print(
    "\nLargest policy-calibrated alpha overlays:"
)


display(

    G2_EXPECTED_RETURNS[
        [
            "ticker",
            "company_name",

            "sector_alpha_return_contribution",
            "company_alpha_return_contribution",
            "valuation_alpha_return_contribution",

            "annual_alpha_overlay",

            "expected_total_return_annual",

            "research_status",
        ]
    ]

    .sort_values(

        "annual_alpha_overlay",

        ascending=False,

    )

    .head(
        15
    )

)


# ==================================================================================================
# 36. HEALTH
# ==================================================================================================

print(
    "\nG2 health:"
)


display(
    G2_HEALTH
)


print(
    "\nG2 summary:"
)


display(
    G2_SUMMARY
)


# ==================================================================================================
# 37. PRODUCTION GATE
# ==================================================================================================

if not G2_PASSED:

    display(

        G2_REQUIRED_FAILURES

    )


    raise RuntimeError(

        "G2 PRODUCTION GATE FAILED. "
        "Do not build covariance / optimize portfolio."

    )


print(
    "\n"
    + "=" * 145
)


print(
    "✓ G2 COMPLETE — annualized expected equity returns generated."
)


print(
    "✓ Expected return = CAPM required equity return + policy-calibrated research alpha."
)


print(
    "✓ CAPM baseline uses the final through-cycle valuation beta from Section F4."
)


print(
    "✓ Alpha mapping is deliberately conservative, bounded, and explicitly non-backtested."
)


print(
    "✓ G1 research confidence is already embedded in the alpha overlay and is not double-counted."
)


print(
    f"✓ CONFIG-driven MOS entry governance remains active (base={float(cfg(['valuation', 'mos_base'], 0.15)):.0%})."
)


print(
    "✓ Watchlist names retain expected-return estimates but are not new-entry optimizer candidates."
)


print(
    "✓ G2_OPTIMIZER_EXPECTED_RETURNS is the expected-return handoff for the risk model."
)


print(
    "✓ Next: G3 — covariance, volatility, downside-risk and correlation engine."
)


print(
    "=" * 145
)


# ===== ORIGINAL NOTEBOOK CELL 81 =====
# ==================================================================================================
# SECTION G — STOCK ALPHA INTEGRATION ENGINE
# CELL G3 — STOCK RISK / COVARIANCE / DOWNSIDE-RISK ENGINE V1.0.0
# ==================================================================================================
#
# PURPOSE
# -------
#
# Build the production stock-level risk model used by portfolio optimization.
#
#
# G3 estimates:
#
#   1. Daily stock returns
#   2. Annualized volatility
#   3. Downside volatility
#   4. Maximum drawdown
#   5. Correlation matrix
#   6. Ledoit-Wolf covariance matrix
#   7. Recent / stress covariance matrix
#   8. Blended optimizer covariance matrix
#   9. Single-stock historical VaR / CVaR diagnostics
#
#
# OPTIMIZER COVARIANCE
# --------------------
#
#   80% × full-lookback Ledoit-Wolf covariance
#
#   +
#
#   20% × recent stress covariance
#
#
# This improves robustness versus using the raw sample covariance alone.
#
#
# LOOKBACK
# --------
#
# Preferred:
#
#       756 trading days ≈ 3 years
#
# Minimum:
#
#       252 observations
#
#
# Stress window:
#
#       most recent 126 trading days
#
#
# IMPORTANT
# ---------
#
#   - Expected returns come from G2.
#   - Risk model does NOT alter expected returns.
#   - MOS governance remains unchanged.
#   - Six provisional specialist names remain blocked.
#   - Historical alpha backtest remains blocked.
#
#
# OUTPUT FOR G4
# -------------
#
#       G3_OPTIMIZER_COVARIANCE
#
#       G3_OPTIMIZER_CORRELATION
#
#       G3_STOCK_RISK_METRICS
#
#       G3_RISK_MODEL_HANDOFF
#
#
# Next:
#
#       G4 — portfolio optimization with turnover,
#            stock/sector limits and MOS governance.
# ==================================================================================================


# ==================================================================================================
# 1. IMPORTS
# ==================================================================================================

from pathlib import Path

import hashlib
import re
import warnings

import numpy as np
import pandas as pd


from sklearn.covariance import LedoitWolf


warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
)


# ==================================================================================================
# 2. VALIDATE UPSTREAM
# ==================================================================================================

required_g3_objects = [

    "G2_PASSED",

    "G2_OPTIMIZER_EXPECTED_RETURNS",

    "G1_FINAL_ALPHA_HANDOFF",

    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",

    "VALUATION_UNIVERSE_FREEZE_ID",

]


missing_g3_objects = [

    obj

    for obj in required_g3_objects

    if obj not in globals()

]


if missing_g3_objects:

    raise RuntimeError(

        "G3 requires completed G1/G2 state. Missing: "
        f"{missing_g3_objects}"

    )


if not bool(
    G2_PASSED
):

    raise RuntimeError(

        "G2 production gate did not pass."

    )


# ==================================================================================================
# 3. VERSION
# ==================================================================================================

G3_VERSION = "1.2.0"


# ==================================================================================================
# 4. RISK CONFIGURATION
# ==================================================================================================

G3_TRADING_DAYS = int(cfg(["risk", "trading_days"], 252))


# ------------------------------------------------------------
# Primary historical window.
# ------------------------------------------------------------

G3_LOOKBACK_DAYS = int(cfg(["risk", "lookback_days"], 756))


# ------------------------------------------------------------
# Minimum acceptable observations per stock.
# ------------------------------------------------------------

G3_MIN_OBSERVATIONS = int(cfg(["risk", "min_observations"], 252))


# ------------------------------------------------------------
# Recent stress covariance window.
# ------------------------------------------------------------

G3_STRESS_WINDOW = int(cfg(["risk", "stress_window"], 126))


# ------------------------------------------------------------
# Optimizer covariance blend.
# ------------------------------------------------------------

G3_BASE_COV_WEIGHT = float(cfg(["risk", "base_cov_weight"], 0.80))

G3_STRESS_COV_WEIGHT = float(cfg(["risk", "stress_cov_weight"], 0.20))


if not np.isclose(

    G3_BASE_COV_WEIGHT
    +
    G3_STRESS_COV_WEIGHT,

    1.0,

):

    raise RuntimeError(

        "G3 covariance weights must sum to 1."

    )


# ------------------------------------------------------------
# Historical risk confidence level.
# ------------------------------------------------------------

G3_VAR_CONFIDENCE = float(cfg(["risk", "var_confidence"], 0.99))


# ------------------------------------------------------------
# Maximum missing-return share allowed after common-window
# construction before a company is considered weak coverage.
# ------------------------------------------------------------

G3_MAX_MISSING_SHARE = float(cfg(["risk", "max_missing_share"], 0.15))

# Market-source overlap requirements are dynamic to the CURRENT universe.
G3_SOURCE_MIN_OVERLAP_RATIO = float(
    cfg(["risk", "market_source_min_overlap_ratio"], 0.70)
)
G3_SOURCE_MIN_OVERLAP_COUNT = int(
    cfg(["risk", "market_source_min_overlap_count"], 3)
)
G3_COMMON_DATE_COVERAGE_RATIO = float(
    cfg(["risk", "common_date_coverage_ratio"], 0.90)
)

if not (0.0 < G3_SOURCE_MIN_OVERLAP_RATIO <= 1.0):
    raise RuntimeError("risk.market_source_min_overlap_ratio must be in (0, 1].")
if G3_SOURCE_MIN_OVERLAP_COUNT < 1:
    raise RuntimeError("risk.market_source_min_overlap_count must be >= 1.")
if not (0.0 < G3_COMMON_DATE_COVERAGE_RATIO <= 1.0):
    raise RuntimeError("risk.common_date_coverage_ratio must be in (0, 1].")


# ==================================================================================================
# 5. TARGET UNIVERSE
# ==================================================================================================

G3_EXPECTED_RETURNS = (

    G2_OPTIMIZER_EXPECTED_RETURNS
    .copy()

)


G3_EXPECTED_RETURNS[
    "ticker"
] = (

    G3_EXPECTED_RETURNS[
        "ticker"
    ]
    .astype(str)

)


G3_ALL_TICKERS = sorted(

    G3_EXPECTED_RETURNS[
        "ticker"
    ]
    .unique()
    .tolist()

)


G3_RESEARCH_TICKERS = sorted(

    G3_EXPECTED_RETURNS.loc[

        G3_EXPECTED_RETURNS[
            "research_optimizer_eligible"
        ]
        .fillna(False),

        "ticker",

    ]
    .astype(str)
    .tolist()

)


G3_ENTRY_TICKERS = sorted(

    G3_EXPECTED_RETURNS.loc[

        G3_EXPECTED_RETURNS[
            "new_entry_optimizer_eligible"
        ]
        .fillna(False),

        "ticker",

    ]
    .astype(str)
    .tolist()

)


G3_EXPECTED_COMPANY_COUNT = len(

    G3_ALL_TICKERS

)


G3_EXPECTED_RESEARCH_COUNT = len(

    G3_RESEARCH_TICKERS

)


# ==================================================================================================
# 6. HELPERS
# ==================================================================================================

def g3_normalize_name(
    value
):

    return re.sub(

        r"[^a-z0-9]+",

        "_",

        str(
            value
        ).lower(),

    ).strip(
        "_"
    )


def g3_find_column(
    columns,
    aliases,
):

    mapping = {

        g3_normalize_name(
            column
        ):
            column

        for column
        in columns

    }


    for alias in aliases:

        alias = g3_normalize_name(
            alias
        )


        if alias in mapping:

            return mapping[
                alias
            ]


    return None


# ==================================================================================================
# 7. MARKET-DATA COLUMN ALIASES
# ==================================================================================================

G3_TICKER_ALIASES = [

    "ticker",
    "symbol",
    "stock_ticker",
    "security_ticker",

]


G3_DATE_ALIASES = [

    "date",
    "datetime",
    "timestamp",
    "price_date",
    "trade_date",

]


G3_PRICE_ALIASES = [

    "adj_close",
    "adjusted_close",
    "adjclose",

    "auto_adjusted_close",

    "close",

]


G3_RETURN_ALIASES = [

    "return",
    "daily_return",
    "stock_return",
    "ret",
    "simple_return",

]


# ==================================================================================================
# 8. PROFILE MARKET DATAFRAME
# ==================================================================================================

def g3_profile_market_dataframe(
    source_name,
    dataframe,
    source_type="MEMORY",
    source_path=None,
):

    if not isinstance(
        dataframe,
        pd.DataFrame,
    ):

        return None


    ticker_column = g3_find_column(

        dataframe.columns,

        G3_TICKER_ALIASES,

    )


    date_column = g3_find_column(

        dataframe.columns,

        G3_DATE_ALIASES,

    )


    price_column = g3_find_column(

        dataframe.columns,

        G3_PRICE_ALIASES,

    )


    return_column = g3_find_column(

        dataframe.columns,

        G3_RETURN_ALIASES,

    )


    if (

        ticker_column is None

        or

        date_column is None

        or

        (
            price_column is None

            and

            return_column is None
        )

    ):

        return None


    try:

        tickers = set(

            dataframe[
                ticker_column
            ]
            .dropna()
            .astype(str)

        )


    except Exception:

        return None


    overlap = len(

        tickers

        &

        set(
            G3_ALL_TICKERS
        )

    )


    required_overlap = min(
        G3_EXPECTED_COMPANY_COUNT,
        max(
            1,
            int(np.ceil(
                G3_SOURCE_MIN_OVERLAP_RATIO
                *
                G3_EXPECTED_COMPANY_COUNT
            )),
            min(
                G3_SOURCE_MIN_OVERLAP_COUNT,
                G3_EXPECTED_COMPANY_COUNT,
            ),
        ),
    )

    if overlap < required_overlap:

        return None


    source_text = (

        str(
            source_name
        )

        +
        " "

        +
        str(
            source_path
            or
            ""
        )

    ).lower()


    score = overlap * 10


    if "e3" in source_text:

        score += 500


    if "market" in source_text:

        score += 100


    if "price" in source_text:

        score += 80


    if "stock" in source_text:

        score += 40


    if price_column is not None:

        score += 50


    if return_column is not None:

        score += 30


    return {

        "source_name":
            str(
                source_name
            ),

        "source_type":
            source_type,

        "source_path":
            source_path,

        "dataframe":
            dataframe,

        "ticker_column":
            ticker_column,

        "date_column":
            date_column,

        "price_column":
            price_column,

        "return_column":
            return_column,

        "ticker_overlap":
            overlap,

        "source_score":
            score,

    }


# ==================================================================================================
# 9. SEARCH MARKET DATA IN MEMORY
# ==================================================================================================

G3_MARKET_DATA_CANDIDATES = []


for object_name, obj in list(

    globals().items()

):

    if not isinstance(
        obj,
        pd.DataFrame,
    ):

        continue


    try:

        candidate = g3_profile_market_dataframe(

            source_name=
                object_name,

            dataframe=
                obj,

            source_type=
                "MEMORY",

        )


        if candidate is not None:

            G3_MARKET_DATA_CANDIDATES.append(

                candidate

            )


    except Exception:

        continue


# ==================================================================================================
# 10. SEARCH SAVED MARKET DATA IF NEEDED
# ==================================================================================================

search_roots = []


for root_candidate in [

    globals().get(
        "PROJECT_ROOT",
        None,
    ),

    Path(
        STOCK_MODEL_DIR
    ),

    Path(
        STOCK_OUTPUT_DIR
    ),

    Path(
        STOCK_MODEL_DIR
    ).parent,

]:

    if root_candidate is None:

        continue


    try:

        root_candidate = Path(

            root_candidate

        )


        if (

            root_candidate.exists()

            and

            root_candidate not in search_roots

        ):

            search_roots.append(

                root_candidate

            )


    except Exception:

        continue


artifact_paths = []


for root in search_roots:

    try:

        artifact_paths.extend(

            list(
                root.rglob(
                    "*.parquet"
                )
            )

        )


        artifact_paths.extend(

            list(
                root.rglob(
                    "*.csv"
                )
            )

        )


    except Exception:

        continue


artifact_paths = list(

    dict.fromkeys(
        artifact_paths
    )

)


# ------------------------------------------------------------
# Prioritize likely E3/market artifacts.
# ------------------------------------------------------------

artifact_paths = sorted(

    artifact_paths,

    key=lambda path: (

        0
        if "e3" in str(
            path
        ).lower()
        else 1,

        0
        if "market" in str(
            path
        ).lower()
        else 1,

        0
        if "price" in str(
            path
        ).lower()
        else 1,

        str(
            path
        ),

    ),

)


artifact_paths = artifact_paths[:1000]


if (

    len(
        G3_MARKET_DATA_CANDIDATES
    )
    ==
    0

):

    for path in artifact_paths:

        path_text = str(
            path
        ).lower()


        if not any(

            token in path_text

            for token in [

                "e3",
                "market",
                "price",
                "stock",

            ]

        ):

            continue


        try:

            if path.suffix.lower() == ".parquet":

                dataframe = pd.read_parquet(

                    path

                )


            elif path.suffix.lower() == ".csv":

                dataframe = pd.read_csv(

                    path

                )


            else:

                continue


            candidate = g3_profile_market_dataframe(

                source_name=
                    path.name,

                dataframe=
                    dataframe,

                source_type=
                    "DISK",

                source_path=
                    str(
                        path
                    ),

            )


            if candidate is not None:

                G3_MARKET_DATA_CANDIDATES.append(

                    candidate

                )


        except Exception:

            continue


# ==================================================================================================
# 11. SELECT MARKET DATA SOURCE
# ==================================================================================================

if not G3_MARKET_DATA_CANDIDATES:

    raise RuntimeError(

        "G3 could not locate the Section E3 stock market "
        "history in memory or saved artifacts."

    )


G3_MARKET_DATA_CANDIDATES = sorted(

    G3_MARKET_DATA_CANDIDATES,

    key=lambda candidate: (

        candidate[
            "source_score"
        ],

        candidate[
            "ticker_overlap"
        ],

    ),

    reverse=True,

)


G3_MARKET_SOURCE_INFO = (

    G3_MARKET_DATA_CANDIDATES[0]

)


G3_MARKET_SOURCE_NAME = (

    G3_MARKET_SOURCE_INFO[
        "source_name"
    ]

)


G3_MARKET_SOURCE_TYPE = (

    G3_MARKET_SOURCE_INFO[
        "source_type"
    ]

)


G3_MARKET_SOURCE_PATH = (

    G3_MARKET_SOURCE_INFO[
        "source_path"
    ]

)


G3_MARKET_RAW = (

    G3_MARKET_SOURCE_INFO[
        "dataframe"
    ]
    .copy()

)


G3_TICKER_COLUMN = (

    G3_MARKET_SOURCE_INFO[
        "ticker_column"
    ]

)


G3_DATE_COLUMN = (

    G3_MARKET_SOURCE_INFO[
        "date_column"
    ]

)


G3_PRICE_COLUMN = (

    G3_MARKET_SOURCE_INFO[
        "price_column"
    ]

)


G3_RETURN_COLUMN = (

    G3_MARKET_SOURCE_INFO[
        "return_column"
    ]

)


# ==================================================================================================
# 12. NORMALIZE MARKET DATA
# ==================================================================================================

G3_MARKET = pd.DataFrame({

    "ticker":

        G3_MARKET_RAW[
            G3_TICKER_COLUMN
        ]
        .astype(str),

    "date":

        pd.to_datetime(

            G3_MARKET_RAW[
                G3_DATE_COLUMN
            ],

            errors="coerce",

        ),

})


if G3_PRICE_COLUMN is not None:

    G3_MARKET[
        "price"
    ] = pd.to_numeric(

        G3_MARKET_RAW[
            G3_PRICE_COLUMN
        ],

        errors="coerce",

    )


else:

    G3_MARKET[
        "price"
    ] = np.nan


if G3_RETURN_COLUMN is not None:

    G3_MARKET[
        "source_return"
    ] = pd.to_numeric(

        G3_MARKET_RAW[
            G3_RETURN_COLUMN
        ],

        errors="coerce",

    )


else:

    G3_MARKET[
        "source_return"
    ] = np.nan


G3_MARKET = (

    G3_MARKET[

        G3_MARKET[
            "ticker"
        ]
        .isin(
            G3_ALL_TICKERS
        )

    ]

    .dropna(
        subset=[
            "date"
        ]
    )

    .sort_values(

        [
            "ticker",
            "date",
        ]

    )

    .drop_duplicates(

        subset=[
            "ticker",
            "date",
        ],

        keep="last",

    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# 13. COMPUTE DAILY RETURNS
# ==================================================================================================

if (

    G3_PRICE_COLUMN is not None

    and

    G3_MARKET[
        "price"
    ]
    .notna()
    .sum()
    >
    0

):

    G3_MARKET[
        "daily_return"
    ] = (

        G3_MARKET

        .groupby(
            "ticker"
        )[
            "price"
        ]

        .pct_change(
            fill_method=None
        )

    )


    G3_RETURN_SOURCE = (

        f"PRICE:{G3_PRICE_COLUMN}"

    )


elif (

    G3_RETURN_COLUMN is not None

):

    G3_MARKET[
        "daily_return"
    ] = (

        G3_MARKET[
            "source_return"
        ]

    )


    G3_RETURN_SOURCE = (

        f"RETURN:{G3_RETURN_COLUMN}"

    )


else:

    raise RuntimeError(

        "Selected market source contains neither usable "
        "price nor return data."

    )


# ==================================================================================================
# 14. CLEAN IMPOSSIBLE RETURN OBSERVATIONS
# ==================================================================================================
#
# Simple return cannot be below -100%.
#
# Very large positive values may represent split/data errors.
# Use a broad upper filter rather than aggressive winsorization.
# ==================================================================================================

G3_MARKET.loc[

    (
        G3_MARKET[
            "daily_return"
        ]
        <=
        -1.0
    )

    |

    (
        G3_MARKET[
            "daily_return"
        ]
        >
        5.0
    ),

    "daily_return",

] = np.nan


# ==================================================================================================
# 15. BUILD WIDE RETURN MATRIX
# ==================================================================================================

G3_RETURNS_WIDE_FULL = (

    G3_MARKET

    .pivot(

        index=
            "date",

        columns=
            "ticker",

        values=
            "daily_return",

    )

    .sort_index()

)


# ==================================================================================================
# 16. USE MOST RECENT LOOKBACK WINDOW
# ==================================================================================================

G3_RETURNS_WIDE = (

    G3_RETURNS_WIDE_FULL

    .tail(
        G3_LOOKBACK_DAYS
    )

    .copy()

)


# ==================================================================================================
# 17. COVERAGE AUDIT
# ==================================================================================================

coverage_rows = []


for ticker in G3_ALL_TICKERS:

    if ticker in G3_RETURNS_WIDE.columns:

        series = (

            G3_RETURNS_WIDE[
                ticker
            ]

        )


        observations = int(

            series
            .notna()
            .sum()

        )


        missing_share = (

            float(
                series.isna().mean()
            )

        )


        first_date = (

            series
            .dropna()
            .index
            .min()

            if observations > 0

            else pd.NaT

        )


        last_date = (

            series
            .dropna()
            .index
            .max()

            if observations > 0

            else pd.NaT

        )


    else:

        observations = 0

        missing_share = 1.0

        first_date = pd.NaT

        last_date = pd.NaT


    coverage_rows.append({

        "ticker":
            ticker,

        "observations":
            observations,

        "missing_share":
            missing_share,

        "first_return_date":
            first_date,

        "last_return_date":
            last_date,

        "minimum_history_pass":
            observations
            >=
            G3_MIN_OBSERVATIONS,

    })


G3_RISK_DATA_COVERAGE = pd.DataFrame(

    coverage_rows

)


# ==================================================================================================
# 18. HARD HISTORY GATE FOR RESEARCH-ELIGIBLE NAMES
# ==================================================================================================

research_coverage = (

    G3_RISK_DATA_COVERAGE[

        G3_RISK_DATA_COVERAGE[
            "ticker"
        ]
        .isin(
            G3_RESEARCH_TICKERS
        )

    ]

)


G3_RESEARCH_HISTORY_FAILURES = (

    research_coverage[

        ~

        research_coverage[
            "minimum_history_pass"
        ]

    ]

    .copy()

)


if not G3_RESEARCH_HISTORY_FAILURES.empty:

    raise RuntimeError(

        "G3 insufficient market history for research-eligible "
        "tickers:\n"
        f"{G3_RESEARCH_HISTORY_FAILURES}"

    )


# ==================================================================================================
# 19. OPTIMIZER RETURN MATRIX
# ==================================================================================================
#
# Portfolio risk model uses the CURRENT research-rankable universe.
#
# Provisional names remain outside optimization.
# ==================================================================================================

G3_RESEARCH_RETURNS = (

    G3_RETURNS_WIDE[
        G3_RESEARCH_TICKERS
    ]

    .copy()

)


# ==================================================================================================
# 20. ALIGN ON COMMON VALID DATES
# ==================================================================================================
#
# Ledoit-Wolf requires a complete matrix.
#
# First retain dates with strong cross-sectional coverage.
# Then fill the remaining small gaps using 0 return.
#
# Zero is preferable here to forward-filling PRICES because
# it preserves the interpretation of no observed daily move.
#
# Coverage must already be strong before this step.
# ==================================================================================================

minimum_names_per_day = int(

    np.ceil(

        G3_COMMON_DATE_COVERAGE_RATIO

        *
        len(
            G3_RESEARCH_TICKERS
        )

    )

)


valid_day_mask = (

    G3_RESEARCH_RETURNS
    .notna()
    .sum(
        axis=1
    )

    >=
    minimum_names_per_day

)


G3_RESEARCH_RETURNS_ALIGNED = (

    G3_RESEARCH_RETURNS.loc[

        valid_day_mask

    ]

    .copy()

)


G3_RESEARCH_RETURNS_ALIGNED = (

    G3_RESEARCH_RETURNS_ALIGNED

    .fillna(
        0.0
    )

)


# ==================================================================================================
# 21. MINIMUM COMMON-WINDOW GATE
# ==================================================================================================

G3_COMMON_OBSERVATIONS = len(

    G3_RESEARCH_RETURNS_ALIGNED

)


if (

    G3_COMMON_OBSERVATIONS
    <
    G3_MIN_OBSERVATIONS

):

    raise RuntimeError(

        "G3 common aligned return history is too short: "
        f"{G3_COMMON_OBSERVATIONS} observations."

    )


# ==================================================================================================
# 22. LEDOIT-WOLF COVARIANCE
# ==================================================================================================

G3_LEDWOIT_MODEL = (

    LedoitWolf(
        assume_centered=False
    )

    .fit(

        G3_RESEARCH_RETURNS_ALIGNED.values

    )

)


G3_BASE_DAILY_COVARIANCE = pd.DataFrame(

    G3_LEDWOIT_MODEL.covariance_,

    index=
        G3_RESEARCH_TICKERS,

    columns=
        G3_RESEARCH_TICKERS,

)


G3_BASE_ANNUAL_COVARIANCE = (

    G3_BASE_DAILY_COVARIANCE

    *
    G3_TRADING_DAYS

)


G3_SHRINKAGE_INTENSITY = float(

    G3_LEDWOIT_MODEL.shrinkage_

)


# ==================================================================================================
# 23. FULL-SAMPLE CORRELATION
# ==================================================================================================

G3_SAMPLE_CORRELATION = (

    G3_RESEARCH_RETURNS_ALIGNED

    .corr()

)


# ==================================================================================================
# 24. RECENT STRESS COVARIANCE
# ==================================================================================================

stress_returns = (

    G3_RESEARCH_RETURNS_ALIGNED

    .tail(
        min(
            G3_STRESS_WINDOW,
            G3_COMMON_OBSERVATIONS,
        )
    )

)


G3_STRESS_DAILY_COVARIANCE = (

    stress_returns
    .cov()

)


G3_STRESS_ANNUAL_COVARIANCE = (

    G3_STRESS_DAILY_COVARIANCE

    *
    G3_TRADING_DAYS

)


# ==================================================================================================
# 25. PSD REPAIR HELPER
# ==================================================================================================

def g3_nearest_psd(
    covariance,
    floor=1e-10,
):

    matrix = np.asarray(

        covariance,

        dtype=float,

    )


    matrix = (

        matrix
        +
        matrix.T

    ) / 2.0


    eigenvalues, eigenvectors = (

        np.linalg.eigh(
            matrix
        )

    )


    eigenvalues = np.maximum(

        eigenvalues,

        floor,

    )


    repaired = (

        eigenvectors

        @

        np.diag(
            eigenvalues
        )

        @

        eigenvectors.T

    )


    repaired = (

        repaired
        +
        repaired.T

    ) / 2.0


    return repaired


# ==================================================================================================
# 26. REPAIR STRESS COVARIANCE
# ==================================================================================================

G3_STRESS_ANNUAL_COVARIANCE = pd.DataFrame(

    g3_nearest_psd(

        G3_STRESS_ANNUAL_COVARIANCE.values

    ),

    index=
        G3_RESEARCH_TICKERS,

    columns=
        G3_RESEARCH_TICKERS,

)


# ==================================================================================================
# 27. BLENDED OPTIMIZER COVARIANCE
# ==================================================================================================

G3_OPTIMIZER_COVARIANCE = (

    G3_BASE_COV_WEIGHT

    *
    G3_BASE_ANNUAL_COVARIANCE

    +

    G3_STRESS_COV_WEIGHT

    *
    G3_STRESS_ANNUAL_COVARIANCE

)


# ==================================================================================================
# 28. FINAL PSD REPAIR
# ==================================================================================================

G3_OPTIMIZER_COVARIANCE = pd.DataFrame(

    g3_nearest_psd(

        G3_OPTIMIZER_COVARIANCE.values

    ),

    index=
        G3_RESEARCH_TICKERS,

    columns=
        G3_RESEARCH_TICKERS,

)


# ==================================================================================================
# 29. OPTIMIZER CORRELATION
# ==================================================================================================

optimizer_volatility = np.sqrt(

    np.diag(

        G3_OPTIMIZER_COVARIANCE.values

    )

)


correlation_denominator = np.outer(

    optimizer_volatility,

    optimizer_volatility,

)


G3_OPTIMIZER_CORRELATION_VALUES = np.divide(

    G3_OPTIMIZER_COVARIANCE.values,

    correlation_denominator,

    out=
        np.zeros_like(

            G3_OPTIMIZER_COVARIANCE.values

        ),

    where=
        correlation_denominator
        >
        0,

)


np.fill_diagonal(

    G3_OPTIMIZER_CORRELATION_VALUES,

    1.0,

)


G3_OPTIMIZER_CORRELATION = pd.DataFrame(

    G3_OPTIMIZER_CORRELATION_VALUES,

    index=
        G3_RESEARCH_TICKERS,

    columns=
        G3_RESEARCH_TICKERS,

)


# ==================================================================================================
# 30. STOCK-LEVEL RISK METRICS
# ==================================================================================================

risk_metric_rows = []


for ticker in G3_RESEARCH_TICKERS:

    series = (

        G3_RESEARCH_RETURNS_ALIGNED[
            ticker
        ]

        .dropna()

    )


    # --------------------------------------------------------
    # Annual volatility.
    # --------------------------------------------------------

    sample_volatility = (

        series.std(
            ddof=1
        )

        *
        np.sqrt(
            G3_TRADING_DAYS
        )

    )


    # --------------------------------------------------------
    # Optimizer volatility.
    # --------------------------------------------------------

    optimizer_variance = (

        G3_OPTIMIZER_COVARIANCE.loc[
            ticker,
            ticker,
        ]

    )


    optimizer_volatility_i = np.sqrt(

        max(
            optimizer_variance,
            0.0,
        )

    )


    # --------------------------------------------------------
    # Downside volatility.
    #
    # Zero-threshold semideviation.
    # --------------------------------------------------------

    downside_series = (

        np.minimum(

            series.values,

            0.0,

        )

    )


    downside_volatility = (

        np.sqrt(

            np.mean(

                downside_series ** 2

            )

        )

        *
        np.sqrt(
            G3_TRADING_DAYS
        )

    )


    # --------------------------------------------------------
    # Annualized historical return.
    # --------------------------------------------------------

    compounded_growth = (

        (
            1.0
            +
            series
        )
        .prod()

    )


    years = (

        len(
            series
        )

        /
        G3_TRADING_DAYS

    )


    if (

        years > 0

        and

        compounded_growth > 0

    ):

        annualized_historical_return = (

            compounded_growth
            **
            (
                1.0
                /
                years
            )

            -
            1.0

        )


    else:

        annualized_historical_return = np.nan


    # --------------------------------------------------------
    # Maximum drawdown.
    # --------------------------------------------------------

    wealth_index = (

        (
            1.0
            +
            series
        )
        .cumprod()

    )


    running_peak = (

        wealth_index
        .cummax()

    )


    drawdown = (

        wealth_index

        /
        running_peak

        -
        1.0

    )


    max_drawdown = float(

        drawdown.min()

    )


    # --------------------------------------------------------
    # Historical 99% VaR / CVaR.
    #
    # Positive numbers represent loss magnitude.
    # --------------------------------------------------------

    loss_series = (

        -
        series

    )


    var_threshold = float(

        np.quantile(

            loss_series,

            G3_VAR_CONFIDENCE,

        )

    )


    tail_losses = (

        loss_series[

            loss_series
            >=
            var_threshold

        ]

    )


    cvar = (

        float(
            tail_losses.mean()
        )

        if len(
            tail_losses
        )
        >
        0

        else var_threshold

    )


    # --------------------------------------------------------
    # Average correlation.
    # --------------------------------------------------------

    correlation_row = (

        G3_OPTIMIZER_CORRELATION.loc[
            ticker
        ]

        .drop(
            labels=[
                ticker
            ],
            errors="ignore",
        )

    )


    average_correlation = float(

        correlation_row.mean()

    )


    max_peer_correlation = float(

        correlation_row.max()

    )


    risk_metric_rows.append({

        "ticker":
            ticker,

        "observations":
            len(
                series
            ),

        "historical_return_annual":
            annualized_historical_return,

        "sample_volatility_annual":
            sample_volatility,

        "optimizer_volatility_annual":
            optimizer_volatility_i,

        "downside_volatility_annual":
            downside_volatility,

        "maximum_drawdown":
            max_drawdown,

        "historical_var_99_daily":
            var_threshold,

        "historical_cvar_99_daily":
            cvar,

        "average_correlation":
            average_correlation,

        "max_peer_correlation":
            max_peer_correlation,

    })


G3_STOCK_RISK_METRICS = pd.DataFrame(

    risk_metric_rows

)


# ==================================================================================================
# 31. MERGE EXPECTED RETURNS WITH RISK
# ==================================================================================================

G3_RISK_MODEL_HANDOFF = (

    G3_EXPECTED_RETURNS

    .merge(

        G3_STOCK_RISK_METRICS,

        on="ticker",

        how="left",

        validate="one_to_one",

    )

)


# ==================================================================================================
# 32. EXPECTED SHARPE-LIKE DIAGNOSTIC
# ==================================================================================================
#
# Not portfolio Sharpe.
#
# Stock-level expected excess return / optimizer volatility.
# ==================================================================================================

risk_free_rate = (

    float(
        globals().get(
            "G2_RISK_FREE_RATE",
            0.0,
        )
    )

)


G3_RISK_MODEL_HANDOFF[
    "expected_excess_return_over_cash"
] = (

    G3_RISK_MODEL_HANDOFF[
        "expected_total_return_annual"
    ]

    -
    risk_free_rate

)


G3_RISK_MODEL_HANDOFF[
    "expected_return_to_risk"
] = (

    G3_RISK_MODEL_HANDOFF[
        "expected_excess_return_over_cash"
    ]

    /

    G3_RISK_MODEL_HANDOFF[
        "optimizer_volatility_annual"
    ]

)


# ==================================================================================================
# 33. DOWNSIDE RETURN-TO-RISK
# ==================================================================================================

G3_RISK_MODEL_HANDOFF[
    "expected_return_to_downside_risk"
] = (

    G3_RISK_MODEL_HANDOFF[
        "expected_excess_return_over_cash"
    ]

    /

    G3_RISK_MODEL_HANDOFF[
        "downside_volatility_annual"
    ]

)


# ==================================================================================================
# 34. RISK RANK
# ==================================================================================================
#
# Lower optimizer volatility = lower risk rank.
# ==================================================================================================

G3_RISK_MODEL_HANDOFF[
    "volatility_rank"
] = (

    G3_RISK_MODEL_HANDOFF[
        "optimizer_volatility_annual"
    ]

    .rank(

        method="min",

        ascending=True,

    )

)


# ==================================================================================================
# 35. RETURN/RISK RANK
# ==================================================================================================

G3_RISK_MODEL_HANDOFF[
    "expected_return_to_risk_rank"
] = (

    G3_RISK_MODEL_HANDOFF[
        "expected_return_to_risk"
    ]

    .rank(

        method="min",

        ascending=False,

    )

)


# ==================================================================================================
# 36. ENTRY-CANDIDATE RISK TABLE
# ==================================================================================================

G3_ENTRY_RISK_TABLE = (

    G3_RISK_MODEL_HANDOFF[

        G3_RISK_MODEL_HANDOFF[
            "new_entry_optimizer_eligible"
        ]

    ]

    .copy()

    .sort_values(

        "expected_return_to_risk",

        ascending=False,

    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# 37. COVARIANCE HEALTH
# ==================================================================================================

G3_MIN_EIGENVALUE = float(

    np.linalg.eigvalsh(

        G3_OPTIMIZER_COVARIANCE.values

    )
    .min()

)


G3_MAX_EIGENVALUE = float(

    np.linalg.eigvalsh(

        G3_OPTIMIZER_COVARIANCE.values

    )
    .max()

)


G3_COVARIANCE_PSD = bool(

    G3_MIN_EIGENVALUE

    >=
    -1e-10

)


G3_COVARIANCE_SYMMETRIC = bool(

    np.allclose(

        G3_OPTIMIZER_COVARIANCE.values,

        G3_OPTIMIZER_COVARIANCE.values.T,

        atol=1e-12,
        rtol=1e-12,

    )

)


G3_CORRELATION_VALID = bool(

    safe_isfinite(

        G3_OPTIMIZER_CORRELATION.values

    )
    .all()

    and

    (
        G3_OPTIMIZER_CORRELATION.values
        <=
        1.000001

    )
    .all()

    and

    (
        G3_OPTIMIZER_CORRELATION.values
        >=
        -1.000001

    )
    .all()

)


# ==================================================================================================
# 38. DATA COVERAGE HEALTH
# ==================================================================================================

G3_RESEARCH_RISK_COVERAGE_COUNT = int(

    G3_STOCK_RISK_METRICS[
        "ticker"
    ]
    .nunique()

)


G3_ENTRY_RISK_COVERAGE_COUNT = int(

    G3_ENTRY_RISK_TABLE[
        "ticker"
    ]
    .nunique()

)


G3_EXPECTED_ENTRY_COUNT = len(

    G3_ENTRY_TICKERS

)


# ==================================================================================================
# 39. VOLATILITY SANITY
# ==================================================================================================

G3_VOLATILITY_FINITE = bool(

    safe_isfinite(

        G3_STOCK_RISK_METRICS[
            "optimizer_volatility_annual"
        ]

    )
    .all()

)


G3_VOLATILITY_POSITIVE = bool(

    (

        G3_STOCK_RISK_METRICS[
            "optimizer_volatility_annual"
        ]

        >
        0

    )
    .all()

)


# ==================================================================================================
# 40. HEALTH TABLE
# ==================================================================================================

G3_HEALTH = pd.DataFrame([

    {

        "check":
            "Research-eligible risk universe coverage is complete",

        "passed":
            G3_RESEARCH_RISK_COVERAGE_COUNT
            ==
            G3_EXPECTED_RESEARCH_COUNT,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{G3_RESEARCH_RISK_COVERAGE_COUNT}/"
                f"{G3_EXPECTED_RESEARCH_COUNT}"
            ),

    },

    {

        "check":
            "Current entry-candidate risk coverage is complete",

        "passed":
            G3_ENTRY_RISK_COVERAGE_COUNT
            ==
            G3_EXPECTED_ENTRY_COUNT,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{G3_ENTRY_RISK_COVERAGE_COUNT}/"
                f"{G3_EXPECTED_ENTRY_COUNT}"
            ),

    },

    {

        "check":
            "Common aligned return history meets minimum length",

        "passed":
            G3_COMMON_OBSERVATIONS
            >=
            G3_MIN_OBSERVATIONS,

        "required":
            True,

        "detail":
            (
                f"observations="
                f"{G3_COMMON_OBSERVATIONS}"
            ),

    },

    {

        "check":
            "Ledoit-Wolf shrinkage is finite and bounded",

        "passed":
            bool(

                safe_isfinite(
                    G3_SHRINKAGE_INTENSITY
                )

                and

                0.0
                <=
                G3_SHRINKAGE_INTENSITY
                <=
                1.0

            ),

        "required":
            True,

        "detail":
            (
                f"shrinkage="
                f"{G3_SHRINKAGE_INTENSITY:.4f}"
            ),

    },

    {

        "check":
            "Optimizer covariance matrix is symmetric",

        "passed":
            G3_COVARIANCE_SYMMETRIC,

        "required":
            True,

        "detail":
            (
                f"dimension="
                f"{len(G3_RESEARCH_TICKERS)}x"
                f"{len(G3_RESEARCH_TICKERS)}"
            ),

    },

    {

        "check":
            "Optimizer covariance matrix is positive semidefinite",

        "passed":
            G3_COVARIANCE_PSD,

        "required":
            True,

        "detail":
            (
                f"min_eigenvalue="
                f"{G3_MIN_EIGENVALUE:.3e}"
            ),

    },

    {

        "check":
            "Optimizer correlation matrix is numerically valid",

        "passed":
            G3_CORRELATION_VALID,

        "required":
            True,

        "detail":
            (
                f"range="
                f"[{G3_OPTIMIZER_CORRELATION.values.min():.3f}, "
                f"{G3_OPTIMIZER_CORRELATION.values.max():.3f}]"
            ),

    },

    {

        "check":
            "Every research stock receives finite optimizer volatility",

        "passed":
            G3_VOLATILITY_FINITE,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{int(safe_isfinite(G3_STOCK_RISK_METRICS['optimizer_volatility_annual']).sum())}/"
                f"{G3_EXPECTED_RESEARCH_COUNT}"
            ),

    },

    {

        "check":
            "Every research stock has positive optimizer volatility",

        "passed":
            G3_VOLATILITY_POSITIVE,

        "required":
            True,

        "detail":
            (
                f"minimum="
                f"{G3_STOCK_RISK_METRICS['optimizer_volatility_annual'].min():.2%}"
            ),

    },

    {

        "check":
            "Historical alpha backtest remains blocked",

        "passed":
            True,

        "required":
            True,

        "detail":
            (
                "risk estimates use current-universe historical prices; "
                "no claim of PIT stock-selection backtest"
            ),

    },

])


G3_HEALTH[
    "status"
] = np.where(

    G3_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


G3_REQUIRED_FAILURES = (

    G3_HEALTH[

        G3_HEALTH[
            "required"
        ]

        &

        ~
        G3_HEALTH[
            "passed"
        ]

    ]

)


G3_PASSED = (

    G3_REQUIRED_FAILURES.empty

)


# ==================================================================================================
# 41. HASH
# ==================================================================================================

G3_HASH_FRAME = (

    G3_RISK_MODEL_HANDOFF[
        [
            "ticker",

            "expected_total_return_annual",

            "optimizer_volatility_annual",

            "downside_volatility_annual",

            "maximum_drawdown",

            "historical_var_99_daily",

            "historical_cvar_99_daily",

            "average_correlation",

            "research_optimizer_eligible",

            "new_entry_optimizer_eligible",
        ]
    ]

    .copy()

    .sort_values(
        "ticker"
    )

    .reset_index(
        drop=True
    )

)


G3_RISK_MODEL_SHA256 = (

    hashlib.sha256(

        pd.util.hash_pandas_object(

            G3_HASH_FRAME,
            index=False,

        )
        .values
        .tobytes()

    )

    .hexdigest()

)


# ==================================================================================================
# 42. SUMMARY
# ==================================================================================================

G3_SUMMARY = pd.DataFrame([{

    "g3_version":
        G3_VERSION,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "risk_model_sha256":
        G3_RISK_MODEL_SHA256,

    "market_source":
        G3_MARKET_SOURCE_NAME,

    "market_source_type":
        G3_MARKET_SOURCE_TYPE,

    "return_source":
        G3_RETURN_SOURCE,

    "all_companies":
        G3_EXPECTED_COMPANY_COUNT,

    "research_risk_universe":
        G3_EXPECTED_RESEARCH_COUNT,

    "entry_candidates":
        G3_EXPECTED_ENTRY_COUNT,

    "common_return_observations":
        G3_COMMON_OBSERVATIONS,

    "lookback_days":
        G3_LOOKBACK_DAYS,

    "stress_window":
        G3_STRESS_WINDOW,

    "ledoit_wolf_shrinkage":
        G3_SHRINKAGE_INTENSITY,

    "base_covariance_weight":
        G3_BASE_COV_WEIGHT,

    "stress_covariance_weight":
        G3_STRESS_COV_WEIGHT,

    "mean_optimizer_volatility":
        float(

            G3_STOCK_RISK_METRICS[
                "optimizer_volatility_annual"
            ]
            .mean()

        ),

    "median_optimizer_volatility":
        float(

            G3_STOCK_RISK_METRICS[
                "optimizer_volatility_annual"
            ]
            .median()

        ),

    "mean_pairwise_correlation":
        float(

            G3_OPTIMIZER_CORRELATION.values[
                np.triu_indices_from(
                    G3_OPTIMIZER_CORRELATION.values,
                    k=1,
                )
            ]
            .mean()

        ),

    "minimum_covariance_eigenvalue":
        G3_MIN_EIGENVALUE,

    "historical_backtest_eligible":
        False,

    "g3_passed":
        G3_PASSED,

}])


# ==================================================================================================
# 43. SAVE OUTPUTS
# ==================================================================================================

G3_RESEARCH_RETURNS_ALIGNED.to_parquet(

    STOCK_MODEL_DIR
    /
    "g3_aligned_daily_returns.parquet",

)


G3_OPTIMIZER_COVARIANCE.to_parquet(

    STOCK_MODEL_DIR
    /
    "g3_optimizer_covariance.parquet",

)


G3_OPTIMIZER_CORRELATION.to_parquet(

    STOCK_MODEL_DIR
    /
    "g3_optimizer_correlation.parquet",

)


G3_STOCK_RISK_METRICS.to_parquet(

    STOCK_MODEL_DIR
    /
    "g3_stock_risk_metrics.parquet",

    index=False,

)


G3_RISK_MODEL_HANDOFF.to_parquet(

    STOCK_MODEL_DIR
    /
    "g3_risk_model_handoff.parquet",

    index=False,

)


G3_RISK_DATA_COVERAGE.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_market_data_coverage.csv",

    index=False,

)


G3_STOCK_RISK_METRICS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_stock_risk_metrics.csv",

    index=False,

)


G3_RISK_MODEL_HANDOFF.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_risk_model_handoff.csv",

    index=False,

)


G3_ENTRY_RISK_TABLE.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_entry_candidate_risk.csv",

    index=False,

)


G3_OPTIMIZER_COVARIANCE.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_optimizer_covariance.csv",

)


G3_OPTIMIZER_CORRELATION.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_optimizer_correlation.csv",

)


G3_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_health.csv",

    index=False,

)


G3_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "g3_summary.csv",

    index=False,

)


# ==================================================================================================
# 44. DISPLAY HEADER
# ==================================================================================================

print(
    "=" * 145
)

print(
    "G3 — STOCK RISK / COVARIANCE / DOWNSIDE-RISK ENGINE V1.0.0"
)

print(
    "=" * 145
)


print(
    f"Market source:                     "
    f"{G3_MARKET_SOURCE_NAME} ({G3_MARKET_SOURCE_TYPE})"
)


print(
    f"Return source:                     "
    f"{G3_RETURN_SOURCE}"
)


print(
    f"Research risk universe:            "
    f"{G3_EXPECTED_RESEARCH_COUNT}"
)


print(
    f"Current entry candidates:          "
    f"{G3_EXPECTED_ENTRY_COUNT}"
)


print(
    f"Common return observations:        "
    f"{G3_COMMON_OBSERVATIONS}"
)


print(
    f"Ledoit-Wolf shrinkage:             "
    f"{G3_SHRINKAGE_INTENSITY:.4f}"
)


print(
    f"Covariance blend:                  "
    f"{G3_BASE_COV_WEIGHT:.0%} base / "
    f"{G3_STRESS_COV_WEIGHT:.0%} recent stress"
)


print(
    f"Mean optimizer volatility:         "
    f"{G3_STOCK_RISK_METRICS['optimizer_volatility_annual'].mean():.2%}"
)


print(
    f"Median optimizer volatility:       "
    f"{G3_STOCK_RISK_METRICS['optimizer_volatility_annual'].median():.2%}"
)


print(
    f"Minimum covariance eigenvalue:     "
    f"{G3_MIN_EIGENVALUE:.3e}"
)


print(
    f"Risk model SHA256:                 "
    f"{G3_RISK_MODEL_SHA256}"
)


# ==================================================================================================
# 45. STOCK RISK TABLE
# ==================================================================================================

print(
    "\nResearch-universe stock risk:"
)


display(

    G3_RISK_MODEL_HANDOFF[
        [
            "ticker",
            "company_name",

            "sector_ticker",
            "allocation_bucket",

            "expected_total_return_annual",

            "optimizer_volatility_annual",
            "downside_volatility_annual",

            "maximum_drawdown",

            "historical_var_99_daily",
            "historical_cvar_99_daily",

            "average_correlation",

            "expected_return_to_risk",
            "expected_return_to_downside_risk",

            "expected_return_to_risk_rank",

            "mos_threshold_met",
            "research_status",
        ]
    ]

    .sort_values(

        "expected_return_to_risk_rank",

        ascending=True,

    )

)


# ==================================================================================================
# 46. ENTRY CANDIDATE RISK
# ==================================================================================================

print(
    "\nCurrent MOS-qualified entry candidates — return / risk:"
)


if G3_ENTRY_RISK_TABLE.empty:

    print(
        "None."
    )


else:

    display(

        G3_ENTRY_RISK_TABLE[
            [
                "ticker",
                "company_name",

                "sector_ticker",

                "expected_total_return_annual",

                "optimizer_volatility_annual",
                "downside_volatility_annual",

                "maximum_drawdown",

                "historical_cvar_99_daily",

                "average_correlation",

                "expected_return_to_risk",

                "expected_return_confidence",

                "valuation_review_required",
            ]
        ]

    )


# ==================================================================================================
# 47. HIGHEST CORRELATION PAIRS
# ==================================================================================================

correlation_pairs = []


for i, ticker_i in enumerate(

    G3_RESEARCH_TICKERS

):

    for j in range(

        i + 1,

        len(
            G3_RESEARCH_TICKERS
        ),

    ):

        ticker_j = (

            G3_RESEARCH_TICKERS[
                j
            ]

        )


        correlation_pairs.append({

            "ticker_1":
                ticker_i,

            "ticker_2":
                ticker_j,

            "correlation":
                float(

                    G3_OPTIMIZER_CORRELATION.loc[
                        ticker_i,
                        ticker_j,
                    ]

                ),

        })


G3_CORRELATION_PAIRS = (

    pd.DataFrame(

        correlation_pairs

    )

    .sort_values(

        "correlation",

        ascending=False,

    )

    .reset_index(
        drop=True
    )

)


print(
    "\nHighest optimizer correlations:"
)


display(

    G3_CORRELATION_PAIRS
    .head(
        15
    )

)


# ==================================================================================================
# 48. HEALTH
# ==================================================================================================

print(
    "\nG3 health:"
)


display(
    G3_HEALTH
)


print(
    "\nG3 summary:"
)


display(
    G3_SUMMARY
)


# ==================================================================================================
# 49. PRODUCTION GATE
# ==================================================================================================

if not G3_PASSED:

    display(

        G3_REQUIRED_FAILURES

    )


    raise RuntimeError(

        "G3 PRODUCTION GATE FAILED. "
        "Do not optimize portfolio weights."

    )


print(
    "\n"
    + "=" * 145
)


print(
    "✓ G3 COMPLETE — stock covariance and downside-risk model generated."
)


print(
    "✓ Ledoit-Wolf shrinkage is used for the base covariance estimate."
)


print(
    "✓ Recent stress covariance receives a 20% overlay."
)


print(
    "✓ Final optimizer covariance is explicitly repaired to positive semidefinite."
)


print(
    "✓ Volatility, downside volatility, drawdown, historical VaR and CVaR are available for every research-eligible stock."
)


print(
    "✓ MOS-qualified entry candidates retain separate risk diagnostics."
)


print(
    "✓ Provisional specialist names remain outside the optimization risk universe."
)


print(
    "✓ G3_OPTIMIZER_COVARIANCE is the covariance handoff for G4."
)


print(
    "✓ G3_RISK_MODEL_HANDOFF is the stock-level return/risk handoff for G4."
)


print(
    "✓ Next: G4 — constrained portfolio optimization with sector caps, stock caps, turnover and transaction costs."
)


print(
    "=" * 145
)


# ===== ORIGINAL NOTEBOOK CELL 82 =====
# ==================================================================================================
# CELL G3B — MISSING-RETURN IMPUTATION AUDIT V1.0.0
# ==================================================================================================
G3B_VERSION = "1.0.0"
G3B_WARNING_THRESHOLD = float(CONFIG.get("risk", {}).get("missing_return_warning_threshold", 0.02))
if "G3_RESEARCH_RETURNS" not in globals() or "valid_day_mask" not in globals():
    raise RuntimeError("G3B requires completed G3 raw research-return state.")
G3B_PRE_FILL_RETURNS = G3_RESEARCH_RETURNS.loc[valid_day_mask].copy()
rows = []
for ticker in G3_RESEARCH_TICKERS:
    s_raw = G3B_PRE_FILL_RETURNS[ticker]
    n_rows = len(s_raw)
    n_missing = int(s_raw.isna().sum())
    share = float(n_missing / n_rows) if n_rows else np.nan
    rows.append({
        "ticker": ticker,
        "aligned_rows": n_rows,
        "imputed_zero_count": n_missing,
        "imputed_zero_share": share,
        "warning_threshold": G3B_WARNING_THRESHOLD,
        "above_warning_threshold": bool(safe_isfinite(share) and share > G3B_WARNING_THRESHOLD),
    })
G3B_IMPUTATION_AUDIT = pd.DataFrame(rows).sort_values(
    ["imputed_zero_share", "ticker"], ascending=[False, True]
).reset_index(drop=True)
G3B_MAX_IMPUTATION_SHARE = float(G3B_IMPUTATION_AUDIT["imputed_zero_share"].max() if len(G3B_IMPUTATION_AUDIT) else 0.0)
G3B_WARNING_COUNT = int(G3B_IMPUTATION_AUDIT["above_warning_threshold"].sum())
G3B_IMPUTATION_ACCEPTABLE = bool(G3B_WARNING_COUNT == 0)
G3B_IMPUTATION_AUDIT.to_csv(STOCK_OUTPUT_DIR / "g3b_missing_return_imputation_audit.csv", index=False)
print("=" * 120)
print("G3B — MISSING-RETURN IMPUTATION AUDIT")
print("=" * 120)
print(f"Warning threshold:                 {G3B_WARNING_THRESHOLD:.2%}")
print(f"Maximum ticker imputation share:   {G3B_MAX_IMPUTATION_SHARE:.2%}")
print(f"Tickers above threshold:           {G3B_WARNING_COUNT}")
display(G3B_IMPUTATION_AUDIT.head(20))
if G3B_WARNING_COUNT:
    print("⚠ Review tickers above the missing-return threshold before relying heavily on covariance estimates.")
else:
    print("✓ Missing-return imputation is below the configured threshold for every research ticker.")


# ===== ORIGINAL NOTEBOOK CELL 83 =====
# ==================================================================================================
# CELL G4A — PERSISTENT PORTFOLIO STATE MANAGER V1.0.0
# ==================================================================================================
PORTFOLIO_STATE_VERSION = "1.0.0"
PORTFOLIO_STATE_MODE = str(CONFIG.get("execution", {}).get("portfolio_state_mode", "MODEL")).upper().strip()
PORTFOLIO_ASSUME_MODEL_TARGETS_EXECUTED = bool(CONFIG.get("execution", {}).get("assume_model_targets_executed", True))
PORTFOLIO_STATE_DIR = Path(STOCK_OUTPUT_DIR) / "portfolio_state"
PORTFOLIO_STATE_DIR.mkdir(parents=True, exist_ok=True)
PORTFOLIO_ACTUAL_PATH = PORTFOLIO_STATE_DIR / "actual_holdings.csv"
PORTFOLIO_MODEL_PATH = PORTFOLIO_STATE_DIR / "model_holdings.csv"
PORTFOLIO_ACTUAL_TEMPLATE_PATH = PORTFOLIO_STATE_DIR / "actual_holdings_TEMPLATE.csv"
if not PORTFOLIO_ACTUAL_TEMPLATE_PATH.exists():
    pd.DataFrame({"ticker": ["EXAMPLE", "CASH"], "current_weight": [0.25, 0.75]}).to_csv(
        PORTFOLIO_ACTUAL_TEMPLATE_PATH, index=False
    )

def _normalize_portfolio_state(df):
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Portfolio state must be a pandas DataFrame.")
    if "ticker" not in df.columns:
        raise RuntimeError("Portfolio state requires a 'ticker' column.")
    weight_col = next((c for c in ["current_weight", "weight", "portfolio_weight", "target_weight"] if c in df.columns), None)
    if weight_col is None:
        raise RuntimeError("Portfolio state requires current_weight (or a recognized weight alias).")
    out = df[["ticker", weight_col]].copy().rename(columns={weight_col: "current_weight"})
    out = out.dropna(subset=["ticker"]).copy()
    out["ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    out = out[~out["ticker"].isin(["", "NAN", "NONE"])].copy()
    out["current_weight"] = pd.to_numeric(out["current_weight"], errors="coerce")
    out = out.dropna(subset=["current_weight"]).groupby("ticker", as_index=False)["current_weight"].sum()
    if (out["current_weight"] < -1e-10).any():
        raise RuntimeError("Negative current portfolio weight detected.")
    risky = float(out.loc[out["ticker"] != "CASH", "current_weight"].sum())
    if (out["ticker"] == "CASH").any():
        total = float(out["current_weight"].sum())
    else:
        if risky > 1.000001:
            raise RuntimeError(f"Risky portfolio weights exceed 100%: {risky:.2%}")
        out = pd.concat([out, pd.DataFrame({"ticker": ["CASH"], "current_weight": [max(0.0, 1.0-risky)]})], ignore_index=True)
        total = float(out["current_weight"].sum())
    if not np.isclose(total, 1.0, atol=1e-4, rtol=1e-4):
        raise RuntimeError(f"Portfolio-state weights must sum to 100%; found {total:.4%}.")
    return out.sort_values("ticker").reset_index(drop=True)

PORTFOLIO_STATE_IS_ACTUAL = False
PORTFOLIO_STATE_SOURCE = None
if PORTFOLIO_STATE_MODE == "REAL":
    if not PORTFOLIO_ACTUAL_PATH.exists():
        raise RuntimeError(
            "REAL portfolio mode selected but actual_holdings.csv is missing. "
            f"Copy/edit the template at: {PORTFOLIO_ACTUAL_TEMPLATE_PATH}"
        )
    CURRENT_PORTFOLIO_WEIGHTS = _normalize_portfolio_state(pd.read_csv(PORTFOLIO_ACTUAL_PATH))
    PORTFOLIO_STATE_IS_ACTUAL = True
    PORTFOLIO_STATE_SOURCE = str(PORTFOLIO_ACTUAL_PATH)
elif PORTFOLIO_STATE_MODE == "MODEL":
    if PORTFOLIO_MODEL_PATH.exists():
        CURRENT_PORTFOLIO_WEIGHTS = _normalize_portfolio_state(pd.read_csv(PORTFOLIO_MODEL_PATH))
        PORTFOLIO_STATE_SOURCE = str(PORTFOLIO_MODEL_PATH)
    else:
        CURRENT_PORTFOLIO_WEIGHTS = pd.DataFrame({"ticker": ["CASH"], "current_weight": [1.0]})
        PORTFOLIO_STATE_SOURCE = "FIRST_MODEL_RUN_ALL_CASH"
elif PORTFOLIO_STATE_MODE == "ZERO":
    CURRENT_PORTFOLIO_WEIGHTS = pd.DataFrame({"ticker": ["CASH"], "current_weight": [1.0]})
    PORTFOLIO_STATE_SOURCE = "INTENTIONAL_ZERO_PORTFOLIO"
else:
    raise RuntimeError("portfolio_state_mode must be MODEL, REAL, or ZERO.")

print("=" * 120)
print("G4A — PORTFOLIO STATE")
print("=" * 120)
print(f"Mode:                         {PORTFOLIO_STATE_MODE}")
print(f"Source:                       {PORTFOLIO_STATE_SOURCE}")
print(f"Actual holdings supplied:     {PORTFOLIO_STATE_IS_ACTUAL}")
print(f"Assume model targets executed:{PORTFOLIO_ASSUME_MODEL_TARGETS_EXECUTED}")
display(CURRENT_PORTFOLIO_WEIGHTS)


# ===== ORIGINAL NOTEBOOK CELL 84 =====
# ==================================================================================================
# SECTION G — REMAINING PORTFOLIO ENGINE
#
# G4 — CONSTRAINED PORTFOLIO OPTIMIZATION
# G5 — PORTFOLIO RISK / MONTE CARLO / RISK CONTRIBUTION
# G6 — TRADE PLAN / TRANSACTION COST / LIQUIDITY CHECK
# G7 — FINAL SECTION G FREEZE
#
# Prerequisite:
#     G3_PASSED == True
# ==================================================================================================

from pathlib import Path
import hashlib
import re
import warnings

import numpy as np
import pandas as pd
import cvxpy as cp

warnings.filterwarnings("ignore", category=FutureWarning)


# ==================================================================================================
# COMMON HELPERS
# ==================================================================================================

def g_cfg(path, default=None):
    """
    Safely read nested CONFIG values.
    Example:
        g_cfg(["portfolio", "max_stock_weight"], 0.10)
    """
    obj = globals().get("CONFIG", {})

    try:
        for key in path:
            obj = obj[key]
        return obj
    except Exception:
        return default


def g_numeric(value, default=np.nan):
    try:
        value = float(value)
        if safe_isfinite(value):
            return value
    except Exception:
        pass
    return default


def g_normalize_name(value):
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value).lower(),
    ).strip("_")


# ==================================================================================================
# GLOBAL VALIDATION
# ==================================================================================================

required_remaining_g = [
    "G3_PASSED",
    "G3_OPTIMIZER_COVARIANCE",
    "G3_STRESS_ANNUAL_COVARIANCE",
    "G3_BASE_ANNUAL_COVARIANCE",
    "G3_RESEARCH_RETURNS_ALIGNED",
    "G3_RISK_MODEL_HANDOFF",
    "G3_RESEARCH_TICKERS",
    "G1_FINAL_ALPHA_HANDOFF",
    "VALUATION_UNIVERSE_FREEZE_ID",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
]

missing = [
    x for x in required_remaining_g
    if x not in globals()
]

if missing:
    raise RuntimeError(
        "Remaining Section G requires completed G3 state. "
        f"Missing: {missing}"
    )

if not bool(G3_PASSED):
    raise RuntimeError(
        "G3 production gate did not pass."
    )


# ##################################################################################################
# ##################################################################################################
# G4 — CONSTRAINED PORTFOLIO OPTIMIZATION
# ##################################################################################################
# ##################################################################################################

G4_VERSION = "1.1.0"


# ==================================================================================================
# G4.1 CONFIGURATION
# ==================================================================================================

G4_MAX_STOCK_WEIGHT = float(
    g_cfg(
        ["portfolio", "max_stock_weight"],
        0.10,
    )
)

G4_WEIGHT_EPSILON = float(
    g_cfg(
        ["portfolio", "optimizer_weight_epsilon"],
        1e-8,
    )
)

G4_MAX_SECTOR_WEIGHT = float(
    g_cfg(
        ["portfolio", "max_sector_weight"],
        0.30,
    )
)

G4_MAX_RISKY_SECTOR_SHARE = float(
    g_cfg(
        ["portfolio", "max_risky_sector_share"],
        0.70,
    )
)

G4_MIN_ELIGIBLE_SECTORS_FOR_RISKY_CAP = int(
    g_cfg(
        ["portfolio", "min_eligible_sectors_for_risky_cap"],
        2,
    )
)

G4_MIN_CASH_WEIGHT = float(
    g_cfg(
        ["portfolio", "min_cash_weight"],
        0.00,
    )
)

G4_ALLOW_SHORT = bool(
    g_cfg(
        ["portfolio", "allow_short"],
        False,
    )
)

G4_RISK_AVERSION = float(
    g_cfg(
        ["optimizer", "risk_aversion"],
        5.0,
    )
)

G4_TURNOVER_PENALTY = float(
    g_cfg(
        ["optimizer", "turnover_penalty"],
        1.0,
    )
)

G4_TC_RATE = float(
    g_cfg(
        ["execution", "transaction_cost_rate"],
        0.001,
    )
)

G4_INITIAL_NAV = float(
    g_cfg(
        ["portfolio", "initial_nav"],
        1_000_000.0,
    )
)

G4_RISK_FREE_RATE = float(
    globals().get(
        "G2_RISK_FREE_RATE",
        globals().get(
            "F4_RISK_FREE_RATE",
            0.0,
        ),
    )
)


if G4_ALLOW_SHORT:
    raise RuntimeError(
        "This G4 implementation is long-only. "
        "CONFIG portfolio.allow_short must remain False."
    )


# ==================================================================================================
# G4.2 CURRENT / PREVIOUS PORTFOLIO WEIGHTS
# ==================================================================================================

def g4_extract_weights(obj):

    if obj is None:
        return {}

    if isinstance(obj, dict):

        return {
            str(k): float(v)
            for k, v in obj.items()
            if pd.notna(v)
        }

    if isinstance(obj, pd.Series):

        return {
            str(k): float(v)
            for k, v in obj.items()
            if pd.notna(v)
        }

    if isinstance(obj, pd.DataFrame):

        ticker_candidates = [
            "ticker",
            "symbol",
        ]

        weight_candidates = [
            "weight",
            "current_weight",
            "portfolio_weight",
            "target_weight",
        ]

        ticker_col = next(
            (
                c for c in ticker_candidates
                if c in obj.columns
            ),
            None,
        )

        weight_col = next(
            (
                c for c in weight_candidates
                if c in obj.columns
            ),
            None,
        )

        if (
            ticker_col is not None
            and weight_col is not None
        ):

            temp = obj[
                [
                    ticker_col,
                    weight_col,
                ]
            ].copy()

            temp[weight_col] = pd.to_numeric(
                temp[weight_col],
                errors="coerce",
            )

            temp = temp.dropna(
                subset=[
                    ticker_col,
                    weight_col,
                ]
            )

            return dict(
                zip(
                    temp[ticker_col].astype(str),
                    temp[weight_col].astype(float),
                )
            )

    return {}


G4_PREVIOUS_WEIGHT_SOURCE = "ZERO_INITIAL_PORTFOLIO"

G4_PREVIOUS_WEIGHT_MAP = {}


for object_name in [
    "CURRENT_PORTFOLIO_WEIGHTS",
    "PREVIOUS_PORTFOLIO_WEIGHTS",
    "PORTFOLIO_WEIGHTS",
    "CURRENT_WEIGHTS",
]:

    if object_name in globals():

        candidate = g4_extract_weights(
            globals()[object_name]
        )

        if candidate:

            G4_PREVIOUS_WEIGHT_MAP = candidate

            G4_PREVIOUS_WEIGHT_SOURCE = object_name

            break


# Remove explicit cash from risky map.
G4_PREVIOUS_CASH_EXPLICIT = None

for cash_key in [
    "CASH",
    "Cash",
    "cash",
]:

    if cash_key in G4_PREVIOUS_WEIGHT_MAP:

        G4_PREVIOUS_CASH_EXPLICIT = float(
            G4_PREVIOUS_WEIGHT_MAP.pop(
                cash_key
            )
        )

        break


# ==================================================================================================
# G4.3 VALIDATE PREVIOUS WEIGHTS
# ==================================================================================================

for ticker, weight in G4_PREVIOUS_WEIGHT_MAP.items():

    if weight < -1e-12:

        raise RuntimeError(
            f"Negative previous weight detected: "
            f"{ticker}={weight:.4f}"
        )


G4_PREVIOUS_RISKY_TOTAL = float(
    sum(
        G4_PREVIOUS_WEIGHT_MAP.values()
    )
)


if G4_PREVIOUS_RISKY_TOTAL > 1.000001:

    raise RuntimeError(
        "Previous risky portfolio weights exceed 100%: "
        f"{G4_PREVIOUS_RISKY_TOTAL:.2%}"
    )


if G4_PREVIOUS_CASH_EXPLICIT is None:

    G4_PREVIOUS_CASH_WEIGHT = max(
        0.0,
        1.0 - G4_PREVIOUS_RISKY_TOTAL,
    )

else:

    G4_PREVIOUS_CASH_WEIGHT = (
        G4_PREVIOUS_CASH_EXPLICIT
    )


# ==================================================================================================
# G4.4 BUILD OPTIMIZATION INPUT
# ==================================================================================================

G4_RESEARCH = (
    G3_RISK_MODEL_HANDOFF
    .copy()
)

G4_RESEARCH["ticker"] = (
    G4_RESEARCH["ticker"]
    .astype(str)
)


G4_RESEARCH_MAP = (
    G4_RESEARCH
    .set_index("ticker")
)


# Include:
#   1. all current MOS-qualified names
#   2. existing research-eligible holdings, even if MOS no longer met
#
# Existing WATCHLIST holdings may be held/reduced but cannot be increased.
G4_OPTIMIZER_TICKERS = []

for ticker in G3_RESEARCH_TICKERS:

    row = G4_RESEARCH_MAP.loc[ticker]

    new_entry = bool(
        row[
            "new_entry_optimizer_eligible"
        ]
    )

    previous_weight = float(
        G4_PREVIOUS_WEIGHT_MAP.get(
            ticker,
            0.0,
        )
    )

    if (
        new_entry
        or
        previous_weight > 1e-12
    ):

        G4_OPTIMIZER_TICKERS.append(
            ticker
        )


G4_OPTIMIZER_TICKERS = sorted(
    set(
        G4_OPTIMIZER_TICKERS
    )
)


if len(G4_OPTIMIZER_TICKERS) == 0:

    # All-cash portfolio.
    G4_OPTIMIZER_STATUS = "ALL_CASH_NO_ELIGIBLE_ASSETS"

else:

    G4_OPTIMIZER_STATUS = "READY"


# ==================================================================================================
# G4.5 EXPECTED EXCESS RETURNS
# ==================================================================================================

G4_EXPECTED_RETURN_VECTOR = np.array(
    [
        float(
            G4_RESEARCH_MAP.loc[
                ticker,
                "expected_total_return_annual",
            ]
        )
        for ticker
        in G4_OPTIMIZER_TICKERS
    ],
    dtype=float,
)


G4_EXPECTED_EXCESS_VECTOR = (
    G4_EXPECTED_RETURN_VECTOR
    -
    G4_RISK_FREE_RATE
)


# ==================================================================================================
# G4.6 COVARIANCE SUBSET
# ==================================================================================================

if G4_OPTIMIZER_TICKERS:

    G4_COVARIANCE = (
        G3_OPTIMIZER_COVARIANCE.loc[
            G4_OPTIMIZER_TICKERS,
            G4_OPTIMIZER_TICKERS,
        ]
        .copy()
    )

else:

    G4_COVARIANCE = pd.DataFrame()


# ==================================================================================================
# G4.7 PREVIOUS WEIGHT VECTOR
# ==================================================================================================

G4_PREVIOUS_VECTOR = np.array(
    [
        float(
            G4_PREVIOUS_WEIGHT_MAP.get(
                ticker,
                0.0,
            )
        )
        for ticker
        in G4_OPTIMIZER_TICKERS
    ],
    dtype=float,
)


# ==================================================================================================
# G4.8 SECTOR MAP
# ==================================================================================================

G4_SECTOR_MAP = (
    G4_RESEARCH[
        [
            "ticker",
            "sector_ticker",
        ]
    ]
    .drop_duplicates("ticker")
    .set_index("ticker")[
        "sector_ticker"
    ]
    .to_dict()
)


# ==================================================================================================
# G4.9 OPTIMIZATION
# ==================================================================================================

G4_ELIGIBLE_SECTOR_COUNT = 0
G4_RISKY_SECTOR_SHARE_CAP_APPLICABLE = False

if G4_OPTIMIZER_TICKERS:

    n_assets = len(
        G4_OPTIMIZER_TICKERS
    )

    w = cp.Variable(
        n_assets
    )

    covariance_psd = cp.psd_wrap(
        G4_COVARIANCE.values
    )

    expected_excess_term = (
        G4_EXPECTED_EXCESS_VECTOR
        @
        w
    )

    risk_term = cp.quad_form(
        w,
        covariance_psd,
    )

    turnover_term = cp.norm1(
        w
        -
        G4_PREVIOUS_VECTOR
    )

    objective = cp.Maximize(

        expected_excess_term

        -

        (
            G4_RISK_AVERSION
            /
            2.0
        )
        *
        risk_term

        -

        G4_TURNOVER_PENALTY
        *
        G4_TC_RATE
        *
        turnover_term

    )


    constraints = [

        w >= 0.0,

        w <= G4_MAX_STOCK_WEIGHT,

        cp.sum(w)
        <=
        (
            1.0
            -
            G4_MIN_CASH_WEIGHT
        ),

    ]


    # ------------------------------------------------------------------
    # MOS governance:
    #
    # New entry eligible:
    #     may increase up to max stock weight.
    #
    # Existing but not currently MOS eligible:
    #     may only HOLD or REDUCE, never add.
    # ------------------------------------------------------------------

    for i, ticker in enumerate(
        G4_OPTIMIZER_TICKERS
    ):

        row = (
            G4_RESEARCH_MAP.loc[
                ticker
            ]
        )

        new_entry = bool(
            row[
                "new_entry_optimizer_eligible"
            ]
        )

        previous_weight = float(
            G4_PREVIOUS_WEIGHT_MAP.get(
                ticker,
                0.0,
            )
        )

        if (
            not new_entry
            and
            previous_weight > 0
        ):

            constraints.append(

                w[i]
                <=
                min(
                    previous_weight,
                    G4_MAX_STOCK_WEIGHT,
                )

            )


    # ------------------------------------------------------------------
    # Sector caps.
    # ------------------------------------------------------------------

    sectors = sorted(
        set(
            G4_SECTOR_MAP[
                ticker
            ]
            for ticker
            in G4_OPTIMIZER_TICKERS
        )
    )

    G4_ELIGIBLE_SECTOR_COUNT = len(sectors)
    G4_RISKY_SECTOR_SHARE_CAP_APPLICABLE = bool(
        G4_ELIGIBLE_SECTOR_COUNT >= G4_MIN_ELIGIBLE_SECTORS_FOR_RISKY_CAP
        and G4_MAX_RISKY_SECTOR_SHARE < 1.0
    )


    for sector in sectors:

        indices = [
            i
            for i, ticker
            in enumerate(
                G4_OPTIMIZER_TICKERS
            )
            if G4_SECTOR_MAP[
                ticker
            ] == sector
        ]

        constraints.append(

            cp.sum(
                w[
                    indices
                ]
            )
            <=
            G4_MAX_SECTOR_WEIGHT

        )

        if G4_RISKY_SECTOR_SHARE_CAP_APPLICABLE:
            constraints.append(
                cp.sum(w[indices]) <= G4_MAX_RISKY_SECTOR_SHARE * cp.sum(w)
            )


    problem = cp.Problem(
        objective,
        constraints,
    )


    installed_solvers = set(
        cp.installed_solvers()
    )


    preferred_solvers = [
        "CLARABEL",
        "OSQP",
        "ECOS",
        "SCS",
    ]


    G4_SOLVER_USED = None
    G4_SOLVE_ERRORS = []


    for solver in preferred_solvers:

        if solver not in installed_solvers:
            continue

        try:

            problem.solve(
                solver=solver,
                verbose=False,
            )

            if problem.status in [
                cp.OPTIMAL,
                cp.OPTIMAL_INACCURATE,
            ]:

                G4_SOLVER_USED = solver

                break

        except Exception as exc:

            G4_SOLVE_ERRORS.append(
                f"{solver}: {exc}"
            )


    if G4_SOLVER_USED is None:

        raise RuntimeError(
            "G4 optimization failed. "
            f"Status={problem.status}; "
            f"Solver errors={G4_SOLVE_ERRORS}"
        )


    G4_RAW_TARGET_VECTOR = np.array(
        w.value,
        dtype=float,
    )


    # Remove tiny numerical negatives.
    G4_RAW_TARGET_VECTOR = np.where(
        G4_RAW_TARGET_VECTOR < 1e-10,
        0.0,
        G4_RAW_TARGET_VECTOR,
    )


else:

    G4_SOLVER_USED = "ALL_CASH"
    G4_RAW_TARGET_VECTOR = np.array(
        [],
        dtype=float,
    )


# ==================================================================================================
# G4.10 BUILD TARGET WEIGHT MAP
# ==================================================================================================

G4_TARGET_WEIGHT_MAP = {
    ticker: 0.0
    for ticker
    in G3_RESEARCH_TICKERS
}


for ticker, weight in zip(
    G4_OPTIMIZER_TICKERS,
    G4_RAW_TARGET_VECTOR,
):

    G4_TARGET_WEIGHT_MAP[
        ticker
    ] = clean_optimizer_weight(
        weight,
        epsilon=G4_WEIGHT_EPSILON,
    )


G4_TOTAL_RISKY_WEIGHT = float(
    sum(
        G4_TARGET_WEIGHT_MAP.values()
    )
)


G4_CASH_WEIGHT = max(
    0.0,
    1.0 - G4_TOTAL_RISKY_WEIGHT,
)


# ==================================================================================================
# G4.11 FULL PORTFOLIO WEIGHT TABLE
# ==================================================================================================

G4_PORTFOLIO_WEIGHTS = (
    G4_RESEARCH[
        [
            "ticker",
            "company_name",
            "sector_ticker",
            "allocation_bucket",
            "expected_total_return_annual",
            "expected_return_confidence",
            "new_entry_optimizer_eligible",
            "research_optimizer_eligible",
            "mos_threshold_met",
            "research_status",
        ]
    ]
    .copy()
)


G4_PORTFOLIO_WEIGHTS[
    "previous_weight"
] = (
    G4_PORTFOLIO_WEIGHTS[
        "ticker"
    ]
    .map(
        G4_PREVIOUS_WEIGHT_MAP
    )
    .fillna(0.0)
)


G4_PORTFOLIO_WEIGHTS[
    "target_weight"
] = (
    G4_PORTFOLIO_WEIGHTS[
        "ticker"
    ]
    .map(
        G4_TARGET_WEIGHT_MAP
    )
    .fillna(0.0)
)


G4_PORTFOLIO_WEIGHTS[
    "delta_weight"
] = (
    G4_PORTFOLIO_WEIGHTS[
        "target_weight"
    ]
    -
    G4_PORTFOLIO_WEIGHTS[
        "previous_weight"
    ]
)


# ==================================================================================================
# G4.12 SECTOR EXPOSURE
# ==================================================================================================

G4_SECTOR_EXPOSURE = (
    G4_PORTFOLIO_WEIGHTS
    .groupby(
        "sector_ticker",
        as_index=False,
    )
    .agg(
        previous_weight=(
            "previous_weight",
            "sum",
        ),
        target_weight=(
            "target_weight",
            "sum",
        ),
    )
)


G4_SECTOR_EXPOSURE[
    "sector_cap"
] = G4_MAX_SECTOR_WEIGHT


G4_SECTOR_EXPOSURE[
    "cap_headroom"
] = (
    G4_MAX_SECTOR_WEIGHT
    -
    G4_SECTOR_EXPOSURE[
        "target_weight"
    ]
)

G4_SECTOR_EXPOSURE["risky_sleeve_share"] = np.where(
    G4_TOTAL_RISKY_WEIGHT > 1e-12,
    G4_SECTOR_EXPOSURE["target_weight"] / G4_TOTAL_RISKY_WEIGHT,
    0.0,
)
G4_SECTOR_EXPOSURE["max_risky_sector_share"] = G4_MAX_RISKY_SECTOR_SHARE
G4_MAX_REALIZED_RISKY_SECTOR_SHARE = float(
    G4_SECTOR_EXPOSURE["risky_sleeve_share"].max() if len(G4_SECTOR_EXPOSURE) else 0.0
)
G4_RISKY_SECTOR_SHARE_VALID = bool(
    (not G4_RISKY_SECTOR_SHARE_CAP_APPLICABLE)
    or G4_MAX_REALIZED_RISKY_SECTOR_SHARE <= G4_MAX_RISKY_SECTOR_SHARE + 1e-7
)


# ==================================================================================================
# G4.13 TURNOVER INCLUDING FORCED EXITS
# ==================================================================================================

all_turnover_tickers = set(
    G4_PREVIOUS_WEIGHT_MAP.keys()
) | set(
    G4_TARGET_WEIGHT_MAP.keys()
)


G4_TOTAL_TURNOVER = float(
    sum(
        abs(
            float(
                G4_TARGET_WEIGHT_MAP.get(
                    ticker,
                    0.0,
                )
            )
            -
            float(
                G4_PREVIOUS_WEIGHT_MAP.get(
                    ticker,
                    0.0,
                )
            )
        )
        for ticker
        in all_turnover_tickers
    )
)


G4_ESTIMATED_TC_PCT = (
    G4_TOTAL_TURNOVER
    *
    G4_TC_RATE
)


G4_ESTIMATED_TC_DOLLARS = (
    G4_ESTIMATED_TC_PCT
    *
    G4_INITIAL_NAV
)


# ==================================================================================================
# G4.14 PORTFOLIO EXPECTED RETURN / VOLATILITY
# ==================================================================================================

G4_TARGET_VECTOR_RESEARCH = np.array(
    [
        G4_TARGET_WEIGHT_MAP.get(
            ticker,
            0.0,
        )
        for ticker
        in G3_RESEARCH_TICKERS
    ],
    dtype=float,
)


G4_MU_RESEARCH = np.array(
    [
        float(
            G4_RESEARCH_MAP.loc[
                ticker,
                "expected_total_return_annual",
            ]
        )
        for ticker
        in G3_RESEARCH_TICKERS
    ],
    dtype=float,
)


G4_EXPECTED_RETURN_GROSS = float(

    G4_CASH_WEIGHT
    *
    G4_RISK_FREE_RATE

    +

    G4_TARGET_VECTOR_RESEARCH
    @
    G4_MU_RESEARCH

)


G4_EXPECTED_RETURN_NET_FIRST_YEAR = (
    G4_EXPECTED_RETURN_GROSS
    -
    G4_ESTIMATED_TC_PCT
)


G4_VARIANCE = float(

    G4_TARGET_VECTOR_RESEARCH

    @
    G3_OPTIMIZER_COVARIANCE.loc[
        G3_RESEARCH_TICKERS,
        G3_RESEARCH_TICKERS,
    ].values

    @
    G4_TARGET_VECTOR_RESEARCH

)


G4_VOLATILITY = float(
    np.sqrt(
        max(
            G4_VARIANCE,
            0.0,
        )
    )
)


G4_EXPECTED_SHARPE = (
    (
        G4_EXPECTED_RETURN_GROSS
        -
        G4_RISK_FREE_RATE
    )
    /
    G4_VOLATILITY
    if G4_VOLATILITY > 0
    else np.nan
)


# ==================================================================================================
# G4.15 HARD CONSTRAINT VALIDATION
# ==================================================================================================

G4_MAX_REALIZED_STOCK_WEIGHT = (
    G4_PORTFOLIO_WEIGHTS[
        "target_weight"
    ].max()
)


G4_MAX_REALIZED_SECTOR_WEIGHT = (
    G4_SECTOR_EXPOSURE[
        "target_weight"
    ].max()
)


G4_STOCK_CAP_VALID = bool(
    G4_MAX_REALIZED_STOCK_WEIGHT
    <=
    G4_MAX_STOCK_WEIGHT
    +
    1e-7
)


G4_SECTOR_CAP_VALID = bool(
    G4_MAX_REALIZED_SECTOR_WEIGHT
    <=
    G4_MAX_SECTOR_WEIGHT
    +
    1e-7
)


G4_CASH_VALID = bool(
    G4_CASH_WEIGHT
    >=
    G4_MIN_CASH_WEIGHT
    -
    1e-7
)


G4_WEIGHT_IDENTITY_VALID = bool(
    np.isclose(
        G4_TOTAL_RISKY_WEIGHT
        +
        G4_CASH_WEIGHT,
        1.0,
        atol=1e-7,
        rtol=1e-7,
    )
)


# No new position without MOS.
G4_UNAUTHORIZED_NEW_POSITIONS = (
    G4_PORTFOLIO_WEIGHTS[
        (
            G4_PORTFOLIO_WEIGHTS[
                "previous_weight"
            ]
            <=
            1e-12
        )
        &
        (
            G4_PORTFOLIO_WEIGHTS[
                "target_weight"
            ]
            >
            1e-8
        )
        &
        (
            ~
            G4_PORTFOLIO_WEIGHTS[
                "new_entry_optimizer_eligible"
            ]
        )
    ]
    .copy()
)


G4_MOS_VALID = bool(
    G4_UNAUTHORIZED_NEW_POSITIONS.empty
)


# ==================================================================================================
# G4.16 HEALTH
# ==================================================================================================

G4_HEALTH = pd.DataFrame([
    {
        "check": "Optimization solved",
        "passed": G4_SOLVER_USED is not None,
        "required": True,
        "detail": f"solver={G4_SOLVER_USED}",
    },
    {
        "check": "Portfolio weights sum to 100% including cash",
        "passed": G4_WEIGHT_IDENTITY_VALID,
        "required": True,
        "detail": (
            f"risky={G4_TOTAL_RISKY_WEIGHT:.2%}; "
            f"cash={G4_CASH_WEIGHT:.2%}"
        ),
    },
    {
        "check": "Single-stock cap respected",
        "passed": G4_STOCK_CAP_VALID,
        "required": True,
        "detail": (
            f"max={G4_MAX_REALIZED_STOCK_WEIGHT:.2%}; "
            f"cap={G4_MAX_STOCK_WEIGHT:.2%}"
        ),
    },
    {
        "check": "Sector cap respected",
        "passed": G4_SECTOR_CAP_VALID,
        "required": True,
        "detail": (
            f"max={G4_MAX_REALIZED_SECTOR_WEIGHT:.2%}; "
            f"cap={G4_MAX_SECTOR_WEIGHT:.2%}"
        ),
    },
    {
        "check": "Risky-sleeve sector concentration governed",
        "passed": G4_RISKY_SECTOR_SHARE_VALID,
        "required": True,
        "detail": (
            f"max_risky_sector_share={G4_MAX_REALIZED_RISKY_SECTOR_SHARE:.2%}; "
            f"cap={G4_MAX_RISKY_SECTOR_SHARE:.2%}; "
            f"eligible_sectors={G4_ELIGIBLE_SECTOR_COUNT}; "
            f"binding={G4_RISKY_SECTOR_SHARE_CAP_APPLICABLE}"
        ),
    },
    {
        "check": "Minimum cash rule respected",
        "passed": G4_CASH_VALID,
        "required": True,
        "detail": (
            f"cash={G4_CASH_WEIGHT:.2%}; "
            f"minimum={G4_MIN_CASH_WEIGHT:.2%}"
        ),
    },
    {
        "check": "No new position violates MOS entry governance",
        "passed": G4_MOS_VALID,
        "required": True,
        "detail": (
            f"violations="
            f"{len(G4_UNAUTHORIZED_NEW_POSITIONS)}"
        ),
    },
    {
        "check": "Portfolio remains long-only",
        "passed": bool(
            (
                G4_PORTFOLIO_WEIGHTS[
                    "target_weight"
                ]
                >=
                -1e-10
            ).all()
        ),
        "required": True,
        "detail": "long_only=True",
    },
])


G4_HEALTH["status"] = np.where(
    G4_HEALTH["passed"],
    "✓ PASS",
    "✗ FAIL",
)


G4_REQUIRED_FAILURES = (
    G4_HEALTH[
        G4_HEALTH["required"]
        &
        ~G4_HEALTH["passed"]
    ]
)


G4_PASSED = (
    G4_REQUIRED_FAILURES.empty
)


if not G4_PASSED:

    display(
        G4_REQUIRED_FAILURES
    )

    raise RuntimeError(
        "G4 PRODUCTION GATE FAILED."
    )


# ==================================================================================================
# G4.17 SUMMARY
# ==================================================================================================

G4_SUMMARY = pd.DataFrame([{
    "g4_version": G4_VERSION,
    "previous_weight_source":
        G4_PREVIOUS_WEIGHT_SOURCE,
    "solver_used":
        G4_SOLVER_USED,
    "optimizer_assets":
        len(
            G4_OPTIMIZER_TICKERS
        ),
    "risk_aversion":
        G4_RISK_AVERSION,
    "turnover_penalty":
        G4_TURNOVER_PENALTY,
    "max_stock_weight":
        G4_MAX_STOCK_WEIGHT,
    "max_sector_weight":
        G4_MAX_SECTOR_WEIGHT,
    "max_risky_sector_share":
        G4_MAX_RISKY_SECTOR_SHARE,
    "eligible_sector_count":
        G4_ELIGIBLE_SECTOR_COUNT,
    "risky_sector_share_cap_applicable":
        G4_RISKY_SECTOR_SHARE_CAP_APPLICABLE,
    "max_realized_risky_sector_share":
        G4_MAX_REALIZED_RISKY_SECTOR_SHARE,
    "minimum_cash_weight":
        G4_MIN_CASH_WEIGHT,
    "target_risky_weight":
        G4_TOTAL_RISKY_WEIGHT,
    "target_cash_weight":
        G4_CASH_WEIGHT,
    "turnover":
        G4_TOTAL_TURNOVER,
    "estimated_transaction_cost_pct":
        G4_ESTIMATED_TC_PCT,
    "estimated_transaction_cost_dollars":
        G4_ESTIMATED_TC_DOLLARS,
    "expected_return_gross":
        G4_EXPECTED_RETURN_GROSS,
    "expected_return_net_first_year":
        G4_EXPECTED_RETURN_NET_FIRST_YEAR,
    "expected_volatility":
        G4_VOLATILITY,
    "expected_sharpe":
        G4_EXPECTED_SHARPE,
    "g4_passed":
        G4_PASSED,
}])


# ==================================================================================================
# G4.18 SAVE
# ==================================================================================================

G4_PORTFOLIO_WEIGHTS.to_parquet(
    STOCK_MODEL_DIR
    /
    "g4_target_portfolio_weights.parquet",
    index=False,
)

G4_PORTFOLIO_WEIGHTS.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g4_target_portfolio_weights.csv",
    index=False,
)

G4_SECTOR_EXPOSURE.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g4_sector_exposure.csv",
    index=False,
)

G4_HEALTH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g4_health.csv",
    index=False,
)

G4_SUMMARY.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g4_summary.csv",
    index=False,
)


# ##################################################################################################
# ##################################################################################################
# G5 — PORTFOLIO RISK / MONTE CARLO / RISK CONTRIBUTION
# ##################################################################################################
# ##################################################################################################

G5_VERSION = "1.0.0"

G5_MONTE_CARLO_SIMULATIONS = int(cfg(["risk", "gaussian_mc_simulations"], 50_000))

G5_RANDOM_SEED = int(
    g_cfg(
        ["system", "random_seed"],
        42,
    )
)

G5_TRADING_DAYS = int(
    globals().get(
        "G3_TRADING_DAYS",
        252,
    )
)

G5_VAR_CONFIDENCE = float(cfg(["risk", "var_confidence"], 0.99))


# ==================================================================================================
# G5.1 PORTFOLIO WEIGHTS ALIGNED TO RISK MODEL
# ==================================================================================================

G5_WEIGHT_VECTOR = np.array(
    [
        G4_TARGET_WEIGHT_MAP.get(
            ticker,
            0.0,
        )
        for ticker
        in G3_RESEARCH_TICKERS
    ],
    dtype=float,
)


G5_EXPECTED_RETURN_VECTOR = np.array(
    [
        float(
            G4_RESEARCH_MAP.loc[
                ticker,
                "expected_total_return_annual",
            ]
        )
        for ticker
        in G3_RESEARCH_TICKERS
    ],
    dtype=float,
)


# ==================================================================================================
# G5.2 PORTFOLIO EXPECTED RETURN / VOL
# ==================================================================================================

G5_GROSS_EXPECTED_RETURN = float(

    G4_CASH_WEIGHT
    *
    G4_RISK_FREE_RATE

    +

    G5_WEIGHT_VECTOR
    @
    G5_EXPECTED_RETURN_VECTOR

)


G5_NET_FIRST_YEAR_EXPECTED_RETURN = (
    G5_GROSS_EXPECTED_RETURN
    -
    G4_ESTIMATED_TC_PCT
)


G5_PORTFOLIO_VARIANCE = float(

    G5_WEIGHT_VECTOR
    @
    G3_OPTIMIZER_COVARIANCE.values
    @
    G5_WEIGHT_VECTOR

)


G5_PORTFOLIO_VOLATILITY = float(
    np.sqrt(
        max(
            G5_PORTFOLIO_VARIANCE,
            0.0,
        )
    )
)


# ==================================================================================================
# G5.3 STRESS VOLATILITY
# ==================================================================================================

G5_BASE_VOLATILITY = float(
    np.sqrt(
        max(
            float(
                G5_WEIGHT_VECTOR
                @
                G3_BASE_ANNUAL_COVARIANCE.values
                @
                G5_WEIGHT_VECTOR
            ),
            0.0,
        )
    )
)


G5_STRESS_VOLATILITY = float(
    np.sqrt(
        max(
            float(
                G5_WEIGHT_VECTOR
                @
                G3_STRESS_ANNUAL_COVARIANCE.values
                @
                G5_WEIGHT_VECTOR
            ),
            0.0,
        )
    )
)


G5_STRESS_VOL_MULTIPLE = (
    G5_STRESS_VOLATILITY
    /
    G5_BASE_VOLATILITY
    if G5_BASE_VOLATILITY > 0
    else np.nan
)


# ==================================================================================================
# G5.4 HISTORICAL DAILY PORTFOLIO RETURN
# ==================================================================================================

G5_PORTFOLIO_DAILY_RETURNS = (
    G3_RESEARCH_RETURNS_ALIGNED[
        G3_RESEARCH_TICKERS
    ].values
    @
    G5_WEIGHT_VECTOR
)


# Daily cash yield approximation.
G5_DAILY_CASH_RETURN = (
    (
        1.0
        +
        G4_RISK_FREE_RATE
    )
    **
    (
        1.0
        /
        G5_TRADING_DAYS
    )
    -
    1.0
)


G5_PORTFOLIO_DAILY_RETURNS = (
    G5_PORTFOLIO_DAILY_RETURNS
    +
    G4_CASH_WEIGHT
    *
    G5_DAILY_CASH_RETURN
)


G5_PORTFOLIO_DAILY_RETURNS = pd.Series(
    G5_PORTFOLIO_DAILY_RETURNS,
    index=
        G3_RESEARCH_RETURNS_ALIGNED.index,
    name=
        "portfolio_return",
)


# ==================================================================================================
# G5.5 HISTORICAL DOWNSIDE VOLATILITY
# ==================================================================================================

downside = np.minimum(
    G5_PORTFOLIO_DAILY_RETURNS.values,
    0.0,
)


G5_DOWNSIDE_VOLATILITY = float(
    np.sqrt(
        np.mean(
            downside ** 2
        )
    )
    *
    np.sqrt(
        G5_TRADING_DAYS
    )
)


# ==================================================================================================
# G5.6 HISTORICAL MAXIMUM DRAWDOWN
# ==================================================================================================

wealth = (
    (
        1.0
        +
        G5_PORTFOLIO_DAILY_RETURNS
    )
    .cumprod()
)


running_peak = (
    wealth.cummax()
)


drawdown = (
    wealth
    /
    running_peak
    -
    1.0
)


G5_MAX_DRAWDOWN = float(
    drawdown.min()
)


# ==================================================================================================
# G5.7 HISTORICAL DAILY VAR / CVAR
# ==================================================================================================

losses = (
    -
    G5_PORTFOLIO_DAILY_RETURNS
)


G5_HISTORICAL_VAR_99_DAILY = float(
    np.quantile(
        losses,
        G5_VAR_CONFIDENCE,
    )
)


tail_losses = losses[
    losses
    >=
    G5_HISTORICAL_VAR_99_DAILY
]


G5_HISTORICAL_CVAR_99_DAILY = float(
    tail_losses.mean()
    if len(tail_losses) > 0
    else G5_HISTORICAL_VAR_99_DAILY
)


# ==================================================================================================
# G5.8 SHARPE / SORTINO / CALMAR
# ==================================================================================================

G5_EXPECTED_EXCESS_RETURN = (
    G5_GROSS_EXPECTED_RETURN
    -
    G4_RISK_FREE_RATE
)


G5_EXPECTED_SHARPE = (
    G5_EXPECTED_EXCESS_RETURN
    /
    G5_PORTFOLIO_VOLATILITY
    if G5_PORTFOLIO_VOLATILITY > 0
    else np.nan
)


G5_EXPECTED_SORTINO = (
    G5_EXPECTED_EXCESS_RETURN
    /
    G5_DOWNSIDE_VOLATILITY
    if G5_DOWNSIDE_VOLATILITY > 0
    else np.nan
)


G5_EXPECTED_CALMAR = (
    G5_GROSS_EXPECTED_RETURN
    /
    abs(
        G5_MAX_DRAWDOWN
    )
    if G5_MAX_DRAWDOWN < 0
    else np.nan
)


# ==================================================================================================
# G5.9 RISK CONTRIBUTION
# ==================================================================================================

if G5_PORTFOLIO_VOLATILITY > 0:

    marginal_risk = (
        G3_OPTIMIZER_COVARIANCE.values
        @
        G5_WEIGHT_VECTOR
    ) / G5_PORTFOLIO_VOLATILITY


    component_risk = (
        G5_WEIGHT_VECTOR
        *
        marginal_risk
    )


    risk_contribution_share = (
        component_risk
        /
        G5_PORTFOLIO_VOLATILITY
    )

else:

    marginal_risk = np.zeros_like(
        G5_WEIGHT_VECTOR
    )

    component_risk = np.zeros_like(
        G5_WEIGHT_VECTOR
    )

    risk_contribution_share = np.zeros_like(
        G5_WEIGHT_VECTOR
    )


G5_RISK_CONTRIBUTION = pd.DataFrame({
    "ticker":
        G3_RESEARCH_TICKERS,
    "weight":
        G5_WEIGHT_VECTOR,
    "marginal_risk":
        marginal_risk,
    "component_risk":
        component_risk,
    "risk_contribution_share":
        risk_contribution_share,
})


G5_RISK_CONTRIBUTION = (
    G5_RISK_CONTRIBUTION[
        G5_RISK_CONTRIBUTION[
            "weight"
        ]
        >
        1e-10
    ]
    .copy()
    .sort_values(
        "risk_contribution_share",
        ascending=False,
    )
    .reset_index(
        drop=True,
    )
)


# ==================================================================================================
# G5.10 MONTE CARLO
# ==================================================================================================

rng = np.random.default_rng(
    G5_RANDOM_SEED
)


if len(
    G3_RESEARCH_TICKERS
) > 0:

    simulated_equity_returns = rng.multivariate_normal(
        mean=
            G5_EXPECTED_RETURN_VECTOR,
        cov=
            G3_OPTIMIZER_COVARIANCE.values,
        size=
            G5_MONTE_CARLO_SIMULATIONS,
        check_valid=
            "ignore",
    )


    G5_MONTE_CARLO_PORTFOLIO_RETURNS = (
        simulated_equity_returns
        @
        G5_WEIGHT_VECTOR
        +
        G4_CASH_WEIGHT
        *
        G4_RISK_FREE_RATE
        -
        G4_ESTIMATED_TC_PCT
    )

else:

    G5_MONTE_CARLO_PORTFOLIO_RETURNS = np.full(
        G5_MONTE_CARLO_SIMULATIONS,
        G4_RISK_FREE_RATE,
    )


# ==================================================================================================
# G5.11 MONTE CARLO STATISTICS
# ==================================================================================================

G5_MC_MEAN = float(
    np.mean(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS
    )
)


G5_MC_MEDIAN = float(
    np.median(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS
    )
)


G5_MC_STD = float(
    np.std(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS,
        ddof=1,
    )
)


G5_MC_P01 = float(
    np.quantile(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS,
        0.01,
    )
)


G5_MC_P05 = float(
    np.quantile(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS,
        0.05,
    )
)


G5_MC_P50 = float(
    np.quantile(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS,
        0.50,
    )
)


G5_MC_P95 = float(
    np.quantile(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS,
        0.95,
    )
)


G5_MC_P99 = float(
    np.quantile(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS,
        0.99,
    )
)


G5_MC_PROBABILITY_OF_LOSS = float(
    np.mean(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS
        <
        0.0
    )
)


G5_MC_PROBABILITY_BELOW_CASH = float(
    np.mean(
        G5_MONTE_CARLO_PORTFOLIO_RETURNS
        <
        G4_RISK_FREE_RATE
    )
)


G5_MC_VAR_99 = max(
    0.0,
    -
    G5_MC_P01,
)


worst_one_percent = (
    G5_MONTE_CARLO_PORTFOLIO_RETURNS[
        G5_MONTE_CARLO_PORTFOLIO_RETURNS
        <=
        G5_MC_P01
    ]
)


G5_MC_CVAR_99 = max(
    0.0,
    -
    float(
        worst_one_percent.mean()
    ),
)


# ==================================================================================================
# G5.12 PORTFOLIO RISK SUMMARY
# ==================================================================================================

G5_PORTFOLIO_RISK_SUMMARY = pd.DataFrame([{
    "g5_version":
        G5_VERSION,

    "expected_return_gross":
        G5_GROSS_EXPECTED_RETURN,

    "expected_return_net_first_year":
        G5_NET_FIRST_YEAR_EXPECTED_RETURN,

    "expected_excess_return":
        G5_EXPECTED_EXCESS_RETURN,

    "optimizer_volatility":
        G5_PORTFOLIO_VOLATILITY,

    "base_volatility":
        G5_BASE_VOLATILITY,

    "stress_volatility":
        G5_STRESS_VOLATILITY,

    "stress_vol_multiple":
        G5_STRESS_VOL_MULTIPLE,

    "downside_volatility":
        G5_DOWNSIDE_VOLATILITY,

    "historical_max_drawdown":
        G5_MAX_DRAWDOWN,

    "historical_var_99_daily":
        G5_HISTORICAL_VAR_99_DAILY,

    "historical_cvar_99_daily":
        G5_HISTORICAL_CVAR_99_DAILY,

    "expected_sharpe":
        G5_EXPECTED_SHARPE,

    "expected_sortino":
        G5_EXPECTED_SORTINO,

    "expected_calmar":
        G5_EXPECTED_CALMAR,

    "monte_carlo_simulations":
        G5_MONTE_CARLO_SIMULATIONS,

    "mc_mean_return":
        G5_MC_MEAN,

    "mc_median_return":
        G5_MC_MEDIAN,

    "mc_1pct":
        G5_MC_P01,

    "mc_5pct":
        G5_MC_P05,

    "mc_95pct":
        G5_MC_P95,

    "mc_99pct":
        G5_MC_P99,

    "mc_probability_of_loss":
        G5_MC_PROBABILITY_OF_LOSS,

    "mc_probability_below_cash":
        G5_MC_PROBABILITY_BELOW_CASH,

    "mc_var_99":
        G5_MC_VAR_99,

    "mc_cvar_99":
        G5_MC_CVAR_99,
}])


# ==================================================================================================
# G5.13 HEALTH
# ==================================================================================================

G5_HEALTH = pd.DataFrame([
    {
        "check":
            "Portfolio volatility is finite",
        "passed":
            safe_isfinite(
                G5_PORTFOLIO_VOLATILITY
            ),
        "required":
            True,
        "detail":
            f"vol={G5_PORTFOLIO_VOLATILITY:.2%}",
    },
    {
        "check":
            "Portfolio volatility is non-negative",
        "passed":
            G5_PORTFOLIO_VOLATILITY >= 0,
        "required":
            True,
        "detail":
            f"vol={G5_PORTFOLIO_VOLATILITY:.2%}",
    },
    {
        "check":
            "Downside volatility is finite",
        "passed":
            safe_isfinite(
                G5_DOWNSIDE_VOLATILITY
            ),
        "required":
            True,
        "detail":
            (
                f"downside_vol="
                f"{G5_DOWNSIDE_VOLATILITY:.2%}"
            ),
    },
    {
        "check":
            "Historical VaR/CVaR are finite",
        "passed":
            bool(
                safe_isfinite(
                    G5_HISTORICAL_VAR_99_DAILY
                )
                and
                safe_isfinite(
                    G5_HISTORICAL_CVAR_99_DAILY
                )
            ),
        "required":
            True,
        "detail":
            (
                f"VaR={G5_HISTORICAL_VAR_99_DAILY:.2%}; "
                f"CVaR={G5_HISTORICAL_CVAR_99_DAILY:.2%}"
            ),
    },
    {
        "check":
            "Monte Carlo output is finite",
        "passed":
            bool(
                safe_isfinite(
                    G5_MONTE_CARLO_PORTFOLIO_RETURNS
                ).all()
            ),
        "required":
            True,
        "detail":
            (
                f"simulations="
                f"{G5_MONTE_CARLO_SIMULATIONS:,}"
            ),
    },
    {
        "check":
            "Risk contribution reconciles to portfolio risk",
        "passed":
            bool(
                np.isclose(
                    G5_RISK_CONTRIBUTION[
                        "component_risk"
                    ].sum(),
                    G5_PORTFOLIO_VOLATILITY,
                    atol=1e-7,
                    rtol=1e-6,
                )
                if G5_PORTFOLIO_VOLATILITY > 0
                else True
            ),
        "required":
            True,
        "detail":
            (
                f"component_sum="
                f"{G5_RISK_CONTRIBUTION['component_risk'].sum():.6f}"
            ),
    },
])


G5_HEALTH["status"] = np.where(
    G5_HEALTH["passed"],
    "✓ PASS",
    "✗ FAIL",
)


G5_REQUIRED_FAILURES = (
    G5_HEALTH[
        G5_HEALTH["required"]
        &
        ~G5_HEALTH["passed"]
    ]
)


G5_PASSED = (
    G5_REQUIRED_FAILURES.empty
)


if not G5_PASSED:

    display(
        G5_REQUIRED_FAILURES
    )

    raise RuntimeError(
        "G5 PRODUCTION GATE FAILED."
    )


# ==================================================================================================
# G5.14 SAVE
# ==================================================================================================

G5_PORTFOLIO_DAILY_RETURNS.to_frame().to_parquet(
    STOCK_MODEL_DIR
    /
    "g5_portfolio_daily_returns.parquet",
)

G5_RISK_CONTRIBUTION.to_parquet(
    STOCK_MODEL_DIR
    /
    "g5_risk_contribution.parquet",
    index=False,
)

G5_PORTFOLIO_RISK_SUMMARY.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g5_portfolio_risk_summary.csv",
    index=False,
)

G5_RISK_CONTRIBUTION.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g5_risk_contribution.csv",
    index=False,
)

G5_HEALTH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g5_health.csv",
    index=False,
)


# ##################################################################################################
# ##################################################################################################
# G6 — TRADE PLAN / TRANSACTION COST / LIQUIDITY CHECK
# ##################################################################################################
# ##################################################################################################

G6_VERSION = "1.0.0"


G6_MIN_TRADE_WEIGHT = float(
    g_cfg(
        ["execution", "min_trade_weight"],
        0.005,
    )
)


G6_MAX_ADV_PCT = float(
    g_cfg(
        ["execution", "max_adv_participation"],
        0.10,
    )
)


G6_NAV = G4_INITIAL_NAV


# ==================================================================================================
# G6.1 ALL TRADE TICKERS
# ==================================================================================================

G6_TRADE_TICKERS = sorted(
    set(
        G4_PREVIOUS_WEIGHT_MAP.keys()
    )
    |
    set(
        G4_TARGET_WEIGHT_MAP.keys()
    )
)


# ==================================================================================================
# G6.2 PRICE MAP
# ==================================================================================================

price_map = (
    G1_FINAL_ALPHA_HANDOFF[
        [
            "ticker",
            "current_price",
        ]
    ]
    .drop_duplicates("ticker")
    .set_index("ticker")[
        "current_price"
    ]
    .to_dict()
)


company_map = (
    G1_FINAL_ALPHA_HANDOFF[
        [
            "ticker",
            "company_name",
        ]
    ]
    .drop_duplicates("ticker")
    .set_index("ticker")[
        "company_name"
    ]
    .to_dict()
)


sector_map = (
    G1_FINAL_ALPHA_HANDOFF[
        [
            "ticker",
            "sector_ticker",
        ]
    ]
    .drop_duplicates("ticker")
    .set_index("ticker")[
        "sector_ticker"
    ]
    .to_dict()
)


# ==================================================================================================
# G6.3 OPTIONAL 20-DAY ADV
# ==================================================================================================

G6_ADV_AVAILABLE = False

G6_ADV20_MAP = {}


if "G3_MARKET_RAW" in globals():

    raw = G3_MARKET_RAW.copy()

    normalized_columns = {
        g_normalize_name(c): c
        for c in raw.columns
    }

    volume_col = None

    for alias in [
        "volume",
        "trading_volume",
        "share_volume",
    ]:

        if alias in normalized_columns:

            volume_col = normalized_columns[
                alias
            ]

            break


    ticker_col = globals().get(
        "G3_TICKER_COLUMN",
        None,
    )

    date_col = globals().get(
        "G3_DATE_COLUMN",
        None,
    )

    price_col = globals().get(
        "G3_PRICE_COLUMN",
        None,
    )


    if (
        volume_col is not None
        and ticker_col is not None
        and date_col is not None
        and price_col is not None
    ):

        try:

            adv = raw[
                [
                    ticker_col,
                    date_col,
                    price_col,
                    volume_col,
                ]
            ].copy()

            adv.columns = [
                "ticker",
                "date",
                "price",
                "volume",
            ]

            adv["ticker"] = (
                adv["ticker"]
                .astype(str)
            )

            adv["date"] = pd.to_datetime(
                adv["date"],
                errors="coerce",
            )

            adv["price"] = pd.to_numeric(
                adv["price"],
                errors="coerce",
            )

            adv["volume"] = pd.to_numeric(
                adv["volume"],
                errors="coerce",
            )

            adv["dollar_volume"] = (
                adv["price"]
                *
                adv["volume"]
            )

            adv = (
                adv
                .dropna(
                    subset=[
                        "ticker",
                        "date",
                        "dollar_volume",
                    ]
                )
                .sort_values(
                    [
                        "ticker",
                        "date",
                    ]
                )
            )


            adv20 = (
                adv
                .groupby(
                    "ticker",
                    group_keys=False,
                )
                .tail(20)
                .groupby(
                    "ticker"
                )[
                    "dollar_volume"
                ]
                .mean()
            )


            G6_ADV20_MAP = (
                adv20.to_dict()
            )


            G6_ADV_AVAILABLE = bool(
                len(
                    G6_ADV20_MAP
                ) > 0
            )


        except Exception:

            G6_ADV_AVAILABLE = False
            G6_ADV20_MAP = {}


# ==================================================================================================
# G6.4 TRADE PLAN
# ==================================================================================================

trade_rows = []


for ticker in G6_TRADE_TICKERS:

    previous_weight = float(
        G4_PREVIOUS_WEIGHT_MAP.get(
            ticker,
            0.0,
        )
    )

    target_weight = float(
        G4_TARGET_WEIGHT_MAP.get(
            ticker,
            0.0,
        )
    )

    delta_weight = (
        target_weight
        -
        previous_weight
    )

    abs_delta_weight = abs(
        delta_weight
    )

    current_notional = (
        previous_weight
        *
        G6_NAV
    )

    target_notional = (
        target_weight
        *
        G6_NAV
    )

    trade_notional = (
        delta_weight
        *
        G6_NAV
    )

    estimated_tc = (
        abs(
            trade_notional
        )
        *
        G4_TC_RATE
    )

    current_price = g_numeric(
        price_map.get(
            ticker,
            np.nan,
        )
    )

    current_shares = (
        current_notional
        /
        current_price
        if (
            safe_isfinite(
                current_price
            )
            and
            current_price > 0
        )
        else np.nan
    )

    target_shares = (
        target_notional
        /
        current_price
        if (
            safe_isfinite(
                current_price
            )
            and
            current_price > 0
        )
        else np.nan
    )

    trade_shares = (
        trade_notional
        /
        current_price
        if (
            safe_isfinite(
                current_price
            )
            and
            current_price > 0
        )
        else np.nan
    )


    trade_required = bool(
        abs_delta_weight
        >=
        G6_MIN_TRADE_WEIGHT
    )

    defer_small_trade = bool(
        (
            abs_delta_weight
            >
            G4_WEIGHT_EPSILON
        )
        and
        not trade_required
    )

    if abs_delta_weight <= G4_WEIGHT_EPSILON:
        action = "HOLD"
    elif defer_small_trade:
        action = "DEFER_SMALL"
    elif delta_weight > 0:
        action = "BUY"
    else:
        action = "SELL"


    adv20 = g_numeric(
        G6_ADV20_MAP.get(
            ticker,
            np.nan,
        )
    )


    if (
        safe_isfinite(
            adv20
        )
        and
        adv20 > 0
    ):

        trade_pct_adv = (
            abs(
                trade_notional
            )
            /
            adv20
        )

        liquidity_check = (
            "PASS"
            if
            trade_pct_adv
            <=
            G6_MAX_ADV_PCT
            else
            "FAIL"
        )

    else:

        trade_pct_adv = np.nan

        liquidity_check = (
            "UNAVAILABLE"
        )


    trade_rows.append({
        "ticker":
            ticker,

        "company_name":
            company_map.get(
                ticker,
                ticker,
            ),

        "sector_ticker":
            sector_map.get(
                ticker,
                None,
            ),

        "current_price":
            current_price,

        "previous_weight":
            previous_weight,

        "target_weight":
            target_weight,

        "delta_weight":
            delta_weight,

        "action":
            action,

        "trade_required":
            trade_required,

        "defer_small_trade":
            defer_small_trade,

        "current_notional":
            current_notional,

        "target_notional":
            target_notional,

        "trade_notional":
            trade_notional,

        "current_shares_est":
            current_shares,

        "target_shares_est":
            target_shares,

        "trade_shares_est":
            trade_shares,

        "estimated_transaction_cost":
            estimated_tc,

        "adv20_dollar":
            adv20,

        "trade_pct_adv":
            trade_pct_adv,

        "liquidity_check":
            liquidity_check,
    })


G6_TRADE_PLAN = pd.DataFrame(
    trade_rows
)


# ==================================================================================================
# G6.5 CASH ROW
# ==================================================================================================

G6_CASH_DELTA = (
    G4_CASH_WEIGHT
    -
    G4_PREVIOUS_CASH_WEIGHT
)


G6_CASH_ROW = pd.DataFrame([{
    "ticker":
        "CASH",

    "company_name":
        "Cash",

    "sector_ticker":
        "CASH",

    "current_price":
        1.0,

    "previous_weight":
        G4_PREVIOUS_CASH_WEIGHT,

    "target_weight":
        G4_CASH_WEIGHT,

    "delta_weight":
        G6_CASH_DELTA,

    "action":
        (
            "INCREASE_CASH"
            if G6_CASH_DELTA > 1e-10
            else
            "DEPLOY_CASH"
            if G6_CASH_DELTA < -1e-10
            else
            "HOLD"
        ),

    "trade_required":
        abs(
            G6_CASH_DELTA
        )
        >=
        G6_MIN_TRADE_WEIGHT,

    "defer_small_trade":
        False,

    "current_notional":
        G4_PREVIOUS_CASH_WEIGHT
        *
        G6_NAV,

    "target_notional":
        G4_CASH_WEIGHT
        *
        G6_NAV,

    "trade_notional":
        G6_CASH_DELTA
        *
        G6_NAV,

    "current_shares_est":
        np.nan,

    "target_shares_est":
        np.nan,

    "trade_shares_est":
        np.nan,

    "estimated_transaction_cost":
        0.0,

    "adv20_dollar":
        np.nan,

    "trade_pct_adv":
        np.nan,

    "liquidity_check":
        "NOT_APPLICABLE",
}])


G6_TRADE_PLAN_WITH_CASH = pd.concat(
    [
        G6_TRADE_PLAN,
        G6_CASH_ROW,
    ],
    ignore_index=True,
)


# ==================================================================================================
# G6.6 EXECUTION SUMMARY
# ==================================================================================================

G6_BUY_NOTIONAL = float(
    G6_TRADE_PLAN.loc[
        G6_TRADE_PLAN[
            "trade_notional"
        ]
        >
        0,
        "trade_notional",
    ]
    .sum()
)


G6_SELL_NOTIONAL = float(
    -
    G6_TRADE_PLAN.loc[
        G6_TRADE_PLAN[
            "trade_notional"
        ]
        <
        0,
        "trade_notional",
    ]
    .sum()
)


G6_GROSS_TRADE_NOTIONAL = float(
    G6_TRADE_PLAN[
        "trade_notional"
    ]
    .abs()
    .sum()
)


G6_TOTAL_TRANSACTION_COST = float(
    G6_TRADE_PLAN[
        "estimated_transaction_cost"
    ]
    .sum()
)


G6_TRANSACTION_COST_PCT_NAV = (
    G6_TOTAL_TRANSACTION_COST
    /
    G6_NAV
)


G6_REQUIRED_TRADE_COUNT = int(
    G6_TRADE_PLAN[
        "trade_required"
    ]
    .sum()
)


G6_SMALL_DEFERRED_COUNT = int(
    G6_TRADE_PLAN[
        "defer_small_trade"
    ]
    .sum()
)


G6_LIQUIDITY_FAILURES = (
    G6_TRADE_PLAN[
        G6_TRADE_PLAN[
            "liquidity_check"
        ]
        ==
        "FAIL"
    ]
    .copy()
)


# ==================================================================================================
# G6.7 HEALTH
# ==================================================================================================

G6_TC_RECONCILES = bool(
    np.isclose(
        G6_TRANSACTION_COST_PCT_NAV,
        G4_ESTIMATED_TC_PCT,
        atol=1e-10,
        rtol=1e-8,
    )
)


G6_TARGET_WEIGHTS_RECONCILE = bool(
    np.isclose(
        G6_TRADE_PLAN[
            "target_weight"
        ].sum()
        +
        G4_CASH_WEIGHT,
        1.0,
        atol=1e-7,
        rtol=1e-7,
    )
)


G6_HEALTH = pd.DataFrame([
    {
        "check":
            "Trade target weights reconcile to optimized portfolio",
        "passed":
            G6_TARGET_WEIGHTS_RECONCILE,
        "required":
            True,
        "detail":
            (
                f"risky="
                f"{G6_TRADE_PLAN['target_weight'].sum():.2%}; "
                f"cash={G4_CASH_WEIGHT:.2%}"
            ),
    },
    {
        "check":
            "Transaction-cost estimate reconciles to optimizer turnover",
        "passed":
            G6_TC_RECONCILES,
        "required":
            True,
        "detail":
            (
                f"TC={G6_TOTAL_TRANSACTION_COST:,.2f}; "
                f"TC_pct_NAV={G6_TRANSACTION_COST_PCT_NAV:.4%}"
            ),
    },
    {
        "check":
            "No negative target weight exists",
        "passed":
            bool(
                (
                    G6_TRADE_PLAN[
                        "target_weight"
                    ]
                    >=
                    -1e-10
                ).all()
            ),
        "required":
            True,
        "detail":
            "long_only=True",
    },
    {
        "check":
            "ADV violations disclosed",
        "passed":
            True,
        "required":
            False,
        "detail":
            (
                f"ADV_available={G6_ADV_AVAILABLE}; "
                f"failures={len(G6_LIQUIDITY_FAILURES)}"
            ),
    },
    {
        "check":
            "Small deferred trades disclosed",
        "passed":
            True,
        "required":
            False,
        "detail":
            (
                f"below_{G6_MIN_TRADE_WEIGHT:.2%}="
                f"{G6_SMALL_DEFERRED_COUNT}"
            ),
    },
])


G6_HEALTH["status"] = np.where(
    G6_HEALTH["passed"],
    "✓ PASS",
    np.where(
        G6_HEALTH["required"],
        "✗ FAIL",
        "⚠ WARN",
    ),
)


G6_REQUIRED_FAILURES = (
    G6_HEALTH[
        G6_HEALTH["required"]
        &
        ~G6_HEALTH["passed"]
    ]
)


G6_PASSED = (
    G6_REQUIRED_FAILURES.empty
)


if not G6_PASSED:

    display(
        G6_REQUIRED_FAILURES
    )

    raise RuntimeError(
        "G6 PRODUCTION GATE FAILED."
    )


# ==================================================================================================
# G6.8 SAVE
# ==================================================================================================

G6_TRADE_PLAN.to_parquet(
    STOCK_MODEL_DIR
    /
    "g6_trade_plan.parquet",
    index=False,
)

G6_TRADE_PLAN.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g6_trade_plan.csv",
    index=False,
)

G6_TRADE_PLAN_WITH_CASH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g6_trade_plan_with_cash.csv",
    index=False,
)

G6_HEALTH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g6_health.csv",
    index=False,
)


G6_SUMMARY = pd.DataFrame([{
    "g6_version":
        G6_VERSION,

    "nav":
        G6_NAV,

    "buy_notional":
        G6_BUY_NOTIONAL,

    "sell_notional":
        G6_SELL_NOTIONAL,

    "gross_trade_notional":
        G6_GROSS_TRADE_NOTIONAL,

    "turnover":
        G4_TOTAL_TURNOVER,

    "transaction_cost":
        G6_TOTAL_TRANSACTION_COST,

    "transaction_cost_pct_nav":
        G6_TRANSACTION_COST_PCT_NAV,

    "required_trade_count":
        G6_REQUIRED_TRADE_COUNT,

    "small_deferred_trade_count":
        G6_SMALL_DEFERRED_COUNT,

    "adv_available":
        G6_ADV_AVAILABLE,

    "liquidity_failures":
        len(
            G6_LIQUIDITY_FAILURES
        ),

    "g6_passed":
        G6_PASSED,
}])


G6_SUMMARY.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g6_summary.csv",
    index=False,
)


# ##################################################################################################
# ##################################################################################################
# G7 — FINAL SECTION G FREEZE
# ##################################################################################################
# ##################################################################################################

G7_VERSION = "1.0.0"


# ==================================================================================================
# G7.1 FINAL PORTFOLIO TABLE
# ==================================================================================================

G7_FINAL_PORTFOLIO = (
    G4_PORTFOLIO_WEIGHTS[
        G4_PORTFOLIO_WEIGHTS[
            "target_weight"
        ]
        >
        1e-10
    ]
    .copy()
)


# Add stock risk information.
risk_columns = [
    "ticker",
    "optimizer_volatility_annual",
    "downside_volatility_annual",
    "maximum_drawdown",
    "historical_cvar_99_daily",
    "average_correlation",
    "expected_return_to_risk",
]


G7_FINAL_PORTFOLIO = (
    G7_FINAL_PORTFOLIO
    .merge(
        G3_RISK_MODEL_HANDOFF[
            risk_columns
        ],
        on="ticker",
        how="left",
        validate="one_to_one",
    )
)


# Add risk contribution.
G7_FINAL_PORTFOLIO = (
    G7_FINAL_PORTFOLIO
    .merge(
        G5_RISK_CONTRIBUTION[
            [
                "ticker",
                "component_risk",
                "risk_contribution_share",
            ]
        ],
        on="ticker",
        how="left",
        validate="one_to_one",
    )
)


# Add trade info.
G7_FINAL_PORTFOLIO = (
    G7_FINAL_PORTFOLIO
    .merge(
        G6_TRADE_PLAN[
            [
                "ticker",
                "action",
                "trade_notional",
                "estimated_transaction_cost",
                "trade_pct_adv",
                "liquidity_check",
            ]
        ],
        on="ticker",
        how="left",
        validate="one_to_one",
    )
)


G7_FINAL_PORTFOLIO = (
    G7_FINAL_PORTFOLIO
    .sort_values(
        "target_weight",
        ascending=False,
    )
    .reset_index(
        drop=True,
    )
)


# ==================================================================================================
# G7.2 FINAL CASH ROW
# ==================================================================================================

G7_FINAL_CASH = pd.DataFrame([{
    "ticker":
        "CASH",

    "company_name":
        "Cash",

    "sector_ticker":
        "CASH",

    "allocation_bucket":
        "CASH",

    "expected_total_return_annual":
        G4_RISK_FREE_RATE,

    "expected_return_confidence":
        1.0,

    "new_entry_optimizer_eligible":
        True,

    "research_optimizer_eligible":
        True,

    "mos_threshold_met":
        True,

    "research_status":
        "CASH",

    "previous_weight":
        G4_PREVIOUS_CASH_WEIGHT,

    "target_weight":
        G4_CASH_WEIGHT,

    "delta_weight":
        G4_CASH_WEIGHT
        -
        G4_PREVIOUS_CASH_WEIGHT,

    "optimizer_volatility_annual":
        0.0,

    "downside_volatility_annual":
        0.0,

    "maximum_drawdown":
        0.0,

    "historical_cvar_99_daily":
        0.0,

    "average_correlation":
        0.0,

    "expected_return_to_risk":
        np.nan,

    "component_risk":
        0.0,

    "risk_contribution_share":
        0.0,

    "action":
        G6_CASH_ROW.iloc[0][
            "action"
        ],

    "trade_notional":
        G6_CASH_ROW.iloc[0][
            "trade_notional"
        ],

    "estimated_transaction_cost":
        0.0,

    "trade_pct_adv":
        np.nan,

    "liquidity_check":
        "NOT_APPLICABLE",
}])


G7_FINAL_PORTFOLIO_WITH_CASH = pd.concat(
    [
        G7_FINAL_PORTFOLIO,
        G7_FINAL_CASH,
    ],
    ignore_index=True,
    sort=False,
)


# ==================================================================================================
# G7.3 FINAL SECTION G SUMMARY
# ==================================================================================================

G7_FINAL_SUMMARY = pd.DataFrame([{
    "section":
        "G",

    "version":
        G7_VERSION,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "portfolio_nav":
        G6_NAV,

    "previous_weight_source":
        G4_PREVIOUS_WEIGHT_SOURCE,

    "stock_positions":
        len(
            G7_FINAL_PORTFOLIO
        ),

    "risky_weight":
        G4_TOTAL_RISKY_WEIGHT,

    "cash_weight":
        G4_CASH_WEIGHT,

    "largest_stock_weight":
        (
            G7_FINAL_PORTFOLIO[
                "target_weight"
            ].max()
            if len(
                G7_FINAL_PORTFOLIO
            ) > 0
            else 0.0
        ),

    "largest_sector_weight":
        G4_SECTOR_EXPOSURE[
            "target_weight"
        ].max(),

    "expected_return_gross":
        G5_GROSS_EXPECTED_RETURN,

    "expected_return_net_first_year":
        G5_NET_FIRST_YEAR_EXPECTED_RETURN,

    "expected_volatility":
        G5_PORTFOLIO_VOLATILITY,

    "stress_volatility":
        G5_STRESS_VOLATILITY,

    "downside_volatility":
        G5_DOWNSIDE_VOLATILITY,

    "expected_sharpe":
        G5_EXPECTED_SHARPE,

    "expected_sortino":
        G5_EXPECTED_SORTINO,

    "expected_calmar":
        G5_EXPECTED_CALMAR,

    "historical_max_drawdown":
        G5_MAX_DRAWDOWN,

    "historical_var_99_daily":
        G5_HISTORICAL_VAR_99_DAILY,

    "historical_cvar_99_daily":
        G5_HISTORICAL_CVAR_99_DAILY,

    "monte_carlo_probability_of_loss":
        G5_MC_PROBABILITY_OF_LOSS,

    "monte_carlo_var_99":
        G5_MC_VAR_99,

    "monte_carlo_cvar_99":
        G5_MC_CVAR_99,

    "turnover":
        G4_TOTAL_TURNOVER,

    "transaction_cost":
        G6_TOTAL_TRANSACTION_COST,

    "transaction_cost_pct_nav":
        G6_TRANSACTION_COST_PCT_NAV,

    "solver":
        G4_SOLVER_USED,

    "historical_alpha_backtest_eligible":
        False,
}])


# ==================================================================================================
# G7.4 FINAL HEALTH
# ==================================================================================================

G7_FINAL_WEIGHT_SUM = float(
    G7_FINAL_PORTFOLIO[
        "target_weight"
    ].sum()
    +
    G4_CASH_WEIGHT
)


G7_FINITE_EXPECTED_RETURN = bool(
    safe_isfinite(
        G5_GROSS_EXPECTED_RETURN
    )
)


G7_FINITE_RISK = bool(
    safe_isfinite(
        G5_PORTFOLIO_VOLATILITY
    )
    and
    safe_isfinite(
        G5_DOWNSIDE_VOLATILITY
    )
)


G7_HEALTH = pd.DataFrame([
    {
        "check":
            "G4 portfolio optimization passed",
        "passed":
            bool(G4_PASSED),
        "required":
            True,
        "detail":
            f"solver={G4_SOLVER_USED}",
    },
    {
        "check":
            "G5 portfolio risk engine passed",
        "passed":
            bool(G5_PASSED),
        "required":
            True,
        "detail":
            (
                f"vol="
                f"{G5_PORTFOLIO_VOLATILITY:.2%}"
            ),
    },
    {
        "check":
            "G6 execution engine passed",
        "passed":
            bool(G6_PASSED),
        "required":
            True,
        "detail":
            (
                f"TC="
                f"{G6_TRANSACTION_COST_PCT_NAV:.4%}"
            ),
    },
    {
        "check":
            "Final portfolio weights sum to 100%",
        "passed":
            bool(
                np.isclose(
                    G7_FINAL_WEIGHT_SUM,
                    1.0,
                    atol=1e-7,
                    rtol=1e-7,
                )
            ),
        "required":
            True,
        "detail":
            (
                f"weight_sum="
                f"{G7_FINAL_WEIGHT_SUM:.8f}"
            ),
    },
    {
        "check":
            "Single-stock cap preserved",
        "passed":
            G4_STOCK_CAP_VALID,
        "required":
            True,
        "detail":
            (
                f"max="
                f"{G4_MAX_REALIZED_STOCK_WEIGHT:.2%}"
            ),
    },
    {
        "check":
            "Sector cap preserved",
        "passed":
            G4_SECTOR_CAP_VALID,
        "required":
            True,
        "detail":
            (
                f"max="
                f"{G4_MAX_REALIZED_SECTOR_WEIGHT:.2%}"
            ),
    },
    {
        "check":
            "MOS new-entry governance preserved",
        "passed":
            G4_MOS_VALID,
        "required":
            True,
        "detail":
            (
                f"violations="
                f"{len(G4_UNAUTHORIZED_NEW_POSITIONS)}"
            ),
    },
    {
        "check":
            "Portfolio expected return is finite",
        "passed":
            G7_FINITE_EXPECTED_RETURN,
        "required":
            True,
        "detail":
            (
                f"expected_return="
                f"{G5_GROSS_EXPECTED_RETURN:.2%}"
            ),
    },
    {
        "check":
            "Portfolio risk metrics are finite",
        "passed":
            G7_FINITE_RISK,
        "required":
            True,
        "detail":
            (
                f"vol={G5_PORTFOLIO_VOLATILITY:.2%}; "
                f"downside={G5_DOWNSIDE_VOLATILITY:.2%}"
            ),
    },
    {
        "check":
            "Historical alpha backtest remains blocked",
        "passed":
            True,
        "required":
            True,
        "detail":
            (
                "current constituent / valuation / "
                "signal stack is not PIT-ready"
            ),
    },
])


G7_HEALTH["status"] = np.where(
    G7_HEALTH["passed"],
    "✓ PASS",
    "✗ FAIL",
)


G7_REQUIRED_FAILURES = (
    G7_HEALTH[
        G7_HEALTH["required"]
        &
        ~G7_HEALTH["passed"]
    ]
)


G7_PASSED = (
    G7_REQUIRED_FAILURES.empty
)


SECTION_G_PASSED = bool(
    G4_PASSED
    and
    G5_PASSED
    and
    G6_PASSED
    and
    G7_PASSED
)


# ==================================================================================================
# G7.5 HASH
# ==================================================================================================

G7_HASH_FRAME = (
    G7_FINAL_PORTFOLIO_WITH_CASH[
        [
            "ticker",
            "target_weight",
        ]
    ]
    .copy()
    .sort_values(
        "ticker"
    )
    .reset_index(
        drop=True,
    )
)


G_FINAL_PORTFOLIO_SHA256 = hashlib.sha256(

    pd.util.hash_pandas_object(
        G7_HASH_FRAME,
        index=False,
    )
    .values
    .tobytes()

).hexdigest()


G7_FINAL_SUMMARY[
    "portfolio_sha256"
] = (
    G_FINAL_PORTFOLIO_SHA256
)


G7_FINAL_SUMMARY[
    "section_g_passed"
] = (
    SECTION_G_PASSED
)


# ==================================================================================================
# G7.6 PROMOTE FINAL SECTION G OBJECTS
# ==================================================================================================

if SECTION_G_PASSED:

    G_FINAL_PORTFOLIO_WEIGHTS = (
        G7_FINAL_PORTFOLIO_WITH_CASH
        .copy()
    )

    G_FINAL_PORTFOLIO_SUMMARY = (
        G7_FINAL_SUMMARY
        .copy()
    )

    G_FINAL_TRADE_PLAN = (
        G6_TRADE_PLAN_WITH_CASH
        .copy()
    )

    G_FINAL_RISK_SUMMARY = (
        G5_PORTFOLIO_RISK_SUMMARY
        .copy()
    )

    G_FINAL_RISK_CONTRIBUTION = (
        G5_RISK_CONTRIBUTION
        .copy()
    )


# ==================================================================================================
# G7.7 SAVE FINAL SECTION G
# ==================================================================================================

G7_FINAL_PORTFOLIO_WITH_CASH.to_parquet(
    STOCK_MODEL_DIR
    /
    "g_final_portfolio.parquet",
    index=False,
)

G7_FINAL_PORTFOLIO_WITH_CASH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g_final_portfolio.csv",
    index=False,
)

G7_FINAL_SUMMARY.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g_final_portfolio_summary.csv",
    index=False,
)

G6_TRADE_PLAN_WITH_CASH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g_final_trade_plan.csv",
    index=False,
)

G5_RISK_CONTRIBUTION.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g_final_risk_contribution.csv",
    index=False,
)

G7_HEALTH.to_csv(
    STOCK_OUTPUT_DIR
    /
    "g_final_health.csv",
    index=False,
)


# ==================================================================================================
# DISPLAY — G4
# ==================================================================================================

print("=" * 150)
print("G4 — CONSTRAINED PORTFOLIO OPTIMIZATION")
print("=" * 150)

print(
    f"Previous portfolio source:          "
    f"{G4_PREVIOUS_WEIGHT_SOURCE}"
)

print(
    f"Solver used:                        "
    f"{G4_SOLVER_USED}"
)

print(
    f"Optimizer assets:                   "
    f"{len(G4_OPTIMIZER_TICKERS)}"
)

print(
    f"Risky target weight:                "
    f"{G4_TOTAL_RISKY_WEIGHT:.2%}"
)

print(
    f"Cash target weight:                 "
    f"{G4_CASH_WEIGHT:.2%}"
)

print(
    f"Expected gross return:              "
    f"{G4_EXPECTED_RETURN_GROSS:.2%}"
)

print(
    f"Expected first-year net return:     "
    f"{G4_EXPECTED_RETURN_NET_FIRST_YEAR:.2%}"
)

print(
    f"Expected volatility:                "
    f"{G4_VOLATILITY:.2%}"
)

print(
    f"Expected Sharpe:                    "
    f"{G4_EXPECTED_SHARPE:.3f}"
)

print(
    f"Turnover:                           "
    f"{G4_TOTAL_TURNOVER:.2%}"
)

print(
    f"Estimated transaction cost:         "
    f"${G4_ESTIMATED_TC_DOLLARS:,.2f}"
)


print("\nOptimized target portfolio:")

display(
    G4_PORTFOLIO_WEIGHTS[
        G4_PORTFOLIO_WEIGHTS[
            "target_weight"
        ] > 1e-10
    ][
        [
            "ticker",
            "company_name",
            "sector_ticker",
            "allocation_bucket",
            "previous_weight",
            "target_weight",
            "delta_weight",
            "expected_total_return_annual",
            "expected_return_confidence",
            "mos_threshold_met",
        ]
    ]
    .sort_values(
        "target_weight",
        ascending=False,
    )
)


print("\nSector exposure:")

display(
    G4_SECTOR_EXPOSURE.sort_values(
        "target_weight",
        ascending=False,
    )
)


print("\nG4 health:")

display(
    G4_HEALTH
)


# ==================================================================================================
# DISPLAY — G5
# ==================================================================================================

print("\n" + "=" * 150)
print("G5 — PORTFOLIO RISK / MONTE CARLO")
print("=" * 150)

display(
    G5_PORTFOLIO_RISK_SUMMARY
)


print("\nRisk contribution:")

display(
    G5_RISK_CONTRIBUTION
)


print("\nG5 health:")

display(
    G5_HEALTH
)


# ==================================================================================================
# DISPLAY — G6
# ==================================================================================================

print("\n" + "=" * 150)
print("G6 — TRADE PLAN / TRANSACTION COST")
print("=" * 150)

display(
    G6_TRADE_PLAN_WITH_CASH[
        [
            "ticker",
            "company_name",
            "previous_weight",
            "target_weight",
            "delta_weight",
            "action",
            "trade_required",
            "trade_notional",
            "estimated_transaction_cost",
            "trade_pct_adv",
            "liquidity_check",
        ]
    ]
    .sort_values(
        "trade_notional",
        key=lambda x: x.abs(),
        ascending=False,
    )
)


print("\nG6 summary:")

display(
    G6_SUMMARY
)


print("\nG6 health:")

display(
    G6_HEALTH
)


# ==================================================================================================
# DISPLAY — G7 FINAL
# ==================================================================================================

print("\n" + "=" * 150)
print("G7 — FINAL SECTION G PORTFOLIO FREEZE")
print("=" * 150)

print(
    f"Stock positions:                    "
    f"{len(G7_FINAL_PORTFOLIO)}"
)

print(
    f"Risky exposure:                     "
    f"{G4_TOTAL_RISKY_WEIGHT:.2%}"
)

print(
    f"Cash exposure:                      "
    f"{G4_CASH_WEIGHT:.2%}"
)

print(
    f"Expected gross annual return:       "
    f"{G5_GROSS_EXPECTED_RETURN:.2%}"
)

print(
    f"Expected net first-year return:     "
    f"{G5_NET_FIRST_YEAR_EXPECTED_RETURN:.2%}"
)

print(
    f"Expected volatility:                "
    f"{G5_PORTFOLIO_VOLATILITY:.2%}"
)

print(
    f"Expected Sharpe:                    "
    f"{G5_EXPECTED_SHARPE:.3f}"
)

print(
    f"Expected Sortino:                   "
    f"{G5_EXPECTED_SORTINO:.3f}"
)

print(
    f"Expected Calmar:                    "
    f"{G5_EXPECTED_CALMAR:.3f}"
)

print(
    f"Historical max drawdown:            "
    f"{G5_MAX_DRAWDOWN:.2%}"
)

print(
    f"99% historical daily VaR:          "
    f"{G5_HISTORICAL_VAR_99_DAILY:.2%}"
)

print(
    f"99% historical daily CVaR:         "
    f"{G5_HISTORICAL_CVAR_99_DAILY:.2%}"
)

print(
    f"Monte Carlo probability of loss:   "
    f"{G5_MC_PROBABILITY_OF_LOSS:.2%}"
)

print(
    f"Monte Carlo 99% VaR:               "
    f"{G5_MC_VAR_99:.2%}"
)

print(
    f"Turnover:                           "
    f"{G4_TOTAL_TURNOVER:.2%}"
)

print(
    f"Estimated transaction cost:        "
    f"${G6_TOTAL_TRANSACTION_COST:,.2f}"
)

print(
    f"Portfolio SHA256:                   "
    f"{G_FINAL_PORTFOLIO_SHA256}"
)


print("\nFINAL portfolio:")

display(
    G7_FINAL_PORTFOLIO_WITH_CASH[
        [
            "ticker",
            "company_name",
            "sector_ticker",
            "target_weight",
            "expected_total_return_annual",
            "optimizer_volatility_annual",
            "risk_contribution_share",
            "action",
            "trade_notional",
            "liquidity_check",
        ]
    ]
    .sort_values(
        "target_weight",
        ascending=False,
    )
)


print("\nFinal Section G summary:")

display(
    G7_FINAL_SUMMARY
)


print("\nFinal Section G health:")

display(
    G7_HEALTH
)


# ==================================================================================================
# FINAL PRODUCTION GATE
# ==================================================================================================

if not SECTION_G_PASSED:

    display(
        G7_REQUIRED_FAILURES
    )

    raise RuntimeError(
        "SECTION G FINAL PRODUCTION GATE FAILED."
    )


print("\n" + "=" * 150)

print(
    "✓ SECTION G COMPLETE AND FROZEN."
)

print(
    "✓ G4 optimized long-only portfolio weights using expected excess return, covariance, risk aversion and turnover costs."
)

print(
    f"✓ {float(cfg(['execution', 'transaction_cost_bps'], G4_TC_RATE * 10_000)):g} bps one-way transaction cost is incorporated."
)

print(
    "✓ Single-stock and sector limits are enforced."
)

print(
    f"✓ No new position may be opened without satisfying MOS and valuation-model-risk governance (base MOS={float(cfg(['valuation', 'mos_base'], 0.15)):.0%})."
)

print(
    "✓ Existing non-MOS holdings may only be maintained or reduced, not increased."
)

print(
    "✓ G5 provides volatility, downside volatility, drawdown, VaR, CVaR, Sharpe, Sortino, Calmar and Monte Carlo diagnostics."
)

print(
    "✓ G5 provides component risk contributions."
)

print(
    "✓ G6 produces target trades, estimated transaction costs and optional ADV liquidity checks."
)

print(
    "✓ Historical alpha backtesting remains blocked until PIT membership / fundamentals / valuation history is available."
)

print(
    "✓ G_FINAL_PORTFOLIO_WEIGHTS is the final portfolio object."
)

print(
    "✓ G_FINAL_TRADE_PLAN is the final execution handoff."
)

print(
    "✓ G_FINAL_PORTFOLIO_SUMMARY is the final portfolio-level summary."
)

print(
    "✓ SECTION_G_PASSED = True."
)

print("=" * 150)


# ===== ORIGINAL NOTEBOOK CELL 85 =====
# ==================================================================================================
# CELL G7B — MODEL PORTFOLIO STATE PERSISTENCE V1.0.0
# ==================================================================================================
MODEL_STATE_PERSISTED = False
if (
    bool(globals().get("SECTION_G_PASSED", False))
    and globals().get("PORTFOLIO_STATE_MODE", "MODEL") == "MODEL"
    and bool(globals().get("PORTFOLIO_ASSUME_MODEL_TARGETS_EXECUTED", True))
):
    MODEL_NEXT_STATE = G_FINAL_PORTFOLIO_WEIGHTS[["ticker", "target_weight"]].copy().rename(
        columns={"target_weight": "current_weight"}
    )
    MODEL_NEXT_STATE.to_csv(PORTFOLIO_MODEL_PATH, index=False)
    MODEL_STATE_PERSISTED = True
print("=" * 120)
print("G7B — PORTFOLIO STATE PERSISTENCE")
print("=" * 120)
print(f"Portfolio-state mode:             {globals().get('PORTFOLIO_STATE_MODE', 'UNKNOWN')}")
print(f"Model state persisted:            {MODEL_STATE_PERSISTED}")
if MODEL_STATE_PERSISTED:
    print(f"Next-run model state:             {PORTFOLIO_MODEL_PATH}")
else:
    print("✓ No actual-holdings file was modified.")


# ===== ORIGINAL NOTEBOOK CELL 86 =====
# ==================================================================================================
# SECTION G — STOCK ALPHA INTEGRATION ENGINE
# CELL G8 — HYPERPARAMETER SENSITIVITY DIAGNOSTIC (IMPROVEMENT #3,
#           NON-BLOCKING) V1.0.0
# ==================================================================================================
#
# Purpose:
#
#   The pipeline from G1 through G4 is driven by a chain of hand-set,
#   policy-calibrated constants that cannot yet be fitted (no PIT
#   backtest exists):
#
#       G1_SECTOR_WEIGHT / G1_COMPANY_WEIGHT / G1_VALUATION_WEIGHT
#       G2_ALPHA_RETURN_PER_SIGNAL / G2_MAX_ABS_ANNUAL_ALPHA
#       G3_BASE_COV_WEIGHT / G3_STRESS_COV_WEIGHT
#       F5_MOS_BASE (see F5 / F5A, improvement #4)
#
#   None of these are wrong, but none are validated either. This
#   cell perturbs each +/-20% ONE AT A TIME, holding everything
#   else at today's production value, and re-solves a portfolio
#   for each scenario -- so you can see which constants are
#   load-bearing (the target portfolio moves a lot) and which are
#   not (it barely moves).
#
#   This is a DIAGNOSTIC ONLY. It does not change
#   G_FINAL_PORTFOLIO_WEIGHTS, G_FINAL_TRADE_PLAN, or any other
#   canonical production object -- it reuses the already-frozen
#   G1/G2/G3 component signals and re-derives the algebra + a
#   fresh QP solve for each scenario, entirely independently of
#   the live G4 cell above.
#
#   Simplifications versus the live G4 optimizer (deliberate, to
#   keep this a fast, self-contained diagnostic):
#
#     - Every scenario is solved from a CLEAN slate (w_prev = 0
#       for all names), not against today's actual holdings. This
#       is intentional: the question here is "where would the
#       optimizer's steady-state target move to", not "what would
#       today's specific trade list look like". It also means the
#       G4 "existing holdings may be held even without new-entry
#       eligibility" carve-out does not apply here -- every name
#       is evaluated purely on the entry rule.
#     - MOS eligibility is recomputed directly from already-frozen
#       DCF outputs (expected_intrinsic_value, current_price,
#       valuation_confidence) using the SAME variable-MOS function
#       added in F5 (improvement #4), rather than re-running the
#       full F5/F5A per-company loop.
#
#   Everything else (stock cap, sector cap, risk aversion, turnover
#   penalty, transaction-cost rate, cash residual, solver, PSD
#   repair) is taken directly from CONFIG / G3 so the diagnostic
#   stays faithful to the live optimizer's actual constraints.
# ==================================================================================================


# ==================================================================================================
# 1. VALIDATE UPSTREAM
# ==================================================================================================

required_g8_objects = [

    "G1_PASSED",
    "G1_FINAL_ALPHA_HANDOFF",

    "G2_PASSED",
    "G2_EXPECTED_RETURNS",
    "G2_RISK_FREE_RATE",
    "G2_ALPHA_RETURN_PER_SIGNAL",
    "G2_MAX_ABS_ANNUAL_ALPHA",

    "G3_PASSED",
    "G3_BASE_ANNUAL_COVARIANCE",
    "G3_STRESS_ANNUAL_COVARIANCE",
    "G3_RESEARCH_TICKERS",
    "G3_BASE_COV_WEIGHT",
    "G3_STRESS_COV_WEIGHT",

    "G1_SECTOR_WEIGHT",
    "G1_COMPANY_WEIGHT",
    "G1_VALUATION_WEIGHT",

    "f5_variable_margin_of_safety",
    "F5_MOS_BASE",
    "F5_MOS_CONFIDENCE_SENSITIVITY",
    "F5_MOS_MIN",
    "F5_MOS_MAX",

    "g3_nearest_psd",

    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",

]

missing_g8_objects = [
    obj
    for obj in required_g8_objects
    if obj not in globals()
]

if missing_g8_objects:
    raise RuntimeError(
        "G8 requires completed G1/G2/G3 state (and the F5 "
        "variable-MOS helper). Missing: "
        f"{missing_g8_objects}"
    )

if not (bool(G1_PASSED) and bool(G2_PASSED) and bool(G3_PASSED)):
    raise RuntimeError(
        "G8 requires G1, G2 and G3 production gates to have passed."
    )

G8_VERSION = "1.0.0"


# ==================================================================================================
# 2. CONFIG CONSTANTS (taken directly from CONFIG / G3, not re-declared)
# ==================================================================================================

G8_MAX_STOCK_WEIGHT = float(CONFIG["portfolio"]["max_stock_weight"])
G8_MAX_SECTOR_WEIGHT = float(CONFIG["portfolio"]["max_sector_weight"])
G8_MIN_CASH_WEIGHT = float(CONFIG["portfolio"]["min_cash_weight"])
G8_RISK_AVERSION = float(CONFIG["optimizer"]["risk_aversion"])
G8_TURNOVER_PENALTY = float(CONFIG["optimizer"]["turnover_penalty"])
G8_TC_RATE = float(CONFIG["execution"]["transaction_cost_rate"])
G8_RISK_FREE_RATE = float(G2_RISK_FREE_RATE)


# ==================================================================================================
# 3. BASE WORKING TABLE
#
#    One row per research-ranking-eligible ticker with the raw,
#    weight-independent inputs needed to re-derive master alpha,
#    expected return and MOS eligibility for any parameter set.
# ==================================================================================================

G8_BASE = (

    G1_FINAL_ALPHA_HANDOFF[
        [
            "ticker",
            "sector_ticker",
            "sector_signal",
            "company_selection_signal",
            "valuation_signal_normalized",
            "research_confidence",
            "valuation_confidence",
            "current_price",
            "expected_intrinsic_value",
            "research_ranking_eligible",
            "valuation_entry_eligible",
            "valuation_critical_block",
        ]
    ]
    .merge(
        G2_EXPECTED_RETURNS[
            [
                "ticker",
                "capm_required_return",
            ]
        ],
        on="ticker",
        how="left",
    )

)

G8_BASE["ticker"] = G8_BASE["ticker"].astype(str)

# Restrict to names with usable covariance coverage (matches the
# universe G3/G4 actually optimize over).
G8_COVARIANCE_TICKERS = set(G3_RESEARCH_TICKERS)

G8_BASE = (
    G8_BASE[
        G8_BASE["ticker"].isin(G8_COVARIANCE_TICKERS)
        & G8_BASE["research_ranking_eligible"].fillna(False)
    ]
    .dropna(
        subset=[
            "sector_signal",
            "company_selection_signal",
            "valuation_signal_normalized",
            "research_confidence",
            "capm_required_return",
            "current_price",
            "expected_intrinsic_value",
        ]
    )
    .reset_index(drop=True)
)

if len(G8_BASE) == 0:
    raise RuntimeError(
        "G8: no research-ranking-eligible tickers with covariance "
        "coverage were found -- cannot run the sensitivity diagnostic."
    )

G8_SECTOR_MAP = (
    G8_BASE.set_index("ticker")["sector_ticker"].to_dict()
)


# ==================================================================================================
# 4. MINI OPTIMIZER (mirrors G4's objective/constraints; w_prev = 0)
# ==================================================================================================

def g8_solve_portfolio(eligible_tickers, expected_total_return, sector_map, covariance_df):
    """
    Re-solve the same long-only MVO + turnover-penalty QP as G4,
    restricted to `eligible_tickers`, from a clean (all-cash)
    starting point. Returns a dict of summary statistics.
    """

    tickers = sorted(eligible_tickers)
    n = len(tickers)

    if n == 0:
        return {
            "status": "ALL_CASH_NO_ELIGIBLE_ASSETS",
            "weights": {},
            "n_invested": 0,
            "cash_weight": 1.0,
            "max_sector_invested_share": 0.0,
            "expected_return": G8_RISK_FREE_RATE,
            "expected_vol": 0.0,
            "expected_sharpe": np.nan,
        }

    mu_total = np.array(
        [expected_total_return[t] for t in tickers],
        dtype=float,
    )
    mu_excess = mu_total - G8_RISK_FREE_RATE

    Sigma = covariance_df.loc[tickers, tickers].values
    Sigma_psd = cp.psd_wrap(Sigma)

    w = cp.Variable(n)

    objective = cp.Maximize(
        mu_excess @ w
        - (G8_RISK_AVERSION / 2.0) * cp.quad_form(w, Sigma_psd)
        - G8_TURNOVER_PENALTY * G8_TC_RATE * cp.norm1(w)
    )

    constraints = [
        w >= 0.0,
        w <= G8_MAX_STOCK_WEIGHT,
        cp.sum(w) <= (1.0 - G8_MIN_CASH_WEIGHT),
    ]

    for sector in sorted(set(sector_map[t] for t in tickers)):
        idx = [i for i, t in enumerate(tickers) if sector_map[t] == sector]
        constraints.append(cp.sum(w[idx]) <= G8_MAX_SECTOR_WEIGHT)

    problem = cp.Problem(objective, constraints)

    solved = False
    for solver in ["CLARABEL", "OSQP", "ECOS", "SCS"]:
        if solver not in cp.installed_solvers():
            continue
        try:
            problem.solve(solver=solver, verbose=False)
            if problem.status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
                solved = True
                break
        except Exception:
            continue

    if not solved:
        return {
            "status": "SOLVE_FAILED",
            "weights": {},
            "n_invested": 0,
            "cash_weight": np.nan,
            "max_sector_invested_share": np.nan,
            "expected_return": np.nan,
            "expected_vol": np.nan,
            "expected_sharpe": np.nan,
        }

    w_value = np.clip(np.array(w.value, dtype=float), 0.0, None)
    w_value = np.where(w_value < 1e-8, 0.0, w_value)

    weights = dict(zip(tickers, w_value))
    invested_total = float(w_value.sum())
    cash_weight = float(max(0.0, 1.0 - invested_total))

    if invested_total > 1e-10:
        sector_shares = {}
        for t, wt in weights.items():
            sector_shares[sector_map[t]] = sector_shares.get(sector_map[t], 0.0) + wt
        max_sector_invested_share = max(
            v / invested_total for v in sector_shares.values()
        )
    else:
        max_sector_invested_share = 0.0

    portfolio_return = float(
        (w_value @ mu_total) + cash_weight * G8_RISK_FREE_RATE
    )
    portfolio_vol = float(np.sqrt(max(0.0, w_value @ Sigma @ w_value)))
    portfolio_sharpe = (
        float((portfolio_return - G8_RISK_FREE_RATE) / portfolio_vol)
        if portfolio_vol > 1e-10
        else np.nan
    )

    return {
        "status": "OK",
        "weights": weights,
        "n_invested": int((w_value > 1e-8).sum()),
        "cash_weight": cash_weight,
        "max_sector_invested_share": max_sector_invested_share,
        "expected_return": portfolio_return,
        "expected_vol": portfolio_vol,
        "expected_sharpe": portfolio_sharpe,
    }


# ==================================================================================================
# 5. FULL RE-DERIVATION FOR ONE PARAMETER SET
# ==================================================================================================

def g8_run_scenario(
    label,
    sector_weight=None,
    company_weight=None,
    valuation_weight=None,
    alpha_scale=None,
    alpha_cap=None,
    base_cov_weight=None,
    mos_base=None,
):

    sector_weight = G1_SECTOR_WEIGHT if sector_weight is None else sector_weight
    company_weight = G1_COMPANY_WEIGHT if company_weight is None else company_weight
    valuation_weight = G1_VALUATION_WEIGHT if valuation_weight is None else valuation_weight
    alpha_scale = G2_ALPHA_RETURN_PER_SIGNAL if alpha_scale is None else alpha_scale
    alpha_cap = G2_MAX_ABS_ANNUAL_ALPHA if alpha_cap is None else alpha_cap
    base_cov_weight = G3_BASE_COV_WEIGHT if base_cov_weight is None else base_cov_weight
    mos_base = F5_MOS_BASE if mos_base is None else mos_base

    df = G8_BASE.copy()

    df["master_alpha_score"] = (
        sector_weight * df["sector_signal"]
        + company_weight * df["company_selection_signal"]
        + valuation_weight * df["valuation_signal_normalized"]
    )

    df["confidence_adjusted_master_alpha"] = (
        df["master_alpha_score"] * df["research_confidence"]
    )

    df["annual_alpha_overlay"] = (
        (alpha_scale * df["confidence_adjusted_master_alpha"])
        .clip(lower=-alpha_cap, upper=alpha_cap)
    )

    df["expected_total_return_annual"] = (
        df["capm_required_return"] + df["annual_alpha_overlay"]
    )

    stress_cov_weight = 1.0 - base_cov_weight

    blended_cov = (
        base_cov_weight
        * G3_BASE_ANNUAL_COVARIANCE.loc[G3_RESEARCH_TICKERS, G3_RESEARCH_TICKERS]
        + stress_cov_weight
        * G3_STRESS_ANNUAL_COVARIANCE.loc[G3_RESEARCH_TICKERS, G3_RESEARCH_TICKERS]
    )

    blended_cov = pd.DataFrame(
        g3_nearest_psd(blended_cov.values),
        index=G3_RESEARCH_TICKERS,
        columns=G3_RESEARCH_TICKERS,
    )

    df["margin_of_safety_applied"] = df["valuation_confidence"].apply(
        lambda c: float(
            np.clip(
                mos_base + F5_MOS_CONFIDENCE_SENSITIVITY * (1.0 - c),
                F5_MOS_MIN,
                F5_MOS_MAX,
            )
        )
    )

    df["mos_price_threshold"] = (
        df["expected_intrinsic_value"] * (1.0 - df["margin_of_safety_applied"])
    )

    df["mos_threshold_met"] = df["current_price"] <= df["mos_price_threshold"]
    df["valuation_entry_eligible"] = (
        df["valuation_entry_eligible"].fillna(False).astype(bool)
    )

    eligible_tickers = df.loc[
        df["mos_threshold_met"] & df["valuation_entry_eligible"],
        "ticker",
    ].tolist()

    expected_return_map = (
        df.set_index("ticker")["expected_total_return_annual"].to_dict()
    )

    result = g8_solve_portfolio(
        eligible_tickers,
        expected_return_map,
        G8_SECTOR_MAP,
        blended_cov,
    )

    return {
        "scenario": label,
        "sector_weight": round(sector_weight, 4),
        "company_weight": round(company_weight, 4),
        "valuation_weight": round(valuation_weight, 4),
        "alpha_scale": round(alpha_scale, 4),
        "alpha_cap": round(alpha_cap, 4),
        "base_cov_weight": round(base_cov_weight, 4),
        "mos_base": round(mos_base, 4),
        "n_mos_eligible": len(eligible_tickers),
        "n_invested": result["n_invested"],
        "cash_weight": round(result["cash_weight"], 4),
        "max_sector_invested_share": round(result["max_sector_invested_share"], 4),
        "expected_return": round(result["expected_return"], 4),
        "expected_vol": round(result["expected_vol"], 4),
        "expected_sharpe": (
            round(result["expected_sharpe"], 4)
            if pd.notna(result["expected_sharpe"])
            else np.nan
        ),
        "status": result["status"],
    }


# ==================================================================================================
# 6. HELPER — RENORMALIZED SIMPLEX PERTURBATION FOR THE THREE G1 WEIGHTS
# ==================================================================================================
#
# G1's three weights must sum to 1, so an independent +/-20% on one
# of them is redistributed proportionally across the other two
# (keeping their relative ratio fixed) rather than left to break
# the constraint.
# ==================================================================================================

def g8_perturb_g1_weight(which, pct_change):

    base = {
        "sector": G1_SECTOR_WEIGHT,
        "company": G1_COMPANY_WEIGHT,
        "valuation": G1_VALUATION_WEIGHT,
    }

    perturbed_target = base[which] * (1.0 + pct_change)

    others = [k for k in base if k != which]
    others_total = base[others[0]] + base[others[1]]

    remaining = 1.0 - perturbed_target

    if others_total > 1e-12:
        out = {
            which: perturbed_target,
            others[0]: remaining * (base[others[0]] / others_total),
            others[1]: remaining * (base[others[1]] / others_total),
        }
    else:
        out = {which: perturbed_target, others[0]: remaining / 2.0, others[1]: remaining / 2.0}

    return out["sector"], out["company"], out["valuation"]


# ==================================================================================================
# 7. RUN THE ONE-AT-A-TIME SENSITIVITY GRID
# ==================================================================================================

G8_SCENARIO_ROWS = []

G8_SCENARIO_ROWS.append(
    g8_run_scenario("BASELINE (production values)")
)

for weight_name in ["sector", "company", "valuation"]:
    for pct in [-0.20, +0.20]:
        s, c, v = g8_perturb_g1_weight(weight_name, pct)
        G8_SCENARIO_ROWS.append(
            g8_run_scenario(
                f"G1 {weight_name}_weight {pct:+.0%}",
                sector_weight=s,
                company_weight=c,
                valuation_weight=v,
            )
        )

for pct in [-0.20, +0.20]:
    G8_SCENARIO_ROWS.append(
        g8_run_scenario(
            f"G2 alpha_scale {pct:+.0%}",
            alpha_scale=G2_ALPHA_RETURN_PER_SIGNAL * (1.0 + pct),
        )
    )

for pct in [-0.20, +0.20]:
    G8_SCENARIO_ROWS.append(
        g8_run_scenario(
            f"G2 alpha_cap {pct:+.0%}",
            alpha_cap=G2_MAX_ABS_ANNUAL_ALPHA * (1.0 + pct),
        )
    )

for pct in [-0.20, +0.20]:
    perturbed_base_cov = float(
        np.clip(G3_BASE_COV_WEIGHT * (1.0 + pct), 0.0, 1.0)
    )
    G8_SCENARIO_ROWS.append(
        g8_run_scenario(
            f"G3 base_cov_weight {pct:+.0%}",
            base_cov_weight=perturbed_base_cov,
        )
    )

for pct in [-0.20, +0.20]:
    G8_SCENARIO_ROWS.append(
        g8_run_scenario(
            f"F5 mos_base {pct:+.0%}",
            mos_base=F5_MOS_BASE * (1.0 + pct),
        )
    )

G8_HYPERPARAMETER_SENSITIVITY = pd.DataFrame(G8_SCENARIO_ROWS)


# ==================================================================================================
# 8. FLAG THE MOST FRAGILE PARAMETERS
#
#    "Fragile" here means expected_sharpe or cash_weight moves by
#    more than the thresholds below relative to baseline, under a
#    plausible +/-20% perturbation.
# ==================================================================================================

G8_BASELINE_ROW = G8_HYPERPARAMETER_SENSITIVITY.iloc[0]

G8_SHARPE_FRAGILITY_THRESHOLD = float(cfg(["alpha", "sharpe_fragility_threshold"], 0.10))
G8_CASH_FRAGILITY_THRESHOLD = float(cfg(["alpha", "cash_fragility_threshold"], 0.10))

G8_HYPERPARAMETER_SENSITIVITY["sharpe_delta_vs_baseline"] = (
    G8_HYPERPARAMETER_SENSITIVITY["expected_sharpe"]
    - G8_BASELINE_ROW["expected_sharpe"]
)

G8_HYPERPARAMETER_SENSITIVITY["cash_delta_vs_baseline"] = (
    G8_HYPERPARAMETER_SENSITIVITY["cash_weight"]
    - G8_BASELINE_ROW["cash_weight"]
)

G8_HYPERPARAMETER_SENSITIVITY["flagged_fragile"] = (
    G8_HYPERPARAMETER_SENSITIVITY["sharpe_delta_vs_baseline"].abs()
    >= G8_SHARPE_FRAGILITY_THRESHOLD
) | (
    G8_HYPERPARAMETER_SENSITIVITY["cash_delta_vs_baseline"].abs()
    >= G8_CASH_FRAGILITY_THRESHOLD
)

G8_FRAGILE_SCENARIOS = (
    G8_HYPERPARAMETER_SENSITIVITY[
        G8_HYPERPARAMETER_SENSITIVITY["flagged_fragile"]
    ]
    ["scenario"]
    .tolist()
)


# ==================================================================================================
# 9. SAVE + DISPLAY
# ==================================================================================================

G8_HYPERPARAMETER_SENSITIVITY.to_parquet(
    STOCK_OUTPUT_DIR / "g8_hyperparameter_sensitivity.parquet",
    index=False,
)

print("=" * 82)
print("G8 — HYPERPARAMETER SENSITIVITY DIAGNOSTIC (non-blocking)")
print("=" * 82)

print(
    f"Scenarios run: {len(G8_HYPERPARAMETER_SENSITIVITY)} "
    f"(baseline + 14 one-at-a-time +/-20% perturbations)"
)

display(
    G8_HYPERPARAMETER_SENSITIVITY[
        [
            "scenario",
            "n_mos_eligible",
            "n_invested",
            "cash_weight",
            "max_sector_invested_share",
            "expected_return",
            "expected_vol",
            "expected_sharpe",
            "sharpe_delta_vs_baseline",
            "cash_delta_vs_baseline",
            "flagged_fragile",
        ]
    ]
)

if G8_FRAGILE_SCENARIOS:
    print(
        f"\n⚠ {len(G8_FRAGILE_SCENARIOS)} scenario(s) moved Sharpe by "
        f">= {G8_SHARPE_FRAGILITY_THRESHOLD:.0%} or cash by "
        f">= {G8_CASH_FRAGILITY_THRESHOLD:.0%} versus baseline under a "
        f"plausible +/-20% perturbation -- these parameters are "
        f"load-bearing and are the priority for future calibration:"
    )
    for s in G8_FRAGILE_SCENARIOS:
        print(f"    - {s}")
else:
    print(
        "\n✓ No tested parameter moved Sharpe or cash weight beyond "
        "the fragility thresholds under a +/-20% one-at-a-time "
        "perturbation."
    )

print(
    "\n✓ G8 COMPLETE — diagnostic only; no production object was "
    "modified by this cell."
)


# ===== ORIGINAL NOTEBOOK CELL 87 =====
# ==================================================================================================
# CELL G9 — DISTRIBUTION-AWARE PATH MONTE CARLO / TAIL-RISK ENGINE V1.2.0
# ==================================================================================================
import scipy.stats as stats
G9_VERSION = "1.2.0"
G9_SIMULATIONS = int(CONFIG.get("risk", {}).get("path_mc_simulations", 20_000))
G9_BLOCK_LENGTH = int(CONFIG.get("risk", {}).get("path_mc_block_length", 5))
G9_HORIZON_DAYS = int(globals().get("G5_TRADING_DAYS", 252))
G9_RANDOM_SEED = int(CONFIG.get("system", {}).get("random_seed", 42)) + 901
G9_CHUNK_SIZE = int(CONFIG.get("risk", {}).get("path_mc_chunk_size", 2_000))

if G9_SIMULATIONS <= 0:
    raise RuntimeError("G9 path_mc_simulations must be positive.")
if G9_BLOCK_LENGTH <= 0:
    raise RuntimeError("G9 path_mc_block_length must be positive.")
if G9_HORIZON_DAYS <= 1:
    raise RuntimeError("G9 horizon must exceed one trading day.")
if G9_CHUNK_SIZE <= 0:
    raise RuntimeError("G9 chunk size must be positive.")

hist = pd.Series(G5_PORTFOLIO_DAILY_RETURNS).dropna().astype(float).values
if len(hist) < max(60, G9_BLOCK_LENGTH + 2):
    raise RuntimeError("G9 requires at least 60 valid historical portfolio-return observations.")

hist_mean = float(np.mean(hist))
residuals = hist - hist_mean
expected_daily = float(
    (1.0 + max(float(G5_GROSS_EXPECTED_RETURN), -0.95)) ** (1.0 / G9_HORIZON_DAYS) - 1.0
)
initial_after_cost = max(1e-8, 1.0 - float(G4_ESTIMATED_TC_PCT))

rng_g9 = np.random.default_rng(G9_RANDOM_SEED)
n_blocks = int(np.ceil(G9_HORIZON_DAYS / G9_BLOCK_LENGTH))
max_start = len(residuals) - G9_BLOCK_LENGTH
offsets = np.arange(G9_BLOCK_LENGTH, dtype=int)

# Process paths in chunks so the notebook does not retain several giant
# (simulations x 252) arrays simultaneously.  Only terminal return and
# path maximum drawdown are persisted.
G9_PATH_MC_RETURNS = np.empty(G9_SIMULATIONS, dtype=float)
G9_PATH_MAX_DRAWDOWNS = np.empty(G9_SIMULATIONS, dtype=float)

for chunk_start in range(0, G9_SIMULATIONS, G9_CHUNK_SIZE):
    chunk_end = min(chunk_start + G9_CHUNK_SIZE, G9_SIMULATIONS)
    n_chunk = chunk_end - chunk_start

    starts = rng_g9.integers(0, max_start + 1, size=(n_chunk, n_blocks))
    indices = starts[:, :, None] + offsets[None, None, :]
    boot_residuals = residuals[indices].reshape(n_chunk, -1)[:, :G9_HORIZON_DAYS]
    daily_paths = np.clip(expected_daily + boot_residuals, -0.999, None)

    wealth_paths = initial_after_cost * np.cumprod(1.0 + daily_paths, axis=1)
    terminal_returns = wealth_paths[:, -1] - 1.0

    # Include initial wealth of 1.0 in the running peak without allocating
    # an additional full wealth matrix.
    running_peak = np.maximum.accumulate(wealth_paths, axis=1)
    running_peak = np.maximum(running_peak, 1.0)
    drawdowns = wealth_paths / running_peak - 1.0

    G9_PATH_MC_RETURNS[chunk_start:chunk_end] = terminal_returns
    G9_PATH_MAX_DRAWDOWNS[chunk_start:chunk_end] = np.min(drawdowns, axis=1)

G9_P01, G9_P05, G9_P50, G9_P95, G9_P99 = [
    float(np.quantile(G9_PATH_MC_RETURNS, q))
    for q in [0.01, 0.05, 0.50, 0.95, 0.99]
]
G9_VAR_99 = max(0.0, -G9_P01)
_tail = G9_PATH_MC_RETURNS[G9_PATH_MC_RETURNS <= G9_P01]
G9_CVAR_99 = max(0.0, -float(_tail.mean())) if len(_tail) else 0.0
G9_RETURN_STD = float(np.std(G9_PATH_MC_RETURNS, ddof=1))

if safe_isfinite(G9_RETURN_STD) and G9_RETURN_STD > 1e-12:
    G9_SKEWNESS = float(scipy_stats.skew(G9_PATH_MC_RETURNS, bias=False))
    G9_EXCESS_KURTOSIS = float(
        scipy_stats.kurtosis(G9_PATH_MC_RETURNS, fisher=True, bias=False)
    )
else:
    # Deterministic / all-cash portfolio: higher moments are not
    # statistically identified. Report neutral values rather than
    # propagating NaN warnings through the dashboard.
    G9_SKEWNESS = 0.0
    G9_EXCESS_KURTOSIS = 0.0
G9_PROB_LOSS = float(np.mean(G9_PATH_MC_RETURNS < 0.0))
G9_PROB_BELOW_CASH = float(np.mean(G9_PATH_MC_RETURNS < G4_RISK_FREE_RATE))
G9_PROB_BELOW_MINUS_10 = float(np.mean(G9_PATH_MC_RETURNS < -0.10))
G9_PROB_BELOW_MINUS_20 = float(np.mean(G9_PATH_MC_RETURNS < -0.20))
G9_PROB_ABOVE_PLUS_10 = float(np.mean(G9_PATH_MC_RETURNS > 0.10))
G9_PROB_ABOVE_PLUS_20 = float(np.mean(G9_PATH_MC_RETURNS > 0.20))
G9_PROB_DD_WORSE_10 = float(np.mean(G9_PATH_MAX_DRAWDOWNS < -0.10))
G9_PROB_DD_WORSE_20 = float(np.mean(G9_PATH_MAX_DRAWDOWNS < -0.20))
G9_PROB_DD_WORSE_30 = float(np.mean(G9_PATH_MAX_DRAWDOWNS < -0.30))

G9_PATH_MC_SUMMARY = pd.DataFrame([{
    "version": G9_VERSION,
    "method": "EMPIRICAL_BLOCK_BOOTSTRAP_CURRENT_PORTFOLIO",
    "simulations": G9_SIMULATIONS,
    "horizon_days": G9_HORIZON_DAYS,
    "block_length": G9_BLOCK_LENGTH,
    "chunk_size": G9_CHUNK_SIZE,
    "expected_return_anchor": G5_GROSS_EXPECTED_RETURN,
    "mean_return": float(np.mean(G9_PATH_MC_RETURNS)),
    "median_return": float(np.median(G9_PATH_MC_RETURNS)),
    "std_return": float(np.std(G9_PATH_MC_RETURNS, ddof=1)),
    "skewness": G9_SKEWNESS,
    "excess_kurtosis": G9_EXCESS_KURTOSIS,
    "p01": G9_P01,
    "p05": G9_P05,
    "p50": G9_P50,
    "p95": G9_P95,
    "p99": G9_P99,
    "var_99": G9_VAR_99,
    "cvar_99": G9_CVAR_99,
    "probability_of_loss": G9_PROB_LOSS,
    "probability_below_cash": G9_PROB_BELOW_CASH,
    "prob_return_below_minus_10pct": G9_PROB_BELOW_MINUS_10,
    "prob_return_below_minus_20pct": G9_PROB_BELOW_MINUS_20,
    "prob_return_above_plus_10pct": G9_PROB_ABOVE_PLUS_10,
    "prob_return_above_plus_20pct": G9_PROB_ABOVE_PLUS_20,
    "median_max_drawdown": float(np.median(G9_PATH_MAX_DRAWDOWNS)),
    "p05_max_drawdown": float(np.quantile(G9_PATH_MAX_DRAWDOWNS, 0.05)),
    "prob_max_drawdown_worse_10pct": G9_PROB_DD_WORSE_10,
    "prob_max_drawdown_worse_20pct": G9_PROB_DD_WORSE_20,
    "prob_max_drawdown_worse_30pct": G9_PROB_DD_WORSE_30,
}])

G9_PATH_MC_DISTRIBUTION = pd.DataFrame({
    "simulation": np.arange(1, G9_SIMULATIONS + 1),
    "annual_return": G9_PATH_MC_RETURNS,
    "max_drawdown": G9_PATH_MAX_DRAWDOWNS,
})

G9_PATH_MC_SUMMARY.to_csv(
    STOCK_OUTPUT_DIR / "g9_path_monte_carlo_summary.csv", index=False
)
G9_PATH_MC_DISTRIBUTION.to_parquet(
    STOCK_MODEL_DIR / "g9_path_monte_carlo_distribution.parquet", index=False
)

print("=" * 140)
print("G9 — DISTRIBUTION-AWARE PATH MONTE CARLO")
print("=" * 140)
print(f"Simulations:                       {G9_SIMULATIONS:,}")
print(f"Method:                            empirical {G9_BLOCK_LENGTH}-day block bootstrap")
print(f"Chunk size:                        {G9_CHUNK_SIZE:,}")
print(f"Skewness:                          {G9_SKEWNESS:.3f}")
print(f"Excess kurtosis:                   {G9_EXCESS_KURTOSIS:.3f}")
print(f"Probability of loss:               {G9_PROB_LOSS:.2%}")
print(f"Probability return < -10%:         {G9_PROB_BELOW_MINUS_10:.2%}")
print(f"Probability return < -20%:         {G9_PROB_BELOW_MINUS_20:.2%}")
print(f"Probability return > +20%:         {G9_PROB_ABOVE_PLUS_20:.2%}")
print(f"99% VaR / CVaR:                    {G9_VAR_99:.2%} / {G9_CVAR_99:.2%}")
print(f"P(max drawdown worse than -20%):   {G9_PROB_DD_WORSE_20:.2%}")
display(G9_PATH_MC_SUMMARY)
print("✓ G9 is a current-portfolio tail-risk simulation, not a historical strategy backtest.")

