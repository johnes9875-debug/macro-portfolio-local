# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 51 =====
# ============================================================
# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E1 — SECTOR-TO-STOCK RESEARCH HANDOFF
# ============================================================
#
# Purpose:
#
#   Translate the final Section D sector decisions into a
#   controlled stock-research universe.
#
# E1 does NOT:
#
#   - fetch constituents
#   - rank stocks
#   - value companies
#   - assign portfolio weights
#
# It defines:
#
#   CORE LONG SECTORS
#   TACTICAL LONG SECTORS
#   CONFLICT / RESEARCH-ONLY SECTORS
#   NEUTRAL SECTORS
#   NEGATIVE / EXCLUDED SECTORS
#
# Historical constituent membership remains OUT OF SCOPE
# until a point-in-time membership layer is implemented.
# ============================================================


# ============================================================
# 1. VALIDATE SECTION D
# ============================================================

required_e1_objects = [

    "SECTION_D_PASSED",
    "FINAL_SECTOR_SIGNAL_DASHBOARD",
    "SECTOR_TICKERS",
    "MARKET_AS_OF_DATE",

]


missing_e1_objects = [

    obj
    for obj in required_e1_objects
    if obj not in globals()

]


if missing_e1_objects:

    raise RuntimeError(
        "E1 requires completed Section D. Missing: "
        f"{missing_e1_objects}"
    )


if not bool(
    SECTION_D_PASSED
):

    raise RuntimeError(
        "Section D production gate did not pass. "
        "Do not start stock selection."
    )


# ============================================================
# 2. STOCK ENGINE DIRECTORIES
# ============================================================

if "MODELS_DIR" in globals():

    STOCK_MODEL_DIR = (

        Path(
            MODELS_DIR
        )
        /
        "stock"

    )

elif "PROJECT_ROOT" in globals():

    STOCK_MODEL_DIR = (

        Path(
            PROJECT_ROOT
        )
        /
        "models"
        /
        "stock"

    )

else:

    raise RuntimeError(
        "Neither MODELS_DIR nor PROJECT_ROOT is available."
    )


STOCK_MODEL_DIR.mkdir(

    parents=True,
    exist_ok=True,

)


if "OUTPUTS_DIR" in globals():

    STOCK_OUTPUT_DIR = (

        Path(
            OUTPUTS_DIR
        )
        /
        "stocks"

    )

else:

    STOCK_OUTPUT_DIR = (

        Path(
            PROJECT_ROOT
        )
        /
        "outputs"
        /
        "stocks"

    )


STOCK_OUTPUT_DIR.mkdir(

    parents=True,
    exist_ok=True,

)


# ============================================================
# 3. STOCK-UNIVERSE GOVERNANCE
# ============================================================
#
# Current design:
#
#   LIVE stock selection only.
#
# Initial universe:
#
#   Current deduplicated S&P 500 + Nasdaq-100 + SOXX constituents.
#
# This is coherent with:
#
#   benchmark = SPY
#   sector ETFs = SPDR S&P sector ETFs
#
# IMPORTANT:
#
# Current membership must NOT be used for historical backtests
# because doing so creates survivorship bias.
# ============================================================

STOCK_UNIVERSE_MODE = (
    "LIVE_ONLY_CURRENT_MEMBERSHIP"
)


STOCK_UNIVERSE_POLICY = {

    "benchmark":
        "SPY",

    "base_universe":
        "S&P 500 core + Nasdaq-100 growth overlay + SOXX semiconductor overlay",

    "sector_classification":
        "GICS",

    "membership_mode":
        STOCK_UNIVERSE_MODE,

    "historical_membership_ready":
        False,

    "allow_survivorship_biased_backtest":
        False,

    "allow_short":
        False,

}


# ============================================================
# 4. SECTOR STATUS → STOCK RESEARCH SCOPE
# ============================================================

CORE_LONG_STATUSES = {

    "STRONG OVERWEIGHT CANDIDATE",
    "OVERWEIGHT CANDIDATE",

}


TACTICAL_LONG_STATUSES = {

    "TACTICAL POSITIVE / WATCHLIST",

}


CONFLICT_STATUSES = {

    "CONFLICT WATCHLIST",

}


NEUTRAL_STATUSES = {

    "NEUTRAL",

}


NEGATIVE_STATUSES = {

    "TACTICAL NEGATIVE / WATCHLIST",
    "UNDERWEIGHT CANDIDATE",
    "STRONG UNDERWEIGHT CANDIDATE",

}


# ============================================================
# 5. CLASSIFICATION FUNCTION
# ============================================================

def classify_stock_research_scope(
    selection_status: str
) -> str:
    """
    Convert Section D status into stock-research scope.
    """

    if selection_status in CORE_LONG_STATUSES:

        return "CORE_LONG"


    if selection_status in TACTICAL_LONG_STATUSES:

        return "TACTICAL_LONG"


    if selection_status in CONFLICT_STATUSES:

        return "CONFLICT_RESEARCH_ONLY"


    if selection_status in NEUTRAL_STATUSES:

        return "NEUTRAL_CONTROL"


    if selection_status in NEGATIVE_STATUSES:

        return "NEGATIVE_EXCLUDED"


    raise ValueError(
        f"Unknown selection status: {selection_status}"
    )


# ============================================================
# 6. CREATE SECTOR → STOCK RESEARCH HANDOFF
# ============================================================

SECTOR_STOCK_RESEARCH_SCOPE = (

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        [
            "ticker",
            "sector",
            "risk_adjusted_rank",
            "risk_adjusted_score_z",
            "selection_status",
            "positive_quality_score",
            "negative_quality_score",
            "risk_bucket",
            "macro_market_alignment",
            "hard_conflict",
        ]
    ]

    .copy()

)


SECTOR_STOCK_RESEARCH_SCOPE[
    "stock_research_scope"
] = (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "selection_status"
    ]

    .apply(
        classify_stock_research_scope
    )

)


# ============================================================
# 7. LONG-ELIGIBILITY FLAGS
# ============================================================
#
# Only CORE_LONG is automatically eligible for downstream
# stock-selection ranking.
#
# TACTICAL_LONG can be researched, but is not yet automatically
# eligible for portfolio construction.
# ============================================================

SECTOR_STOCK_RESEARCH_SCOPE[
    "core_long_eligible"
] = (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "stock_research_scope"
    ]
    ==
    "CORE_LONG"

)


SECTOR_STOCK_RESEARCH_SCOPE[
    "tactical_research_eligible"
] = (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "stock_research_scope"
    ]

    .isin(
        [
            "CORE_LONG",
            "TACTICAL_LONG",
        ]
    )

)


SECTOR_STOCK_RESEARCH_SCOPE[
    "company_ranking_allowed"
] = (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "stock_research_scope"
    ]

    .isin(
        [
            "CORE_LONG",
            "TACTICAL_LONG",
            "CONFLICT_RESEARCH_ONLY",
            "NEUTRAL_CONTROL",
        ]
    )

)


SECTOR_STOCK_RESEARCH_SCOPE[
    "portfolio_long_allowed"
] = (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "stock_research_scope"
    ]
    ==
    "CORE_LONG"

)


# ============================================================
# 8. RESEARCH PRIORITY
# ============================================================
#
# Lower number = higher research priority.
# ============================================================

RESEARCH_SCOPE_PRIORITY = {

    "CORE_LONG":
        1,

    "TACTICAL_LONG":
        2,

    "CONFLICT_RESEARCH_ONLY":
        3,

    "NEUTRAL_CONTROL":
        4,

    "NEGATIVE_EXCLUDED":
        5,

}


SECTOR_STOCK_RESEARCH_SCOPE[
    "research_priority"
] = (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "stock_research_scope"
    ]

    .map(
        RESEARCH_SCOPE_PRIORITY
    )

)


# ============================================================
# 9. CREATE SECTOR GROUPS
# ============================================================

CORE_LONG_SECTORS = (

    SECTOR_STOCK_RESEARCH_SCOPE.loc[

        SECTOR_STOCK_RESEARCH_SCOPE[
            "stock_research_scope"
        ]
        ==
        "CORE_LONG",

        [
            "ticker",
            "sector",
        ],

    ]

    .copy()

)


TACTICAL_LONG_SECTORS = (

    SECTOR_STOCK_RESEARCH_SCOPE.loc[

        SECTOR_STOCK_RESEARCH_SCOPE[
            "stock_research_scope"
        ]
        ==
        "TACTICAL_LONG",

        [
            "ticker",
            "sector",
        ],

    ]

    .copy()

)


CONFLICT_SECTORS = (

    SECTOR_STOCK_RESEARCH_SCOPE.loc[

        SECTOR_STOCK_RESEARCH_SCOPE[
            "stock_research_scope"
        ]
        ==
        "CONFLICT_RESEARCH_ONLY",

        [
            "ticker",
            "sector",
        ],

    ]

    .copy()

)


NEGATIVE_SECTORS = (

    SECTOR_STOCK_RESEARCH_SCOPE.loc[

        SECTOR_STOCK_RESEARCH_SCOPE[
            "stock_research_scope"
        ]
        ==
        "NEGATIVE_EXCLUDED",

        [
            "ticker",
            "sector",
        ],

    ]

    .copy()

)


# ============================================================
# 10. ACTIVE STOCK-RESEARCH SECTORS
# ============================================================
#
# Active universe includes:
#
#   CORE_LONG
#   TACTICAL_LONG
#
# Conflict / neutral sectors remain available for relative
# comparison but are not active stock-selection sectors.
# ============================================================

ACTIVE_STOCK_RESEARCH_SECTORS = (

    SECTOR_STOCK_RESEARCH_SCOPE.loc[

        SECTOR_STOCK_RESEARCH_SCOPE[
            "tactical_research_eligible"
        ],

        [
            "ticker",
            "sector",
            "stock_research_scope",
            "risk_adjusted_rank",
            "risk_adjusted_score_z",
            "positive_quality_score",
        ],

    ]

    .sort_values(

        [
            "research_priority"
            if "research_priority"
            in SECTOR_STOCK_RESEARCH_SCOPE.columns
            else "risk_adjusted_rank",
            "risk_adjusted_rank",
        ]
        if False
        else
        [
            "risk_adjusted_rank",
        ],

        ascending=True,

    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 11. SANITY CHECK — NO NEGATIVE SECTOR IN LONG UNIVERSE
# ============================================================

negative_sector_tickers = set(

    NEGATIVE_SECTORS[
        "ticker"
    ]

)


active_sector_tickers = set(

    ACTIVE_STOCK_RESEARCH_SECTORS[
        "ticker"
    ]

)


invalid_overlap = (

    negative_sector_tickers
    &
    active_sector_tickers

)


if invalid_overlap:

    raise RuntimeError(

        "Negative sectors entered active stock universe: "
        f"{sorted(invalid_overlap)}"

    )


# ============================================================
# 12. SANITY CHECK — HARD CONFLICTS NOT CORE LONG
# ============================================================

invalid_conflict_core = (

    SECTOR_STOCK_RESEARCH_SCOPE[

        SECTOR_STOCK_RESEARCH_SCOPE[
            "hard_conflict"
        ]

        &

        SECTOR_STOCK_RESEARCH_SCOPE[
            "core_long_eligible"
        ]

    ]

)


if not invalid_conflict_core.empty:

    raise RuntimeError(

        "Hard-conflict sector incorrectly classified "
        "as CORE_LONG."

    )


# ============================================================
# 13. SANITY CHECK — STATUS COVERAGE
# ============================================================

if (

    SECTOR_STOCK_RESEARCH_SCOPE[
        "stock_research_scope"
    ]

    .isna()

    .any()

):

    raise RuntimeError(
        "Missing E1 stock research scope."
    )


if len(
    SECTOR_STOCK_RESEARCH_SCOPE
) != len(
    SECTOR_TICKERS
):

    raise RuntimeError(
        "E1 sector coverage mismatch."
    )


# ============================================================
# 14. E1 HEALTH TABLE
# ============================================================

E1_HEALTH = pd.DataFrame(

    [

        {

            "check":
                "Section D passed",

            "passed":
                bool(
                    SECTION_D_PASSED
                ),

        },

        {

            "check":
                "All sectors mapped",

            "passed":
                (
                    len(
                        SECTOR_STOCK_RESEARCH_SCOPE
                    )
                    ==
                    len(
                        SECTOR_TICKERS
                    )
                ),

        },

        {

            "check":
                "No missing research scope",

            "passed":
                (
                    ~
                    SECTOR_STOCK_RESEARCH_SCOPE[
                        "stock_research_scope"
                    ]
                    .isna()
                    .any()
                ),

        },

        {

            "check":
                "No negative sector in active long research",

            "passed":
                (
                    len(
                        invalid_overlap
                    )
                    ==
                    0
                ),

        },

        {

            "check":
                "No hard conflict in core long",

            "passed":
                invalid_conflict_core.empty,

        },

        {

            "check":
                "Historical membership backtest blocked",

            "passed":
                (
                    STOCK_UNIVERSE_POLICY[
                        "historical_membership_ready"
                    ]
                    is False
                ),

        },

    ]

)


E1_HEALTH[
    "status"
] = np.where(

    E1_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


E1_PASSED = bool(

    E1_HEALTH[
        "passed"
    ]
    .all()

)


# ============================================================
# 15. SUMMARY
# ============================================================

E1_SUMMARY = pd.DataFrame(

    [

        {

            "stock_universe_mode":
                STOCK_UNIVERSE_MODE,

            "core_long_sectors":
                len(
                    CORE_LONG_SECTORS
                ),

            "tactical_long_sectors":
                len(
                    TACTICAL_LONG_SECTORS
                ),

            "conflict_sectors":
                len(
                    CONFLICT_SECTORS
                ),

            "negative_sectors":
                len(
                    NEGATIVE_SECTORS
                ),

            "active_stock_research_sectors":
                len(
                    ACTIVE_STOCK_RESEARCH_SECTORS
                ),

            "market_as_of_date":
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ),

            "e1_passed":
                E1_PASSED,

        }

    ]

)


# ============================================================
# 16. SAVE OUTPUTS
# ============================================================

SECTOR_STOCK_RESEARCH_SCOPE.to_parquet(

    STOCK_MODEL_DIR
    /
    "sector_stock_research_scope.parquet",

    index=False,

)


E1_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e1_health.csv",

    index=False,

)


E1_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e1_summary.csv",

    index=False,

)


# ============================================================
# 17. DISPLAY
# ============================================================

print(
    "=" * 110
)

print(
    "E1 — SECTOR → STOCK RESEARCH HANDOFF"
)

print(
    "=" * 110
)


print(
    f"Universe mode:              "
    f"{STOCK_UNIVERSE_MODE}"
)


print(
    f"Market as-of date:          "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    f"Core long sectors:          "
    f"{len(CORE_LONG_SECTORS)}"
)


print(
    f"Tactical long sectors:      "
    f"{len(TACTICAL_LONG_SECTORS)}"
)


print(
    f"Conflict sectors:           "
    f"{len(CONFLICT_SECTORS)}"
)


print(
    f"Negative/excluded sectors:  "
    f"{len(NEGATIVE_SECTORS)}"
)


print(
    "\nSector → stock research scope:"
)


display(

    SECTOR_STOCK_RESEARCH_SCOPE[
        [
            "risk_adjusted_rank",
            "ticker",
            "sector",
            "selection_status",
            "stock_research_scope",
            "core_long_eligible",
            "tactical_research_eligible",
            "portfolio_long_allowed",
            "hard_conflict",
        ]
    ]

    .sort_values(
        "risk_adjusted_rank"
    )

)


print(
    "\nActive stock-research sectors:"
)


display(
    ACTIVE_STOCK_RESEARCH_SECTORS
)


print(
    "\nE1 health:"
)


display(
    E1_HEALTH
)


if not E1_PASSED:

    raise RuntimeError(
        "E1 PRODUCTION GATE FAILED."
    )


print(
    "\n✓ E1 COMPLETE — "
    "stock-research scope and governance established."
)

# ===== ORIGINAL NOTEBOOK CELL 52 =====
# ============================================================
# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E2 — DYNAMIC MASTER UNIVERSE: S&P 500 + NASDAQ-100 + SOXX
# ============================================================
# Core = S&P 500, growth overlay = Nasdaq-100, specialist overlay = SOXX.
# Membership is current/live only and is explicitly blocked from historical PIT backtests.

from pathlib import Path
import numpy as np
import pandas as pd

from macro_portfolio.universe import (
    GICS_TO_SECTOR_ETF,
    combine_current_universes,
    enrich_gics_sector_coverage,
    fetch_nasdaq100,
    fetch_soxx,
    fetch_sp500,
    load_live_or_cache,
    _load_bundled_soxx_snapshot,
)

required_e2_objects = ["E1_PASSED", "SECTOR_STOCK_RESEARCH_SCOPE", "STOCK_MODEL_DIR", "STOCK_OUTPUT_DIR", "MARKET_AS_OF_DATE", "STOCK_UNIVERSE_MODE"]
missing_e2_objects = [x for x in required_e2_objects if x not in globals()]
if missing_e2_objects:
    raise RuntimeError(f"E2 requires E1 first. Missing: {missing_e2_objects}")
if not bool(E1_PASSED):
    raise RuntimeError("E1 production gate did not pass.")

UNIVERSE_CFG = CONFIG.get("universe", {}) if "CONFIG" in globals() else {}
UNIVERSE_HTTP_TIMEOUT = int(UNIVERSE_CFG.get("http_timeout_seconds", 30))
CONSTITUENT_SNAPSHOT_DATE = pd.Timestamp(MARKET_AS_OF_DATE).normalize()
_base_data = Path(DATA_DIR) if "DATA_DIR" in globals() else Path(PROJECT_ROOT) / "data"
CONSTITUENT_RAW_ROOT = _base_data / "raw" / "constituents"
CONSTITUENT_CURATED_DIR = _base_data / "curated" / "constituents"
CONSTITUENT_CURATED_DIR.mkdir(parents=True, exist_ok=True)

SP500_ONLY_CONSTITUENTS, SP500_SOURCE_MODE, SP500_SOURCE_DETAIL = load_live_or_cache(
    "sp500", CONSTITUENT_SNAPSHOT_DATE, CONSTITUENT_RAW_ROOT / "sp500", CONSTITUENT_CURATED_DIR,
    lambda: fetch_sp500(timeout=UNIVERSE_HTTP_TIMEOUT),
)
NASDAQ100_CONSTITUENTS, NASDAQ100_SOURCE_MODE, NASDAQ100_SOURCE_DETAIL = load_live_or_cache(
    "nasdaq100", CONSTITUENT_SNAPSHOT_DATE, CONSTITUENT_RAW_ROOT / "nasdaq100", CONSTITUENT_CURATED_DIR,
    lambda: fetch_nasdaq100(timeout=UNIVERSE_HTTP_TIMEOUT),
)
SOXX_BUNDLED_FALLBACK = Path(PROJECT_ROOT) / "data" / "reference" / "constituents" / "soxx_last_known_good.csv"
SOXX_CONSTITUENTS, SOXX_SOURCE_MODE, SOXX_SOURCE_DETAIL = load_live_or_cache(
    "soxx", CONSTITUENT_SNAPSHOT_DATE, CONSTITUENT_RAW_ROOT / "soxx", CONSTITUENT_CURATED_DIR,
    lambda: fetch_soxx(timeout=UNIVERSE_HTTP_TIMEOUT),
    bundled_fallback=SOXX_BUNDLED_FALLBACK,
    bundled_loader=_load_bundled_soxx_snapshot,
)

# Degraded SOXX membership is allowed for continuity but never hidden.
_SOXX_SNAPSHOT_DATES = pd.to_datetime(
    SOXX_CONSTITUENTS.get("snapshot_date", pd.Series(dtype="object")),
    errors="coerce",
).dropna()
SOXX_FALLBACK_SNAPSHOT_DATE = (_SOXX_SNAPSHOT_DATES.max() if not _SOXX_SNAPSHOT_DATES.empty else pd.NaT)
SOXX_FALLBACK_AGE_DAYS = (
    int((CONSTITUENT_SNAPSHOT_DATE - SOXX_FALLBACK_SNAPSHOT_DATE).days)
    if pd.notna(SOXX_FALLBACK_SNAPSHOT_DATE) else None
)
_SOXX_WARN_AGE = int(UNIVERSE_CFG.get("resilience", {}).get("warn_if_bundled_snapshot_older_than_days", 90))
SOXX_SOURCE_WARNING = None
if SOXX_SOURCE_MODE == "FALLBACK_BUNDLED_SNAPSHOT":
    SOXX_SOURCE_WARNING = (
        f"SOXX live source unavailable; using bundled last-known-good snapshot "
        f"dated {SOXX_FALLBACK_SNAPSHOT_DATE.date() if pd.notna(SOXX_FALLBACK_SNAPSHOT_DATE) else 'unknown'}."
    )
    if SOXX_FALLBACK_AGE_DAYS is not None and SOXX_FALLBACK_AGE_DAYS > _SOXX_WARN_AGE:
        SOXX_SOURCE_WARNING += f" WARNING: snapshot age={SOXX_FALLBACK_AGE_DAYS} days."
    print("⚠ " + SOXX_SOURCE_WARNING)

MASTER_STOCK_UNIVERSE = combine_current_universes(
    SP500_ONLY_CONSTITUENTS, NASDAQ100_CONSTITUENTS, SOXX_CONSTITUENTS, CONSTITUENT_SNAPSHOT_DATE
)

# Sector enrichment belongs to universe construction, not downstream research.
# Every ticker must resolve to exactly one of the 11 canonical GICS sectors
# before the master universe is handed to E1/E3/F.  S&P metadata is canonicalized,
# every SOXX semiconductor member maps to Information Technology, and any remaining
# Nasdaq-only gaps are enriched from persistent/company metadata.
MASTER_STOCK_UNIVERSE = enrich_gics_sector_coverage(
    MASTER_STOCK_UNIVERSE,
    curated_dir=CONSTITUENT_CURATED_DIR,
    snapshot_date=CONSTITUENT_SNAPSHOT_DATE,
)
MASTER_STOCK_UNIVERSE["membership_mode"] = STOCK_UNIVERSE_MODE
MASTER_STOCK_UNIVERSE["source_mode"] = (
    "SP500=" + SP500_SOURCE_MODE + ";NASDAQ100=" + NASDAQ100_SOURCE_MODE + ";SOXX=" + SOXX_SOURCE_MODE
)
MASTER_STOCK_UNIVERSE["source_detail"] = (
    "SP500=" + str(SP500_SOURCE_DETAIL) + ";NASDAQ100=" + str(NASDAQ100_SOURCE_DETAIL) + ";SOXX=" + str(SOXX_SOURCE_DETAIL)
)

if MASTER_STOCK_UNIVERSE.empty:
    raise RuntimeError("Dynamic master universe is empty.")
if MASTER_STOCK_UNIVERSE["ticker"].duplicated().any():
    raise RuntimeError("Duplicate tickers detected after S&P500/Nasdaq100/SOXX deduplication.")
GICS_SECTOR_COVERAGE = float(MASTER_STOCK_UNIVERSE["sector_ticker"].notna().mean())
if not np.isclose(GICS_SECTOR_COVERAGE, 1.0):
    bad = MASTER_STOCK_UNIVERSE.loc[
        MASTER_STOCK_UNIVERSE["sector_ticker"].isna(),
        ["ticker", "company_name", "gics_sector", "universe_memberships", "gics_sector_source"],
    ]
    display(bad)
    raise RuntimeError(
        f"Master universe must have 100% canonical GICS-sector coverage; "
        f"found {GICS_SECTOR_COVERAGE:.2%}."
    )

sector_scope_columns = [
    "ticker", "sector", "risk_adjusted_rank", "risk_adjusted_score_z", "selection_status",
    "stock_research_scope", "core_long_eligible", "tactical_research_eligible",
    "company_ranking_allowed", "portfolio_long_allowed", "research_priority",
]
sector_scope_map = SECTOR_STOCK_RESEARCH_SCOPE[sector_scope_columns].rename(columns={
    "ticker":"sector_ticker", "sector":"sector_name", "risk_adjusted_rank":"sector_rank",
    "risk_adjusted_score_z":"sector_signal_z",
})
MASTER_STOCK_UNIVERSE = MASTER_STOCK_UNIVERSE.merge(sector_scope_map, on="sector_ticker", how="left", validate="many_to_one")
if MASTER_STOCK_UNIVERSE["stock_research_scope"].isna().any():
    raise RuntimeError("Missing E1 research-scope mapping for part of the master universe.")

MASTER_STOCK_UNIVERSE["active_stock_research"] = MASTER_STOCK_UNIVERSE["tactical_research_eligible"].astype(bool)
MASTER_STOCK_UNIVERSE["core_long_company_universe"] = MASTER_STOCK_UNIVERSE["core_long_eligible"].astype(bool)
MASTER_STOCK_UNIVERSE["portfolio_long_allowed_company"] = MASTER_STOCK_UNIVERSE["portfolio_long_allowed"].astype(bool)

# Backward compatibility: downstream sections historically refer to SP500_CONSTITUENTS.
# It now intentionally aliases the deduplicated master universe, not S&P-only membership.
SP500_CONSTITUENTS = MASTER_STOCK_UNIVERSE

ACTIVE_STOCK_UNIVERSE = MASTER_STOCK_UNIVERSE.loc[MASTER_STOCK_UNIVERSE["active_stock_research"]].copy()
CORE_LONG_STOCK_UNIVERSE = MASTER_STOCK_UNIVERSE.loc[MASTER_STOCK_UNIVERSE["core_long_company_universe"]].copy()
RESEARCHABLE_STOCK_UNIVERSE = MASTER_STOCK_UNIVERSE.loc[MASTER_STOCK_UNIVERSE["company_ranking_allowed"]].copy()
for _df in [ACTIVE_STOCK_UNIVERSE, CORE_LONG_STOCK_UNIVERSE, RESEARCHABLE_STOCK_UNIVERSE]:
    _df.sort_values(["sector_rank","company_name"], inplace=True)
    _df.reset_index(drop=True, inplace=True)

_SOXX_MEMBERSHIP_SOURCES = sorted(
    {str(x) for x in MASTER_STOCK_UNIVERSE.loc[MASTER_STOCK_UNIVERSE["member_soxx"], "soxx_membership_source"].dropna().unique()}
) if "soxx_membership_source" in MASTER_STOCK_UNIVERSE.columns else []
_SOXX_EXACT_COUNT = int(
    MASTER_STOCK_UNIVERSE.loc[MASTER_STOCK_UNIVERSE["member_soxx"], "soxx_membership_exact"].fillna(False).sum()
) if "soxx_membership_exact" in MASTER_STOCK_UNIVERSE.columns else 0
_SOXX_TOTAL_COUNT = int(MASTER_STOCK_UNIVERSE["member_soxx"].sum())
if _SOXX_TOTAL_COUNT > 0 and _SOXX_EXACT_COUNT == _SOXX_TOTAL_COUNT:
    _SOXX_SOURCE_QUALITY = "ISSUER_EXACT"
elif SOXX_SOURCE_MODE == "LIVE_FETCH":
    _SOXX_SOURCE_QUALITY = "SECONDARY_LIVE_OR_MIXED"
elif SOXX_SOURCE_MODE == "FALLBACK_CURATED_CACHE":
    _SOXX_SOURCE_QUALITY = "CACHED_LAST_KNOWN_GOOD"
elif SOXX_SOURCE_MODE == "FALLBACK_BUNDLED_SNAPSHOT":
    _SOXX_SOURCE_QUALITY = "BUNDLED_LAST_KNOWN_GOOD"
else:
    _SOXX_SOURCE_QUALITY = "DEGRADED"

MASTER_UNIVERSE_SOURCE_SUMMARY = pd.DataFrame([
    {"source":"S&P 500 core", "members":int(MASTER_STOCK_UNIVERSE["member_sp500"].sum()), "mode":SP500_SOURCE_MODE, "detail":str(SP500_SOURCE_DETAIL)},
    {"source":"Nasdaq-100 growth overlay", "members":int(MASTER_STOCK_UNIVERSE["member_nasdaq100"].sum()), "mode":NASDAQ100_SOURCE_MODE, "detail":str(NASDAQ100_SOURCE_DETAIL)},
    {"source":"SOXX semiconductor overlay", "members":_SOXX_TOTAL_COUNT, "mode":SOXX_SOURCE_MODE, "detail":";".join(_SOXX_MEMBERSHIP_SOURCES) or str(SOXX_SOURCE_DETAIL), "quality":_SOXX_SOURCE_QUALITY},
    {"source":"Deduplicated master", "members":len(MASTER_STOCK_UNIVERSE), "mode":"UNION", "detail":"S&P500 + Nasdaq100 + semiconductor specialist overlay"},
])
SP500_SECTOR_COVERAGE = MASTER_STOCK_UNIVERSE.groupby(["sector_rank","sector_ticker","sector_name","stock_research_scope"], as_index=False).agg(company_count=("ticker","count")).sort_values("sector_rank")

_e2_checks = [
    ("Master universe non-empty", len(MASTER_STOCK_UNIVERSE) > 0, f"rows={len(MASTER_STOCK_UNIVERSE)}"),
    ("Master tickers unique", MASTER_STOCK_UNIVERSE["ticker"].nunique()==len(MASTER_STOCK_UNIVERSE), f"unique={MASTER_STOCK_UNIVERSE['ticker'].nunique()}"),
    ("S&P 500 core loaded", int(MASTER_STOCK_UNIVERSE["member_sp500"].sum()) >= 450, f"members={int(MASTER_STOCK_UNIVERSE['member_sp500'].sum())}"),
    ("Nasdaq-100 overlay loaded", int(MASTER_STOCK_UNIVERSE["member_nasdaq100"].sum()) >= 90, f"members={int(MASTER_STOCK_UNIVERSE['member_nasdaq100'].sum())}"),
    ("SOXX overlay loaded", int(MASTER_STOCK_UNIVERSE["member_soxx"].sum()) >= 20, f"members={int(MASTER_STOCK_UNIVERSE['member_soxx'].sum())}"),
    ("100% canonical GICS sector coverage", np.isclose(GICS_SECTOR_COVERAGE, 1.0), f"coverage={GICS_SECTOR_COVERAGE:.2%}"),
    ("All companies mapped to sector scope", MASTER_STOCK_UNIVERSE["stock_research_scope"].notna().all(), "E1 mapping complete"),
    ("Historical membership backtest blocked", (~MASTER_STOCK_UNIVERSE["historical_backtest_eligible"].astype(bool)).all(), "LIVE_ONLY"),
    ("Active stock universe non-empty", len(ACTIVE_STOCK_UNIVERSE)>0, f"active={len(ACTIVE_STOCK_UNIVERSE)}"),
]
E2_HEALTH = pd.DataFrame(_e2_checks, columns=["check","passed","detail"])
E2_HEALTH["status"] = np.where(E2_HEALTH["passed"], "✓ PASS", "✗ FAIL")
E2_PASSED = bool(E2_HEALTH["passed"].all())
E2_SUMMARY = pd.DataFrame([{
    "stock_universe_mode":STOCK_UNIVERSE_MODE,
    "master_company_count":len(MASTER_STOCK_UNIVERSE),
    "active_company_count":len(ACTIVE_STOCK_UNIVERSE),
    "core_long_company_count":len(CORE_LONG_STOCK_UNIVERSE),
    "researchable_company_count":len(RESEARCHABLE_STOCK_UNIVERSE),
    "sp500_members":int(MASTER_STOCK_UNIVERSE["member_sp500"].sum()),
    "nasdaq100_members":int(MASTER_STOCK_UNIVERSE["member_nasdaq100"].sum()),
    "soxx_members":int(MASTER_STOCK_UNIVERSE["member_soxx"].sum()),
    "soxx_exact_members":_SOXX_EXACT_COUNT,
    "soxx_source_quality":_SOXX_SOURCE_QUALITY,
    "soxx_membership_sources":";".join(_SOXX_MEMBERSHIP_SOURCES),
    "gics_sector_coverage":GICS_SECTOR_COVERAGE,
    "passed":E2_PASSED,
}])

MASTER_STOCK_UNIVERSE.to_parquet(Path(STOCK_MODEL_DIR)/"master_current_stock_universe.parquet", index=False)
MASTER_STOCK_UNIVERSE.to_csv(Path(STOCK_OUTPUT_DIR)/"master_current_stock_universe.csv", index=False)
SP500_ONLY_CONSTITUENTS.to_parquet(Path(STOCK_MODEL_DIR)/"sp500_current_constituents.parquet", index=False)
NASDAQ100_CONSTITUENTS.to_parquet(Path(STOCK_MODEL_DIR)/"nasdaq100_current_constituents.parquet", index=False)
SOXX_CONSTITUENTS.to_parquet(Path(STOCK_MODEL_DIR)/"soxx_current_holdings.parquet", index=False)
ACTIVE_STOCK_UNIVERSE.to_parquet(Path(STOCK_MODEL_DIR)/"active_stock_research_universe.parquet", index=False)
CORE_LONG_STOCK_UNIVERSE.to_parquet(Path(STOCK_MODEL_DIR)/"core_long_stock_universe.parquet", index=False)
RESEARCHABLE_STOCK_UNIVERSE.to_parquet(Path(STOCK_MODEL_DIR)/"researchable_stock_universe.parquet", index=False)
E2_HEALTH.to_csv(Path(STOCK_OUTPUT_DIR)/"e2_health.csv", index=False)
E2_SUMMARY.to_csv(Path(STOCK_OUTPUT_DIR)/"e2_summary.csv", index=False)
MASTER_UNIVERSE_SOURCE_SUMMARY.to_csv(Path(STOCK_OUTPUT_DIR)/"e2_universe_source_summary.csv", index=False)

print("="*120)
print("E2 — DYNAMIC MASTER UNIVERSE: S&P 500 + NASDAQ-100 + SOXX")
print("="*120)
display(MASTER_UNIVERSE_SOURCE_SUMMARY)
print(f"Deduplicated master universe: {len(MASTER_STOCK_UNIVERSE)}")
print(f"Active macro-sector research universe: {len(ACTIVE_STOCK_UNIVERSE)}")
print(f"Researchable/control universe: {len(RESEARCHABLE_STOCK_UNIVERSE)}")
print(f"Canonical GICS sector coverage: {GICS_SECTOR_COVERAGE:.2%}")
print("GICS sector counts:")
display(MASTER_STOCK_UNIVERSE.groupby(["gics_sector","sector_ticker"], as_index=False).agg(company_count=("ticker","count")).sort_values("company_count", ascending=False))
display(E2_HEALTH)
if not E2_PASSED:
    raise RuntimeError("E2 DYNAMIC MASTER UNIVERSE PRODUCTION GATE FAILED.")
print("✓ E2 COMPLETE — current S&P500 core + Nasdaq100 growth overlay + SOXX specialist overlay acquired and deduplicated.")


# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E3 — STOCK MARKET DATA ACQUISITION + QA
# ============================================================
#
# Purpose:
#
#   1. Download market history for researchable S&P 500 stocks
#   2. Cache each stock independently in Parquet
#   3. Update incrementally on subsequent runs
#   4. Preserve adjusted-price history for return signals
#   5. Run freshness / history / coverage checks
#   6. Build a consolidated stock-price panel for E4
#
# IMPORTANT:
#
#   Current-membership universe remains LIVE ONLY.
#
#   These prices must NOT be used to backtest the present-day
#   constituent universe historically.
#
# ============================================================


# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import math
import re
import time

import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# 2. VALIDATE E2
# ============================================================

required_e3_objects = [

    "E2_PASSED",
    "RESEARCHABLE_STOCK_UNIVERSE",
    "CORE_LONG_STOCK_UNIVERSE",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
    "MARKET_AS_OF_DATE",

]


missing_e3_objects = [

    obj
    for obj in required_e3_objects
    if obj not in globals()

]


if missing_e3_objects:

    raise RuntimeError(
        "E3 requires E2 first. Missing: "
        f"{missing_e3_objects}"
    )


if not bool(
    E2_PASSED
):

    raise RuntimeError(
        "E2 production gate did not pass."
    )


# ============================================================
# 3. STORAGE DIRECTORIES
# ============================================================

if "DATA_DIR" in globals():

    STOCK_PRICE_RAW_DIR = (

        Path(
            DATA_DIR
        )
        /
        "raw"
        /
        "stocks"
        /
        "prices"

    )


    STOCK_PRICE_CURATED_DIR = (

        Path(
            DATA_DIR
        )
        /
        "curated"
        /
        "stocks"

    )


elif "PROJECT_ROOT" in globals():

    STOCK_PRICE_RAW_DIR = (

        Path(
            PROJECT_ROOT
        )
        /
        "data"
        /
        "raw"
        /
        "stocks"
        /
        "prices"

    )


    STOCK_PRICE_CURATED_DIR = (

        Path(
            PROJECT_ROOT
        )
        /
        "data"
        /
        "curated"
        /
        "stocks"

    )


else:

    raise RuntimeError(
        "Neither DATA_DIR nor PROJECT_ROOT is available."
    )


STOCK_PRICE_RAW_DIR.mkdir(
    parents=True,
    exist_ok=True
)


STOCK_PRICE_CURATED_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 4. E3 PARAMETERS
# ============================================================
#
# Three years is sufficient for the LIVE stock-selection
# signals planned in E4:
#
#   momentum
#   relative strength
#   beta
#   volatility
#   residual / alpha diagnostics
#
# Historical signal backtesting remains blocked anyway.
# ============================================================

STOCK_PRICE_LOOKBACK_YEARS = 3


STOCK_PRICE_MIN_OBSERVATIONS = 126

STOCK_PRICE_PREFERRED_OBSERVATIONS = 504


STOCK_PRICE_MAX_LAG_DAYS = 7


STOCK_DOWNLOAD_BATCH_SIZE = 50


if (
    "CONFIG" in globals()
    and
    isinstance(
        CONFIG,
        dict
    )
):

    STOCK_UPDATE_OVERLAP_DAYS = int(

        CONFIG.get(
            "data",
            {}
        ).get(
            "update_overlap_days",
            5
        )

    )

else:

    STOCK_UPDATE_OVERLAP_DAYS = 5


# Dynamic universe breadth guardrails. These are investability/data-quality
# screens, not alpha signals.
_UNIVERSE_LIQ_CFG = CONFIG.get("universe", {}).get("liquidity", {}) if "CONFIG" in globals() else {}
STOCK_MIN_ADV20_DOLLAR = float(_UNIVERSE_LIQ_CFG.get("min_adv20_usd", 20_000_000))
STOCK_MIN_PRICE = float(_UNIVERSE_LIQ_CFG.get("min_price_usd", 3.0))
STOCK_LIQUIDITY_WINDOW = int(_UNIVERSE_LIQ_CFG.get("adv_window", 20))


STOCK_PRICE_START_DATE = (

    pd.Timestamp(
        MARKET_AS_OF_DATE
    )

    -
    pd.DateOffset(
        years=STOCK_PRICE_LOOKBACK_YEARS
    )

)


# Yahoo's end date is exclusive.
STOCK_PRICE_END_DATE = (

    pd.Timestamp(
        MARKET_AS_OF_DATE
    )

    +
    pd.Timedelta(
        days=1
    )

)


# ============================================================
# 5. STOCK PRICE UNIVERSE
# ============================================================
#
# Use RESEARCHABLE_STOCK_UNIVERSE rather than downloading
# negative/excluded sectors unnecessarily.
#
# This includes:
#
#   CORE_LONG
#   TACTICAL_LONG
#   CONFLICT_RESEARCH_ONLY
#   NEUTRAL_CONTROL
# ============================================================

required_universe_columns = [

    "ticker",
    "yahoo_ticker",
    "company_name",
    "sector_ticker",
    "sector_name",
    "stock_research_scope",
    "member_sp500",
    "member_nasdaq100",
    "member_soxx",
    "specialist_group",
    "universe_memberships",

]


missing_universe_columns = [

    column

    for column in required_universe_columns

    if column
    not in
    RESEARCHABLE_STOCK_UNIVERSE.columns

]


if missing_universe_columns:

    raise RuntimeError(

        "RESEARCHABLE_STOCK_UNIVERSE missing columns: "
        f"{missing_universe_columns}"

    )


STOCK_PRICE_UNIVERSE = (

    RESEARCHABLE_STOCK_UNIVERSE[
        required_universe_columns
        +
        [
            "sector_rank",
            "sector_signal_z",
            "core_long_eligible",
            "tactical_research_eligible",
        ]
    ]

    .drop_duplicates(
        subset=[
            "yahoo_ticker"
        ]
    )

    .sort_values(
        [
            "sector_rank",
            "company_name",
        ]
    )

    .reset_index(
        drop=True
    )

)


if STOCK_PRICE_UNIVERSE.empty:

    raise RuntimeError(
        "E3 stock price universe is empty."
    )


# ============================================================
# 6. SAFE FILE NAME
# ============================================================

def safe_stock_filename(
    ticker: str
) -> str:

    ticker = str(
        ticker
    )


    return re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        ticker
    )


# ============================================================
# 7. RAW PRICE PATH
# ============================================================

def get_stock_price_path(
    yahoo_ticker: str
) -> Path:

    return (

        STOCK_PRICE_RAW_DIR
        /
        (
            safe_stock_filename(
                yahoo_ticker
            )
            +
            ".parquet"
        )

    )


# ============================================================
# 8. LOAD EXISTING STOCK PRICE CACHE
# ============================================================

def load_stock_price_cache(
    yahoo_ticker: str
) -> pd.DataFrame:

    path = get_stock_price_path(
        yahoo_ticker
    )


    if not path.exists():

        return pd.DataFrame()


    try:

        df = pd.read_parquet(
            path
        )


    except Exception:

        return pd.DataFrame()


    if df.empty:

        return df


    if "date" not in df.columns:

        return pd.DataFrame()


    df = df.copy()


    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )


    df = (

        df

        .dropna(
            subset=["date"]
        )

        .sort_values(
            "date"
        )

        .drop_duplicates(
            subset=["date"],
            keep="last"
        )

        .reset_index(
            drop=True
        )

    )


    return df


# ============================================================
# 9. MERGE INCREMENTAL PRICE DATA
# ============================================================

def merge_stock_price_data(
    existing: pd.DataFrame,
    new_data: pd.DataFrame
) -> pd.DataFrame:

    frames = []


    if (
        existing is not None
        and
        not existing.empty
    ):

        frames.append(
            existing.copy()
        )


    if (
        new_data is not None
        and
        not new_data.empty
    ):

        frames.append(
            new_data.copy()
        )


    if not frames:

        return pd.DataFrame()


    combined = pd.concat(

        frames,

        ignore_index=True,

        sort=False,

    )


    combined[
        "date"
    ] = pd.to_datetime(

        combined[
            "date"
        ],

        errors="coerce",

    )


    combined = (

        combined

        .dropna(
            subset=["date"]
        )

        .loc[
            lambda x:
            x["date"]
            <=
            pd.Timestamp(
                MARKET_AS_OF_DATE
            )
        ]

        .sort_values(
            "date"
        )

        .drop_duplicates(
            subset=["date"],
            keep="last"
        )

        .reset_index(
            drop=True
        )

    )


    return combined


# ============================================================
# 10. SAVE STOCK PRICE CACHE
# ============================================================

def save_stock_price_cache(
    yahoo_ticker: str,
    df: pd.DataFrame
):

    if df.empty:

        return


    path = get_stock_price_path(
        yahoo_ticker
    )


    df.to_parquet(

        path,

        index=False,

    )


# ============================================================
# 11. NORMALIZE YFINANCE OUTPUT FOR ONE TICKER
# ============================================================

def normalize_yfinance_stock_frame(
    frame: pd.DataFrame,
    yahoo_ticker: str
) -> pd.DataFrame:
    """
    Convert a yfinance output block into our canonical schema.
    """

    if (
        frame is None
        or
        frame.empty
    ):

        return pd.DataFrame()


    df = frame.copy()


    # --------------------------------------------------------
    # Flatten unexpected residual MultiIndex
    # --------------------------------------------------------

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = [

            "_".join(
                [
                    str(x)
                    for x in column
                    if str(x) != ""
                ]
            )

            for column in df.columns

        ]


    # --------------------------------------------------------
    # Move index into date column
    # --------------------------------------------------------

    df = df.reset_index()


    # --------------------------------------------------------
    # Normalize column names
    # --------------------------------------------------------

    def normalize_column_name(
        column
    ) -> str:

        return (

            str(
                column
            )

            .strip()

            .lower()

            .replace(
                " ",
                "_"
            )

            .replace(
                "-",
                "_"
            )

        )


    df.columns = [

        normalize_column_name(
            column
        )

        for column in df.columns

    ]


    # --------------------------------------------------------
    # Identify date
    # --------------------------------------------------------

    if "date" not in df.columns:

        datetime_candidates = [

            column

            for column in df.columns

            if (
                "date" in column
                or
                "datetime" in column
            )

        ]


        if not datetime_candidates:

            return pd.DataFrame()


        df = df.rename(

            columns={
                datetime_candidates[0]:
                    "date"
            }

        )


    # --------------------------------------------------------
    # Normalize price columns
    # --------------------------------------------------------

    canonical_map = {}


    for column in df.columns:

        compact = (

            column

            .replace(
                "_",
                ""
            )

        )


        if compact == "open":

            canonical_map[
                column
            ] = "open"


        elif compact == "high":

            canonical_map[
                column
            ] = "high"


        elif compact == "low":

            canonical_map[
                column
            ] = "low"


        elif compact == "close":

            canonical_map[
                column
            ] = "close"


        elif compact in {
            "adjclose",
            "adjustedclose",
        }:

            canonical_map[
                column
            ] = "adj_close"


        elif compact == "volume":

            canonical_map[
                column
            ] = "volume"


    df = df.rename(
        columns=canonical_map
    )


    if "close" not in df.columns:

        return pd.DataFrame()


    # --------------------------------------------------------
    # Adjusted-close fallback
    # --------------------------------------------------------

    if "adj_close" not in df.columns:

        df[
            "adj_close"
        ] = df[
            "close"
        ]


        adjusted_close_fallback = True


    else:

        adjusted_close_fallback = False


    # --------------------------------------------------------
    # Guarantee optional columns
    # --------------------------------------------------------

    for column in [

        "open",
        "high",
        "low",
        "volume",

    ]:

        if column not in df.columns:

            df[
                column
            ] = np.nan


    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    for column in [

        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",

    ]:

        df[
            column
        ] = pd.to_numeric(

            df[
                column
            ],

            errors="coerce",

        )


    df[
        "date"
    ] = pd.to_datetime(

        df[
            "date"
        ],

        errors="coerce",

    )


    # Remove timezone if present.
    try:

        df[
            "date"
        ] = (

            df[
                "date"
            ]

            .dt.tz_localize(
                None
            )

        )

    except (TypeError, AttributeError):

        pass


    df[
        "yahoo_ticker"
    ] = yahoo_ticker


    df[
        "adj_close_fallback"
    ] = adjusted_close_fallback


    df = (

        df[
            [
                "date",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "yahoo_ticker",
                "adj_close_fallback",
            ]
        ]

        .dropna(
            subset=[
                "date",
                "adj_close",
            ]
        )

        .sort_values(
            "date"
        )

        .drop_duplicates(
            subset=["date"],
            keep="last"
        )

        .reset_index(
            drop=True
        )

    )


    return df


# ============================================================
# 12. EXTRACT ONE TICKER FROM BATCH DOWNLOAD
# ============================================================

def extract_ticker_from_yfinance_batch(
    raw: pd.DataFrame,
    yahoo_ticker: str
) -> pd.DataFrame:

    if (
        raw is None
        or
        raw.empty
    ):

        return pd.DataFrame()


    # --------------------------------------------------------
    # Multi-ticker yfinance output
    # --------------------------------------------------------

    if isinstance(
        raw.columns,
        pd.MultiIndex
    ):

        level_0 = set(
            raw.columns.get_level_values(
                0
            )
        )


        level_1 = set(
            raw.columns.get_level_values(
                1
            )
        )


        if yahoo_ticker in level_0:

            sub = raw[
                yahoo_ticker
            ].copy()


        elif yahoo_ticker in level_1:

            sub = raw.xs(

                yahoo_ticker,

                axis=1,

                level=1,

                drop_level=True,

            ).copy()


        else:

            return pd.DataFrame()


    # --------------------------------------------------------
    # Single ticker output
    # --------------------------------------------------------

    else:

        sub = raw.copy()


    return normalize_yfinance_stock_frame(

        sub,

        yahoo_ticker,

    )


# ============================================================
# 13. DOWNLOAD ONE BATCH
# ============================================================

def download_stock_batch(
    tickers,
    start_date,
    end_date
):

    tickers = list(
        dict.fromkeys(
            tickers
        )
    )


    if not tickers:

        return {}


    last_exception = None


    for attempt in range(
        2
    ):

        try:

            raw = yf.download(

                tickers=tickers,

                start=(
                    pd.Timestamp(
                        start_date
                    )
                    .strftime(
                        "%Y-%m-%d"
                    )
                ),

                end=(
                    pd.Timestamp(
                        end_date
                    )
                    .strftime(
                        "%Y-%m-%d"
                    )
                ),

                auto_adjust=False,

                actions=False,

                group_by="ticker",

                progress=False,

                threads=True,

            )


            result = {}


            for ticker in tickers:

                result[
                    ticker
                ] = (

                    extract_ticker_from_yfinance_batch(

                        raw,
                        ticker,

                    )

                )


            return result


        except Exception as exc:

            last_exception = exc


            if attempt == 0:

                time.sleep(
                    2
                )


    raise RuntimeError(

        "Yahoo batch download failed for "
        f"{tickers[:5]}"
        f"{'...' if len(tickers) > 5 else ''}: "
        f"{last_exception}"

    )


# ============================================================
# 14. BUILD INCREMENTAL UPDATE PLAN
# ============================================================

update_plan_rows = []


for _, row in (
    STOCK_PRICE_UNIVERSE.iterrows()
):

    yahoo_ticker = (
        row[
            "yahoo_ticker"
        ]
    )


    existing = load_stock_price_cache(
        yahoo_ticker
    )


    if existing.empty:

        latest_cached_date = pd.NaT


        download_start = pd.Timestamp(
            STOCK_PRICE_START_DATE
        )


        update_required = True


    else:

        latest_cached_date = pd.to_datetime(

            existing[
                "date"
            ]

        ).max()


        if (

            latest_cached_date
            >=
            pd.Timestamp(
                MARKET_AS_OF_DATE
            )

        ):

            download_start = pd.NaT

            update_required = False


        else:

            download_start = max(

                pd.Timestamp(
                    STOCK_PRICE_START_DATE
                ),

                (
                    latest_cached_date

                    -
                    pd.Timedelta(
                        days=STOCK_UPDATE_OVERLAP_DAYS
                    )
                ),

            )


            update_required = True


    update_plan_rows.append(

        {

            "ticker":
                row[
                    "ticker"
                ],

            "yahoo_ticker":
                yahoo_ticker,

            "latest_cached_date":
                latest_cached_date,

            "download_start":
                download_start,

            "update_required":
                update_required,

        }

    )


STOCK_PRICE_UPDATE_PLAN = pd.DataFrame(
    update_plan_rows
)


# ============================================================
# 15. DOWNLOAD INCREMENTAL UPDATES
# ============================================================

STOCK_DOWNLOAD_FAILURES = []


stocks_requiring_update = (

    STOCK_PRICE_UPDATE_PLAN[

        STOCK_PRICE_UPDATE_PLAN[
            "update_required"
        ]

    ]

    .copy()

)


if not stocks_requiring_update.empty:

    # --------------------------------------------------------
    # Group stocks sharing the same start date.
    #
    # Usually:
    #   first run -> one group
    #   later run -> very few groups
    # --------------------------------------------------------

    for download_start, group in (

        stocks_requiring_update

        .groupby(
            "download_start"
        )

    ):

        group_tickers = (

            group[
                "yahoo_ticker"
            ]

            .tolist()

        )


        # ----------------------------------------------------
        # Batch download
        # ----------------------------------------------------

        for batch_start in range(

            0,
            len(
                group_tickers
            ),
            STOCK_DOWNLOAD_BATCH_SIZE,

        ):

            batch = (

                group_tickers[

                    batch_start:
                    batch_start
                    +
                    STOCK_DOWNLOAD_BATCH_SIZE

                ]

            )


            try:

                downloaded = (

                    download_stock_batch(

                        batch,

                        start_date=download_start,

                        end_date=STOCK_PRICE_END_DATE,

                    )

                )


            except Exception as exc:

                downloaded = {}


                for ticker in batch:

                    STOCK_DOWNLOAD_FAILURES.append(

                        {

                            "yahoo_ticker":
                                ticker,

                            "stage":
                                "batch",

                            "error":
                                str(
                                    exc
                                ),

                        }

                    )


            # ------------------------------------------------
            # Save each ticker
            # ------------------------------------------------

            retry_tickers = []


            for ticker in batch:

                new_data = downloaded.get(

                    ticker,
                    pd.DataFrame(),

                )


                if new_data.empty:

                    retry_tickers.append(
                        ticker
                    )

                    continue


                existing = load_stock_price_cache(
                    ticker
                )


                merged = merge_stock_price_data(

                    existing,
                    new_data,

                )


                save_stock_price_cache(

                    ticker,
                    merged,

                )


            # ------------------------------------------------
            # Individual fallback for missing batch tickers
            # ------------------------------------------------

            for ticker in retry_tickers:

                try:

                    individual_result = (

                        download_stock_batch(

                            [
                                ticker
                            ],

                            start_date=download_start,

                            end_date=STOCK_PRICE_END_DATE,

                        )

                    )


                    individual_data = (

                        individual_result.get(

                            ticker,
                            pd.DataFrame(),

                        )

                    )


                    if individual_data.empty:

                        raise RuntimeError(
                            "Yahoo returned empty data."
                        )


                    existing = load_stock_price_cache(
                        ticker
                    )


                    merged = merge_stock_price_data(

                        existing,
                        individual_data,

                    )


                    save_stock_price_cache(

                        ticker,
                        merged,

                    )


                except Exception as exc:

                    STOCK_DOWNLOAD_FAILURES.append(

                        {

                            "yahoo_ticker":
                                ticker,

                            "stage":
                                "individual_retry",

                            "error":
                                str(
                                    exc
                                ),

                        }

                    )


# ============================================================
# 16. DOWNLOAD FAILURE TABLE
# ============================================================

if STOCK_DOWNLOAD_FAILURES:

    STOCK_DOWNLOAD_FAILURES = pd.DataFrame(

        STOCK_DOWNLOAD_FAILURES

    )


else:

    STOCK_DOWNLOAD_FAILURES = pd.DataFrame(

        columns=[

            "yahoo_ticker",
            "stage",
            "error",

        ]

    )


# ============================================================
# 17. STOCK PRICE QA
# ============================================================

qa_rows = []


for _, meta in (

    STOCK_PRICE_UNIVERSE.iterrows()

):

    ticker = (
        meta[
            "ticker"
        ]
    )


    yahoo_ticker = (
        meta[
            "yahoo_ticker"
        ]
    )


    df = load_stock_price_cache(
        yahoo_ticker
    )


    # --------------------------------------------------------
    # Missing data
    # --------------------------------------------------------

    if df.empty:

        qa_rows.append(

            {

                "ticker":
                    ticker,

                "yahoo_ticker":
                    yahoo_ticker,

                "company_name":
                    meta[
                        "company_name"
                    ],

                "sector_ticker":
                    meta[
                        "sector_ticker"
                    ],

                "sector_name":
                    meta[
                        "sector_name"
                    ],

                "stock_research_scope":
                    meta[
                        "stock_research_scope"
                    ],

                "row_count":
                    0,

                "first_date":
                    pd.NaT,

                "last_date":
                    pd.NaT,

                "history_years":
                    0.0,

                "days_since_latest":
                    np.nan,

                "adj_close_missing":
                    np.nan,

                "adj_close_fallback":
                    False,

                "status":
                    "MISSING",

                "feature_eligible":
                    False,

                "preferred_history_ready":
                    False,

                "last_price":
                    np.nan,

                "adv20_dollar":
                    np.nan,

                "liquidity_eligible":
                    False,

            }

        )


        continue


    # --------------------------------------------------------
    # Respect live market cutoff
    # --------------------------------------------------------

    df = (

        df[
            df[
                "date"
            ]
            <=
            pd.Timestamp(
                MARKET_AS_OF_DATE
            )
        ]

        .copy()

    )


    row_count = len(
        df
    )


    first_date = (

        pd.to_datetime(
            df[
                "date"
            ]
        )
        .min()

    )


    last_date = (

        pd.to_datetime(
            df[
                "date"
            ]
        )
        .max()

    )


    if (
        pd.notna(
            first_date
        )
        and
        pd.notna(
            last_date
        )
    ):

        history_years = (

            (
                last_date
                -
                first_date
            ).days

            /
            365.25

        )


        days_since_latest = int(

            (
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ).normalize()

                -
                pd.Timestamp(
                    last_date
                ).normalize()

            ).days

        )


    else:

        history_years = 0.0

        days_since_latest = np.nan


    adj_close_missing = int(

        df[
            "adj_close"
        ]
        .isna()
        .sum()

    )


    if (
        "adj_close_fallback"
        in df.columns
    ):

        adj_close_fallback = bool(

            df[
                "adj_close_fallback"
            ]
            .fillna(
                False
            )
            .any()

        )


    else:

        adj_close_fallback = False


    # --------------------------------------------------------
    # Investability / liquidity diagnostics
    # --------------------------------------------------------
    _recent_liq = df.tail(max(STOCK_LIQUIDITY_WINDOW, 1)).copy()
    last_price = float(pd.to_numeric(df["adj_close"], errors="coerce").dropna().iloc[-1]) if pd.to_numeric(df["adj_close"], errors="coerce").notna().any() else np.nan
    if "volume" in _recent_liq.columns:
        _dollar_volume = pd.to_numeric(_recent_liq["adj_close"], errors="coerce") * pd.to_numeric(_recent_liq["volume"], errors="coerce")
        adv20_dollar = float(_dollar_volume.dropna().mean()) if _dollar_volume.notna().any() else np.nan
    else:
        adv20_dollar = np.nan
    liquidity_eligible = bool(
        safe_isfinite(last_price) and last_price >= STOCK_MIN_PRICE
        and safe_isfinite(adv20_dollar) and adv20_dollar >= STOCK_MIN_ADV20_DOLLAR
    )

    # --------------------------------------------------------
    # Status hierarchy
    # --------------------------------------------------------

    if row_count == 0:

        status = "MISSING"


    elif (

        pd.isna(
            days_since_latest
        )

        or

        days_since_latest
        >
        STOCK_PRICE_MAX_LAG_DAYS

    ):

        status = "STALE"


    elif row_count < STOCK_PRICE_MIN_OBSERVATIONS:

        status = "INSUFFICIENT_HISTORY"


    elif row_count < STOCK_PRICE_PREFERRED_OBSERVATIONS:

        status = "SHORT_HISTORY"


    else:

        status = "PASS"


    feature_eligible = bool(

        row_count
        >=
        STOCK_PRICE_MIN_OBSERVATIONS

        and

        pd.notna(
            days_since_latest
        )

        and

        days_since_latest
        <=
        STOCK_PRICE_MAX_LAG_DAYS

        and

        adj_close_missing
        ==
        0

        and

        liquidity_eligible

    )


    preferred_history_ready = bool(

        row_count
        >=
        STOCK_PRICE_PREFERRED_OBSERVATIONS

        and

        feature_eligible

    )


    qa_rows.append(

        {

            "ticker":
                ticker,

            "yahoo_ticker":
                yahoo_ticker,

            "company_name":
                meta[
                    "company_name"
                ],

            "sector_ticker":
                meta[
                    "sector_ticker"
                ],

            "sector_name":
                meta[
                    "sector_name"
                ],

            "stock_research_scope":
                meta[
                    "stock_research_scope"
                ],

            "row_count":
                row_count,

            "first_date":
                first_date,

            "last_date":
                last_date,

            "history_years":
                history_years,

            "days_since_latest":
                days_since_latest,

            "adj_close_missing":
                adj_close_missing,

            "adj_close_fallback":
                adj_close_fallback,

            "status":
                status,

            "feature_eligible":
                feature_eligible,

            "preferred_history_ready":
                preferred_history_ready,

            "last_price":
                last_price,

            "adv20_dollar":
                adv20_dollar,

            "liquidity_eligible":
                liquidity_eligible,

        }

    )


STOCK_PRICE_QA = pd.DataFrame(
    qa_rows
)


# ============================================================
# 18. ATTACH E2 ELIGIBILITY METADATA
# ============================================================

eligibility_metadata = (

    STOCK_PRICE_UNIVERSE[
        [
            "ticker",
            "core_long_eligible",
            "tactical_research_eligible",
            "sector_rank",
            "sector_signal_z",
        ]
    ]

    .drop_duplicates(
        subset=[
            "ticker"
        ]
    )

)


STOCK_PRICE_QA = (

    STOCK_PRICE_QA

    .merge(

        eligibility_metadata,

        on="ticker",

        how="left",

        validate="one_to_one",

    )

)


# ============================================================
# 19. FEATURE-ELIGIBLE STOCK UNIVERSE
# ============================================================

eligible_tickers = set(

    STOCK_PRICE_QA.loc[

        STOCK_PRICE_QA[
            "feature_eligible"
        ],

        "ticker",

    ]

)


ELIGIBLE_STOCK_PRICE_UNIVERSE = (

    STOCK_PRICE_UNIVERSE[

        STOCK_PRICE_UNIVERSE[
            "ticker"
        ]

        .isin(
            eligible_tickers
        )

    ]

    .copy()

    .reset_index(
        drop=True
    )

)

# Reconcile the expensive fundamental-research universe to the live investability screen.
# Research/control price history can remain broader, but E5+ only process liquid, usable names.
ACTIVE_STOCK_UNIVERSE = ACTIVE_STOCK_UNIVERSE[ACTIVE_STOCK_UNIVERSE["ticker"].isin(eligible_tickers)].copy().reset_index(drop=True)
CORE_LONG_STOCK_UNIVERSE = CORE_LONG_STOCK_UNIVERSE[CORE_LONG_STOCK_UNIVERSE["ticker"].isin(eligible_tickers)].copy().reset_index(drop=True)



# ============================================================
# 20. BUILD CONSOLIDATED LIVE PRICE PANEL
# ============================================================

stock_price_panel_frames = []


for _, meta in (

    ELIGIBLE_STOCK_PRICE_UNIVERSE.iterrows()

):

    ticker = (
        meta[
            "ticker"
        ]
    )


    yahoo_ticker = (
        meta[
            "yahoo_ticker"
        ]
    )


    df = load_stock_price_cache(
        yahoo_ticker
    )


    if df.empty:

        continue


    df = (

        df[
            df[
                "date"
            ]
            <=
            pd.Timestamp(
                MARKET_AS_OF_DATE
            )
        ]

        .copy()

    )


    df[
        "ticker"
    ] = ticker


    df[
        "company_name"
    ] = (

        meta[
            "company_name"
        ]

    )


    df[
        "sector_ticker"
    ] = (

        meta[
            "sector_ticker"
        ]

    )


    df[
        "sector_name"
    ] = (

        meta[
            "sector_name"
        ]

    )


    df[
        "stock_research_scope"
    ] = (

        meta[
            "stock_research_scope"
        ]

    )


    stock_price_panel_frames.append(
        df
    )


if stock_price_panel_frames:

    STOCK_PRICE_PANEL = pd.concat(

        stock_price_panel_frames,

        ignore_index=True,

        sort=False,

    )


else:

    STOCK_PRICE_PANEL = pd.DataFrame()


# ============================================================
# 21. PANEL VALIDATION
# ============================================================

if STOCK_PRICE_PANEL.empty:

    raise RuntimeError(
        "No eligible stock-price panel could be created."
    )


STOCK_PRICE_PANEL[
    "date"
] = pd.to_datetime(

    STOCK_PRICE_PANEL[
        "date"
    ]

)


STOCK_PRICE_PANEL = (

    STOCK_PRICE_PANEL

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


future_rows = int(

    (
        STOCK_PRICE_PANEL[
            "date"
        ]

        >
        pd.Timestamp(
            MARKET_AS_OF_DATE
        )
    )
    .sum()

)


# ============================================================
# 22. COVERAGE METRICS
# ============================================================

requested_stock_count = len(
    STOCK_PRICE_UNIVERSE
)


feature_eligible_count = int(

    STOCK_PRICE_QA[
        "feature_eligible"
    ]
    .sum()

)


preferred_history_count = int(

    STOCK_PRICE_QA[
        "preferred_history_ready"
    ]
    .sum()

)


overall_feature_coverage = (

    feature_eligible_count
    /
    requested_stock_count

    if requested_stock_count > 0

    else 0.0

)


# ------------------------------------------------------------
# Core-long coverage
# ------------------------------------------------------------

core_qa = (

    STOCK_PRICE_QA[

        STOCK_PRICE_QA[
            "core_long_eligible"
        ]
        ==
        True

    ]

)


core_requested_count = len(
    core_qa
)


core_feature_eligible_count = int(

    core_qa[
        "feature_eligible"
    ]
    .sum()

)


core_feature_coverage = (

    core_feature_eligible_count
    /
    core_requested_count

    if core_requested_count > 0

    else 1.0

)


# ============================================================
# 23. STATUS SUMMARY
# ============================================================

STOCK_PRICE_STATUS_SUMMARY = (

    STOCK_PRICE_QA[
        "status"
    ]

    .value_counts(
        dropna=False
    )

    .rename_axis(
        "status"
    )

    .reset_index(
        name="stock_count"
    )

)


# ============================================================
# 24. E3 HEALTH CHECKS
# ============================================================

e3_checks = []


def add_e3_check(
    check: str,
    passed: bool,
    detail: str
):

    e3_checks.append(

        {

            "check":
                check,

            "passed":
                bool(
                    passed
                ),

            "detail":
                str(
                    detail
                ),

        }

    )


add_e3_check(

    "Stock price universe non-empty",

    requested_stock_count
    >
    0,

    (
        f"requested_stocks="
        f"{requested_stock_count}"
    ),

)


add_e3_check(

    "Stock universe tickers unique",

    STOCK_PRICE_UNIVERSE[
        "ticker"
    ]
    .nunique()
    ==
    requested_stock_count,

    (
        f"rows={requested_stock_count}, "
        f"unique="
        f"{STOCK_PRICE_UNIVERSE['ticker'].nunique()}"
    ),

)


add_e3_check(

    "Overall feature coverage >= 98%",

    overall_feature_coverage
    >=
    0.98,

    (
        f"eligible="
        f"{feature_eligible_count}"
        f"/{requested_stock_count} "
        f"({overall_feature_coverage:.1%})"
    ),

)


add_e3_check(

    "Core-long feature coverage >= 98%",

    core_feature_coverage
    >=
    0.98,

    (
        f"eligible="
        f"{core_feature_eligible_count}"
        f"/{core_requested_count} "
        f"({core_feature_coverage:.1%})"
    ),

)


add_e3_check(

    "No observations after market cutoff",

    future_rows
    ==
    0,

    (
        f"future_rows="
        f"{future_rows}"
    ),

)


add_e3_check(

    "Consolidated price panel non-empty",

    not STOCK_PRICE_PANEL.empty,

    (
        f"panel_rows="
        f"{len(STOCK_PRICE_PANEL)}"
    ),

)


add_e3_check(

    "Historical membership backtest remains blocked",

    bool(

        (
            SP500_CONSTITUENTS[
                "historical_backtest_eligible"
            ]
            ==
            False
        )
        .all()

    ),

    "Current-membership universe remains LIVE_ONLY",

)


E3_HEALTH = pd.DataFrame(
    e3_checks
)


E3_HEALTH[
    "status"
] = np.where(

    E3_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


E3_PASSED = bool(

    E3_HEALTH[
        "passed"
    ]
    .all()

)


# ============================================================
# 25. E3 SUMMARY
# ============================================================

E3_SUMMARY = pd.DataFrame(

    [

        {

            "market_as_of_date":
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ),

            "lookback_years":
                STOCK_PRICE_LOOKBACK_YEARS,

            "update_overlap_days":
                STOCK_UPDATE_OVERLAP_DAYS,

            "requested_stocks":
                requested_stock_count,

            "feature_eligible_stocks":
                feature_eligible_count,

            "preferred_history_stocks":
                preferred_history_count,

            "overall_feature_coverage":
                overall_feature_coverage,

            "core_long_requested":
                core_requested_count,

            "core_long_feature_eligible":
                core_feature_eligible_count,

            "core_long_feature_coverage":
                core_feature_coverage,

            "download_failure_records":
                len(
                    STOCK_DOWNLOAD_FAILURES
                ),

            "price_panel_rows":
                len(
                    STOCK_PRICE_PANEL
                ),

            "e3_passed":
                E3_PASSED,

        }

    ]

)


# ============================================================
# 26. SAVE OUTPUTS
# ============================================================

STOCK_PRICE_PANEL.to_parquet(

    STOCK_PRICE_CURATED_DIR
    /
    "stock_prices_live_panel.parquet",

    index=False,

)


STOCK_PRICE_QA.to_parquet(

    STOCK_MODEL_DIR
    /
    "stock_price_qa.parquet",

    index=False,

)


ELIGIBLE_STOCK_PRICE_UNIVERSE.to_parquet(

    STOCK_MODEL_DIR
    /
    "eligible_stock_price_universe.parquet",

    index=False,

)


STOCK_PRICE_UPDATE_PLAN.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e3_update_plan.csv",

    index=False,

)


STOCK_PRICE_QA.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e3_stock_price_qa.csv",

    index=False,

)


STOCK_DOWNLOAD_FAILURES.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e3_download_failures.csv",

    index=False,

)


E3_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e3_health.csv",

    index=False,

)


E3_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e3_summary.csv",

    index=False,

)


# ============================================================
# 27. DISPLAY
# ============================================================

print(
    "=" * 120
)

print(
    "E3 — STOCK MARKET DATA ACQUISITION + QA"
)

print(
    "=" * 120
)


print(
    f"Market as-of date:           "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    f"Historical lookback:         "
    f"{STOCK_PRICE_LOOKBACK_YEARS} years"
)


print(
    f"Update overlap:              "
    f"{STOCK_UPDATE_OVERLAP_DAYS} days"
)


print(
    f"Requested stocks:            "
    f"{requested_stock_count}"
)


print(
    f"Feature-eligible stocks:     "
    f"{feature_eligible_count} "
    f"({overall_feature_coverage:.1%})"
)


print(
    f"Preferred-history stocks:    "
    f"{preferred_history_count}"
)


print(
    f"Core-long coverage:          "
    f"{core_feature_eligible_count}"
    f"/{core_requested_count} "
    f"({core_feature_coverage:.1%})"
)


print(
    f"Consolidated panel rows:     "
    f"{len(STOCK_PRICE_PANEL)}"
)


print(
    f"Download failure records:    "
    f"{len(STOCK_DOWNLOAD_FAILURES)}"
)


print(
    "\nStock-price status summary:"
)


display(
    STOCK_PRICE_STATUS_SUMMARY
)


print(
    "\nStocks requiring attention:"
)


attention_table = (

    STOCK_PRICE_QA[

        STOCK_PRICE_QA[
            "status"
        ]
        !=
        "PASS"

    ][
        [
            "ticker",
            "yahoo_ticker",
            "company_name",
            "sector_ticker",
            "row_count",
            "last_date",
            "days_since_latest",
            "status",
            "feature_eligible",
        ]
    ]

    .sort_values(
        [
            "status",
            "sector_ticker",
            "ticker",
        ]
    )

)


if attention_table.empty:

    print(
        "None — all requested stocks passed preferred-history QA."
    )

else:

    display(
        attention_table
    )


print(
    "\nDownload failures:"
)


if STOCK_DOWNLOAD_FAILURES.empty:

    print(
        "None."
    )

else:

    display(
        STOCK_DOWNLOAD_FAILURES
    )


print(
    "\nE3 health:"
)


display(
    E3_HEALTH
)


print(
    "\nE3 summary:"
)


display(
    E3_SUMMARY
)


# ============================================================
# 28. PRODUCTION GATE
# ============================================================

if not E3_PASSED:

    failed_e3_checks = (

        E3_HEALTH.loc[

            ~E3_HEALTH[
                "passed"
            ],

            [
                "check",
                "detail",
            ],

        ]

    )


    display(
        failed_e3_checks
    )


    raise RuntimeError(

        "E3 PRODUCTION GATE FAILED. "
        "Review missing/stale stock-price data "
        "before running E4."

    )


print(
    "\n✓ E3 COMPLETE — stock market data acquired and validated."
)


print(
    "✓ Incremental stock-price cache is operational."
)


print(
    "✓ Consolidated live stock-price panel created."
)


print(
    "✓ Ready for E4 stock-level market-factor construction."
)

# ===== ORIGINAL NOTEBOOK CELL 54 =====
# ============================================================
# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E4 — STOCK-LEVEL MARKET FACTOR ENGINE
# ============================================================
#
# Purpose:
#
#   Construct live stock-level empirical factors:
#
#       - 1M / 3M / 6M / 12M momentum
#       - sector-relative strength
#       - SPY-relative strength
#       - 50D / 200D price trend
#       - annualized volatility
#       - downside volatility
#       - beta to SPY
#       - beta to sector
#       - correlation
#       - sector-relative alpha
#       - sector information ratio
#
# CRITICAL DESIGN:
#
#   Stocks are standardized WITHIN THEIR OWN SECTOR.
#
#   We do not compare Energy raw momentum directly with
#   Health Care raw momentum.
#
# SHORT-HISTORY POLICY:
#
#   Missing long-horizon factors are allowed.
#
#   Available factor weights are renormalized and a separate
#   confidence score records how much evidence is available.
#
# GOVERNANCE:
#
#   LIVE ONLY.
#   No historical constituent backtest.
# ============================================================


# ============================================================
# 1. VALIDATE E3
# ============================================================

required_e4_objects = [

    "E3_PASSED",
    "STOCK_PRICE_PANEL",
    "STOCK_PRICE_QA",
    "ELIGIBLE_STOCK_PRICE_UNIVERSE",
    "MARKET_AS_OF_DATE",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",

]


missing_e4_objects = [

    obj
    for obj in required_e4_objects
    if obj not in globals()

]


if missing_e4_objects:

    raise RuntimeError(
        "E4 requires E3 first. Missing: "
        f"{missing_e4_objects}"
    )


if not bool(
    E3_PASSED
):

    raise RuntimeError(
        "E3 production gate did not pass."
    )


if "load_market_price_series" not in globals():

    raise RuntimeError(
        "E4 requires load_market_price_series() "
        "from Section D4."
    )


# ============================================================
# 2. PARAMETERS
# ============================================================

TRADING_DAYS = 252


HORIZONS = {

    "1m": 21,
    "3m": 63,
    "6m": 126,
    "12m": 252,

}


RISK_WINDOW = 126

ALPHA_WINDOW = 126


PREFERRED_HISTORY_OBSERVATIONS = 504


# ============================================================
# 3. FACTOR WEIGHTS
# ============================================================
#
# Total = 100%
#
# Momentum             32%
# Relative strength    30%
# Trend                16%
# Residual performance 12%
# Standalone risk      10%
#
# Beta is diagnostic only.
# ============================================================

STOCK_MARKET_FACTOR_WEIGHTS = {

    # Momentum
    "momentum_1m":
        0.05,

    "momentum_3m":
        0.08,

    "momentum_6m":
        0.09,

    "momentum_12m":
        0.10,


    # Relative strength
    "sector_relative_3m":
        0.08,

    "sector_relative_6m":
        0.08,

    "spy_relative_3m":
        0.07,

    "spy_relative_6m":
        0.07,


    # Trend
    "trend_50d":
        0.07,

    "trend_200d":
        0.09,


    # Alpha / residual performance
    "sector_alpha":
        0.07,

    "sector_information_ratio":
        0.05,


    # Risk — lower is better
    "volatility":
        0.05,

    "downside_volatility":
        0.05,

}


if not np.isclose(

    sum(
        STOCK_MARKET_FACTOR_WEIGHTS.values()
    ),

    1.0,

):

    raise RuntimeError(
        "E4 factor weights must sum to 1."
    )


# ============================================================
# 4. FACTOR DIRECTIONS
# ============================================================
#
# +1 = higher is better
# -1 = lower is better
# ============================================================

STOCK_MARKET_FACTOR_DIRECTION = {

    "momentum_1m":
        +1.0,

    "momentum_3m":
        +1.0,

    "momentum_6m":
        +1.0,

    "momentum_12m":
        +1.0,

    "sector_relative_3m":
        +1.0,

    "sector_relative_6m":
        +1.0,

    "spy_relative_3m":
        +1.0,

    "spy_relative_6m":
        +1.0,

    "trend_50d":
        +1.0,

    "trend_200d":
        +1.0,

    "sector_alpha":
        +1.0,

    "sector_information_ratio":
        +1.0,

    "volatility":
        -1.0,

    "downside_volatility":
        -1.0,

}


# ============================================================
# 5. HELPER — PERIOD RETURN
# ============================================================

def e4_period_return_pct(
    prices: pd.Series,
    periods: int
) -> float:
    """
    Percentage return over N trading observations.
    """

    clean = (

        pd.to_numeric(
            prices,
            errors="coerce"
        )

        .dropna()

    )


    if len(
        clean
    ) <= periods:

        return np.nan


    start_price = float(
        clean.iloc[
            -1 - periods
        ]
    )


    end_price = float(
        clean.iloc[-1]
    )


    if (
        not safe_isfinite(
            start_price
        )
        or
        not safe_isfinite(
            end_price
        )
        or
        start_price <= 0
    ):

        return np.nan


    return float(

        (
            end_price
            /
            start_price
            -
            1.0
        )

        *
        100.0

    )


# ============================================================
# 6. HELPER — ANNUALIZED VOLATILITY
# ============================================================

def e4_annualized_volatility_pct(
    returns: pd.Series
) -> float:

    returns = (

        pd.to_numeric(
            returns,
            errors="coerce"
        )

        .dropna()

    )


    if len(
        returns
    ) < 20:

        return np.nan


    return float(

        returns.std(
            ddof=1
        )

        *
        np.sqrt(
            TRADING_DAYS
        )

        *
        100.0

    )


# ============================================================
# 7. HELPER — DOWNSIDE VOLATILITY
# ============================================================

def e4_downside_volatility_pct(
    returns: pd.Series
) -> float:
    """
    sqrt(mean(min(return,0)^2)) annualized.
    """

    returns = (

        pd.to_numeric(
            returns,
            errors="coerce"
        )

        .dropna()

        .to_numpy(
            dtype=float
        )

    )


    if len(
        returns
    ) < 20:

        return np.nan


    downside = np.minimum(
        returns,
        0.0
    )


    return float(

        np.sqrt(
            np.mean(
                downside ** 2
            )
        )

        *
        np.sqrt(
            TRADING_DAYS
        )

        *
        100.0

    )


# ============================================================
# 8. HELPER — BETA
# ============================================================

def e4_beta(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series
) -> float:

    aligned = pd.concat(

        [
            asset_returns,
            benchmark_returns,
        ],

        axis=1,

    ).dropna()


    if len(
        aligned
    ) < 20:

        return np.nan


    x = aligned.iloc[
        :,
        1
    ]


    y = aligned.iloc[
        :,
        0
    ]


    variance = float(
        x.var(
            ddof=1
        )
    )


    if (
        not safe_isfinite(
            variance
        )
        or
        variance <= 1e-16
    ):

        return np.nan


    covariance = float(

        np.cov(

            y.to_numpy(
                dtype=float
            ),

            x.to_numpy(
                dtype=float
            ),

            ddof=1,

        )[0, 1]

    )


    return float(
        covariance
        /
        variance
    )


# ============================================================
# 9. HELPER — ALPHA + INFORMATION RATIO VS SECTOR
# ============================================================

def e4_sector_alpha_metrics(
    stock_returns: pd.Series,
    sector_returns: pd.Series
):
    """
    Estimate:

        stock_return = alpha + beta * sector_return + residual

    Alpha is annualized arithmetically.

    Information ratio uses stock minus sector return.
    """

    aligned = pd.concat(

        [
            stock_returns.rename(
                "stock"
            ),

            sector_returns.rename(
                "sector"
            ),
        ],

        axis=1,

    ).dropna()


    if len(
        aligned
    ) < 40:

        return (
            np.nan,
            np.nan,
        )


    y = aligned[
        "stock"
    ].to_numpy(
        dtype=float
    )


    x = aligned[
        "sector"
    ].to_numpy(
        dtype=float
    )


    X = np.column_stack(

        [
            np.ones(
                len(x)
            ),
            x,
        ]

    )


    coefficients = np.linalg.lstsq(

        X,
        y,
        rcond=None,

    )[0]


    daily_alpha = float(
        coefficients[0]
    )


    annualized_alpha_pct = (

        daily_alpha
        *
        TRADING_DAYS
        *
        100.0

    )


    relative_returns = (

        aligned[
            "stock"
        ]

        -
        aligned[
            "sector"
        ]

    )


    tracking_error = float(

        relative_returns.std(
            ddof=1
        )

    )


    if (

        not safe_isfinite(
            tracking_error
        )
        or
        tracking_error <= 1e-12

    ):

        information_ratio = np.nan


    else:

        information_ratio = float(

            relative_returns.mean()

            /
            tracking_error

            *
            np.sqrt(
                TRADING_DAYS
            )

        )


    return (

        float(
            annualized_alpha_pct
        ),

        float(
            information_ratio
        ),

    )


# ============================================================
# 10. LOAD SPY PRICE HISTORY
# ============================================================

E4_SPY = (

    load_market_price_series(
        "SPY"
    )[
        [
            "date",
            "price",
        ]
    ]

    .rename(
        columns={
            "price":
                "spy_price"
        }
    )

)


E4_SPY[
    "date"
] = pd.to_datetime(
    E4_SPY[
        "date"
    ]
)


# ============================================================
# 11. LOAD SECTOR ETF HISTORY
# ============================================================

research_sector_tickers = (

    ELIGIBLE_STOCK_PRICE_UNIVERSE[
        "sector_ticker"
    ]

    .dropna()

    .unique()

    .tolist()

)


E4_SECTOR_PRICE_HISTORY = {}


for sector_ticker in research_sector_tickers:

    sector_df = (

        load_market_price_series(
            sector_ticker
        )[
            [
                "date",
                "price",
            ]
        ]

        .rename(
            columns={
                "price":
                    "sector_price"
            }
        )

    )


    sector_df[
        "date"
    ] = pd.to_datetime(
        sector_df[
            "date"
        ]
    )


    E4_SECTOR_PRICE_HISTORY[
        sector_ticker
    ] = sector_df


# ============================================================
# 12. METADATA LOOKUP
# ============================================================

stock_metadata = (

    ELIGIBLE_STOCK_PRICE_UNIVERSE

    .drop_duplicates(
        subset=["ticker"]
    )

    .set_index(
        "ticker"
    )

)


stock_qa_lookup = (

    STOCK_PRICE_QA

    .drop_duplicates(
        subset=["ticker"]
    )

    .set_index(
        "ticker"
    )

)


# ============================================================
# 13. BUILD RAW STOCK FACTORS
# ============================================================

stock_factor_rows = []


for ticker, metadata in (
    stock_metadata.iterrows()
):

    sector_ticker = (
        metadata[
            "sector_ticker"
        ]
    )


    # --------------------------------------------------------
    # Stock history
    # --------------------------------------------------------

    stock_df = (

        STOCK_PRICE_PANEL[

            STOCK_PRICE_PANEL[
                "ticker"
            ]
            ==
            ticker

        ][
            [
                "date",
                "adj_close",
            ]
        ]

        .copy()

        .rename(
            columns={
                "adj_close":
                    "stock_price"
            }
        )

    )


    stock_df[
        "date"
    ] = pd.to_datetime(
        stock_df[
            "date"
        ]
    )


    stock_df = (

        stock_df

        .sort_values(
            "date"
        )

        .drop_duplicates(
            subset=["date"],
            keep="last"
        )

        .reset_index(
            drop=True
        )

    )


    if stock_df.empty:

        continue


    # --------------------------------------------------------
    # Sector ETF
    # --------------------------------------------------------

    sector_df = (

        E4_SECTOR_PRICE_HISTORY[
            sector_ticker
        ]

        .copy()

    )


    # --------------------------------------------------------
    # Align stock + sector + SPY
    # --------------------------------------------------------

    aligned = (

        stock_df

        .merge(

            sector_df,

            on="date",

            how="inner",

        )

        .merge(

            E4_SPY,

            on="date",

            how="inner",

        )

        .sort_values(
            "date"
        )

        .reset_index(
            drop=True
        )

    )


    if len(
        aligned
    ) < 60:

        continue


    # ========================================================
    # 14. ABSOLUTE MOMENTUM
    # ========================================================

    momentum_1m = e4_period_return_pct(

        aligned[
            "stock_price"
        ],

        HORIZONS[
            "1m"
        ],

    )


    momentum_3m = e4_period_return_pct(

        aligned[
            "stock_price"
        ],

        HORIZONS[
            "3m"
        ],

    )


    momentum_6m = e4_period_return_pct(

        aligned[
            "stock_price"
        ],

        HORIZONS[
            "6m"
        ],

    )


    momentum_12m = e4_period_return_pct(

        aligned[
            "stock_price"
        ],

        HORIZONS[
            "12m"
        ],

    )


    # ========================================================
    # 15. SECTOR RETURNS
    # ========================================================

    sector_3m = e4_period_return_pct(

        aligned[
            "sector_price"
        ],

        HORIZONS[
            "3m"
        ],

    )


    sector_6m = e4_period_return_pct(

        aligned[
            "sector_price"
        ],

        HORIZONS[
            "6m"
        ],

    )


    # ========================================================
    # 16. SPY RETURNS
    # ========================================================

    spy_3m = e4_period_return_pct(

        aligned[
            "spy_price"
        ],

        HORIZONS[
            "3m"
        ],

    )


    spy_6m = e4_period_return_pct(

        aligned[
            "spy_price"
        ],

        HORIZONS[
            "6m"
        ],

    )


    # ========================================================
    # 17. RELATIVE STRENGTH
    # ========================================================

    sector_relative_3m = (

        momentum_3m
        -
        sector_3m

        if (
            safe_isfinite(
                momentum_3m
            )
            and
            safe_isfinite(
                sector_3m
            )
        )

        else np.nan

    )


    sector_relative_6m = (

        momentum_6m
        -
        sector_6m

        if (
            safe_isfinite(
                momentum_6m
            )
            and
            safe_isfinite(
                sector_6m
            )
        )

        else np.nan

    )


    spy_relative_3m = (

        momentum_3m
        -
        spy_3m

        if (
            safe_isfinite(
                momentum_3m
            )
            and
            safe_isfinite(
                spy_3m
            )
        )

        else np.nan

    )


    spy_relative_6m = (

        momentum_6m
        -
        spy_6m

        if (
            safe_isfinite(
                momentum_6m
            )
            and
            safe_isfinite(
                spy_6m
            )
        )

        else np.nan

    )


    # ========================================================
    # 18. TREND
    # ========================================================

    current_price = float(

        aligned[
            "stock_price"
        ].iloc[-1]

    )


    if len(
        aligned
    ) >= 50:

        ma_50 = float(

            aligned[
                "stock_price"
            ]

            .tail(
                50
            )

            .mean()

        )


        trend_50d = (

            (
                current_price
                /
                ma_50
            )

            -
            1.0

        ) * 100.0


    else:

        trend_50d = np.nan


    if len(
        aligned
    ) >= 200:

        ma_200 = float(

            aligned[
                "stock_price"
            ]

            .tail(
                200
            )

            .mean()

        )


        trend_200d = (

            (
                current_price
                /
                ma_200
            )

            -
            1.0

        ) * 100.0


    else:

        trend_200d = np.nan


    # ========================================================
    # 19. DAILY RETURNS
    # ========================================================

    aligned[
        "stock_return"
    ] = (

        aligned[
            "stock_price"
        ]

        .pct_change()

    )


    aligned[
        "sector_return"
    ] = (

        aligned[
            "sector_price"
        ]

        .pct_change()

    )


    aligned[
        "spy_return"
    ] = (

        aligned[
            "spy_price"
        ]

        .pct_change()

    )


    return_frame = (

        aligned[
            [
                "stock_return",
                "sector_return",
                "spy_return",
            ]
        ]

        .dropna()

    )


    # ========================================================
    # 20. RISK WINDOW
    # ========================================================

    risk_returns = (

        return_frame

        .tail(
            RISK_WINDOW
        )

    )


    annualized_volatility = (

        e4_annualized_volatility_pct(

            risk_returns[
                "stock_return"
            ]

        )

    )


    downside_volatility = (

        e4_downside_volatility_pct(

            risk_returns[
                "stock_return"
            ]

        )

    )


    beta_to_spy = e4_beta(

        risk_returns[
            "stock_return"
        ],

        risk_returns[
            "spy_return"
        ],

    )


    beta_to_sector = e4_beta(

        risk_returns[
            "stock_return"
        ],

        risk_returns[
            "sector_return"
        ],

    )


    correlation_to_spy = float(

        risk_returns[
            "stock_return"
        ]

        .corr(

            risk_returns[
                "spy_return"
            ]

        )

    )


    correlation_to_sector = float(

        risk_returns[
            "stock_return"
        ]

        .corr(

            risk_returns[
                "sector_return"
            ]

        )

    )


    # ========================================================
    # 21. ALPHA / INFORMATION RATIO
    # ========================================================

    alpha_returns = (

        return_frame

        .tail(
            ALPHA_WINDOW
        )

    )


    (
        sector_alpha_ann_pct,
        sector_information_ratio,

    ) = e4_sector_alpha_metrics(

        alpha_returns[
            "stock_return"
        ],

        alpha_returns[
            "sector_return"
        ],

    )


    # ========================================================
    # 22. HISTORY METADATA
    # ========================================================

    qa_row = stock_qa_lookup.loc[
        ticker
    ]


    row_count = int(
        qa_row[
            "row_count"
        ]
    )


    history_confidence = float(

        min(

            row_count
            /
            PREFERRED_HISTORY_OBSERVATIONS,

            1.0,

        )

    )


    # ========================================================
    # 23. STORE RAW FACTORS
    # ========================================================

    stock_factor_rows.append(

        {

            "ticker":
                ticker,

            "yahoo_ticker":
                metadata[
                    "yahoo_ticker"
                ],

            "company_name":
                metadata[
                    "company_name"
                ],

            "sector_ticker":
                sector_ticker,

            "sector_name":
                metadata[
                    "sector_name"
                ],

            "stock_research_scope":
                metadata[
                    "stock_research_scope"
                ],

            "sector_rank":
                metadata[
                    "sector_rank"
                ],

            "sector_signal_z":
                metadata[
                    "sector_signal_z"
                ],

            "as_of_date":
                aligned[
                    "date"
                ].iloc[-1],

            "price":
                current_price,

            "history_observations":
                row_count,

            "history_confidence":
                history_confidence,


            # Momentum
            "momentum_1m":
                momentum_1m,

            "momentum_3m":
                momentum_3m,

            "momentum_6m":
                momentum_6m,

            "momentum_12m":
                momentum_12m,


            # Relative strength
            "sector_relative_3m":
                sector_relative_3m,

            "sector_relative_6m":
                sector_relative_6m,

            "spy_relative_3m":
                spy_relative_3m,

            "spy_relative_6m":
                spy_relative_6m,


            # Trend
            "trend_50d":
                trend_50d,

            "trend_200d":
                trend_200d,


            # Risk
            "volatility":
                annualized_volatility,

            "downside_volatility":
                downside_volatility,

            "beta_to_spy":
                beta_to_spy,

            "beta_to_sector":
                beta_to_sector,

            "correlation_to_spy":
                correlation_to_spy,

            "correlation_to_sector":
                correlation_to_sector,


            # Residual performance
            "sector_alpha":
                sector_alpha_ann_pct,

            "sector_information_ratio":
                sector_information_ratio,

        }

    )


STOCK_MARKET_FACTORS_RAW = pd.DataFrame(
    stock_factor_rows
)


if STOCK_MARKET_FACTORS_RAW.empty:

    raise RuntimeError(
        "E4 produced no stock factor observations."
    )


# ============================================================
# 24. VALIDATE UNIQUE STOCKS
# ============================================================

if (

    STOCK_MARKET_FACTORS_RAW[
        "ticker"
    ]

    .duplicated()

    .any()

):

    raise RuntimeError(
        "Duplicate stock ticker detected in E4."
    )


# ============================================================
# 25. WITHIN-SECTOR Z-SCORE
# ============================================================

def e4_within_sector_zscore(
    series: pd.Series
) -> pd.Series:
    """
    Standardize one factor within a sector.
    """

    values = pd.to_numeric(
        series,
        errors="coerce"
    )


    valid_count = int(
        values.notna().sum()
    )


    if valid_count < 3:

        return pd.Series(

            np.nan,

            index=series.index,

            dtype=float,

        )


    mean_value = float(
        values.mean()
    )


    std_value = float(

        values.std(
            ddof=0
        )

    )


    if (

        not safe_isfinite(
            std_value
        )

        or

        std_value <= 1e-12

    ):

        result = pd.Series(

            0.0,

            index=series.index,

            dtype=float,

        )


        result[
            values.isna()
        ] = np.nan


        return result


    result = (

        (
            values
            -
            mean_value
        )

        /
        std_value

    )


    return result.clip(

        lower=-3.0,
        upper=3.0,

    )


# ============================================================
# 26. STANDARDIZE ALL SCORING FACTORS WITHIN SECTOR
# ============================================================

for factor_name in (
    STOCK_MARKET_FACTOR_WEIGHTS
):

    z_column = (
        f"z_{factor_name}"
    )


    STOCK_MARKET_FACTORS_RAW[
        z_column
    ] = (

        STOCK_MARKET_FACTORS_RAW

        .groupby(
            "sector_ticker",
            group_keys=False
        )[
            factor_name
        ]

        .transform(
            e4_within_sector_zscore
        )

    )


    # --------------------------------------------------------
    # Orient factor so higher always means better
    # --------------------------------------------------------

    STOCK_MARKET_FACTORS_RAW[
        z_column
    ] = (

        STOCK_MARKET_FACTORS_RAW[
            z_column
        ]

        *
        STOCK_MARKET_FACTOR_DIRECTION[
            factor_name
        ]

    )


# ============================================================
# 27. AVAILABLE FACTOR WEIGHT
# ============================================================
#
# Allows newer listings to use available evidence without
# pretending that missing 12M history exists.
# ============================================================

available_weight = np.zeros(
    len(
        STOCK_MARKET_FACTORS_RAW
    )
)


weighted_signal = np.zeros(
    len(
        STOCK_MARKET_FACTORS_RAW
    )
)


available_factor_count = np.zeros(
    len(
        STOCK_MARKET_FACTORS_RAW
    )
)


for factor_name, factor_weight in (
    STOCK_MARKET_FACTOR_WEIGHTS.items()
):

    z_column = (
        f"z_{factor_name}"
    )


    valid = (

        STOCK_MARKET_FACTORS_RAW[
            z_column
        ]

        .notna()

        .to_numpy()

    )


    values = (

        STOCK_MARKET_FACTORS_RAW[
            z_column
        ]

        .fillna(
            0.0
        )

        .to_numpy(
            dtype=float
        )

    )


    available_weight += (

        valid.astype(
            float
        )

        *
        factor_weight

    )


    weighted_signal += (

        values

        *
        factor_weight

    )


    available_factor_count += (

        valid.astype(
            float
        )

    )


STOCK_MARKET_FACTORS_RAW[
    "factor_weight_available"
] = available_weight


STOCK_MARKET_FACTORS_RAW[
    "factor_coverage"
] = available_weight


STOCK_MARKET_FACTORS_RAW[
    "factor_count_available"
] = available_factor_count.astype(
    int
)


# ============================================================
# 28. RENORMALIZED RAW MARKET FACTOR SCORE
# ============================================================

STOCK_MARKET_FACTORS_RAW[
    "market_factor_score_raw"
] = np.where(

    available_weight
    >
    0,

    weighted_signal
    /
    available_weight,

    np.nan,

)


# ============================================================
# 29. SIGNAL CONFIDENCE
# ============================================================
#
# Confidence combines:
#
#   factor availability
#   history depth
#
# Geometric mean penalizes weakness in either dimension.
# ============================================================

STOCK_MARKET_FACTORS_RAW[
    "market_factor_confidence"
] = np.sqrt(

    STOCK_MARKET_FACTORS_RAW[
        "factor_coverage"
    ]

    *

    STOCK_MARKET_FACTORS_RAW[
        "history_confidence"
    ]

)


STOCK_MARKET_FACTORS_RAW[
    "market_factor_confidence"
] = (

    STOCK_MARKET_FACTORS_RAW[
        "market_factor_confidence"
    ]

    .clip(
        lower=0.0,
        upper=1.0
    )

)


# ============================================================
# 30. RE-STANDARDIZE COMPOSITE SCORE WITHIN SECTOR
# ============================================================

STOCK_MARKET_FACTORS_RAW[
    "market_factor_score_z"
] = (

    STOCK_MARKET_FACTORS_RAW

    .groupby(
        "sector_ticker",
        group_keys=False
    )[
        "market_factor_score_raw"
    ]

    .transform(
        e4_within_sector_zscore
    )

)


# ============================================================
# 31. WITHIN-SECTOR RANK
# ============================================================

STOCK_MARKET_FACTORS_RAW[
    "market_rank_within_sector"
] = (

    STOCK_MARKET_FACTORS_RAW

    .groupby(
        "sector_ticker"
    )[
        "market_factor_score_raw"
    ]

    .rank(
        method="first",
        ascending=False
    )

    .astype(
        int
    )

)


STOCK_MARKET_FACTORS_RAW[
    "market_percentile_within_sector"
] = (

    STOCK_MARKET_FACTORS_RAW

    .groupby(
        "sector_ticker"
    )[
        "market_factor_score_raw"
    ]

    .rank(
        method="average",
        pct=True,
        ascending=True,
    )

    *
    100.0

)


# ============================================================
# 32. SIGNAL LABEL
# ============================================================

def classify_stock_market_signal(
    z_score: float
) -> str:

    if pd.isna(
        z_score
    ):

        return "Unavailable"


    if z_score >= 1.25:

        return "Strong positive"


    elif z_score >= 0.40:

        return "Positive"


    elif z_score <= -1.25:

        return "Strong negative"


    elif z_score <= -0.40:

        return "Negative"


    else:

        return "Neutral"


STOCK_MARKET_FACTORS_RAW[
    "market_signal"
] = (

    STOCK_MARKET_FACTORS_RAW[
        "market_factor_score_z"
    ]

    .apply(
        classify_stock_market_signal
    )

)


# ============================================================
# 33. CONFIDENCE LABEL
# ============================================================

def classify_e4_confidence(
    confidence: float
) -> str:

    if confidence >= 0.90:

        return "High"


    elif confidence >= 0.70:

        return "Medium"


    else:

        return "Low"


STOCK_MARKET_FACTORS_RAW[
    "market_factor_confidence_label"
] = (

    STOCK_MARKET_FACTORS_RAW[
        "market_factor_confidence"
    ]

    .apply(
        classify_e4_confidence
    )

)


# ============================================================
# 34. FINAL SORT
# ============================================================

STOCK_MARKET_FACTORS = (

    STOCK_MARKET_FACTORS_RAW

    .sort_values(

        [
            "sector_rank",
            "market_rank_within_sector",
        ]

    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 35. TOP STOCKS BY SECTOR
# ============================================================

E4_TOP_STOCKS_BY_SECTOR = (

    STOCK_MARKET_FACTORS

    .groupby(
        "sector_ticker",
        group_keys=False
    )

    .head(
        5
    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 36. COVERAGE DIAGNOSTICS
# ============================================================

stock_count = len(
    STOCK_MARKET_FACTORS
)


high_factor_coverage_count = int(

    (
        STOCK_MARKET_FACTORS[
            "factor_coverage"
        ]

        >=
        0.90

    ).sum()

)


acceptable_factor_coverage_count = int(

    (
        STOCK_MARKET_FACTORS[
            "factor_coverage"
        ]

        >=
        0.80

    ).sum()

)


finite_score_count = int(

    safe_isfinite(

        STOCK_MARKET_FACTORS[
            "market_factor_score_z"
        ]

    ).sum()

)


future_rows = int(

    (
        pd.to_datetime(

            STOCK_MARKET_FACTORS[
                "as_of_date"
            ]

        )

        >
        pd.Timestamp(
            MARKET_AS_OF_DATE
        )

    ).sum()

)


# ============================================================
# 37. CORE-LONG COVERAGE
# ============================================================

core_long_e4 = (

    STOCK_MARKET_FACTORS[

        STOCK_MARKET_FACTORS[
            "stock_research_scope"
        ]
        ==
        "CORE_LONG"

    ]

)


core_low_coverage = (

    core_long_e4[

        core_long_e4[
            "factor_coverage"
        ]
        <
        0.80

    ]

)


# ============================================================
# 38. E4 HEALTH CHECK ENGINE
# ============================================================

e4_checks = []


def add_e4_check(
    check: str,
    passed: bool,
    detail: str
):

    e4_checks.append(

        {

            "check":
                check,

            "passed":
                bool(
                    passed
                ),

            "detail":
                str(
                    detail
                ),

        }

    )


add_e4_check(

    "Stock factor universe matches E3 eligible universe",

    stock_count
    ==
    len(
        ELIGIBLE_STOCK_PRICE_UNIVERSE
    ),

    (
        f"E4={stock_count}, "
        f"E3="
        f"{len(ELIGIBLE_STOCK_PRICE_UNIVERSE)}"
    ),

)


add_e4_check(

    "Stock tickers unique",

    STOCK_MARKET_FACTORS[
        "ticker"
    ]
    .nunique()
    ==
    stock_count,

    (
        f"rows={stock_count}, "
        f"unique="
        f"{STOCK_MARKET_FACTORS['ticker'].nunique()}"
    ),

)


add_e4_check(

    "All final market-factor scores finite",

    finite_score_count
    ==
    stock_count,

    (
        f"finite="
        f"{finite_score_count}"
        f"/{stock_count}"
    ),

)


add_e4_check(

    "At least 98% stocks have >=80% factor coverage",

    (

        acceptable_factor_coverage_count
        /
        stock_count

    )
    >=
    0.98,

    (
        f"coverage="
        f"{acceptable_factor_coverage_count}"
        f"/{stock_count} "
        f"("
        f"{acceptable_factor_coverage_count / stock_count:.1%}"
        f")"
    ),

)


add_e4_check(

    "Core-long stocks have >=80% factor coverage",

    core_low_coverage.empty,

    (
        f"low_coverage_core_names="
        f"{len(core_low_coverage)}"
    ),

)


add_e4_check(

    "No factor observation after market cutoff",

    future_rows
    ==
    0,

    (
        f"future_rows="
        f"{future_rows}"
    ),

)


add_e4_check(

    "Historical membership backtest remains blocked",

    bool(

        (
            SP500_CONSTITUENTS[
                "historical_backtest_eligible"
            ]
            ==
            False
        )
        .all()

    ),

    "Current membership remains LIVE_ONLY",

)


E4_HEALTH = pd.DataFrame(
    e4_checks
)


E4_HEALTH[
    "status"
] = np.where(

    E4_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


E4_PASSED = bool(

    E4_HEALTH[
        "passed"
    ]
    .all()

)


# ============================================================
# 39. E4 SUMMARY
# ============================================================

E4_SUMMARY = pd.DataFrame(

    [

        {

            "market_as_of_date":
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ),

            "stocks":
                stock_count,

            "research_sectors":
                STOCK_MARKET_FACTORS[
                    "sector_ticker"
                ]
                .nunique(),

            "high_factor_coverage_stocks":
                high_factor_coverage_count,

            "acceptable_factor_coverage_stocks":
                acceptable_factor_coverage_count,

            "mean_factor_coverage":
                float(

                    STOCK_MARKET_FACTORS[
                        "factor_coverage"
                    ].mean()

                ),

            "mean_factor_confidence":
                float(

                    STOCK_MARKET_FACTORS[
                        "market_factor_confidence"
                    ].mean()

                ),

            "low_confidence_stocks":
                int(

                    (
                        STOCK_MARKET_FACTORS[
                            "market_factor_confidence"
                        ]
                        <
                        0.70
                    ).sum()

                ),

            "e4_passed":
                E4_PASSED,

        }

    ]

)


# ============================================================
# 40. SAVE OUTPUTS
# ============================================================

STOCK_MARKET_FACTORS.to_parquet(

    STOCK_MODEL_DIR
    /
    "live_stock_market_factors.parquet",

    index=False,

)


E4_TOP_STOCKS_BY_SECTOR.to_parquet(

    STOCK_MODEL_DIR
    /
    "e4_top_stocks_by_sector.parquet",

    index=False,

)


STOCK_MARKET_FACTORS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e4_stock_market_factors.csv",

    index=False,

)


E4_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e4_health.csv",

    index=False,

)


E4_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e4_summary.csv",

    index=False,

)


# ============================================================
# 41. DISPLAY
# ============================================================

print(
    "=" * 125
)

print(
    "E4 — STOCK-LEVEL MARKET FACTOR ENGINE"
)

print(
    "=" * 125
)


print(
    f"Market as-of date:           "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    f"Stocks analyzed:             "
    f"{stock_count}"
)


print(
    f"Research sectors:            "
    f"{STOCK_MARKET_FACTORS['sector_ticker'].nunique()}"
)


print(
    f">=90% factor coverage:       "
    f"{high_factor_coverage_count}"
    f"/{stock_count}"
)


print(
    f">=80% factor coverage:       "
    f"{acceptable_factor_coverage_count}"
    f"/{stock_count}"
)


print(
    f"Mean factor confidence:      "
    f"{STOCK_MARKET_FACTORS['market_factor_confidence'].mean():.3f}"
)


print(
    "\nTop 5 stocks within each research sector:"
)


display(

    E4_TOP_STOCKS_BY_SECTOR[
        [
            "sector_ticker",
            "sector_name",
            "market_rank_within_sector",
            "ticker",
            "company_name",

            "momentum_1m",
            "momentum_3m",
            "momentum_6m",
            "momentum_12m",

            "sector_relative_3m",
            "sector_relative_6m",

            "trend_50d",
            "trend_200d",

            "sector_alpha",
            "sector_information_ratio",

            "volatility",
            "downside_volatility",

            "market_factor_score_z",
            "market_percentile_within_sector",
            "market_factor_confidence",
            "market_signal",
        ]
    ]

)


print(
    "\nLow-confidence / shorter-history stocks:"
)


low_confidence_table = (

    STOCK_MARKET_FACTORS[

        STOCK_MARKET_FACTORS[
            "market_factor_confidence"
        ]
        <
        0.70

    ][
        [
            "ticker",
            "company_name",
            "sector_ticker",
            "history_observations",
            "factor_coverage",
            "history_confidence",
            "market_factor_confidence",
            "market_rank_within_sector",
        ]
    ]

    .sort_values(
        "market_factor_confidence"
    )

)


if low_confidence_table.empty:

    print(
        "None."
    )

else:

    display(
        low_confidence_table
    )


print(
    "\nE4 health:"
)


display(
    E4_HEALTH
)


print(
    "\nE4 summary:"
)


display(
    E4_SUMMARY
)


# ============================================================
# 42. PRODUCTION GATE
# ============================================================

if not E4_PASSED:

    failed_e4_checks = (

        E4_HEALTH.loc[

            ~E4_HEALTH[
                "passed"
            ],

            [
                "check",
                "detail",
            ],

        ]

    )


    display(
        failed_e4_checks
    )


    raise RuntimeError(

        "E4 PRODUCTION GATE FAILED. "
        "Do not proceed to company-quality ranking."

    )


print(
    "\n✓ E4 COMPLETE — "
    "stock-level market factors constructed."
)


print(
    "✓ Stocks standardized within sector."
)


print(
    "✓ Short-history stocks handled without backward filling."
)


print(
    "✓ Beta retained as diagnostic rather than standalone alpha."
)


print(
    "✓ Ready for E5."
)

# ===== ORIGINAL NOTEBOOK CELL 55 =====
# ============================================================
# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E5 — SYSTEMATIC FUNDAMENTAL DATA ENGINE + AUTO-REPAIR
# ============================================================
#
# Pipeline:
#
#   1. Define active stock universe
#   2. Load same-day validated cache if available
#   3. Fetch Yahoo summary fundamentals
#   4. Calculate derived metrics
#   5. Measure sector-specific factor coverage
#   6. Automatically identify incomplete companies
#   7. Fetch quarterly / annual statements for those companies
#   8. Reconstruct missing fundamental metrics
#   9. Fill MISSING values only
#  10. Record field-level provenance
#  11. Recalculate coverage / eligibility
#  12. Run production QA
#  13. Persist immutable dated snapshot + latest snapshot
#
# IMPORTANT:
#
#   - No ticker-specific repair logic
#   - No artificial imputation
#   - Valid summary fields are never overwritten
#   - Financials use different required fields
#   - Valuation fields are stored but not scored here
#   - Current fundamentals remain LIVE_ONLY
# ============================================================


# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json

import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# 2. VALIDATE UPSTREAM
# ============================================================

required_e5_objects = [

    "E2_PASSED",
    "E3_PASSED",
    "ACTIVE_STOCK_UNIVERSE",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
    "MARKET_AS_OF_DATE",

]


missing_e5_objects = [

    obj
    for obj in required_e5_objects
    if obj not in globals()

]


if missing_e5_objects:

    raise RuntimeError(
        "E5 requires E2-E3 first. Missing: "
        f"{missing_e5_objects}"
    )


if not bool(E2_PASSED):

    raise RuntimeError(
        "E2 production gate did not pass."
    )


if not bool(E3_PASSED):

    raise RuntimeError(
        "E3 production gate did not pass."
    )


# ============================================================
# 3. PIPELINE VERSION
# ============================================================
#
# Versioned so an old E5 daily cache cannot silently bypass
# this redesigned pipeline.
# ============================================================

FUNDAMENTAL_PIPELINE_VERSION = "2.0.0"


# ============================================================
# 4. STORAGE DIRECTORIES
# ============================================================

if "DATA_DIR" in globals():

    FUNDAMENTAL_RAW_DIR = (
        Path(DATA_DIR)
        /
        "raw"
        /
        "stocks"
        /
        "fundamentals"
    )


    FUNDAMENTAL_CURATED_DIR = (
        Path(DATA_DIR)
        /
        "curated"
        /
        "stocks"
        /
        "fundamentals"
    )


elif "PROJECT_ROOT" in globals():

    FUNDAMENTAL_RAW_DIR = (
        Path(PROJECT_ROOT)
        /
        "data"
        /
        "raw"
        /
        "stocks"
        /
        "fundamentals"
    )


    FUNDAMENTAL_CURATED_DIR = (
        Path(PROJECT_ROOT)
        /
        "data"
        /
        "curated"
        /
        "stocks"
        /
        "fundamentals"
    )


else:

    raise RuntimeError(
        "Neither DATA_DIR nor PROJECT_ROOT is available."
    )


FUNDAMENTAL_RAW_DIR.mkdir(
    parents=True,
    exist_ok=True
)


FUNDAMENTAL_CURATED_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 5. SNAPSHOT GOVERNANCE
# ============================================================

FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC = (
    pd.Timestamp.now(
        tz="UTC"
    )
    .tz_localize(None)
)


FUNDAMENTAL_SNAPSHOT_DATE = (
    FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC
    .normalize()
)


snapshot_date_string = (
    FUNDAMENTAL_SNAPSHOT_DATE
    .strftime("%Y-%m-%d")
)


# ------------------------------------------------------------
# Raw normalized Yahoo summary
# ------------------------------------------------------------

FUNDAMENTAL_RAW_SUMMARY_PATH = (

    FUNDAMENTAL_RAW_DIR
    /
    (
        "yahoo_summary_v2_"
        f"{snapshot_date_string}.parquet"
    )

)


# ------------------------------------------------------------
# Final reconciled dated snapshot
# ------------------------------------------------------------

FUNDAMENTAL_RECONCILED_SNAPSHOT_PATH = (

    FUNDAMENTAL_CURATED_DIR
    /
    (
        "fundamentals_reconciled_v2_"
        f"{snapshot_date_string}.parquet"
    )

)


# ------------------------------------------------------------
# Latest production snapshot
# ------------------------------------------------------------

FUNDAMENTAL_LATEST_PATH = (

    FUNDAMENTAL_CURATED_DIR
    /
    "active_stock_fundamentals_latest_v2.parquet"

)


# ============================================================
# 6. ACTIVE FUNDAMENTAL UNIVERSE
# ============================================================

required_universe_columns = [

    "ticker",
    "yahoo_ticker",
    "company_name",

    "sector_ticker",
    "sector_name",

    "stock_research_scope",

    "sector_rank",
    "sector_signal_z",

    "core_long_eligible",
    "portfolio_long_allowed",

    "member_sp500",
    "member_nasdaq100",
    "member_soxx",
    "specialist_group",
    "universe_memberships",

]


missing_universe_columns = [

    column

    for column in required_universe_columns

    if column not in ACTIVE_STOCK_UNIVERSE.columns

]


if missing_universe_columns:

    raise RuntimeError(

        "ACTIVE_STOCK_UNIVERSE missing columns: "
        f"{missing_universe_columns}"

    )


FUNDAMENTAL_UNIVERSE = (

    ACTIVE_STOCK_UNIVERSE[
        required_universe_columns
    ]

    .drop_duplicates(
        subset=["ticker"]
    )

    .sort_values(
        [
            "sector_rank",
            "company_name",
        ]
    )

    .reset_index(drop=True)

)


if FUNDAMENTAL_UNIVERSE.empty:

    raise RuntimeError(
        "E5 fundamental universe is empty."
    )


# ============================================================
# 7. YAHOO SUMMARY FIELD MAP
# ============================================================

YAHOO_INFO_FIELD_MAP = {

    # Company metadata
    "sector":
        "yahoo_sector",

    "industry":
        "yahoo_industry",

    "currency":
        "currency",

    "financialCurrency":
        "financial_currency",


    # Scale
    "marketCap":
        "market_cap",

    "enterpriseValue":
        "enterprise_value",

    "totalRevenue":
        "total_revenue",

    "ebitda":
        "ebitda",

    "sharesOutstanding":
        "shares_outstanding",


    # Profitability
    "grossMargins":
        "gross_margin",

    "operatingMargins":
        "operating_margin",

    "profitMargins":
        "profit_margin",

    "returnOnAssets":
        "return_on_assets",

    "returnOnEquity":
        "return_on_equity",


    # Growth
    "revenueGrowth":
        "revenue_growth",

    "earningsGrowth":
        "earnings_growth",


    # Cash flow
    "operatingCashflow":
        "operating_cash_flow",

    "freeCashflow":
        "free_cash_flow",


    # Balance sheet
    "totalCash":
        "total_cash",

    "totalDebt":
        "total_debt",

    "debtToEquity":
        "debt_to_equity",

    "currentRatio":
        "current_ratio",

    "quickRatio":
        "quick_ratio",


    # Earnings
    "trailingEps":
        "trailing_eps",

    "forwardEps":
        "forward_eps",


    # Valuation — stored for later use
    "trailingPE":
        "trailing_pe",

    "forwardPE":
        "forward_pe",

    "priceToBook":
        "price_to_book",

    "enterpriseToEbitda":
        "enterprise_to_ebitda",


    # Diagnostics
    "beta":
        "yahoo_beta",

    "dividendYield":
        "dividend_yield",

    "payoutRatio":
        "payout_ratio",

}


# ============================================================
# 8. QUALITY INPUT DEFINITIONS
# ============================================================
#
# These align with what E6 will actually score.
# ============================================================

NON_FINANCIAL_QUALITY_FIELDS = [

    "gross_margin",
    "operating_margin",
    "profit_margin",

    "return_on_assets",
    "return_on_equity",

    "revenue_growth",
    "earnings_growth",

    "operating_cash_flow_margin",
    "free_cash_flow_margin",

    "net_debt_to_ebitda",
    "current_ratio",

]


FINANCIAL_QUALITY_FIELDS = [

    "profit_margin",

    "return_on_assets",
    "return_on_equity",

    "revenue_growth",
    "earnings_growth",

]


ALL_QUALITY_FIELDS = sorted(

    set(
        NON_FINANCIAL_QUALITY_FIELDS
    )
    |
    set(
        FINANCIAL_QUALITY_FIELDS
    )

)


# ============================================================
# 9. REPAIR POLICY
# ============================================================
#
# Any company missing ANY applicable quality factor is eligible
# for statement repair.
#
# This does not mean the production gate requires every single
# factor to exist. Some metrics may genuinely be unavailable.
# ============================================================

STATEMENT_REPAIR_TRIGGER_COVERAGE = 1.00


MIN_FEATURE_ELIGIBILITY_COVERAGE = 0.50


SUMMARY_FETCH_WORKERS = 4

STATEMENT_FETCH_WORKERS = 2


MAX_FETCH_ATTEMPTS = 3

RETRY_DELAY_SECONDS = 1.5


# ============================================================
# 10. HELPER — SAFE SCALAR
# ============================================================

def safe_scalar(
    value
):

    if value is None:

        return np.nan


    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            np.integer,
            np.floating,
        )
    ):

        return value


    return np.nan


# ============================================================
# 11. HELPER — SAFE RATIO
# ============================================================

def safe_ratio(
    numerator,
    denominator
):

    try:

        numerator = float(
            numerator
        )

        denominator = float(
            denominator
        )


    except Exception:

        return np.nan


    if (

        not safe_isfinite(numerator)

        or

        not safe_isfinite(denominator)

        or

        abs(denominator) <= 1e-12

    ):

        return np.nan


    return float(
        numerator
        /
        denominator
    )


# ============================================================
# 12. HELPER — STATEMENT LABEL NORMALIZATION
# ============================================================

def normalize_statement_label(
    value
):

    return (

        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
        .replace("&", "and")

    )


# ============================================================
# 13. HELPER — EXTRACT STATEMENT SERIES
# ============================================================

def get_statement_series(
    statement,
    candidate_labels,
):

    if (
        statement is None
        or
        statement.empty
    ):

        return pd.Series(
            dtype=float
        )


    normalized_index = {

        normalize_statement_label(index_value):
            index_value

        for index_value in statement.index

    }


    selected_index = None


    for candidate in candidate_labels:

        normalized_candidate = (
            normalize_statement_label(
                candidate
            )
        )


        if normalized_candidate in normalized_index:

            selected_index = (
                normalized_index[
                    normalized_candidate
                ]
            )

            break


    if selected_index is None:

        return pd.Series(
            dtype=float
        )


    values = pd.to_numeric(

        statement.loc[
            selected_index
        ],

        errors="coerce",

    )


    parsed_dates = pd.to_datetime(

        values.index,

        errors="coerce",

    )


    valid = ~pd.isna(
        parsed_dates
    )


    values = values[
        valid
    ]


    values.index = parsed_dates[
        valid
    ]


    return (

        values

        .dropna()

        .sort_index(
            ascending=False
        )

    )


# ============================================================
# 14. HELPER — TTM SUM
# ============================================================

def trailing_four_quarters(
    series
):

    series = (

        pd.to_numeric(
            series,
            errors="coerce"
        )

        .dropna()

    )


    if len(series) < 4:

        return np.nan


    return float(

        series.iloc[:4]
        .sum()

    )


# ============================================================
# 15. HELPER — AVERAGE TTM BALANCE
# ============================================================

def average_ttm_balance(
    series
):

    series = (

        pd.to_numeric(
            series,
            errors="coerce"
        )

        .dropna()

    )


    if len(series) == 0:

        return np.nan


    if len(series) >= 5:

        return float(

            (
                series.iloc[0]
                +
                series.iloc[4]
            )
            /
            2.0

        )


    if len(series) >= 2:

        return float(

            (
                series.iloc[0]
                +
                series.iloc[-1]
            )
            /
            2.0

        )


    return float(
        series.iloc[0]
    )


# ============================================================
# 16. HELPER — YOY GROWTH
# ============================================================
#
# Priority:
#
#   1. TTM vs previous TTM if 8 quarters available
#   2. Latest quarter vs same quarter prior year
#   3. Annual latest vs previous year
#
# For earnings, negative prior-period earnings are not turned
# into a misleading percentage growth rate.
# ============================================================

def calculate_yoy_growth(
    quarterly_series,
    annual_series=None,
    require_positive_base=True,
):

    quarterly_series = (

        pd.to_numeric(
            quarterly_series,
            errors="coerce"
        )

        .dropna()

    )


    # --------------------------------------------------------
    # TTM vs prior TTM
    # --------------------------------------------------------

    if len(quarterly_series) >= 8:

        latest = float(
            quarterly_series.iloc[:4].sum()
        )


        prior = float(
            quarterly_series.iloc[4:8].sum()
        )


        if (
            safe_isfinite(latest)
            and
            safe_isfinite(prior)
            and
            abs(prior) > 1e-12
            and
            (
                not require_positive_base
                or
                prior > 0
            )
        ):

            return float(
                latest / prior - 1.0
            )


    # --------------------------------------------------------
    # Latest quarter YoY
    # --------------------------------------------------------

    if len(quarterly_series) >= 5:

        latest = float(
            quarterly_series.iloc[0]
        )


        prior = float(
            quarterly_series.iloc[4]
        )


        if (
            safe_isfinite(latest)
            and
            safe_isfinite(prior)
            and
            abs(prior) > 1e-12
            and
            (
                not require_positive_base
                or
                prior > 0
            )
        ):

            return float(
                latest / prior - 1.0
            )


    # --------------------------------------------------------
    # Annual fallback
    # --------------------------------------------------------

    if annual_series is not None:

        annual_series = (

            pd.to_numeric(
                annual_series,
                errors="coerce"
            )

            .dropna()

        )


        if len(annual_series) >= 2:

            latest = float(
                annual_series.iloc[0]
            )


            prior = float(
                annual_series.iloc[1]
            )


            if (
                safe_isfinite(latest)
                and
                safe_isfinite(prior)
                and
                abs(prior) > 1e-12
                and
                (
                    not require_positive_base
                    or
                    prior > 0
                )
            ):

                return float(
                    latest / prior - 1.0
                )


    return np.nan


# ============================================================
# 17. HELPER — DERIVE SUMMARY METRICS
# ============================================================

def derive_summary_metrics(
    row
):

    result = row.copy()


    # --------------------------------------------------------
    # OCF margin
    # --------------------------------------------------------

    result[
        "operating_cash_flow_margin"
    ] = safe_ratio(

        result.get(
            "operating_cash_flow",
            np.nan
        ),

        result.get(
            "total_revenue",
            np.nan
        ),

    )


    # --------------------------------------------------------
    # FCF margin
    # --------------------------------------------------------

    result[
        "free_cash_flow_margin"
    ] = safe_ratio(

        result.get(
            "free_cash_flow",
            np.nan
        ),

        result.get(
            "total_revenue",
            np.nan
        ),

    )


    # --------------------------------------------------------
    # Net debt
    # --------------------------------------------------------

    total_debt = result.get(
        "total_debt",
        np.nan
    )


    total_cash = result.get(
        "total_cash",
        np.nan
    )


    if (
        pd.notna(total_debt)
        and
        pd.notna(total_cash)
    ):

        result[
            "net_debt"
        ] = (

            float(total_debt)
            -
            float(total_cash)

        )


    else:

        result[
            "net_debt"
        ] = np.nan


    # --------------------------------------------------------
    # Net debt / EBITDA
    # --------------------------------------------------------

    ebitda = result.get(
        "ebitda",
        np.nan
    )


    if (
        pd.notna(ebitda)
        and
        float(ebitda) > 0
    ):

        result[
            "net_debt_to_ebitda"
        ] = safe_ratio(

            result[
                "net_debt"
            ],

            ebitda,

        )


    else:

        result[
            "net_debt_to_ebitda"
        ] = np.nan


    return result


# ============================================================
# 18. HELPER — FETCH YAHOO SUMMARY
# ============================================================

def fetch_yahoo_summary(
    metadata
):

    ticker = metadata[
        "ticker"
    ]


    yahoo_ticker = metadata[
        "yahoo_ticker"
    ]


    last_error = None


    for attempt in range(
        1,
        MAX_FETCH_ATTEMPTS + 1
    ):

        try:

            ticker_object = yf.Ticker(
                yahoo_ticker
            )


            info = ticker_object.get_info()


            if not isinstance(
                info,
                dict
            ):

                raise RuntimeError(
                    "Yahoo returned invalid info object."
                )


            result = {

                **metadata,

                "pipeline_version":
                    FUNDAMENTAL_PIPELINE_VERSION,

                "fundamental_snapshot_timestamp_utc":
                    FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC,

                "market_data_as_of":
                    pd.Timestamp(
                        MARKET_AS_OF_DATE
                    ),

                "summary_fetch_success":
                    True,

                "summary_source":
                    "Yahoo Finance get_info",

                "historical_backtest_eligible":
                    False,

            }


            for (
                yahoo_field,
                output_field
            ) in YAHOO_INFO_FIELD_MAP.items():

                result[
                    output_field
                ] = safe_scalar(

                    info.get(
                        yahoo_field
                    )

                )


            # -----------------------------------------------
            # fast_info fallback for market cap
            # -----------------------------------------------

            if pd.isna(
                result.get(
                    "market_cap",
                    np.nan
                )
            ):

                try:

                    market_cap_fast = (

                        ticker_object
                        .fast_info[
                            "market_cap"
                        ]

                    )


                    if pd.notna(
                        market_cap_fast
                    ):

                        result[
                            "market_cap"
                        ] = float(
                            market_cap_fast
                        )


                except Exception:

                    pass


            result = derive_summary_metrics(
                result
            )


            return (
                result,
                None,
            )


        except Exception as exc:

            last_error = (

                f"{type(exc).__name__}: "
                f"{exc}"

            )


            if attempt < MAX_FETCH_ATTEMPTS:

                time.sleep(

                    RETRY_DELAY_SECONDS
                    *
                    attempt

                )


    # --------------------------------------------------------
    # Preserve company even when summary failed.
    # Statement fallback may still recover it.
    # --------------------------------------------------------

    result = {

        **metadata,

        "pipeline_version":
            FUNDAMENTAL_PIPELINE_VERSION,

        "fundamental_snapshot_timestamp_utc":
            FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC,

        "market_data_as_of":
            pd.Timestamp(
                MARKET_AS_OF_DATE
            ),

        "summary_fetch_success":
            False,

        "summary_source":
            "Yahoo Finance get_info",

        "historical_backtest_eligible":
            False,

    }


    failure = {

        "ticker":
            ticker,

        "yahoo_ticker":
            yahoo_ticker,

        "stage":
            "summary",

        "error":
            last_error,

    }


    return (
        result,
        failure,
    )


# ============================================================
# 19. HELPER — CALCULATE APPLICABLE COVERAGE
# ============================================================

def get_applicable_quality_fields(
    sector_ticker
):

    if sector_ticker == "XLF":

        return (
            FINANCIAL_QUALITY_FIELDS
        )


    return (
        NON_FINANCIAL_QUALITY_FIELDS
    )


def calculate_quality_coverage(
    row
):

    fields = get_applicable_quality_fields(

        row[
            "sector_ticker"
        ]

    )


    available = sum(

        pd.notna(
            row.get(
                field,
                np.nan
            )
        )

        for field in fields

    )


    expected = len(
        fields
    )


    return pd.Series({

        "fundamental_fields_available":
            int(available),

        "fundamental_fields_expected":
            int(expected),

        "fundamental_field_coverage":
            (
                available / expected
                if expected > 0
                else 0.0
            ),

    })


# ============================================================
# 20. HELPER — STATEMENT FALLBACK
# ============================================================

def fetch_statement_fallback(
    metadata
):

    ticker = metadata[
        "ticker"
    ]


    yahoo_ticker = metadata[
        "yahoo_ticker"
    ]


    last_error = None


    for attempt in range(
        1,
        MAX_FETCH_ATTEMPTS + 1
    ):

        try:

            obj = yf.Ticker(
                yahoo_ticker
            )


            # =================================================
            # Quarterly statements
            # =================================================

            q_income = (
                obj.quarterly_income_stmt
            )


            q_balance = (
                obj.quarterly_balance_sheet
            )


            q_cashflow = (
                obj.quarterly_cashflow
            )


            # =================================================
            # Annual statements
            # =================================================

            a_income = (
                obj.income_stmt
            )


            # =================================================
            # Income statement series
            # =================================================

            q_revenue = get_statement_series(

                q_income,

                [
                    "Total Revenue",
                    "Operating Revenue",
                    "Revenue",
                ],

            )


            a_revenue = get_statement_series(

                a_income,

                [
                    "Total Revenue",
                    "Operating Revenue",
                    "Revenue",
                ],

            )


            q_gross_profit = get_statement_series(

                q_income,

                [
                    "Gross Profit",
                ],

            )


            q_operating_income = get_statement_series(

                q_income,

                [
                    "Operating Income",
                ],

            )


            q_net_income = get_statement_series(

                q_income,

                [
                    "Net Income",
                    "Net Income Common Stockholders",
                    "Net Income Including Noncontrolling Interests",
                ],

            )


            a_net_income = get_statement_series(

                a_income,

                [
                    "Net Income",
                    "Net Income Common Stockholders",
                    "Net Income Including Noncontrolling Interests",
                ],

            )


            q_ebitda = get_statement_series(

                q_income,

                [
                    "EBITDA",
                    "Normalized EBITDA",
                ],

            )


            # =================================================
            # Balance sheet series
            # =================================================

            total_assets = get_statement_series(

                q_balance,

                [
                    "Total Assets",
                ],

            )


            total_equity = get_statement_series(

                q_balance,

                [
                    "Stockholders Equity",
                    "Stockholders' Equity",
                    "Total Stockholder Equity",
                    "Common Stock Equity",
                ],

            )


            total_cash = get_statement_series(

                q_balance,

                [
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash And Cash Equivalents",
                    "Cash",
                ],

            )


            total_debt = get_statement_series(

                q_balance,

                [
                    "Total Debt",
                ],

            )


            current_assets = get_statement_series(

                q_balance,

                [
                    "Current Assets",
                    "Total Current Assets",
                ],

            )


            current_liabilities = get_statement_series(

                q_balance,

                [
                    "Current Liabilities",
                    "Total Current Liabilities",
                ],

            )


            # =================================================
            # Cash-flow series
            # =================================================

            operating_cash_flow = get_statement_series(

                q_cashflow,

                [
                    "Operating Cash Flow",
                    "Total Cash From Operating Activities",
                ],

            )


            free_cash_flow = get_statement_series(

                q_cashflow,

                [
                    "Free Cash Flow",
                ],

            )


            capital_expenditure = get_statement_series(

                q_cashflow,

                [
                    "Capital Expenditure",
                    "Capital Expenditures",
                ],

            )


            # =================================================
            # TTM values
            # =================================================

            ttm_revenue = trailing_four_quarters(
                q_revenue
            )


            ttm_gross_profit = trailing_four_quarters(
                q_gross_profit
            )


            ttm_operating_income = trailing_four_quarters(
                q_operating_income
            )


            ttm_net_income = trailing_four_quarters(
                q_net_income
            )


            ttm_ebitda = trailing_four_quarters(
                q_ebitda
            )


            ttm_ocf = trailing_four_quarters(
                operating_cash_flow
            )


            ttm_fcf = trailing_four_quarters(
                free_cash_flow
            )


            # -------------------------------------------------
            # Derive FCF if statement did not report it
            # -------------------------------------------------

            if pd.isna(ttm_fcf):

                ttm_capex = trailing_four_quarters(
                    capital_expenditure
                )


                if (
                    pd.notna(ttm_ocf)
                    and
                    pd.notna(ttm_capex)
                ):

                    # Yahoo commonly reports CapEx as negative.
                    if ttm_capex <= 0:

                        ttm_fcf = (
                            ttm_ocf
                            +
                            ttm_capex
                        )


                    else:

                        ttm_fcf = (
                            ttm_ocf
                            -
                            ttm_capex
                        )


            # =================================================
            # Profitability
            # =================================================

            gross_margin = safe_ratio(

                ttm_gross_profit,
                ttm_revenue,

            )


            operating_margin = safe_ratio(

                ttm_operating_income,
                ttm_revenue,

            )


            profit_margin = safe_ratio(

                ttm_net_income,
                ttm_revenue,

            )


            average_assets = average_ttm_balance(
                total_assets
            )


            average_equity = average_ttm_balance(
                total_equity
            )


            return_on_assets = safe_ratio(

                ttm_net_income,
                average_assets,

            )


            return_on_equity = safe_ratio(

                ttm_net_income,
                average_equity,

            )


            # =================================================
            # Growth
            # =================================================

            revenue_growth = calculate_yoy_growth(

                q_revenue,
                a_revenue,
                require_positive_base=True,

            )


            earnings_growth = calculate_yoy_growth(

                q_net_income,
                a_net_income,
                require_positive_base=True,

            )


            # =================================================
            # Cash generation
            # =================================================

            operating_cash_flow_margin = safe_ratio(

                ttm_ocf,
                ttm_revenue,

            )


            free_cash_flow_margin = safe_ratio(

                ttm_fcf,
                ttm_revenue,

            )


            # =================================================
            # Balance sheet
            # =================================================

            latest_cash = (

                float(total_cash.iloc[0])
                if len(total_cash) > 0
                else np.nan

            )


            latest_debt = (

                float(total_debt.iloc[0])
                if len(total_debt) > 0
                else np.nan

            )


            latest_current_assets = (

                float(current_assets.iloc[0])
                if len(current_assets) > 0
                else np.nan

            )


            latest_current_liabilities = (

                float(current_liabilities.iloc[0])
                if len(current_liabilities) > 0
                else np.nan

            )


            if (
                pd.notna(latest_debt)
                and
                pd.notna(latest_cash)
            ):

                net_debt = (
                    latest_debt
                    -
                    latest_cash
                )


            else:

                net_debt = np.nan


            if (
                pd.notna(ttm_ebitda)
                and
                ttm_ebitda > 0
            ):

                net_debt_to_ebitda = safe_ratio(

                    net_debt,
                    ttm_ebitda,

                )


            else:

                net_debt_to_ebitda = np.nan


            current_ratio = safe_ratio(

                latest_current_assets,
                latest_current_liabilities,

            )


            # =================================================
            # Market capitalization fallback
            # =================================================

            market_cap = np.nan


            try:

                market_cap_candidate = (

                    obj.fast_info[
                        "market_cap"
                    ]

                )


                if pd.notna(
                    market_cap_candidate
                ):

                    market_cap = float(
                        market_cap_candidate
                    )


            except Exception:

                pass


            # =================================================
            # Final fallback payload
            # =================================================

            result = {

                "ticker":
                    ticker,

                "yahoo_ticker":
                    yahoo_ticker,

                "statement_fallback_success":
                    True,


                # Scale
                "total_revenue":
                    ttm_revenue,

                "market_cap":
                    market_cap,

                "ebitda":
                    ttm_ebitda,

                "total_cash":
                    latest_cash,

                "total_debt":
                    latest_debt,

                "net_debt":
                    net_debt,


                # Quality fields
                "gross_margin":
                    gross_margin,

                "operating_margin":
                    operating_margin,

                "profit_margin":
                    profit_margin,

                "return_on_assets":
                    return_on_assets,

                "return_on_equity":
                    return_on_equity,

                "revenue_growth":
                    revenue_growth,

                "earnings_growth":
                    earnings_growth,

                "operating_cash_flow_margin":
                    operating_cash_flow_margin,

                "free_cash_flow_margin":
                    free_cash_flow_margin,

                "net_debt_to_ebitda":
                    net_debt_to_ebitda,

                "current_ratio":
                    current_ratio,


                # Audit
                "fallback_income_quarters":
                    len(q_revenue),

                "fallback_balance_periods":
                    len(total_assets),

                "fallback_cashflow_quarters":
                    len(operating_cash_flow),

            }


            return (
                result,
                None,
            )


        except Exception as exc:

            last_error = (

                f"{type(exc).__name__}: "
                f"{exc}"

            )


            if attempt < MAX_FETCH_ATTEMPTS:

                time.sleep(

                    RETRY_DELAY_SECONDS
                    *
                    attempt

                )


    failure = {

        "ticker":
            ticker,

        "yahoo_ticker":
            yahoo_ticker,

        "stage":
            "statement_fallback",

        "error":
            last_error,

    }


    return (
        None,
        failure,
    )


# ============================================================
# 21. CHECK FOR VALID SAME-DAY V2 CACHE
# ============================================================

USE_EXISTING_E5_CACHE = False


if FUNDAMENTAL_RECONCILED_SNAPSHOT_PATH.exists():

    try:

        cached_fundamentals = pd.read_parquet(

            FUNDAMENTAL_RECONCILED_SNAPSHOT_PATH

        )


        valid_cache = (

            not cached_fundamentals.empty

            and

            "pipeline_version"
            in cached_fundamentals.columns

            and

            (
                cached_fundamentals[
                    "pipeline_version"
                ]
                ==
                FUNDAMENTAL_PIPELINE_VERSION
            )
            .all()

            and

            cached_fundamentals[
                "ticker"
            ]
            .nunique()
            ==
            len(
                FUNDAMENTAL_UNIVERSE
            )

        )


        if valid_cache:

            USE_EXISTING_E5_CACHE = True


    except Exception:

        USE_EXISTING_E5_CACHE = False


# ============================================================
# 22. CACHE BRANCH
# ============================================================

if USE_EXISTING_E5_CACHE:

    STOCK_FUNDAMENTAL_QA = (

        cached_fundamentals
        .copy()

    )


    FUNDAMENTAL_SOURCE_MODE = (
        "CACHED_RECONCILED_V2"
    )


    FUNDAMENTAL_FETCH_FAILURES = pd.DataFrame(

        columns=[
            "ticker",
            "yahoo_ticker",
            "stage",
            "error",
        ]

    )


    FUNDAMENTAL_REPAIR_FAILURES = pd.DataFrame(

        columns=[
            "ticker",
            "yahoo_ticker",
            "stage",
            "error",
        ]

    )


# ============================================================
# 23. LIVE BUILD BRANCH
# ============================================================

else:

    FUNDAMENTAL_SOURCE_MODE = (
        "LIVE_SYSTEMATIC_V2"
    )


    # ========================================================
    # 23A. FETCH SUMMARY DATA
    # ========================================================

    summary_results = []

    summary_failures = []


    fundamental_records = (

        FUNDAMENTAL_UNIVERSE
        .to_dict(
            orient="records"
        )

    )


    with ThreadPoolExecutor(

        max_workers=SUMMARY_FETCH_WORKERS

    ) as executor:

        futures = {

            executor.submit(

                fetch_yahoo_summary,
                record,

            ):
            record["ticker"]

            for record in fundamental_records

        }


        completed = 0


        for future in as_completed(
            futures
        ):

            completed += 1


            result, failure = (
                future.result()
            )


            summary_results.append(
                result
            )


            if failure is not None:

                summary_failures.append(
                    failure
                )


            if (
                completed % 25 == 0
                or
                completed == len(
                    fundamental_records
                )
            ):

                print(

                    "Summary fetch progress: "
                    f"{completed}/"
                    f"{len(fundamental_records)}"

                )


    STOCK_FUNDAMENTALS_SUMMARY = pd.DataFrame(
        summary_results
    )


    FUNDAMENTAL_FETCH_FAILURES = pd.DataFrame(
        summary_failures
    )


    # ========================================================
    # 23B. GUARANTEE OUTPUT COLUMNS
    # ========================================================

    for output_field in (

        YAHOO_INFO_FIELD_MAP.values()

    ):

        if output_field not in STOCK_FUNDAMENTALS_SUMMARY.columns:

            STOCK_FUNDAMENTALS_SUMMARY[
                output_field
            ] = np.nan


    for field in [

        "operating_cash_flow_margin",
        "free_cash_flow_margin",
        "net_debt",
        "net_debt_to_ebitda",

    ]:

        if field not in STOCK_FUNDAMENTALS_SUMMARY.columns:

            STOCK_FUNDAMENTALS_SUMMARY[
                field
            ] = np.nan


    # ========================================================
    # 23C. NUMERIC CONVERSION
    # ========================================================

    numeric_columns = [

        "market_cap",
        "enterprise_value",
        "total_revenue",
        "ebitda",
        "shares_outstanding",

        "gross_margin",
        "operating_margin",
        "profit_margin",
        "return_on_assets",
        "return_on_equity",

        "revenue_growth",
        "earnings_growth",

        "operating_cash_flow",
        "free_cash_flow",

        "total_cash",
        "total_debt",
        "debt_to_equity",

        "current_ratio",
        "quick_ratio",

        "trailing_eps",
        "forward_eps",

        "trailing_pe",
        "forward_pe",
        "price_to_book",
        "enterprise_to_ebitda",

        "yahoo_beta",
        "dividend_yield",
        "payout_ratio",

        "operating_cash_flow_margin",
        "free_cash_flow_margin",

        "net_debt",
        "net_debt_to_ebitda",

    ]


    for column in numeric_columns:

        STOCK_FUNDAMENTALS_SUMMARY[
            column
        ] = pd.to_numeric(

            STOCK_FUNDAMENTALS_SUMMARY[
                column
            ],

            errors="coerce",

        )


    # ========================================================
    # 23D. SAVE RAW NORMALIZED SUMMARY
    # ========================================================

    STOCK_FUNDAMENTALS_SUMMARY.to_parquet(

        FUNDAMENTAL_RAW_SUMMARY_PATH,

        index=False,

    )


    # ========================================================
    # 23E. INITIAL FIELD PROVENANCE
    # ========================================================

    STOCK_FUNDAMENTAL_QA = (

        STOCK_FUNDAMENTALS_SUMMARY
        .copy()

    )


    summary_derived_fields = {

        "operating_cash_flow_margin",
        "free_cash_flow_margin",
        "net_debt_to_ebitda",

    }


    for field in ALL_QUALITY_FIELDS:

        source_column = (
            f"source_{field}"
        )


        if field not in STOCK_FUNDAMENTAL_QA.columns:

            STOCK_FUNDAMENTAL_QA[
                field
            ] = np.nan


        STOCK_FUNDAMENTAL_QA[
            source_column
        ] = np.where(

            STOCK_FUNDAMENTAL_QA[
                field
            ].notna(),

            (
                "yahoo_info_derived"
                if field in summary_derived_fields
                else
                "yahoo_info"
            ),

            "missing",

        )


    # ========================================================
    # 23F. INITIAL COVERAGE
    # ========================================================

    initial_coverage = (

        STOCK_FUNDAMENTAL_QA

        .apply(

            calculate_quality_coverage,

            axis=1,

        )

    )


    STOCK_FUNDAMENTAL_QA[
        "coverage_before_repair"
    ] = (

        initial_coverage[
            "fundamental_field_coverage"
        ]

    )


    # ========================================================
    # 23G. AUTO-IDENTIFY REPAIR UNIVERSE
    # ========================================================

    repair_mask = (

        STOCK_FUNDAMENTAL_QA[
            "coverage_before_repair"
        ]

        <
        STATEMENT_REPAIR_TRIGGER_COVERAGE

    )


    FUNDAMENTAL_REPAIR_UNIVERSE = (

        STOCK_FUNDAMENTAL_QA.loc[

            repair_mask,

            [
                "ticker",
                "yahoo_ticker",
                "company_name",

                "sector_ticker",
                "sector_name",

                "stock_research_scope",

                "coverage_before_repair",
            ]

        ]

        .copy()

        .reset_index(drop=True)

    )


    print(
        "\nCompanies requiring automatic statement repair: "
        f"{len(FUNDAMENTAL_REPAIR_UNIVERSE)}"
    )


    # ========================================================
    # 23H. FETCH STATEMENT FALLBACK
    # ========================================================

    repair_results = []

    repair_failures = []


    if not FUNDAMENTAL_REPAIR_UNIVERSE.empty:

        repair_records = (

            FUNDAMENTAL_REPAIR_UNIVERSE
            .to_dict(
                orient="records"
            )

        )


        with ThreadPoolExecutor(

            max_workers=STATEMENT_FETCH_WORKERS

        ) as executor:

            futures = {

                executor.submit(

                    fetch_statement_fallback,
                    record,

                ):
                record["ticker"]

                for record in repair_records

            }


            completed = 0


            for future in as_completed(
                futures
            ):

                completed += 1


                result, failure = (
                    future.result()
                )


                if result is not None:

                    repair_results.append(
                        result
                    )


                if failure is not None:

                    repair_failures.append(
                        failure
                    )


                if (
                    completed % 10 == 0
                    or
                    completed == len(
                        repair_records
                    )
                ):

                    print(

                        "Statement repair progress: "
                        f"{completed}/"
                        f"{len(repair_records)}"

                    )


    FUNDAMENTAL_REPAIR_RESULTS = pd.DataFrame(
        repair_results
    )


    FUNDAMENTAL_REPAIR_FAILURES = pd.DataFrame(
        repair_failures
    )


    # ========================================================
    # 23I. PATCH MISSING FIELDS ONLY
    # ========================================================

    repairable_fields = (

        ALL_QUALITY_FIELDS
        +
        [
            "total_revenue",
            "market_cap",
            "ebitda",

            "total_cash",
            "total_debt",
            "net_debt",
        ]

    )


    STOCK_FUNDAMENTAL_QA[
        "statement_repair_attempted"
    ] = (

        STOCK_FUNDAMENTAL_QA[
            "ticker"
        ]

        .isin(
            FUNDAMENTAL_REPAIR_UNIVERSE[
                "ticker"
            ]
        )

    )


    STOCK_FUNDAMENTAL_QA[
        "statement_repair_success"
    ] = False


    STOCK_FUNDAMENTAL_QA[
        "repair_field_count"
    ] = 0


    STOCK_FUNDAMENTAL_QA[
        "repair_fields"
    ] = ""


    if not FUNDAMENTAL_REPAIR_RESULTS.empty:

        for _, repair in (
            FUNDAMENTAL_REPAIR_RESULTS
            .iterrows()
        ):

            ticker = repair[
                "ticker"
            ]


            mask = (

                STOCK_FUNDAMENTAL_QA[
                    "ticker"
                ]
                ==
                ticker

            )


            patched_fields = []


            for field in repairable_fields:

                if field not in repair.index:

                    continue


                fallback_value = repair[
                    field
                ]


                if pd.isna(
                    fallback_value
                ):

                    continue


                current_value = (

                    STOCK_FUNDAMENTAL_QA.loc[
                        mask,
                        field
                    ]

                )


                if (

                    len(current_value) == 1

                    and

                    pd.isna(
                        current_value.iloc[0]
                    )

                ):

                    STOCK_FUNDAMENTAL_QA.loc[

                        mask,
                        field

                    ] = fallback_value


                    patched_fields.append(
                        field
                    )


                    source_column = (
                        f"source_{field}"
                    )


                    if source_column in STOCK_FUNDAMENTAL_QA.columns:

                        STOCK_FUNDAMENTAL_QA.loc[

                            mask,
                            source_column

                        ] = (
                            "yahoo_financial_statements"
                        )


            STOCK_FUNDAMENTAL_QA.loc[

                mask,
                "statement_repair_success"

            ] = True


            STOCK_FUNDAMENTAL_QA.loc[

                mask,
                "repair_field_count"

            ] = len(
                patched_fields
            )


            STOCK_FUNDAMENTAL_QA.loc[

                mask,
                "repair_fields"

            ] = ",".join(
                patched_fields
            )


    # ========================================================
    # 23J. FINAL COVERAGE
    # ========================================================

    final_coverage = (

        STOCK_FUNDAMENTAL_QA

        .apply(

            calculate_quality_coverage,

            axis=1,

        )

    )


    for column in [

        "fundamental_fields_available",
        "fundamental_fields_expected",
        "fundamental_field_coverage",

    ]:

        STOCK_FUNDAMENTAL_QA[
            column
        ] = final_coverage[
            column
        ]


    # ========================================================
    # 23K. DATA STATUS
    # ========================================================

    def classify_fundamental_status(
        coverage
    ):

        if np.isclose(
            coverage,
            1.0
        ):

            return "COMPLETE"


        elif coverage >= 0.80:

            return "PASS"


        elif coverage >= 0.50:

            return "PARTIAL"


        else:

            return "INSUFFICIENT"


    STOCK_FUNDAMENTAL_QA[
        "fundamental_data_status"
    ] = (

        STOCK_FUNDAMENTAL_QA[
            "fundamental_field_coverage"
        ]

        .apply(
            classify_fundamental_status
        )

    )


    # ========================================================
    # 23L. FEATURE ELIGIBILITY
    # ========================================================

    STOCK_FUNDAMENTAL_QA[
        "fundamental_feature_eligible"
    ] = (

        STOCK_FUNDAMENTAL_QA[
            "fundamental_field_coverage"
        ]

        >=
        MIN_FEATURE_ELIGIBILITY_COVERAGE

    )


    # ========================================================
    # 23M. FINAL SOURCE SUMMARY
    # ========================================================

    def derive_source_summary(
        row
    ):

        if row[
            "statement_repair_success"
        ]:

            return (
                "Yahoo summary + financial statements"
            )


        if row[
            "summary_fetch_success"
        ]:

            return (
                "Yahoo summary"
            )


        return (
            "Unresolved"
        )


    STOCK_FUNDAMENTAL_QA[
        "fundamental_source"
    ] = (

        STOCK_FUNDAMENTAL_QA

        .apply(

            derive_source_summary,

            axis=1,

        )

    )


    # ========================================================
    # 23N. PIPELINE METADATA
    # ========================================================

    STOCK_FUNDAMENTAL_QA[
        "pipeline_version"
    ] = FUNDAMENTAL_PIPELINE_VERSION


    STOCK_FUNDAMENTAL_QA[
        "fundamental_snapshot_timestamp_utc"
    ] = FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC


    STOCK_FUNDAMENTAL_QA[
        "market_data_as_of"
    ] = pd.Timestamp(
        MARKET_AS_OF_DATE
    )


    STOCK_FUNDAMENTAL_QA[
        "historical_backtest_eligible"
    ] = False


    # ========================================================
    # 23O. SAVE RECONCILED DAILY SNAPSHOT
    # ========================================================

    STOCK_FUNDAMENTAL_QA.to_parquet(

        FUNDAMENTAL_RECONCILED_SNAPSHOT_PATH,

        index=False,

    )


# ============================================================
# 24. BACKWARD-COMPATIBILITY VARIABLE
# ============================================================
#
# Downstream code should use STOCK_FUNDAMENTAL_QA.
# Keep this alias so older notebook references do not break.
# ============================================================

STOCK_FUNDAMENTALS_RAW = (

    STOCK_FUNDAMENTAL_QA
    .copy()

)


# ============================================================
# 25. ENSURE EXPECTED FINAL COLUMNS
# ============================================================

for field in ALL_QUALITY_FIELDS:

    if field not in STOCK_FUNDAMENTAL_QA.columns:

        STOCK_FUNDAMENTAL_QA[
            field
        ] = np.nan


    source_column = (
        f"source_{field}"
    )


    if source_column not in STOCK_FUNDAMENTAL_QA.columns:

        STOCK_FUNDAMENTAL_QA[
            source_column
        ] = np.where(

            STOCK_FUNDAMENTAL_QA[
                field
            ].notna(),

            "unknown",

            "missing",

        )


# ============================================================
# 26. RECOMPUTE FINAL COVERAGE EVEN ON CACHE LOAD
# ============================================================

final_coverage = (

    STOCK_FUNDAMENTAL_QA

    .apply(

        calculate_quality_coverage,

        axis=1,

    )

)


for column in [

    "fundamental_fields_available",
    "fundamental_fields_expected",
    "fundamental_field_coverage",

]:

    STOCK_FUNDAMENTAL_QA[
        column
    ] = final_coverage[
        column
    ]


# ============================================================
# 27. FINAL STATUS / ELIGIBILITY
# ============================================================

def final_status_classifier(
    coverage
):

    if np.isclose(
        coverage,
        1.0
    ):

        return "COMPLETE"


    elif coverage >= 0.80:

        return "PASS"


    elif coverage >= 0.50:

        return "PARTIAL"


    else:

        return "INSUFFICIENT"


STOCK_FUNDAMENTAL_QA[
    "fundamental_data_status"
] = (

    STOCK_FUNDAMENTAL_QA[
        "fundamental_field_coverage"
    ]

    .apply(
        final_status_classifier
    )

)


STOCK_FUNDAMENTAL_QA[
    "fundamental_feature_eligible"
] = (

    STOCK_FUNDAMENTAL_QA[
        "fundamental_field_coverage"
    ]

    >=
    MIN_FEATURE_ELIGIBILITY_COVERAGE

)


# ============================================================
# 28. REPAIR AUDIT
# ============================================================

if "statement_repair_attempted" not in STOCK_FUNDAMENTAL_QA.columns:

    STOCK_FUNDAMENTAL_QA[
        "statement_repair_attempted"
    ] = False


if "statement_repair_success" not in STOCK_FUNDAMENTAL_QA.columns:

    STOCK_FUNDAMENTAL_QA[
        "statement_repair_success"
    ] = False


if "repair_field_count" not in STOCK_FUNDAMENTAL_QA.columns:

    STOCK_FUNDAMENTAL_QA[
        "repair_field_count"
    ] = 0


if "repair_fields" not in STOCK_FUNDAMENTAL_QA.columns:

    STOCK_FUNDAMENTAL_QA[
        "repair_fields"
    ] = ""


FUNDAMENTAL_REPAIR_AUDIT = (

    STOCK_FUNDAMENTAL_QA[

        STOCK_FUNDAMENTAL_QA[
            "statement_repair_attempted"
        ]

    ][
        [
            "ticker",
            "company_name",
            "sector_ticker",

            "coverage_before_repair",
            "fundamental_field_coverage",

            "statement_repair_success",
            "repair_field_count",
            "repair_fields",

            "fundamental_data_status",
            "fundamental_feature_eligible",

        ]
    ]

    .copy()

    .sort_values(

        [
            "sector_ticker",
            "ticker",
        ]

    )

    .reset_index(drop=True)

)


# ============================================================
# 29. FIELD-LEVEL PROVENANCE VALIDATION
# ============================================================

provenance_errors = 0


for field in ALL_QUALITY_FIELDS:

    source_column = (
        f"source_{field}"
    )


    invalid = (

        STOCK_FUNDAMENTAL_QA[
            field
        ].notna()

        &

        (
            STOCK_FUNDAMENTAL_QA[
                source_column
            ].isna()

            |

            (
                STOCK_FUNDAMENTAL_QA[
                    source_column
                ]
                ==
                "missing"
            )
        )

    )


    provenance_errors += int(
        invalid.sum()
    )


# ============================================================
# 30. COVERAGE STATISTICS
# ============================================================

requested_count = len(
    STOCK_FUNDAMENTAL_QA
)


eligible_count = int(

    STOCK_FUNDAMENTAL_QA[
        "fundamental_feature_eligible"
    ]
    .sum()

)


eligible_rate = (

    eligible_count
    /
    requested_count

)


complete_count = int(

    (
        STOCK_FUNDAMENTAL_QA[
            "fundamental_data_status"
        ]
        ==
        "COMPLETE"
    )

    .sum()

)


complete_rate = (

    complete_count
    /
    requested_count

)


# ------------------------------------------------------------
# Core-long
# ------------------------------------------------------------

CORE_FUNDAMENTAL_QA = (

    STOCK_FUNDAMENTAL_QA[

        STOCK_FUNDAMENTAL_QA[
            "core_long_eligible"
        ]
        ==
        True

    ]

)


core_count = len(
    CORE_FUNDAMENTAL_QA
)


core_eligible_count = int(

    CORE_FUNDAMENTAL_QA[
        "fundamental_feature_eligible"
    ]
    .sum()

)


core_eligible_rate = (

    core_eligible_count
    /
    core_count

    if core_count > 0

    else 1.0

)


core_complete_count = int(

    (
        CORE_FUNDAMENTAL_QA[
            "fundamental_data_status"
        ]
        ==
        "COMPLETE"
    )

    .sum()

)


core_complete_rate = (

    core_complete_count
    /
    core_count

    if core_count > 0

    else 1.0

)


# ============================================================
# 31. STATUS SUMMARY
# ============================================================

FUNDAMENTAL_STATUS_SUMMARY = (

    STOCK_FUNDAMENTAL_QA[
        "fundamental_data_status"
    ]

    .value_counts(
        dropna=False
    )

    .rename_axis(
        "status"
    )

    .reset_index(
        name="stock_count"
    )

)


# ============================================================
# 32. SECTOR COVERAGE SUMMARY
# ============================================================

E5_SECTOR_COVERAGE = (

    STOCK_FUNDAMENTAL_QA

    .groupby(
        [
            "sector_rank",
            "sector_ticker",
            "sector_name",
            "stock_research_scope",
        ],
        as_index=False,
    )

    .agg(

        company_count=(
            "ticker",
            "count"
        ),

        mean_field_coverage=(
            "fundamental_field_coverage",
            "mean"
        ),

        feature_eligible_rate=(
            "fundamental_feature_eligible",
            "mean"
        ),

        repair_attempt_rate=(
            "statement_repair_attempted",
            "mean"
        ),

        repair_success_rate=(
            "statement_repair_success",
            "mean"
        ),

    )

    .sort_values(
        "sector_rank"
    )

    .reset_index(drop=True)

)


# ============================================================
# 33. HEALTH CHECK ENGINE
# ============================================================
#
# required=True  -> production gate
# required=False -> diagnostic warning only
# ============================================================

e5_checks = []


def add_e5_check(
    check,
    passed,
    detail,
    required=True,
):

    e5_checks.append({

        "check":
            check,

        "passed":
            bool(passed),

        "required":
            bool(required),

        "detail":
            str(detail),

    })


# ------------------------------------------------------------
# Required gates
# ------------------------------------------------------------

add_e5_check(

    "Fundamental universe preserved",

    requested_count
    ==
    len(FUNDAMENTAL_UNIVERSE),

    (
        f"E5={requested_count}, "
        f"expected={len(FUNDAMENTAL_UNIVERSE)}"
    ),

)


add_e5_check(

    "Fundamental tickers unique",

    STOCK_FUNDAMENTAL_QA[
        "ticker"
    ]
    .nunique()
    ==
    requested_count,

    (
        f"rows={requested_count}, "
        f"unique="
        f"{STOCK_FUNDAMENTAL_QA['ticker'].nunique()}"
    ),

)


add_e5_check(

    "Overall quality-input eligibility >= 99%",

    eligible_rate >= 0.99,

    (
        f"eligible="
        f"{eligible_count}/"
        f"{requested_count} "
        f"({eligible_rate:.1%})"
    ),

)


add_e5_check(

    "Core-long quality-input eligibility = 100%",

    np.isclose(
        core_eligible_rate,
        1.0
    ),

    (
        f"eligible="
        f"{core_eligible_count}/"
        f"{core_count} "
        f"({core_eligible_rate:.1%})"
    ),

)


add_e5_check(

    "Populated quality fields have provenance",

    provenance_errors == 0,

    (
        f"provenance_errors="
        f"{provenance_errors}"
    ),

)


add_e5_check(

    "Historical fundamental backtest blocked",

    bool(

        (
            STOCK_FUNDAMENTAL_QA[
                "historical_backtest_eligible"
            ]

            .fillna(False)

            ==
            False
        )

        .all()

    ),

    "Current vendor/statement snapshot remains LIVE_ONLY",

)


# ------------------------------------------------------------
# Diagnostic checks — not hard failures
# ------------------------------------------------------------

add_e5_check(

    "Overall complete-factor coverage >= 90%",

    complete_rate >= 0.90,

    (
        f"complete="
        f"{complete_count}/"
        f"{requested_count} "
        f"({complete_rate:.1%})"
    ),

    required=False,

)


add_e5_check(

    "Core-long complete-factor coverage >= 90%",

    core_complete_rate >= 0.90,

    (
        f"complete="
        f"{core_complete_count}/"
        f"{core_count} "
        f"({core_complete_rate:.1%})"
    ),

    required=False,

)


E5_HEALTH = pd.DataFrame(
    e5_checks
)


E5_HEALTH[
    "status"
] = np.where(

    E5_HEALTH[
        "passed"
    ],

    "✓ PASS",

    np.where(

        E5_HEALTH[
            "required"
        ],

        "✗ FAIL",

        "⚠ WARN",

    )

)


required_failures = (

    E5_HEALTH[

        E5_HEALTH[
            "required"
        ]

        &

        ~E5_HEALTH[
            "passed"
        ]

    ]

)


E5_PASSED = (
    required_failures.empty
)


# ============================================================
# 34. E5 SUMMARY
# ============================================================

E5_SUMMARY = pd.DataFrame([{

    "pipeline_version":
        FUNDAMENTAL_PIPELINE_VERSION,

    "source_mode":
        FUNDAMENTAL_SOURCE_MODE,

    "snapshot_timestamp_utc":
        FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC,

    "market_data_as_of":
        pd.Timestamp(
            MARKET_AS_OF_DATE
        ),

    "requested_companies":
        requested_count,

    "quality_input_eligible":
        eligible_count,

    "quality_input_eligible_rate":
        eligible_rate,

    "complete_factor_companies":
        complete_count,

    "complete_factor_rate":
        complete_rate,

    "core_long_companies":
        core_count,

    "core_long_eligible_rate":
        core_eligible_rate,

    "core_long_complete_rate":
        core_complete_rate,

    "repair_attempted_companies":
        int(
            STOCK_FUNDAMENTAL_QA[
                "statement_repair_attempted"
            ].sum()
        ),

    "repair_success_companies":
        int(
            STOCK_FUNDAMENTAL_QA[
                "statement_repair_success"
            ].sum()
        ),

    "provenance_errors":
        provenance_errors,

    "historical_backtest_eligible":
        False,

    "e5_passed":
        E5_PASSED,

}])


# ============================================================
# 35. SAVE PRODUCTION OUTPUTS
# ============================================================

STOCK_FUNDAMENTAL_QA.to_parquet(

    FUNDAMENTAL_LATEST_PATH,

    index=False,

)


STOCK_FUNDAMENTAL_QA.to_parquet(

    STOCK_MODEL_DIR
    /
    "live_stock_fundamental_qa.parquet",

    index=False,

)


STOCK_FUNDAMENTAL_QA.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e5_stock_fundamental_qa.csv",

    index=False,

)


FUNDAMENTAL_REPAIR_AUDIT.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e5_fundamental_repair_audit.csv",

    index=False,

)


if "FUNDAMENTAL_FETCH_FAILURES" in globals():

    FUNDAMENTAL_FETCH_FAILURES.to_csv(

        STOCK_OUTPUT_DIR
        /
        "e5_summary_fetch_failures.csv",

        index=False,

    )


if "FUNDAMENTAL_REPAIR_FAILURES" in globals():

    FUNDAMENTAL_REPAIR_FAILURES.to_csv(

        STOCK_OUTPUT_DIR
        /
        "e5_statement_repair_failures.csv",

        index=False,

    )


E5_SECTOR_COVERAGE.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e5_sector_coverage.csv",

    index=False,

)


E5_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e5_health.csv",

    index=False,

)


E5_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e5_summary.csv",

    index=False,

)


# ============================================================
# 36. DISPLAY
# ============================================================

print(
    "=" * 125
)

print(
    "E5 — SYSTEMATIC FUNDAMENTAL DATA ENGINE + AUTO-REPAIR"
)

print(
    "=" * 125
)


print(
    f"Pipeline version:               "
    f"{FUNDAMENTAL_PIPELINE_VERSION}"
)


print(
    f"Source mode:                    "
    f"{FUNDAMENTAL_SOURCE_MODE}"
)


print(
    f"Snapshot timestamp UTC:         "
    f"{FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC}"
)


print(
    f"Market data as-of:              "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    f"Companies:                      "
    f"{requested_count}"
)


print(
    f"Quality-input eligible:         "
    f"{eligible_count}/"
    f"{requested_count} "
    f"({eligible_rate:.1%})"
)


print(
    f"Complete applicable factors:    "
    f"{complete_count}/"
    f"{requested_count} "
    f"({complete_rate:.1%})"
)


print(
    f"Core-long eligible:             "
    f"{core_eligible_count}/"
    f"{core_count} "
    f"({core_eligible_rate:.1%})"
)


print(
    f"Core-long complete:             "
    f"{core_complete_count}/"
    f"{core_count} "
    f"({core_complete_rate:.1%})"
)


print(
    f"Statement repair attempts:      "
    f"{int(STOCK_FUNDAMENTAL_QA['statement_repair_attempted'].sum())}"
)


print(
    f"Successful statement repairs:   "
    f"{int(STOCK_FUNDAMENTAL_QA['statement_repair_success'].sum())}"
)


print(
    f"Field provenance errors:        "
    f"{provenance_errors}"
)


print(
    "\nFundamental status:"
)


display(
    FUNDAMENTAL_STATUS_SUMMARY
)


print(
    "\nSector coverage:"
)


display(
    E5_SECTOR_COVERAGE
)


print(
    "\nAutomatic repair audit:"
)


if FUNDAMENTAL_REPAIR_AUDIT.empty:

    print(
        "No companies required statement repair."
    )


else:

    display(
        FUNDAMENTAL_REPAIR_AUDIT
    )


# ============================================================
# 37. UNRESOLVED COMPANIES
# ============================================================

unresolved_companies = (

    STOCK_FUNDAMENTAL_QA[

        ~
        STOCK_FUNDAMENTAL_QA[
            "fundamental_feature_eligible"
        ]

    ][
        [
            "ticker",
            "company_name",
            "sector_ticker",

            "fundamental_fields_available",
            "fundamental_fields_expected",
            "fundamental_field_coverage",

            "statement_repair_attempted",
            "statement_repair_success",

            "fundamental_data_status",
        ]
    ]

)


print(
    "\nUnresolved / ineligible companies:"
)


if unresolved_companies.empty:

    print(
        "None."
    )


else:

    display(
        unresolved_companies
    )


# ============================================================
# 38. HEALTH
# ============================================================

print(
    "\nE5 health:"
)


display(
    E5_HEALTH[
        [
            "status",
            "required",
            "check",
            "detail",
        ]
    ]
)


print(
    "\nE5 summary:"
)


display(
    E5_SUMMARY
)


# ============================================================
# 39. PRODUCTION GATE
# ============================================================

if not E5_PASSED:

    display(
        required_failures
    )


    raise RuntimeError(

        "E5 PRODUCTION GATE FAILED. "
        "Resolve required fundamental-data issues "
        "before running E6."

    )


print(
    "\n"
    + "=" * 125
)


print(
    "✓ E5 COMPLETE — systematic fundamental pipeline operational."
)


print(
    "✓ Yahoo summary fundamentals acquired."
)


print(
    "✓ Incomplete companies automatically routed to statement fallback."
)


print(
    "✓ Existing valid values were never overwritten."
)


print(
    "✓ Missing fields were reconstructed only from reported statements."
)


print(
    "✓ Field-level source provenance preserved."
)


print(
    "✓ Sector-aware quality-input coverage validated."
)


print(
    "✓ Historical PIT fundamental backtesting remains blocked."
)


print(
    "✓ Ready for revised E6."
)


print(
    "=" * 125
)

# ===== ORIGINAL NOTEBOOK CELL 56 =====
# ============================================================
# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E6 — SECTOR-AWARE FUNDAMENTAL QUALITY ENGINE V2
# ============================================================
#
# Purpose:
#
#   Convert the systematic E5 fundamental dataset into
#   sector-relative company-quality signals.
#
# Architecture:
#
#   E5 raw / repaired fundamentals
#        ↓
#   robust within-sector factor standardization
#        ↓
#   sector-appropriate quality model
#        ↓
#   missing-factor weight renormalization
#        ↓
#   dimension scores
#        ↓
#   composite quality score
#        ↓
#   coverage-aware confidence
#        ↓
#   within-sector quality ranking
#
#
# NON-FINANCIAL MODEL:
#
#   Profitability — 45%
#       gross margin              5%
#       operating margin         12%
#       profit margin             8%
#       ROA                      10%
#       ROE                      10%
#
#   Growth — 20%
#       revenue growth           10%
#       earnings growth          10%
#
#   Cash generation — 25%
#       OCF margin               10%
#       FCF margin               15%
#
#   Balance sheet — 10%
#       net debt / EBITDA         7%
#       current ratio             3%
#
#
# FINANCIAL MODEL:
#
#   Profitability — 65%
#       ROA                      25%
#       ROE                      25%
#       profit margin            15%
#
#   Growth — 35%
#       revenue growth           15%
#       earnings growth          20%
#
#
# IMPORTANT:
#
#   - Companies are ranked WITHIN sector.
#   - Missing factors are never imputed.
#   - Missing factor weights are renormalized.
#   - E5 field provenance is retained.
#   - Statement-derived metrics are not penalized simply
#     because they came from reported statements.
#   - Financials receive a lower structural confidence ceiling
#     because the available model lacks bank-specific fields
#     such as CET1, NIM, reserve quality, efficiency ratio, etc.
#   - Valuation is deliberately excluded.
#   - LIVE_ONLY.
# ============================================================


# ============================================================
# 1. VALIDATE SYSTEMATIC E5
# ============================================================

required_e6_objects = [

    "E5_PASSED",
    "FUNDAMENTAL_PIPELINE_VERSION",
    "STOCK_FUNDAMENTAL_QA",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
    "MARKET_AS_OF_DATE",

]


missing_e6_objects = [

    obj

    for obj in required_e6_objects

    if obj not in globals()

]


if missing_e6_objects:

    raise RuntimeError(

        "E6 requires systematic E5 first. Missing: "
        f"{missing_e6_objects}"

    )


if not bool(
    E5_PASSED
):

    raise RuntimeError(
        "E5 production gate did not pass."
    )


if FUNDAMENTAL_PIPELINE_VERSION != "2.0.0":

    raise RuntimeError(

        "E6 expects systematic E5 pipeline version 2.0.0. "
        f"Found {FUNDAMENTAL_PIPELINE_VERSION}."

    )


# ============================================================
# 2. QUALITY MODEL VERSION
# ============================================================

QUALITY_MODEL_VERSION = "2.0.0"


# ============================================================
# 3. NON-FINANCIAL QUALITY MODEL
# ============================================================

NON_FINANCIAL_QUALITY_MODEL = {

    # --------------------------------------------------------
    # PROFITABILITY — 45%
    # --------------------------------------------------------

    "gross_margin": {

        "weight": 0.05,
        "direction": +1.0,
        "dimension": "profitability",

    },

    "operating_margin": {

        "weight": 0.12,
        "direction": +1.0,
        "dimension": "profitability",

    },

    "profit_margin": {

        "weight": 0.08,
        "direction": +1.0,
        "dimension": "profitability",

    },

    "return_on_assets": {

        "weight": 0.10,
        "direction": +1.0,
        "dimension": "profitability",

    },

    "return_on_equity": {

        "weight": 0.10,
        "direction": +1.0,
        "dimension": "profitability",

    },


    # --------------------------------------------------------
    # GROWTH — 20%
    # --------------------------------------------------------

    "revenue_growth": {

        "weight": 0.10,
        "direction": +1.0,
        "dimension": "growth",

    },

    "earnings_growth": {

        "weight": 0.10,
        "direction": +1.0,
        "dimension": "growth",

    },


    # --------------------------------------------------------
    # CASH GENERATION — 25%
    # --------------------------------------------------------

    "operating_cash_flow_margin": {

        "weight": 0.10,
        "direction": +1.0,
        "dimension": "cash_generation",

    },

    "free_cash_flow_margin": {

        "weight": 0.15,
        "direction": +1.0,
        "dimension": "cash_generation",

    },


    # --------------------------------------------------------
    # BALANCE SHEET — 10%
    # --------------------------------------------------------

    "net_debt_to_ebitda": {

        "weight": 0.07,
        "direction": -1.0,
        "dimension": "balance_sheet",

    },

    "current_ratio": {

        "weight": 0.03,
        "direction": +1.0,
        "dimension": "balance_sheet",

    },

}


# ============================================================
# 4. FINANCIALS QUALITY MODEL
# ============================================================
#
# This is intentionally narrower.
#
# We do NOT force industrial-company measures such as:
#
#   FCF margin
#   net debt / EBITDA
#   current ratio
#
# onto banks, insurers or other financial institutions.
# ============================================================

FINANCIAL_QUALITY_MODEL = {

    # --------------------------------------------------------
    # PROFITABILITY — 65%
    # --------------------------------------------------------

    "return_on_assets": {

        "weight": 0.25,
        "direction": +1.0,
        "dimension": "profitability",

    },

    "return_on_equity": {

        "weight": 0.25,
        "direction": +1.0,
        "dimension": "profitability",

    },

    "profit_margin": {

        "weight": 0.15,
        "direction": +1.0,
        "dimension": "profitability",

    },


    # --------------------------------------------------------
    # GROWTH — 35%
    # --------------------------------------------------------

    "revenue_growth": {

        "weight": 0.15,
        "direction": +1.0,
        "dimension": "growth",

    },

    "earnings_growth": {

        "weight": 0.20,
        "direction": +1.0,
        "dimension": "growth",

    },

}


# ============================================================
# 5. VALIDATE MODEL WEIGHTS
# ============================================================

QUALITY_MODELS = {

    "NON_FINANCIAL":
        NON_FINANCIAL_QUALITY_MODEL,

    "FINANCIAL":
        FINANCIAL_QUALITY_MODEL,

}


for model_name, model in QUALITY_MODELS.items():

    total_weight = sum(

        specification[
            "weight"
        ]

        for specification in model.values()

    )


    if not np.isclose(

        total_weight,
        1.0,

        atol=1e-12,

    ):

        raise RuntimeError(

            f"{model_name} quality weights "
            f"must sum to 1. "
            f"Current={total_weight:.8f}"

        )


# ============================================================
# 6. CONFIDENCE PARAMETERS
# ============================================================
#
# Financials receive a maximum final quality confidence of
# 85% because this generic dataset lacks specialized banking /
# insurance quality variables.
# ============================================================

NON_FINANCIAL_STRUCTURAL_CONFIDENCE = 1.00

FINANCIAL_STRUCTURAL_CONFIDENCE = 0.85


MIN_QUALITY_WEIGHT_COVERAGE = 0.50


# ============================================================
# 7. BASE TABLE
# ============================================================

FUNDAMENTAL_QUALITY_BASE = (

    STOCK_FUNDAMENTAL_QA

    .copy()

)


FUNDAMENTAL_QUALITY_BASE[
    "quality_model_version"
] = QUALITY_MODEL_VERSION


FUNDAMENTAL_QUALITY_BASE[
    "quality_model"
] = np.where(

    FUNDAMENTAL_QUALITY_BASE[
        "sector_ticker"
    ]
    ==
    "XLF",

    "FINANCIAL",

    "NON_FINANCIAL",

)


# ============================================================
# 8. VALIDATE REQUIRED FIELDS
# ============================================================

ALL_QUALITY_FACTORS = sorted(

    set(

        NON_FINANCIAL_QUALITY_MODEL.keys()

    )

    |

    set(

        FINANCIAL_QUALITY_MODEL.keys()

    )

)


missing_quality_fields = [

    field

    for field in ALL_QUALITY_FACTORS

    if field not in FUNDAMENTAL_QUALITY_BASE.columns

]


if missing_quality_fields:

    raise RuntimeError(

        "Systematic E5 is missing quality fields: "
        f"{missing_quality_fields}"

    )


# ============================================================
# 9. ROBUST WITHIN-SECTOR FACTOR STANDARDIZATION
# ============================================================
#
# Why winsorize?
#
# Fundamental ratios can contain genuine but extreme values.
# A single outlier should not dominate the cross-section.
#
# Process:
#
#   1. retain missing as missing
#   2. winsorize at 5th / 95th percentile within sector
#   3. calculate population z-score
#   4. clip z-score to [-3, +3]
# ============================================================

def robust_within_sector_zscore(
    series: pd.Series
) -> pd.Series:

    values = pd.to_numeric(

        series,

        errors="coerce",

    )


    valid = values.dropna()


    if len(valid) < 3:

        return pd.Series(

            np.nan,

            index=series.index,

            dtype=float,

        )


    lower_bound = float(

        valid.quantile(
            0.05
        )

    )


    upper_bound = float(

        valid.quantile(
            0.95
        )

    )


    winsorized = values.clip(

        lower=lower_bound,
        upper=upper_bound,

    )


    mean_value = float(
        winsorized.mean()
    )


    standard_deviation = float(

        winsorized.std(
            ddof=0
        )

    )


    if (

        not safe_isfinite(
            standard_deviation
        )

        or

        standard_deviation <= 1e-12

    ):

        result = pd.Series(

            0.0,

            index=series.index,

            dtype=float,

        )


        result[
            values.isna()
        ] = np.nan


        return result


    result = (

        winsorized
        -
        mean_value

    ) / standard_deviation


    return result.clip(

        lower=-3.0,
        upper=3.0,

    )


# ============================================================
# 10. COMPOSITE STANDARDIZATION HELPER
# ============================================================
#
# Composite quality scores have already been built from
# winsorized factor z-scores, so we do not winsorize them again.
# ============================================================

def standard_within_sector_zscore(
    series: pd.Series
) -> pd.Series:

    values = pd.to_numeric(

        series,

        errors="coerce",

    )


    valid = values.dropna()


    if len(valid) < 3:

        return pd.Series(

            np.nan,

            index=series.index,

            dtype=float,

        )


    mean_value = float(
        valid.mean()
    )


    standard_deviation = float(

        valid.std(
            ddof=0
        )

    )


    if (

        not safe_isfinite(
            standard_deviation
        )

        or

        standard_deviation <= 1e-12

    ):

        result = pd.Series(

            0.0,

            index=series.index,

            dtype=float,

        )


        result[
            values.isna()
        ] = np.nan


        return result


    return (

        (
            values
            -
            mean_value
        )

        /
        standard_deviation

    ).clip(

        lower=-3.0,
        upper=3.0,

    )


# ============================================================
# 11. CREATE FACTOR Z-SCORES
# ============================================================

for factor in ALL_QUALITY_FACTORS:

    raw_z_column = (
        f"quality_z_{factor}"
    )


    FUNDAMENTAL_QUALITY_BASE[
        raw_z_column
    ] = (

        FUNDAMENTAL_QUALITY_BASE

        .groupby(
            "sector_ticker",
            group_keys=False,
        )[
            factor
        ]

        .transform(
            robust_within_sector_zscore
        )

    )


# ============================================================
# 12. CREATE ORIENTED FACTOR Z-SCORES
# ============================================================
#
# After orientation:
#
#       higher = better quality
#
# for every factor.
# ============================================================

for factor in ALL_QUALITY_FACTORS:

    oriented_column = (
        f"quality_oriented_z_{factor}"
    )


    raw_z_column = (
        f"quality_z_{factor}"
    )


    FUNDAMENTAL_QUALITY_BASE[
        oriented_column
    ] = np.nan


    # --------------------------------------------------------
    # Non-financial companies
    # --------------------------------------------------------

    if factor in NON_FINANCIAL_QUALITY_MODEL:

        mask = (

            FUNDAMENTAL_QUALITY_BASE[
                "quality_model"
            ]
            ==
            "NON_FINANCIAL"

        )


        direction = (

            NON_FINANCIAL_QUALITY_MODEL[
                factor
            ][
                "direction"
            ]

        )


        FUNDAMENTAL_QUALITY_BASE.loc[

            mask,
            oriented_column,

        ] = (

            FUNDAMENTAL_QUALITY_BASE.loc[

                mask,
                raw_z_column,

            ]

            *
            direction

        )


    # --------------------------------------------------------
    # Financial companies
    # --------------------------------------------------------

    if factor in FINANCIAL_QUALITY_MODEL:

        mask = (

            FUNDAMENTAL_QUALITY_BASE[
                "quality_model"
            ]
            ==
            "FINANCIAL"

        )


        direction = (

            FINANCIAL_QUALITY_MODEL[
                factor
            ][
                "direction"
            ]

        )


        FUNDAMENTAL_QUALITY_BASE.loc[

            mask,
            oriented_column,

        ] = (

            FUNDAMENTAL_QUALITY_BASE.loc[

                mask,
                raw_z_column,

            ]

            *
            direction

        )


# ============================================================
# 13. BUILD COMPANY QUALITY SCORES
# ============================================================

quality_score_rows = []


for row_index, row in (

    FUNDAMENTAL_QUALITY_BASE
    .iterrows()

):

    model_name = row[
        "quality_model"
    ]


    model = QUALITY_MODELS[
        model_name
    ]


    score_numerator = 0.0

    available_weight = 0.0

    available_factor_count = 0


    # --------------------------------------------------------
    # Dimension containers
    # --------------------------------------------------------

    dimension_numerator = {

        "profitability":
            0.0,

        "growth":
            0.0,

        "cash_generation":
            0.0,

        "balance_sheet":
            0.0,

    }


    dimension_available_weight = {

        "profitability":
            0.0,

        "growth":
            0.0,

        "cash_generation":
            0.0,

        "balance_sheet":
            0.0,

    }


    # --------------------------------------------------------
    # Source audit
    # --------------------------------------------------------

    statement_factor_count = 0

    summary_factor_count = 0

    missing_factor_count = 0


    # ========================================================
    # SCORE AVAILABLE FACTORS
    # ========================================================

    for factor, specification in (
        model.items()
    ):

        weight = float(

            specification[
                "weight"
            ]

        )


        dimension = (

            specification[
                "dimension"
            ]

        )


        oriented_column = (
            f"quality_oriented_z_{factor}"
        )


        value = row[
            oriented_column
        ]


        source_column = (
            f"source_{factor}"
        )


        source = row.get(

            source_column,
            "missing",

        )


        # ----------------------------------------------------
        # Source audit
        # ----------------------------------------------------

        if pd.notna(value):

            if source == "yahoo_financial_statements":

                statement_factor_count += 1


            else:

                summary_factor_count += 1


        else:

            missing_factor_count += 1


        # ----------------------------------------------------
        # Factor score
        # ----------------------------------------------------

        if pd.notna(value):

            score_numerator += (

                weight
                *
                float(value)

            )


            available_weight += (
                weight
            )


            available_factor_count += 1


            dimension_numerator[
                dimension
            ] += (

                weight
                *
                float(value)

            )


            dimension_available_weight[
                dimension
            ] += weight


    # ========================================================
    # RENORMALIZED QUALITY SCORE
    # ========================================================

    fundamentally_eligible = bool(

        row[
            "fundamental_feature_eligible"
        ]

    )


    if (

        available_weight
        >=
        MIN_QUALITY_WEIGHT_COVERAGE

        and

        fundamentally_eligible

    ):

        quality_score = (

            score_numerator
            /
            available_weight

        )


    else:

        quality_score = np.nan


    # ========================================================
    # DIMENSION SCORES
    # ========================================================

    dimension_scores = {}


    for dimension in [

        "profitability",
        "growth",
        "cash_generation",
        "balance_sheet",

    ]:

        weight = (

            dimension_available_weight[
                dimension
            ]

        )


        if weight > 0:

            dimension_scores[
                dimension
            ] = (

                dimension_numerator[
                    dimension
                ]

                /
                weight

            )


        else:

            dimension_scores[
                dimension
            ] = np.nan


    # ========================================================
    # SOURCE MIX
    # ========================================================

    available_factor_total = (

        statement_factor_count
        +
        summary_factor_count

    )


    if available_factor_total > 0:

        statement_factor_share = (

            statement_factor_count
            /
            available_factor_total

        )


    else:

        statement_factor_share = np.nan


    quality_score_rows.append({

        "row_index":
            row_index,

        "quality_score_raw":
            quality_score,

        "quality_weight_coverage":
            available_weight,

        "quality_factor_count":
            available_factor_count,

        "quality_factor_count_expected":
            len(model),

        "quality_missing_factor_count":
            missing_factor_count,

        "quality_summary_factor_count":
            summary_factor_count,

        "quality_statement_factor_count":
            statement_factor_count,

        "quality_statement_factor_share":
            statement_factor_share,

        "profitability_score":
            dimension_scores[
                "profitability"
            ],

        "growth_score":
            dimension_scores[
                "growth"
            ],

        "cash_generation_score":
            dimension_scores[
                "cash_generation"
            ],

        "balance_sheet_score":
            dimension_scores[
                "balance_sheet"
            ],

    })


quality_score_frame = (

    pd.DataFrame(
        quality_score_rows
    )

    .set_index(
        "row_index"
    )

)


# ============================================================
# 14. ATTACH QUALITY RESULTS
# ============================================================

for column in (

    quality_score_frame.columns

):

    FUNDAMENTAL_QUALITY_BASE[
        column
    ] = (

        quality_score_frame[
            column
        ]

    )


# ============================================================
# 15. STRUCTURAL MODEL CONFIDENCE
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_structural_confidence"
] = np.where(

    FUNDAMENTAL_QUALITY_BASE[
        "quality_model"
    ]
    ==
    "FINANCIAL",

    FINANCIAL_STRUCTURAL_CONFIDENCE,

    NON_FINANCIAL_STRUCTURAL_CONFIDENCE,

)


# ============================================================
# 16. COVERAGE-AWARE QUALITY CONFIDENCE
# ============================================================
#
# Confidence =
#
#   sqrt(
#       scoring-weight coverage
#       ×
#       E5 field coverage
#   )
#   ×
#   structural-model confidence
#
#
# Therefore:
#
#   complete non-financial company -> max 1.00
#   complete financial company     -> max 0.85
#
# Missing factors reduce confidence but do NOT create fake data.
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_confidence"
] = (

    np.sqrt(

        FUNDAMENTAL_QUALITY_BASE[
            "quality_weight_coverage"
        ]

        *

        FUNDAMENTAL_QUALITY_BASE[
            "fundamental_field_coverage"
        ]

    )

    *

    FUNDAMENTAL_QUALITY_BASE[
        "quality_structural_confidence"
    ]

)


FUNDAMENTAL_QUALITY_BASE[
    "quality_confidence"
] = (

    FUNDAMENTAL_QUALITY_BASE[
        "quality_confidence"
    ]

    .clip(
        lower=0.0,
        upper=1.0,
    )

)


FUNDAMENTAL_QUALITY_BASE.loc[

    FUNDAMENTAL_QUALITY_BASE[
        "quality_score_raw"
    ]
    .isna(),

    "quality_confidence",

] = 0.0


# ============================================================
# 17. STANDARDIZE COMPOSITE QUALITY WITHIN SECTOR
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_score_z"
] = (

    FUNDAMENTAL_QUALITY_BASE

    .groupby(
        "sector_ticker",
        group_keys=False,
    )[
        "quality_score_raw"
    ]

    .transform(
        standard_within_sector_zscore
    )

)


# ============================================================
# 18. CONFIDENCE-ADJUSTED QUALITY SCORE
# ============================================================
#
# This is a diagnostic/downstream input.
#
# Raw quality ranking remains separate from confidence.
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_confidence_adjusted_z"
] = (

    FUNDAMENTAL_QUALITY_BASE[
        "quality_score_z"
    ]

    *

    FUNDAMENTAL_QUALITY_BASE[
        "quality_confidence"
    ]

)


# ============================================================
# 19. SCORE ELIGIBILITY
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_score_eligible"
] = (

    FUNDAMENTAL_QUALITY_BASE[
        "quality_score_raw"
    ]
    .notna()

    &

    FUNDAMENTAL_QUALITY_BASE[
        "quality_score_z"
    ]
    .notna()

    &

    (
        FUNDAMENTAL_QUALITY_BASE[
            "quality_weight_coverage"
        ]
        >=
        MIN_QUALITY_WEIGHT_COVERAGE
    )

    &

    FUNDAMENTAL_QUALITY_BASE[
        "fundamental_feature_eligible"
    ]

)


# ============================================================
# 20. WITHIN-SECTOR QUALITY RANK
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_rank_within_sector"
] = (

    FUNDAMENTAL_QUALITY_BASE

    .groupby(
        "sector_ticker"
    )[
        "quality_score_raw"
    ]

    .rank(
        method="first",
        ascending=False,
        na_option="keep",
    )

)


# ============================================================
# 21. WITHIN-SECTOR QUALITY PERCENTILE
# ============================================================

FUNDAMENTAL_QUALITY_BASE[
    "quality_percentile_within_sector"
] = (

    FUNDAMENTAL_QUALITY_BASE

    .groupby(
        "sector_ticker"
    )[
        "quality_score_raw"
    ]

    .rank(
        method="average",
        pct=True,
        ascending=True,
        na_option="keep",
    )

    *
    100.0

)


# ============================================================
# 22. QUALITY SIGNAL LABEL
# ============================================================

def classify_quality_signal(
    score
):

    if pd.isna(score):

        return "Unavailable"


    if score >= 1.25:

        return "Strong quality"


    elif score >= 0.40:

        return "Above average"


    elif score <= -1.25:

        return "Weak quality"


    elif score <= -0.40:

        return "Below average"


    else:

        return "Average"


FUNDAMENTAL_QUALITY_BASE[
    "quality_signal"
] = (

    FUNDAMENTAL_QUALITY_BASE[
        "quality_score_z"
    ]

    .apply(
        classify_quality_signal
    )

)


# ============================================================
# 23. CONFIDENCE LABEL
# ============================================================

def classify_quality_confidence(
    confidence
):

    if pd.isna(confidence):

        return "Unavailable"


    if confidence >= 0.90:

        return "High"


    elif confidence >= 0.70:

        return "Medium"


    elif confidence > 0:

        return "Low"


    else:

        return "Unavailable"


FUNDAMENTAL_QUALITY_BASE[
    "quality_confidence_label"
] = (

    FUNDAMENTAL_QUALITY_BASE[
        "quality_confidence"
    ]

    .apply(
        classify_quality_confidence
    )

)


# ============================================================
# 24. FINAL QUALITY TABLE
# ============================================================

STOCK_FUNDAMENTAL_QUALITY = (

    FUNDAMENTAL_QUALITY_BASE

    .sort_values(

        [
            "sector_rank",
            "quality_rank_within_sector",
        ],

        na_position="last",

    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 25. TOP 10 QUALITY NAMES BY SECTOR
# ============================================================

E6_TOP_QUALITY_BY_SECTOR = (

    STOCK_FUNDAMENTAL_QUALITY[

        STOCK_FUNDAMENTAL_QUALITY[
            "quality_score_eligible"
        ]

    ]

    .groupby(
        "sector_ticker",
        group_keys=False,
    )

    .head(
        10
    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 26. INCOMPLETE-BUT-ELIGIBLE AUDIT
# ============================================================

E6_INCOMPLETE_QUALITY_AUDIT = (

    STOCK_FUNDAMENTAL_QUALITY[

        (
            STOCK_FUNDAMENTAL_QUALITY[
                "fundamental_data_status"
            ]
            !=
            "COMPLETE"
        )

        &

        STOCK_FUNDAMENTAL_QUALITY[
            "quality_score_eligible"
        ]

    ][
        [
            "ticker",
            "company_name",
            "sector_ticker",

            "fundamental_data_status",
            "fundamental_field_coverage",

            "quality_weight_coverage",

            "quality_factor_count",
            "quality_factor_count_expected",

            "quality_missing_factor_count",

            "quality_score_z",
            "quality_confidence",

            "quality_rank_within_sector",

        ]
    ]

    .copy()

    .sort_values(
        [
            "sector_ticker",
            "quality_rank_within_sector",
        ]
    )

    .reset_index(drop=True)

)


# ============================================================
# 27. REPAIRED-COMPANY QUALITY AUDIT
# ============================================================
#
# Generic — not Fiserv-specific.
# ============================================================

E6_REPAIRED_COMPANY_AUDIT = (

    STOCK_FUNDAMENTAL_QUALITY[

        STOCK_FUNDAMENTAL_QUALITY[
            "statement_repair_attempted"
        ]

    ][
        [
            "ticker",
            "company_name",
            "sector_ticker",

            "statement_repair_success",
            "repair_field_count",

            "fundamental_field_coverage",

            "quality_score_z",
            "quality_confidence",

            "quality_statement_factor_count",
            "quality_statement_factor_share",

            "quality_rank_within_sector",
            "quality_signal",

        ]
    ]

    .copy()

    .sort_values(
        [
            "sector_ticker",
            "quality_rank_within_sector",
        ]
    )

    .reset_index(drop=True)

)


# ============================================================
# 28. QUALITY COVERAGE METRICS
# ============================================================

company_count = len(
    STOCK_FUNDAMENTAL_QUALITY
)


quality_eligible_count = int(

    STOCK_FUNDAMENTAL_QUALITY[
        "quality_score_eligible"
    ]

    .sum()

)


quality_eligible_rate = (

    quality_eligible_count
    /
    company_count

    if company_count > 0

    else 0.0

)


finite_quality_score_count = int(

    safe_isfinite(

        STOCK_FUNDAMENTAL_QUALITY.loc[

            STOCK_FUNDAMENTAL_QUALITY[
                "quality_score_eligible"
            ],

            "quality_score_z",

        ]

    ).sum()

)


# ============================================================
# 29. CORE-LONG QUALITY COVERAGE
# ============================================================

CORE_LONG_FUNDAMENTAL_QUALITY = (

    STOCK_FUNDAMENTAL_QUALITY[

        STOCK_FUNDAMENTAL_QUALITY[
            "core_long_eligible"
        ]
        ==
        True

    ]

)


core_quality_count = len(
    CORE_LONG_FUNDAMENTAL_QUALITY
)


core_quality_eligible_count = int(

    CORE_LONG_FUNDAMENTAL_QUALITY[
        "quality_score_eligible"
    ]

    .sum()

)


core_quality_eligible_rate = (

    core_quality_eligible_count
    /
    core_quality_count

    if core_quality_count > 0

    else 1.0

)


# ============================================================
# 30. FINANCIALS CONFIDENCE DIAGNOSTIC
# ============================================================

FINANCIAL_FUNDAMENTAL_QUALITY = (

    STOCK_FUNDAMENTAL_QUALITY[

        STOCK_FUNDAMENTAL_QUALITY[
            "quality_model"
        ]
        ==
        "FINANCIAL"

    ]

)


financial_company_count = len(
    FINANCIAL_FUNDAMENTAL_QUALITY
)


if financial_company_count > 0:

    financial_max_confidence = float(

        FINANCIAL_FUNDAMENTAL_QUALITY[
            "quality_confidence"
        ].max()

    )


    financial_mean_confidence = float(

        FINANCIAL_FUNDAMENTAL_QUALITY[
            "quality_confidence"
        ].mean()

    )


    financial_confidence_cap_valid = bool(

        safe_isfinite(
            financial_max_confidence
        )

        and

        financial_max_confidence
        <=
        FINANCIAL_STRUCTURAL_CONFIDENCE
        +
        1e-12

    )


    financial_confidence_cap_detail = (

        f"max_financial_confidence="
        f"{financial_max_confidence:.4f}, "
        f"ceiling="
        f"{FINANCIAL_STRUCTURAL_CONFIDENCE:.4f}"

    )


else:

    # No financial companies are present in the current research
    # universe.  The financial-specific ceiling is therefore N/A,
    # not a production failure.

    financial_max_confidence = np.nan
    financial_mean_confidence = np.nan
    financial_confidence_cap_valid = True

    financial_confidence_cap_detail = (
        "N/A — no FINANCIAL companies in current E6 universe"
    )


# ============================================================
# 31. SOURCE-AUDIT CONSISTENCY
# ============================================================

source_audit_expected = (

    STOCK_FUNDAMENTAL_QUALITY[
        "quality_factor_count_expected"
    ]

)


source_audit_actual = (

    STOCK_FUNDAMENTAL_QUALITY[
        "quality_summary_factor_count"
    ]

    +

    STOCK_FUNDAMENTAL_QUALITY[
        "quality_statement_factor_count"
    ]

    +

    STOCK_FUNDAMENTAL_QUALITY[
        "quality_missing_factor_count"
    ]

)


source_audit_consistent = bool(

    (
        source_audit_actual
        ==
        source_audit_expected
    )
    .all()

)


# ============================================================
# 32. CONFIDENCE VALIDATION
# ============================================================

confidence_valid = bool(

    STOCK_FUNDAMENTAL_QUALITY[
        "quality_confidence"
    ]

    .between(
        0.0,
        1.0,
        inclusive="both",
    )

    .all()

)


# ============================================================
# 33. SECTOR QUALITY SUMMARY
# ============================================================

E6_SECTOR_QUALITY_SUMMARY = (

    STOCK_FUNDAMENTAL_QUALITY

    .groupby(
        [
            "sector_rank",
            "sector_ticker",
            "sector_name",
            "stock_research_scope",
            "quality_model",
        ],
        as_index=False,
    )

    .agg(

        company_count=(
            "ticker",
            "count"
        ),

        quality_eligible_count=(
            "quality_score_eligible",
            "sum"
        ),

        mean_field_coverage=(
            "fundamental_field_coverage",
            "mean"
        ),

        mean_weight_coverage=(
            "quality_weight_coverage",
            "mean"
        ),

        mean_quality_confidence=(
            "quality_confidence",
            "mean"
        ),

        mean_statement_factor_share=(
            "quality_statement_factor_share",
            "mean"
        ),

    )

    .sort_values(
        "sector_rank"
    )

    .reset_index(drop=True)

)


E6_SECTOR_QUALITY_SUMMARY[
    "quality_eligible_rate"
] = (

    E6_SECTOR_QUALITY_SUMMARY[
        "quality_eligible_count"
    ]

    /

    E6_SECTOR_QUALITY_SUMMARY[
        "company_count"
    ]

)


# ============================================================
# 34. HEALTH CHECK ENGINE
# ============================================================

e6_checks = []


def add_e6_check(
    check,
    passed,
    detail,
):

    e6_checks.append({

        "check":
            check,

        "passed":
            bool(passed),

        "detail":
            str(detail),

    })


# ------------------------------------------------------------
# Universe
# ------------------------------------------------------------

add_e6_check(

    "E5 company universe preserved",

    company_count
    ==
    len(STOCK_FUNDAMENTAL_QA),

    (
        f"E6={company_count}, "
        f"E5={len(STOCK_FUNDAMENTAL_QA)}"
    ),

)


add_e6_check(

    "Company tickers unique",

    STOCK_FUNDAMENTAL_QUALITY[
        "ticker"
    ]
    .nunique()
    ==
    company_count,

    (
        f"rows={company_count}, "
        f"unique="
        f"{STOCK_FUNDAMENTAL_QUALITY['ticker'].nunique()}"
    ),

)


# ------------------------------------------------------------
# Eligibility
# ------------------------------------------------------------

add_e6_check(

    "Quality-score eligibility = 100%",

    np.isclose(
        quality_eligible_rate,
        1.0,
    ),

    (
        f"eligible="
        f"{quality_eligible_count}/"
        f"{company_count} "
        f"({quality_eligible_rate:.1%})"
    ),

)


add_e6_check(

    "Core-long quality-score eligibility = 100%",

    np.isclose(
        core_quality_eligible_rate,
        1.0,
    ),

    (
        f"eligible="
        f"{core_quality_eligible_count}/"
        f"{core_quality_count} "
        f"({core_quality_eligible_rate:.1%})"
    ),

)


# ------------------------------------------------------------
# Scores
# ------------------------------------------------------------

add_e6_check(

    "All eligible composite z-scores finite",

    finite_quality_score_count
    ==
    quality_eligible_count,

    (
        f"finite="
        f"{finite_quality_score_count}/"
        f"{quality_eligible_count}"
    ),

)


# ------------------------------------------------------------
# Confidence
# ------------------------------------------------------------

add_e6_check(

    "Quality confidence bounded [0,1]",

    confidence_valid,

    (
        "min="
        f"{STOCK_FUNDAMENTAL_QUALITY['quality_confidence'].min():.4f}, "
        "max="
        f"{STOCK_FUNDAMENTAL_QUALITY['quality_confidence'].max():.4f}"
    ),

)


add_e6_check(

    "Financial final confidence capped at 85%",

    financial_confidence_cap_valid,

    financial_confidence_cap_detail,

)


# ------------------------------------------------------------
# Provenance
# ------------------------------------------------------------

add_e6_check(

    "Quality factor source audit consistent",

    source_audit_consistent,

    "summary + statement + missing = expected factors",

)


# ------------------------------------------------------------
# Governance
# ------------------------------------------------------------

add_e6_check(

    "Historical fundamental backtest remains blocked",

    bool(

        (
            STOCK_FUNDAMENTAL_QUALITY[
                "historical_backtest_eligible"
            ]

            .fillna(False)

            ==
            False

        )

        .all()

    ),

    "Systematic E5/E6 fundamentals remain LIVE_ONLY",

)


E6_HEALTH = pd.DataFrame(
    e6_checks
)


E6_HEALTH[
    "status"
] = np.where(

    E6_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


E6_PASSED = bool(

    E6_HEALTH[
        "passed"
    ]
    .all()

)


# ============================================================
# 35. SUMMARY
# ============================================================

E6_SUMMARY = pd.DataFrame([{

    "quality_model_version":
        QUALITY_MODEL_VERSION,

    "fundamental_pipeline_version":
        FUNDAMENTAL_PIPELINE_VERSION,

    "companies":
        company_count,

    "quality_eligible_companies":
        quality_eligible_count,

    "quality_eligible_rate":
        quality_eligible_rate,

    "core_long_companies":
        core_quality_count,

    "core_long_quality_eligible_rate":
        core_quality_eligible_rate,

    "mean_quality_confidence":
        float(

            STOCK_FUNDAMENTAL_QUALITY[
                "quality_confidence"
            ]
            .mean()

        ),

    "financial_mean_confidence":
        financial_mean_confidence,

    "financial_max_confidence":
        financial_max_confidence,

    "incomplete_but_eligible_companies":
        len(
            E6_INCOMPLETE_QUALITY_AUDIT
        ),

    "statement_repaired_companies":
        len(
            E6_REPAIRED_COMPANY_AUDIT
        ),

    "market_data_as_of":
        pd.Timestamp(
            MARKET_AS_OF_DATE
        ),

    "fundamental_snapshot_timestamp_utc":
        FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC,

    "historical_backtest_eligible":
        False,

    "e6_passed":
        E6_PASSED,

}])


# ============================================================
# 36. SAVE OUTPUTS
# ============================================================

STOCK_FUNDAMENTAL_QUALITY.to_parquet(

    STOCK_MODEL_DIR
    /
    "live_stock_fundamental_quality_v2.parquet",

    index=False,

)


E6_TOP_QUALITY_BY_SECTOR.to_parquet(

    STOCK_MODEL_DIR
    /
    "e6_top_quality_by_sector_v2.parquet",

    index=False,

)


E6_INCOMPLETE_QUALITY_AUDIT.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e6_incomplete_quality_audit.csv",

    index=False,

)


E6_REPAIRED_COMPANY_AUDIT.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e6_repaired_company_quality_audit.csv",

    index=False,

)


E6_SECTOR_QUALITY_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e6_sector_quality_summary_v2.csv",

    index=False,

)


STOCK_FUNDAMENTAL_QUALITY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e6_stock_fundamental_quality_v2.csv",

    index=False,

)


E6_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e6_health_v2.csv",

    index=False,

)


E6_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e6_summary_v2.csv",

    index=False,

)


# ============================================================
# 37. DISPLAY
# ============================================================

print(
    "=" * 130
)

print(
    "E6 — SECTOR-AWARE FUNDAMENTAL QUALITY ENGINE V2"
)

print(
    "=" * 130
)


print(
    f"Quality model version:           "
    f"{QUALITY_MODEL_VERSION}"
)


print(
    f"Fundamental pipeline version:    "
    f"{FUNDAMENTAL_PIPELINE_VERSION}"
)


print(
    f"Companies analyzed:              "
    f"{company_count}"
)


print(
    f"Quality eligible:                "
    f"{quality_eligible_count}/"
    f"{company_count} "
    f"({quality_eligible_rate:.1%})"
)


print(
    f"Core-long quality eligible:      "
    f"{core_quality_eligible_count}/"
    f"{core_quality_count} "
    f"({core_quality_eligible_rate:.1%})"
)


print(
    f"Mean quality confidence:         "
    f"{STOCK_FUNDAMENTAL_QUALITY['quality_confidence'].mean():.3f}"
)


print(
    f"Financial mean confidence:       "
    +
    (
        f"{financial_mean_confidence:.3f}"
        if financial_company_count > 0
        else "N/A (no financial companies)"
    )
)


print(
    f"Financial max confidence:        "
    +
    (
        f"{financial_max_confidence:.3f}"
        if financial_company_count > 0
        else "N/A (no financial companies)"
    )
)


print(
    f"Incomplete but eligible:         "
    f"{len(E6_INCOMPLETE_QUALITY_AUDIT)}"
)


print(
    f"Statement-repaired companies:    "
    f"{len(E6_REPAIRED_COMPANY_AUDIT)}"
)


# ============================================================
# 38. SECTOR SUMMARY
# ============================================================

print(
    "\nSector fundamental-quality summary:"
)


display(
    E6_SECTOR_QUALITY_SUMMARY
)


# ============================================================
# 39. TOP QUALITY COMPANIES
# ============================================================

print(
    "\nTop 10 fundamental-quality companies within each sector:"
)


display(

    E6_TOP_QUALITY_BY_SECTOR[
        [
            "sector_ticker",
            "sector_name",

            "quality_rank_within_sector",

            "ticker",
            "company_name",

            "profitability_score",
            "growth_score",
            "cash_generation_score",
            "balance_sheet_score",

            "quality_score_z",
            "quality_confidence_adjusted_z",

            "quality_percentile_within_sector",

            "quality_weight_coverage",
            "quality_confidence",
            "quality_confidence_label",

            "quality_signal",
        ]
    ]

)


# ============================================================
# 40. INCOMPLETE-BUT-ELIGIBLE AUDIT
# ============================================================

print(
    "\nIncomplete but quality-eligible companies:"
)


if E6_INCOMPLETE_QUALITY_AUDIT.empty:

    print(
        "None."
    )


else:

    display(
        E6_INCOMPLETE_QUALITY_AUDIT
    )


# ============================================================
# 41. REPAIRED-COMPANY AUDIT
# ============================================================

print(
    "\nStatement-repaired companies in quality model:"
)


if E6_REPAIRED_COMPANY_AUDIT.empty:

    print(
        "None."
    )


else:

    display(
        E6_REPAIRED_COMPANY_AUDIT
    )


# ============================================================
# 42. HEALTH
# ============================================================

print(
    "\nE6 health:"
)


display(
    E6_HEALTH[
        [
            "status",
            "check",
            "detail",
        ]
    ]
)


print(
    "\nE6 summary:"
)


display(
    E6_SUMMARY
)


# ============================================================
# 43. PRODUCTION GATE
# ============================================================

if not E6_PASSED:

    failed_e6_checks = (

        E6_HEALTH.loc[

            ~
            E6_HEALTH[
                "passed"
            ],

            [
                "check",
                "detail",
            ],

        ]

    )


    display(
        failed_e6_checks
    )


    raise RuntimeError(

        "E6 PRODUCTION GATE FAILED. "
        "Do not proceed to combined stock selection."

    )


print(
    "\n"
    + "=" * 130
)


print(
    "✓ E6 COMPLETE — sector-aware quality engine operational."
)


print(
    "✓ Scores standardized within sector."
)


print(
    "✓ Missing factors handled through weight renormalization."
)


print(
    "✓ Incomplete companies remain usable with lower confidence."
)


print(
    "✓ Statement-derived factors retain explicit provenance."
)


print(
    "✓ Financials use a separate structural-confidence framework."
)


print(
    "✓ Valuation remains outside the quality score."
)


print(
    "✓ Ready for E7 combined stock-selection signal."
)


print(
    "=" * 130
)

# ===== ORIGINAL NOTEBOOK CELL 57 =====
# ============================================================
# SECTION E — STOCK UNIVERSE + COMPANY SELECTION ENGINE
# CELL E7 — COMBINED COMPANY SELECTION ENGINE
# ============================================================
#
# Purpose:
#
#   Combine:
#
#       E4 — market leadership
#       E6 — fundamental quality
#
#   into the first integrated company-selection signal.
#
#
# Company-specific weights:
#
#       w_market =
#           market confidence
#           / total confidence
#
#       w_quality =
#           quality confidence
#           / total confidence
#
#
# Combined signal:
#
#       S_i =
#           w_market * Z_market
#           +
#           w_quality * Z_quality
#
#
# Evidence confidence:
#
#       C_i =
#           sqrt(
#               C_market
#               *
#               C_quality
#           )
#
#
# Ranking score:
#
#       S*_i =
#           S_i * C_i
#
#
# IMPORTANT:
#
#   - Rankings remain WITHIN sector.
#   - E7 is NOT a buy signal.
#   - E7 identifies valuation/research candidates.
#   - Valuation remains separate.
#   - Portfolio construction remains separate.
#   - LIVE_ONLY.
# ============================================================


# ============================================================
# 1. VALIDATE UPSTREAM
# ============================================================

required_e7_objects = [

    "E4_PASSED",
    "STOCK_MARKET_FACTORS",

    "E6_PASSED",
    "STOCK_FUNDAMENTAL_QUALITY",

    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
    "MARKET_AS_OF_DATE",

]


missing_e7_objects = [

    obj

    for obj in required_e7_objects

    if obj not in globals()

]


if missing_e7_objects:

    raise RuntimeError(

        "E7 requires E4 and E6 first. Missing: "
        f"{missing_e7_objects}"

    )


if not bool(
    E4_PASSED
):

    raise RuntimeError(
        "E4 production gate did not pass."
    )


if not bool(
    E6_PASSED
):

    raise RuntimeError(
        "E6 production gate did not pass."
    )


# ============================================================
# 2. MODEL VERSION
# ============================================================

STOCK_SELECTION_MODEL_VERSION = "1.0.1"


# ============================================================
# 3. SELECTION PARAMETERS
# ============================================================

PRIMARY_SELECTION_Z = 0.75

PRIMARY_SELECTION_PERCENTILE = 80.0


SECONDARY_SELECTION_Z = 0.25

SECONDARY_SELECTION_PERCENTILE = 60.0


MIN_PRIMARY_CONFIDENCE = 0.75

MIN_SECONDARY_CONFIDENCE = 0.65


NEGATIVE_SELECTION_Z = -0.75

NEGATIVE_SELECTION_PERCENTILE = 20.0


# ============================================================
# 4. MARKET / QUALITY CONFLICT THRESHOLD
# ============================================================

HARD_STOCK_CONFLICT_THRESHOLD = 1.00


# ============================================================
# 5. MARKET FACTOR INPUT
# ============================================================

required_market_columns = [

    "ticker",
    "sector_ticker",

    "market_factor_score_z",
    "market_factor_confidence",

    "market_rank_within_sector",
    "market_percentile_within_sector",

    "market_signal",

    "momentum_1m",
    "momentum_3m",
    "momentum_6m",
    "momentum_12m",

    "sector_relative_3m",
    "sector_relative_6m",

    "trend_50d",
    "trend_200d",

    "sector_alpha",
    "sector_information_ratio",

    "volatility",
    "downside_volatility",

]


missing_market_columns = [

    column

    for column in required_market_columns

    if column not in STOCK_MARKET_FACTORS.columns

]


if missing_market_columns:

    raise RuntimeError(

        "E4 market-factor table missing columns: "
        f"{missing_market_columns}"

    )


E7_MARKET_INPUT = (

    STOCK_MARKET_FACTORS[
        required_market_columns
    ]

    .copy()

    .rename(

        columns={

            "sector_ticker":
                "market_sector_ticker",

        }

    )

)


# ============================================================
# 6. FUNDAMENTAL QUALITY INPUT
# ============================================================

required_quality_columns = [

    "ticker",
    "company_name",

    "sector_ticker",
    "sector_name",

    "sector_rank",
    "sector_signal_z",

    "stock_research_scope",

    "core_long_eligible",
    "portfolio_long_allowed",

    "quality_score_z",
    "quality_confidence",

    "quality_rank_within_sector",
    "quality_percentile_within_sector",

    "quality_signal",

    "profitability_score",
    "growth_score",
    "cash_generation_score",
    "balance_sheet_score",

    "fundamental_field_coverage",
    "quality_weight_coverage",

    "quality_statement_factor_share",

    "fundamental_snapshot_timestamp_utc",

    "market_cap",
    "member_sp500",
    "member_nasdaq100",
    "member_soxx",
    "specialist_group",
    "universe_memberships",

    # ========================================================
    # FIX:
    # Required later by E7 governance check.
    # ========================================================
    "historical_backtest_eligible",

]


missing_quality_columns = [

    column

    for column in required_quality_columns

    if column not in STOCK_FUNDAMENTAL_QUALITY.columns

]


if missing_quality_columns:

    raise RuntimeError(

        "E6 fundamental-quality table missing columns: "
        f"{missing_quality_columns}"

    )


E7_QUALITY_INPUT = (

    STOCK_FUNDAMENTAL_QUALITY[
        required_quality_columns
    ]

    .copy()

)


# ============================================================
# 7. MERGE MARKET + FUNDAMENTAL SIGNALS
# ============================================================

STOCK_SELECTION_BASE = (

    E7_QUALITY_INPUT

    .merge(

        E7_MARKET_INPUT,

        on="ticker",

        how="left",

        validate="one_to_one",

    )

)


# ============================================================
# 8. SECTOR MAPPING VALIDATION
# ============================================================

sector_mapping_consistent = (

    STOCK_SELECTION_BASE[
        "sector_ticker"
    ]
    ==
    STOCK_SELECTION_BASE[
        "market_sector_ticker"
    ]

)


if not bool(
    sector_mapping_consistent.all()
):

    mismatches = (

        STOCK_SELECTION_BASE.loc[

            ~sector_mapping_consistent,

            [
                "ticker",
                "company_name",
                "sector_ticker",
                "market_sector_ticker",
            ],

        ]

    )


    display(
        mismatches
    )


    raise RuntimeError(
        "E4/E6 sector mapping mismatch."
    )


# ============================================================
# 9. VALIDATE SIGNAL AVAILABILITY
# ============================================================

required_signal_columns = [

    "market_factor_score_z",
    "market_factor_confidence",

    "quality_score_z",
    "quality_confidence",

]


missing_signal_rows = (

    STOCK_SELECTION_BASE[

        STOCK_SELECTION_BASE[
            required_signal_columns
        ]

        .isna()

        .any(axis=1)

    ]

)


if not missing_signal_rows.empty:

    display(

        missing_signal_rows[
            [
                "ticker",
                "company_name",
                "sector_ticker",
            ]
            +
            required_signal_columns
        ]

    )


    raise RuntimeError(

        "E7 found companies with missing E4/E6 signals."

    )


# ============================================================
# 10. CONFIDENCE VALIDATION
# ============================================================

for column in [

    "market_factor_confidence",
    "quality_confidence",

]:

    valid_confidence = bool(

        STOCK_SELECTION_BASE[
            column
        ]

        .between(
            0.0,
            1.0,
            inclusive="both",
        )

        .all()

    )


    if not valid_confidence:

        raise RuntimeError(

            f"{column} contains values outside [0,1]."

        )


# ============================================================
# 11. COMPANY-SPECIFIC DYNAMIC WEIGHTS
# ============================================================

STOCK_SELECTION_BASE[
    "total_signal_confidence"
] = (

    STOCK_SELECTION_BASE[
        "market_factor_confidence"
    ]

    +

    STOCK_SELECTION_BASE[
        "quality_confidence"
    ]

)


if (

    STOCK_SELECTION_BASE[
        "total_signal_confidence"
    ]
    <=
    0

).any():

    raise RuntimeError(

        "At least one company has zero total "
        "market + quality confidence."

    )


STOCK_SELECTION_BASE[
    "market_effective_weight"
] = (

    STOCK_SELECTION_BASE[
        "market_factor_confidence"
    ]

    /

    STOCK_SELECTION_BASE[
        "total_signal_confidence"
    ]

)


STOCK_SELECTION_BASE[
    "quality_effective_weight"
] = (

    STOCK_SELECTION_BASE[
        "quality_confidence"
    ]

    /

    STOCK_SELECTION_BASE[
        "total_signal_confidence"
    ]

)


# ============================================================
# 12. VALIDATE WEIGHTS
# ============================================================

STOCK_SELECTION_BASE[
    "effective_weight_sum"
] = (

    STOCK_SELECTION_BASE[
        "market_effective_weight"
    ]

    +

    STOCK_SELECTION_BASE[
        "quality_effective_weight"
    ]

)


if not np.allclose(

    STOCK_SELECTION_BASE[
        "effective_weight_sum"
    ],

    1.0,

    atol=1e-12,

):

    raise RuntimeError(

        "E7 effective weights do not sum to 1."

    )


# ============================================================
# 13. RAW COMBINED SIGNAL
# ============================================================

STOCK_SELECTION_BASE[
    "combined_stock_signal_raw"
] = (

    STOCK_SELECTION_BASE[
        "market_effective_weight"
    ]

    *
    STOCK_SELECTION_BASE[
        "market_factor_score_z"
    ]

    +

    STOCK_SELECTION_BASE[
        "quality_effective_weight"
    ]

    *
    STOCK_SELECTION_BASE[
        "quality_score_z"
    ]

)


# ============================================================
# 14. OVERALL EVIDENCE CONFIDENCE
# ============================================================

STOCK_SELECTION_BASE[
    "stock_selection_confidence"
] = np.sqrt(

    STOCK_SELECTION_BASE[
        "market_factor_confidence"
    ]

    *

    STOCK_SELECTION_BASE[
        "quality_confidence"
    ]

)


STOCK_SELECTION_BASE[
    "stock_selection_confidence"
] = (

    STOCK_SELECTION_BASE[
        "stock_selection_confidence"
    ]

    .clip(
        lower=0.0,
        upper=1.0,
    )

)


# ============================================================
# 15. CONFIDENCE-ADJUSTED SCORE
# ============================================================

STOCK_SELECTION_BASE[
    "combined_stock_signal_conf_adj"
] = (

    STOCK_SELECTION_BASE[
        "combined_stock_signal_raw"
    ]

    *

    STOCK_SELECTION_BASE[
        "stock_selection_confidence"
    ]

)


# ============================================================
# 16. WITHIN-SECTOR STANDARDIZATION
# ============================================================

def e7_within_sector_zscore(
    series
):

    values = pd.to_numeric(

        series,

        errors="coerce",

    )


    valid = values.dropna()


    if len(valid) < 3:

        return pd.Series(

            np.nan,

            index=series.index,

            dtype=float,

        )


    mean_value = float(
        valid.mean()
    )


    standard_deviation = float(

        valid.std(
            ddof=0
        )

    )


    if (

        not safe_isfinite(
            standard_deviation
        )

        or

        standard_deviation <= 1e-12

    ):

        result = pd.Series(

            0.0,

            index=series.index,

            dtype=float,

        )


        result[
            values.isna()
        ] = np.nan


        return result


    return (

        (
            values
            -
            mean_value
        )

        /
        standard_deviation

    ).clip(

        lower=-3.0,
        upper=3.0,

    )


STOCK_SELECTION_BASE[
    "stock_selection_score_z"
] = (

    STOCK_SELECTION_BASE

    .groupby(
        "sector_ticker",
        group_keys=False,
    )[
        "combined_stock_signal_conf_adj"
    ]

    .transform(
        e7_within_sector_zscore
    )

)


# ============================================================
# 17. WITHIN-SECTOR RANK
# ============================================================

STOCK_SELECTION_BASE[
    "stock_selection_rank_within_sector"
] = (

    STOCK_SELECTION_BASE

    .groupby(
        "sector_ticker"
    )[
        "combined_stock_signal_conf_adj"
    ]

    .rank(
        method="first",
        ascending=False,
    )

    .astype(int)

)


# ============================================================
# 18. WITHIN-SECTOR PERCENTILE
# ============================================================

STOCK_SELECTION_BASE[
    "stock_selection_percentile"
] = (

    STOCK_SELECTION_BASE

    .groupby(
        "sector_ticker"
    )[
        "combined_stock_signal_conf_adj"
    ]

    .rank(
        method="average",
        ascending=True,
        pct=True,
    )

    *
    100.0

)


# ============================================================
# 19. MARKET / QUALITY ALIGNMENT
# ============================================================

def classify_stock_signal_alignment(
    row
):

    market = row[
        "market_factor_score_z"
    ]


    quality = row[
        "quality_score_z"
    ]


    if (
        market >= 0.40
        and
        quality >= 0.40
    ):

        return "Positive confirmation"


    if (
        market <= -0.40
        and
        quality <= -0.40
    ):

        return "Negative confirmation"


    if (
        market > 0
        and
        quality < 0
    ):

        return "Market positive / quality weak"


    if (
        quality > 0
        and
        market < 0
    ):

        return "Quality positive / market weak"


    if (
        market >= 0.40
        and
        quality >= -0.40
    ):

        return "Market-led positive"


    if (
        quality >= 0.40
        and
        market >= -0.40
    ):

        return "Quality-led positive"


    return "Mixed / neutral"


STOCK_SELECTION_BASE[
    "market_quality_alignment"
] = (

    STOCK_SELECTION_BASE

    .apply(

        classify_stock_signal_alignment,

        axis=1,

    )

)


# ============================================================
# 20. HARD MARKET / QUALITY CONFLICT
# ============================================================

STOCK_SELECTION_BASE[
    "hard_stock_conflict"
] = (

    (
        STOCK_SELECTION_BASE[
            "market_factor_score_z"
        ]

        *

        STOCK_SELECTION_BASE[
            "quality_score_z"
        ]

        <
        0
    )

    &

    (
        STOCK_SELECTION_BASE[
            "market_factor_score_z"
        ]
        .abs()

        >=
        HARD_STOCK_CONFLICT_THRESHOLD
    )

    &

    (
        STOCK_SELECTION_BASE[
            "quality_score_z"
        ]
        .abs()

        >=
        HARD_STOCK_CONFLICT_THRESHOLD
    )

)


STOCK_SELECTION_BASE[
    "absolute_market_quality_gap"
] = (

    STOCK_SELECTION_BASE[
        "market_factor_score_z"
    ]

    -

    STOCK_SELECTION_BASE[
        "quality_score_z"
    ]

).abs()


# ============================================================
# 21. SELECTION GATES
# ============================================================

primary_gate = (

    (
        STOCK_SELECTION_BASE[
            "stock_selection_score_z"
        ]
        >=
        PRIMARY_SELECTION_Z
    )

    &

    (
        STOCK_SELECTION_BASE[
            "stock_selection_percentile"
        ]
        >=
        PRIMARY_SELECTION_PERCENTILE
    )

    &

    (
        STOCK_SELECTION_BASE[
            "stock_selection_confidence"
        ]
        >=
        MIN_PRIMARY_CONFIDENCE
    )

    &

    (
        ~
        STOCK_SELECTION_BASE[
            "hard_stock_conflict"
        ]
    )

)


secondary_gate = (

    (
        STOCK_SELECTION_BASE[
            "stock_selection_score_z"
        ]
        >=
        SECONDARY_SELECTION_Z
    )

    &

    (
        STOCK_SELECTION_BASE[
            "stock_selection_percentile"
        ]
        >=
        SECONDARY_SELECTION_PERCENTILE
    )

    &

    (
        STOCK_SELECTION_BASE[
            "stock_selection_confidence"
        ]
        >=
        MIN_SECONDARY_CONFIDENCE
    )

    &

    (
        ~
        STOCK_SELECTION_BASE[
            "hard_stock_conflict"
        ]
    )

)


negative_gate = (

    (
        STOCK_SELECTION_BASE[
            "stock_selection_score_z"
        ]
        <=
        NEGATIVE_SELECTION_Z
    )

    &

    (
        STOCK_SELECTION_BASE[
            "stock_selection_percentile"
        ]
        <=
        NEGATIVE_SELECTION_PERCENTILE
    )

)


# ============================================================
# 22. SELECTION STATUS
# ============================================================

def classify_stock_selection_status(
    row
):

    index = row.name


    if row[
        "hard_stock_conflict"
    ]:

        return "CONFLICT WATCHLIST"


    if primary_gate.loc[
        index
    ]:

        if (
            row[
                "stock_research_scope"
            ]
            ==
            "CORE_LONG"
        ):

            return "PRIMARY VALUATION CANDIDATE"


        if (
            row[
                "stock_research_scope"
            ]
            ==
            "TACTICAL_LONG"
        ):

            return "TACTICAL VALUATION CANDIDATE"


    if secondary_gate.loc[
        index
    ]:

        return "SECONDARY RESEARCH CANDIDATE"


    if negative_gate.loc[
        index
    ]:

        return "LOW PRIORITY / EXCLUDE"


    return "WATCHLIST"


STOCK_SELECTION_BASE[
    "stock_selection_status"
] = (

    STOCK_SELECTION_BASE

    .apply(

        classify_stock_selection_status,

        axis=1,

    )

)


# ============================================================
# 23. VALUATION CANDIDATE FLAG
# ============================================================

VALUATION_CANDIDATE_STATUSES = {

    "PRIMARY VALUATION CANDIDATE",
    "TACTICAL VALUATION CANDIDATE",

}


STOCK_SELECTION_BASE[
    "valuation_candidate"
] = (

    STOCK_SELECTION_BASE[
        "stock_selection_status"
    ]

    .isin(
        VALUATION_CANDIDATE_STATUSES
    )

)


# ============================================================
# 24. CORE PORTFOLIO RESEARCH FLAG
# ============================================================

STOCK_SELECTION_BASE[
    "core_portfolio_research_candidate"
] = (

    (
        STOCK_SELECTION_BASE[
            "stock_selection_status"
        ]
        ==
        "PRIMARY VALUATION CANDIDATE"
    )

    &

    STOCK_SELECTION_BASE[
        "portfolio_long_allowed"
    ]

)


# ============================================================
# 25. FINAL SORT
# ============================================================

STOCK_SELECTION_SIGNAL = (

    STOCK_SELECTION_BASE

    .sort_values(

        [
            "sector_rank",
            "stock_selection_rank_within_sector",
        ]

    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 26. VALUATION CANDIDATES
# ============================================================

STRICT_PRIMARY_VALUATION_CANDIDATES = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "valuation_candidate"
        ]

    ]

    .copy()

    .reset_index(
        drop=True
    )

)

# ============================================================
# 26B. DYNAMIC DEEP-VALUATION RESEARCH POOL
# ============================================================
# Valuation is research, not yet a buy decision.  We therefore value a broader
# 30-60 name pool rather than only names already passing the strongest E7 gate.
# MOS remains downstream in F/G and is NOT weakened here.
_FUNNEL_CFG = CONFIG.get("universe", {}).get("research_funnel", {}) if "CONFIG" in globals() else {}
E7_DEEP_VALUATION_TARGET_MIN = int(_FUNNEL_CFG.get("deep_valuation_target_min", 30))
E7_DEEP_VALUATION_MAX_TOTAL = int(_FUNNEL_CFG.get("deep_valuation_max_total", 60))
E7_DEEP_VALUATION_CORE_CAP = int(_FUNNEL_CFG.get("max_per_core_sector", 20))
E7_DEEP_VALUATION_TACTICAL_CAP = int(_FUNNEL_CFG.get("max_per_tactical_sector", 15))
E7_DEEP_VALUATION_MIN_CONFIDENCE = float(_FUNNEL_CFG.get("min_selection_confidence", 0.60))
E7_DEEP_VALUATION_MIN_MARKET_CAP = float(_FUNNEL_CFG.get("min_market_cap_usd", 5_000_000_000))
E7_SOXX_SPECIALIST_FLOOR = int(_FUNNEL_CFG.get("soxx_min_deep_names_when_xlk_active", 8))

_deep_base = STOCK_SELECTION_SIGNAL.copy()
_deep_base["market_cap"] = pd.to_numeric(_deep_base["market_cap"], errors="coerce")
_deep_base = _deep_base[
    _deep_base["stock_research_scope"].isin(["CORE_LONG", "TACTICAL_LONG"])
    & (~_deep_base["hard_stock_conflict"].fillna(False).astype(bool))
    & (_deep_base["stock_selection_confidence"] >= E7_DEEP_VALUATION_MIN_CONFIDENCE)
    & (_deep_base["market_cap"] >= E7_DEEP_VALUATION_MIN_MARKET_CAP)
].copy()
_deep_base["deep_sector_cap"] = np.where(
    _deep_base["stock_research_scope"].eq("CORE_LONG"),
    E7_DEEP_VALUATION_CORE_CAP,
    E7_DEEP_VALUATION_TACTICAL_CAP,
)
_deep_base = _deep_base.sort_values(
    ["sector_rank", "stock_selection_score_z", "stock_selection_confidence"],
    ascending=[True, False, False],
)
if not _deep_base.empty:
    _deep_base["deep_rank_within_sector"] = _deep_base.groupby("sector_ticker").cumcount() + 1
    _deep_sector_limited = _deep_base[
        _deep_base["deep_rank_within_sector"] <= _deep_base["deep_sector_cap"]
    ].copy().reset_index(drop=True)
else:
    _deep_sector_limited = _deep_base.copy()

# Reserve specialist semiconductor research breadth whenever XLK is an active
# long-research sector. This affects research coverage only, never portfolio eligibility.
_xlk_active = "XLK" in set(_deep_base["sector_ticker"].astype(str))
if _xlk_active and E7_SOXX_SPECIALIST_FLOOR > 0:
    _soxx_reserved = (
        _deep_base[_deep_base["member_soxx"].fillna(False).astype(bool)]
        .sort_values(["stock_selection_score_z", "stock_selection_confidence"], ascending=False)
        .head(E7_SOXX_SPECIALIST_FLOOR)
    )
else:
    _soxx_reserved = _deep_base.iloc[0:0].copy()

_reserved_tickers = set(_soxx_reserved["ticker"].astype(str))
_remainder = _deep_sector_limited[~_deep_sector_limited["ticker"].astype(str).isin(_reserved_tickers)].copy()
_remainder["strict_gate_priority"] = _remainder["valuation_candidate"].fillna(False).astype(int)
_remainder = _remainder.sort_values(
    ["strict_gate_priority", "sector_rank", "stock_selection_score_z", "stock_selection_confidence"],
    ascending=[False, True, False, False],
)
_slots = max(0, E7_DEEP_VALUATION_MAX_TOTAL - len(_soxx_reserved))
DEEP_VALUATION_UNIVERSE = pd.concat([_soxx_reserved, _remainder.head(_slots)], ignore_index=True)
DEEP_VALUATION_UNIVERSE = (
    DEEP_VALUATION_UNIVERSE.drop_duplicates("ticker", keep="first")
    .sort_values(["sector_rank", "stock_selection_score_z"], ascending=[True, False])
    .reset_index(drop=True)
)
DEEP_VALUATION_UNIVERSE["deep_valuation_research_candidate"] = True
DEEP_VALUATION_UNIVERSE["strict_e7_valuation_candidate"] = DEEP_VALUATION_UNIVERSE["valuation_candidate"].fillna(False).astype(bool)

if DEEP_VALUATION_UNIVERSE.empty:
    raise RuntimeError("E7 produced no investable deep-valuation research names after breadth/data-quality filters.")
if len(DEEP_VALUATION_UNIVERSE) < E7_DEEP_VALUATION_TARGET_MIN:
    print(
        f"WARNING: deep valuation pool has {len(DEEP_VALUATION_UNIVERSE)} names, "
        f"below the research target of {E7_DEEP_VALUATION_TARGET_MIN}; no names are forced in solely to hit the target."
    )

# Backward-compatible handoff name consumed by Section F.  Semantics are now
# broader: this is the deep-valuation research pool, not a buy/entry list.
PRIMARY_VALUATION_CANDIDATES = DEEP_VALUATION_UNIVERSE.copy()


# ============================================================
# 27. CORE-LONG VALUATION CANDIDATES
# ============================================================

CORE_LONG_VALUATION_CANDIDATES = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "core_portfolio_research_candidate"
        ]

    ]

    .copy()

    .reset_index(
        drop=True
    )

)


# ============================================================
# 28. TACTICAL VALUATION CANDIDATES
# ============================================================

TACTICAL_VALUATION_CANDIDATES = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "stock_selection_status"
        ]
        ==
        "TACTICAL VALUATION CANDIDATE"

    ]

    .copy()

    .reset_index(
        drop=True
    )

)


# ============================================================
# 29. SECONDARY CANDIDATES
# ============================================================

SECONDARY_STOCK_CANDIDATES = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "stock_selection_status"
        ]
        ==
        "SECONDARY RESEARCH CANDIDATE"

    ]

    .copy()

    .reset_index(
        drop=True
    )

)


# ============================================================
# 30. CONFLICT WATCHLIST
# ============================================================

STOCK_CONFLICT_WATCHLIST = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "hard_stock_conflict"
        ]

    ]

    .copy()

    .reset_index(
        drop=True
    )

)


# ============================================================
# 31. TOP FIVE BY SECTOR
# ============================================================

E7_TOP_STOCKS_BY_SECTOR = (

    STOCK_SELECTION_SIGNAL

    .groupby(
        "sector_ticker",
        group_keys=False,
    )

    .head(5)

    .reset_index(
        drop=True
    )

)


# ============================================================
# 32. SECTOR SELECTION SUMMARY
# ============================================================

E7_SECTOR_SELECTION_SUMMARY = (

    STOCK_SELECTION_SIGNAL

    .groupby(
        [
            "sector_rank",
            "sector_ticker",
            "sector_name",
            "stock_research_scope",
        ],
        as_index=False,
    )

    .agg(

        company_count=(
            "ticker",
            "count"
        ),

        valuation_candidates=(
            "valuation_candidate",
            "sum"
        ),

        core_research_candidates=(
            "core_portfolio_research_candidate",
            "sum"
        ),

        mean_market_weight=(
            "market_effective_weight",
            "mean"
        ),

        mean_quality_weight=(
            "quality_effective_weight",
            "mean"
        ),

        mean_selection_confidence=(
            "stock_selection_confidence",
            "mean"
        ),

        hard_conflicts=(
            "hard_stock_conflict",
            "sum"
        ),

    )

    .sort_values(
        "sector_rank"
    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 33. MODEL INTEGRITY CHECKS
# ============================================================

company_count = len(
    STOCK_SELECTION_SIGNAL
)


expected_company_count = len(
    STOCK_FUNDAMENTAL_QUALITY
)


unique_company_count = (

    STOCK_SELECTION_SIGNAL[
        "ticker"
    ]
    .nunique()

)


finite_selection_scores = int(

    safe_isfinite(

        STOCK_SELECTION_SIGNAL[
            "stock_selection_score_z"
        ]

    ).sum()

)


dynamic_weights_valid = bool(

    np.allclose(

        STOCK_SELECTION_SIGNAL[
            "market_effective_weight"
        ]

        +

        STOCK_SELECTION_SIGNAL[
            "quality_effective_weight"
        ],

        1.0,

        atol=1e-12,

    )

)


confidence_valid = bool(

    STOCK_SELECTION_SIGNAL[
        "stock_selection_confidence"
    ]

    .between(
        0.0,
        1.0,
        inclusive="both",
    )

    .all()

)


# ============================================================
# 34. STATUS CONSISTENCY
# ============================================================

ALLOWED_E7_STATUSES = {

    "PRIMARY VALUATION CANDIDATE",
    "TACTICAL VALUATION CANDIDATE",
    "SECONDARY RESEARCH CANDIDATE",
    "CONFLICT WATCHLIST",
    "LOW PRIORITY / EXCLUDE",
    "WATCHLIST",

}


unknown_statuses = (

    set(

        STOCK_SELECTION_SIGNAL[
            "stock_selection_status"
        ]

    )

    -
    ALLOWED_E7_STATUSES

)


# ============================================================
# 35. CORE CANDIDATE CONSISTENCY
# ============================================================

invalid_core_candidates = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "core_portfolio_research_candidate"
        ]

        &

        (
            STOCK_SELECTION_SIGNAL[
                "stock_research_scope"
            ]
            !=
            "CORE_LONG"
        )

    ]

)


# ============================================================
# 36. CONFLICT CONSISTENCY
# ============================================================

invalid_conflict_candidates = (

    STOCK_SELECTION_SIGNAL[

        STOCK_SELECTION_SIGNAL[
            "hard_stock_conflict"
        ]

        &

        STOCK_SELECTION_SIGNAL[
            "valuation_candidate"
        ]

    ]

)


# ============================================================
# 37. HISTORICAL GOVERNANCE CONSISTENCY
# ============================================================

historical_backtest_blocked = bool(

    (
        STOCK_SELECTION_SIGNAL[
            "historical_backtest_eligible"
        ]

        .fillna(False)

        ==
        False
    )

    .all()

)


# ============================================================
# 38. E7 HEALTH CHECK ENGINE
# ============================================================

e7_checks = []


def add_e7_check(
    check,
    passed,
    detail,
):

    e7_checks.append({

        "check":
            check,

        "passed":
            bool(passed),

        "detail":
            str(detail),

    })


add_e7_check(

    "E6 active company universe preserved",

    company_count
    ==
    expected_company_count,

    (
        f"E7={company_count}, "
        f"E6={expected_company_count}"
    ),

)


add_e7_check(

    "Company tickers unique",

    unique_company_count
    ==
    company_count,

    (
        f"rows={company_count}, "
        f"unique={unique_company_count}"
    ),

)


add_e7_check(

    "All combined selection scores finite",

    finite_selection_scores
    ==
    company_count,

    (
        f"finite="
        f"{finite_selection_scores}/"
        f"{company_count}"
    ),

)


add_e7_check(

    "Dynamic market/quality weights sum to 1",

    dynamic_weights_valid,

    (
        "mean market weight="
        f"{STOCK_SELECTION_SIGNAL['market_effective_weight'].mean():.3f}, "
        "mean quality weight="
        f"{STOCK_SELECTION_SIGNAL['quality_effective_weight'].mean():.3f}"
    ),

)


add_e7_check(

    "Selection confidence bounded [0,1]",

    confidence_valid,

    (
        "min="
        f"{STOCK_SELECTION_SIGNAL['stock_selection_confidence'].min():.3f}, "
        "max="
        f"{STOCK_SELECTION_SIGNAL['stock_selection_confidence'].max():.3f}"
    ),

)


add_e7_check(

    "Selection statuses valid",

    len(
        unknown_statuses
    )
    ==
    0,

    (
        f"unknown="
        f"{sorted(unknown_statuses)}"
    ),

)


add_e7_check(

    "Core research candidates belong to CORE_LONG sectors",

    invalid_core_candidates.empty,

    (
        f"invalid="
        f"{len(invalid_core_candidates)}"
    ),

)


add_e7_check(

    "Hard-conflict stocks excluded from valuation candidates",

    invalid_conflict_candidates.empty,

    (
        f"invalid="
        f"{len(invalid_conflict_candidates)}"
    ),

)


add_e7_check(

    "Historical fundamental backtest remains blocked",

    historical_backtest_blocked,

    "Combined company signal remains LIVE_ONLY",

)


E7_HEALTH = pd.DataFrame(
    e7_checks
)


E7_HEALTH[
    "status"
] = np.where(

    E7_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


E7_PASSED = bool(

    E7_HEALTH[
        "passed"
    ]

    .all()

)


# ============================================================
# 39. E7 SUMMARY
# ============================================================

E7_SUMMARY = pd.DataFrame([{

    "selection_model_version":
        STOCK_SELECTION_MODEL_VERSION,

    "companies":
        company_count,

    "sectors":
        STOCK_SELECTION_SIGNAL[
            "sector_ticker"
        ]
        .nunique(),

    "valuation_candidates":
        len(
            PRIMARY_VALUATION_CANDIDATES
        ),

    "core_long_valuation_candidates":
        len(
            CORE_LONG_VALUATION_CANDIDATES
        ),

    "tactical_valuation_candidates":
        len(
            TACTICAL_VALUATION_CANDIDATES
        ),

    "secondary_candidates":
        len(
            SECONDARY_STOCK_CANDIDATES
        ),

    "hard_conflict_stocks":
        len(
            STOCK_CONFLICT_WATCHLIST
        ),

    "mean_market_effective_weight":
        float(

            STOCK_SELECTION_SIGNAL[
                "market_effective_weight"
            ]
            .mean()

        ),

    "mean_quality_effective_weight":
        float(

            STOCK_SELECTION_SIGNAL[
                "quality_effective_weight"
            ]
            .mean()

        ),

    "mean_selection_confidence":
        float(

            STOCK_SELECTION_SIGNAL[
                "stock_selection_confidence"
            ]
            .mean()

        ),

    "market_data_as_of":
        pd.Timestamp(
            MARKET_AS_OF_DATE
        ),

    "fundamental_snapshot_timestamp_utc":
        FUNDAMENTAL_SNAPSHOT_TIMESTAMP_UTC,

    "historical_backtest_eligible":
        False,

    "e7_passed":
        E7_PASSED,

}])


# ============================================================
# 40. SAVE OUTPUTS
# ============================================================

STOCK_SELECTION_SIGNAL.to_parquet(

    STOCK_MODEL_DIR
    /
    "live_combined_stock_selection.parquet",

    index=False,

)


PRIMARY_VALUATION_CANDIDATES.to_parquet(

    STOCK_MODEL_DIR
    /
    "primary_valuation_candidates.parquet",

    index=False,

)


CORE_LONG_VALUATION_CANDIDATES.to_parquet(

    STOCK_MODEL_DIR
    /
    "core_long_valuation_candidates.parquet",

    index=False,

)


TACTICAL_VALUATION_CANDIDATES.to_parquet(

    STOCK_MODEL_DIR
    /
    "tactical_valuation_candidates.parquet",

    index=False,

)


SECONDARY_STOCK_CANDIDATES.to_parquet(

    STOCK_MODEL_DIR
    /
    "secondary_stock_candidates.parquet",

    index=False,

)


STOCK_CONFLICT_WATCHLIST.to_parquet(

    STOCK_MODEL_DIR
    /
    "stock_conflict_watchlist.parquet",

    index=False,

)


STOCK_SELECTION_SIGNAL.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e7_combined_stock_selection.csv",

    index=False,

)


E7_SECTOR_SELECTION_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e7_sector_selection_summary.csv",

    index=False,

)


E7_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e7_health.csv",

    index=False,

)


E7_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "e7_summary.csv",

    index=False,

)


# ============================================================
# 41. DISPLAY
# ============================================================

print(
    "=" * 135
)

print(
    "E7 — COMBINED COMPANY SELECTION ENGINE"
)

print(
    "=" * 135
)


print(
    f"Selection model version:         "
    f"{STOCK_SELECTION_MODEL_VERSION}"
)


print(
    f"Companies analyzed:              "
    f"{company_count}"
)


print(
    f"Active sectors:                  "
    f"{STOCK_SELECTION_SIGNAL['sector_ticker'].nunique()}"
)


print(
    f"Valuation candidates:            "
    f"{len(PRIMARY_VALUATION_CANDIDATES)}"
)


print(
    f"  Core-long candidates:          "
    f"{len(CORE_LONG_VALUATION_CANDIDATES)}"
)


print(
    f"  Tactical candidates:           "
    f"{len(TACTICAL_VALUATION_CANDIDATES)}"
)


print(
    f"Secondary research candidates:   "
    f"{len(SECONDARY_STOCK_CANDIDATES)}"
)


print(
    f"Hard market/quality conflicts:   "
    f"{len(STOCK_CONFLICT_WATCHLIST)}"
)


print(
    f"Mean market effective weight:    "
    f"{STOCK_SELECTION_SIGNAL['market_effective_weight'].mean():.3f}"
)


print(
    f"Mean quality effective weight:   "
    f"{STOCK_SELECTION_SIGNAL['quality_effective_weight'].mean():.3f}"
)


print(
    f"Mean selection confidence:       "
    f"{STOCK_SELECTION_SIGNAL['stock_selection_confidence'].mean():.3f}"
)


# ============================================================
# 42. SECTOR SUMMARY
# ============================================================

print(
    "\nSector selection summary:"
)


display(
    E7_SECTOR_SELECTION_SUMMARY
)


# ============================================================
# 43. TOP FIVE PER SECTOR
# ============================================================

print(
    "\nTop 5 combined company signals within each sector:"
)


display(

    E7_TOP_STOCKS_BY_SECTOR[
        [
            "sector_ticker",
            "sector_name",

            "stock_selection_rank_within_sector",

            "ticker",
            "company_name",

            "market_factor_score_z",
            "quality_score_z",

            "market_effective_weight",
            "quality_effective_weight",

            "combined_stock_signal_raw",

            "stock_selection_confidence",
            "stock_selection_score_z",
            "stock_selection_percentile",

            "market_quality_alignment",
            "hard_stock_conflict",

            "stock_selection_status",
        ]
    ]

)


# ============================================================
# 44. VALUATION CANDIDATES
# ============================================================

print(
    "\nPrimary / tactical valuation candidates:"
)


display(

    PRIMARY_VALUATION_CANDIDATES[
        [
            "sector_ticker",
            "sector_name",

            "ticker",
            "company_name",

            "stock_research_scope",

            "stock_selection_rank_within_sector",

            "market_factor_score_z",
            "quality_score_z",

            "stock_selection_score_z",
            "stock_selection_percentile",

            "stock_selection_confidence",

            "market_quality_alignment",

            "stock_selection_status",
        ]
    ]

)


# ============================================================
# 45. CONFLICT WATCHLIST
# ============================================================

print(
    "\nHard market / quality conflicts:"
)


if STOCK_CONFLICT_WATCHLIST.empty:

    print(
        "None."
    )


else:

    display(

        STOCK_CONFLICT_WATCHLIST[
            [
                "sector_ticker",
                "ticker",
                "company_name",

                "market_factor_score_z",
                "quality_score_z",

                "absolute_market_quality_gap",

                "market_quality_alignment",
                "stock_selection_status",
            ]
        ]

    )


# ============================================================
# 46. HEALTH
# ============================================================

print(
    "\nE7 health:"
)


display(

    E7_HEALTH[
        [
            "status",
            "check",
            "detail",
        ]
    ]

)


print(
    "\nE7 summary:"
)


display(
    E7_SUMMARY
)


# ============================================================
# 47. PRODUCTION GATE
# ============================================================

if not E7_PASSED:

    failed_e7_checks = (

        E7_HEALTH.loc[

            ~
            E7_HEALTH[
                "passed"
            ],

            [
                "check",
                "detail",
            ],

        ]

    )


    display(
        failed_e7_checks
    )


    raise RuntimeError(

        "E7 PRODUCTION GATE FAILED. "
        "Do not proceed to valuation."

    )


print(
    "\n"
    + "=" * 135
)


print(
    "✓ E7 COMPLETE — integrated company-selection signal operational."
)


print(
    "✓ Market and quality weights are company-specific and confidence-driven."
)


print(
    "✓ Company rankings remain sector-relative."
)


print(
    "✓ Hard market/fundamental conflicts are quarantined."
)


print(
    "✓ Core-long and tactical candidates remain separated."
)


print(
    "✓ Historical backtest governance propagated from E6."
)


print(
    "✓ No valuation information has contaminated stock selection."
)


print(
    "✓ Ready for valuation layer."
)


print(
    "=" * 135
)
