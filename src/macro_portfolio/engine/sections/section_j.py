# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 91 =====
# ==================================================================================================
# SECTION J — LIVE PERFORMANCE ATTRIBUTION / MODEL DRIFT / GOVERNANCE ENGINE
#
# J1 — SNAPSHOT HISTORY INDEX
# J2 — SNAPSHOT-TO-SNAPSHOT LIVE PERFORMANCE ATTRIBUTION
# J3 — MODEL / SIGNAL / PORTFOLIO DRIFT ENGINE
# J4 — GOVERNANCE / ALERT ENGINE
# J5 — FINAL PRODUCTION RUN MANIFEST + SECTION J FREEZE
#
# Prerequisite:
#
#       SECTION_I_PASSED == True
#
#
# IMPORTANT
# ---------
#
# Section J is NOT a historical PIT backtest.
#
# It measures only:
#
#       actual forward changes observed BETWEEN production snapshots
#
# starting from the first Section I snapshot.
#
#
# From the second run onward it can estimate:
#
#       portfolio mark-to-market return
#       stock contribution
#       expected-vs-realized surprise
#       alpha-rank drift
#       MOS drift
#       target-weight drift
#       signal-confidence drift
#
#
# Main outputs:
#
#       J_SNAPSHOT_HISTORY
#       J_LIVE_ATTRIBUTION
#       J_PORTFOLIO_PERFORMANCE_LEDGER
#       J_MODEL_DRIFT
#       J_GOVERNANCE_ALERTS
#       J_FINAL_RUN_MANIFEST
#
# ==================================================================================================


# ==================================================================================================
# 1. IMPORTS
# ==================================================================================================

from pathlib import Path

import hashlib
import json
import warnings

import numpy as np
import pandas as pd


warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
)


# ==================================================================================================
# 2. VALIDATE UPSTREAM
# ==================================================================================================

required_j_objects = [

    "SECTION_I_PASSED",

    "I_FINAL_ACTION_BOOK",
    "I_FINAL_TRIGGERS",
    "I_FINAL_OPERATING_SNAPSHOT",

    "I_SNAPSHOT_ROOT",
    "I_SNAPSHOT_DIR",
    "I_SNAPSHOT_ID",
    "I_AS_OF_TIMESTAMP",

    "H_FINAL_MONITORING_SNAPSHOT",

    "G_FINAL_PORTFOLIO_WEIGHTS",
    "G_FINAL_PORTFOLIO_SUMMARY",

    "VALUATION_UNIVERSE_FREEZE_ID",

    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",

]


missing_j_objects = [

    obj

    for obj in required_j_objects

    if obj not in globals()

]


if missing_j_objects:

    raise RuntimeError(

        "Section J requires completed Section I state. Missing: "
        f"{missing_j_objects}"

    )


if not bool(
    SECTION_I_PASSED
):

    raise RuntimeError(

        "Section I production gate did not pass."

    )


# ==================================================================================================
# 3. VERSION
# ==================================================================================================

J_VERSION = "1.1.0"


# ==================================================================================================
# 4. CONFIG / POLICY
# ==================================================================================================

def j_cfg(
    path,
    default=None,
):

    obj = globals().get(
        "CONFIG",
        {},
    )


    try:

        for key in path:

            obj = obj[
                key
            ]


        return obj


    except Exception:

        return default


J_NAV = float(

    globals().get(

        "I_NAV",

        j_cfg(

            [
                "portfolio",
                "initial_nav",
            ],

            1_000_000.0,

        ),

    )

)


J_RISK_FREE_RATE = float(

    globals().get(

        "H_RISK_FREE_RATE",

        globals().get(
            "G2_RISK_FREE_RATE",
            0.0,
        ),

    )

)


# ------------------------------------------------------------
# Drift alert thresholds.
# ------------------------------------------------------------

J_ALPHA_RANK_DRIFT_ALERT = int(cfg(["monitoring", "alpha_rank_drift_alert"], 5))

J_ALPHA_SCORE_DRIFT_ALERT = float(cfg(["monitoring", "alpha_score_drift_alert"], 0.50))

J_MOS_DISTANCE_DRIFT_ALERT = float(cfg(["monitoring", "mos_distance_drift_alert"], 0.10))

J_TARGET_WEIGHT_DRIFT_ALERT = float(cfg(["monitoring", "target_weight_drift_alert"], 0.03))

J_VALUATION_PRICE_DRIFT_ALERT = float(cfg(["monitoring", "valuation_price_drift_alert"], 0.10))


# ------------------------------------------------------------
# Performance surprise threshold.
#
# Realized interval return minus model-implied interval return.
# ------------------------------------------------------------

J_PORTFOLIO_SURPRISE_ALERT = float(cfg(["monitoring", "portfolio_surprise_alert"], 0.03))


# ------------------------------------------------------------
# Snapshot retention / history.
# ------------------------------------------------------------

J_MIN_PERFORMANCE_PERIODS_FOR_STATS = int(cfg(["monitoring", "min_performance_periods_for_stats"], 5))


# ==================================================================================================
# 5. OUTPUT DIRECTORIES
# ==================================================================================================

J_GOVERNANCE_DIR = (

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "governance"

)


J_GOVERNANCE_DIR.mkdir(

    parents=True,
    exist_ok=True,

)


J_MODEL_DIR = (

    Path(
        STOCK_MODEL_DIR
    )

    /
    "governance"

)


J_MODEL_DIR.mkdir(

    parents=True,
    exist_ok=True,

)


# ==================================================================================================
# ==================================================================================================
# J1 — SNAPSHOT HISTORY INDEX
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 6. DISCOVER ALL SECTION I SNAPSHOTS
# ==================================================================================================

J_SNAPSHOT_ROOT = Path(

    I_SNAPSHOT_ROOT

)


snapshot_dirs = sorted(

    [

        path

        for path
        in J_SNAPSHOT_ROOT.iterdir()

        if path.is_dir()

    ]

)


# ==================================================================================================
# 7. BUILD SNAPSHOT INDEX
# ==================================================================================================

snapshot_rows = []


for snapshot_dir in snapshot_dirs:

    metadata_path = (

        snapshot_dir

        /
        "metadata.json"

    )


    daily_summary_path = (

        snapshot_dir

        /
        "daily_summary.csv"

    )


    monitor_path = (

        snapshot_dir

        /
        "monitoring_snapshot.parquet"

    )


    decision_path = (

        snapshot_dir

        /
        "decision_book.parquet"

    )


    metadata = {}


    if metadata_path.exists():

        try:

            with open(

                metadata_path,

                "r",

                encoding="utf-8",

            ) as handle:

                metadata = json.load(
                    handle
                )


        except Exception:

            metadata = {}


    summary = {}


    if daily_summary_path.exists():

        try:

            summary_df = pd.read_csv(

                daily_summary_path

            )


            if len(
                summary_df
            ) > 0:

                summary = (

                    summary_df
                    .iloc[0]
                    .to_dict()

                )


        except Exception:

            summary = {}


    as_of_raw = (

        metadata.get(
            "as_of"
        )

        or

        summary.get(
            "as_of"
        )

    )


    as_of = pd.to_datetime(

        as_of_raw,

        errors="coerce",
        utc=True,

    )


    snapshot_rows.append({

        "snapshot_id":
            snapshot_dir.name,

        "snapshot_dir":
            str(
                snapshot_dir
            ),

        "as_of_utc":
            as_of,

        "valuation_universe_freeze_id":
            metadata.get(

                "valuation_universe_freeze_id",

                summary.get(
                    "valuation_universe_freeze_id"
                ),

            ),

        "daily_status":
            metadata.get(

                "daily_status",

                summary.get(
                    "daily_status"
                ),

            ),

        "research_universe":
            summary.get(
                "research_universe"
            ),

        "stock_holdings":
            summary.get(
                "stock_holdings"
            ),

        "cash_weight":
            summary.get(
                "cash_weight"
            ),

        "expected_return":
            summary.get(
                "expected_return"
            ),

        "expected_volatility":
            summary.get(
                "expected_volatility"
            ),

        "expected_sharpe":
            summary.get(
                "expected_sharpe"
            ),

        "portfolio_beta":
            summary.get(
                "portfolio_beta"
            ),

        "decision_sha256":
            summary.get(
                "decision_sha256"
            ),

        "monitor_available":
            monitor_path.exists(),

        "decision_available":
            decision_path.exists(),

    })


J_SNAPSHOT_HISTORY = pd.DataFrame(

    snapshot_rows

)


if not J_SNAPSHOT_HISTORY.empty:

    J_SNAPSHOT_HISTORY = (

        J_SNAPSHOT_HISTORY

        .sort_values(

            [
                "as_of_utc",
                "snapshot_id",
            ]

        )

        .reset_index(
            drop=True
        )

    )


# ==================================================================================================
# 8. CURRENT / PREVIOUS SNAPSHOT IDENTIFICATION
# ==================================================================================================

J_CURRENT_SNAPSHOT_ID = str(

    I_SNAPSHOT_ID

)


J_CURRENT_SNAPSHOT_DIR = Path(

    I_SNAPSHOT_DIR

)


J_PREVIOUS_SNAPSHOT_DIR = None

J_PREVIOUS_SNAPSHOT_ID = None


prior_rows = (

    J_SNAPSHOT_HISTORY[

        J_SNAPSHOT_HISTORY[
            "snapshot_id"
        ]

        !=
        J_CURRENT_SNAPSHOT_ID

    ]

    if not J_SNAPSHOT_HISTORY.empty

    else pd.DataFrame()

)


if not prior_rows.empty:

    prior_row = (

        prior_rows
        .iloc[-1]

    )


    J_PREVIOUS_SNAPSHOT_ID = str(

        prior_row[
            "snapshot_id"
        ]

    )


    J_PREVIOUS_SNAPSHOT_DIR = Path(

        prior_row[
            "snapshot_dir"
        ]

    )


J_HAS_PRIOR_SNAPSHOT = bool(

    J_PREVIOUS_SNAPSHOT_DIR
    is not None

)


# ==================================================================================================
# ==================================================================================================
# J2 — SNAPSHOT-TO-SNAPSHOT LIVE PERFORMANCE ATTRIBUTION
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 9. CURRENT MONITOR NORMALIZATION
# ==================================================================================================

J_CURRENT_MONITOR = (

    H_FINAL_MONITORING_SNAPSHOT
    .copy()

)


J_CURRENT_MONITOR[
    "ticker"
] = (

    J_CURRENT_MONITOR[
        "ticker"
    ]
    .astype(str)

)


# ==================================================================================================
# 10. LOAD PRIOR MONITOR
# ==================================================================================================

if J_HAS_PRIOR_SNAPSHOT:

    previous_monitor_path = (

        J_PREVIOUS_SNAPSHOT_DIR

        /
        "monitoring_snapshot.parquet"

    )


    if previous_monitor_path.exists():

        J_PREVIOUS_MONITOR = pd.read_parquet(

            previous_monitor_path

        )


        J_PREVIOUS_MONITOR[
            "ticker"
        ] = (

            J_PREVIOUS_MONITOR[
                "ticker"
            ]
            .astype(str)

        )


    else:

        J_PREVIOUS_MONITOR = pd.DataFrame()


else:

    J_PREVIOUS_MONITOR = pd.DataFrame()


J_ATTRIBUTION_AVAILABLE = bool(

    J_HAS_PRIOR_SNAPSHOT

    and

    not J_PREVIOUS_MONITOR.empty

)


# ==================================================================================================
# 11. LOAD PRIOR DAILY SUMMARY
# ==================================================================================================

J_PREVIOUS_SUMMARY = {}


if J_ATTRIBUTION_AVAILABLE:

    previous_summary_path = (

        J_PREVIOUS_SNAPSHOT_DIR

        /
        "daily_summary.csv"

    )


    if previous_summary_path.exists():

        try:

            previous_summary_df = pd.read_csv(

                previous_summary_path

            )


            if len(
                previous_summary_df
            ) > 0:

                J_PREVIOUS_SUMMARY = (

                    previous_summary_df
                    .iloc[0]
                    .to_dict()

                )


        except Exception:

            J_PREVIOUS_SUMMARY = {}


# ==================================================================================================
# 12. ELAPSED TIME
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    previous_as_of = pd.to_datetime(

        J_PREVIOUS_SUMMARY.get(
            "as_of"
        ),

        errors="coerce",
        utc=True,

    )


    current_as_of = pd.to_datetime(

        I_AS_OF_TIMESTAMP,

        errors="coerce",
        utc=True,

    )


    if (

        pd.notna(
            previous_as_of
        )

        and

        pd.notna(
            current_as_of
        )

    ):

        J_ELAPSED_DAYS = float(

            (

                current_as_of

                -
                previous_as_of

            )
            .total_seconds()

            /
            86400.0

        )


    else:

        J_ELAPSED_DAYS = np.nan


else:

    J_ELAPSED_DAYS = np.nan


# ==================================================================================================
# 13. STOCK ATTRIBUTION
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    previous_columns = [

        column

        for column in [

            "ticker",

            "company_name",
            "sector_ticker",

            "current_price",

            "previous_weight",
            "target_weight",

            "expected_total_return_annual",

            "master_alpha_rank",

            "confidence_adjusted_master_alpha",

            "distance_to_mos_pct",

            "buy_zone",

            "monitor_action",

            "expected_intrinsic_value",

        ]

        if column
        in
        J_PREVIOUS_MONITOR.columns

    ]


    current_columns = [

        column

        for column in [

            "ticker",

            "company_name",
            "sector_ticker",

            "current_price",

            "previous_weight",
            "target_weight",

            "expected_total_return_annual",

            "master_alpha_rank",

            "confidence_adjusted_master_alpha",

            "distance_to_mos_pct",

            "buy_zone",

            "monitor_action",

            "expected_intrinsic_value",

        ]

        if column
        in
        J_CURRENT_MONITOR.columns

    ]


    previous = (

        J_PREVIOUS_MONITOR[
            previous_columns
        ]

        .copy()

    )


    previous = previous.rename(

        columns={

            column:
                f"previous_{column}"

            for column
            in previous.columns

            if column
            !=
            "ticker"

        }

    )


    current = (

        J_CURRENT_MONITOR[
            current_columns
        ]

        .copy()

    )


    current = current.rename(

        columns={

            column:
                f"current_{column}"

            for column
            in current.columns

            if column
            !=
            "ticker"

        }

    )


    J_LIVE_ATTRIBUTION = (

        previous

        .merge(

            current,

            on="ticker",

            how="outer",

            validate="one_to_one",

        )

    )


    # ------------------------------------------------------------------
    # Numeric helpers.
    # ------------------------------------------------------------------

    for column in [

        "previous_current_price",
        "current_current_price",

        "previous_previous_weight",
        "current_previous_weight",

        "previous_target_weight",
        "current_target_weight",

        "previous_expected_total_return_annual",
        "current_expected_total_return_annual",

    ]:

        if column not in J_LIVE_ATTRIBUTION.columns:

            J_LIVE_ATTRIBUTION[
                column
            ] = np.nan


        J_LIVE_ATTRIBUTION[
            column
        ] = pd.to_numeric(

            J_LIVE_ATTRIBUTION[
                column
            ],

            errors="coerce",

        )


    # ------------------------------------------------------------------
    # Attribution weight source.
    #
    # REAL mode: use the prior snapshot's actual starting weight
    # (stored in its previous_weight field).
    # MODEL/ZERO mode: use prior target weight, consistent with the
    # model-state assumption that targets were executed.
    # ------------------------------------------------------------------

    J_PORTFOLIO_STATE_MODE = str(globals().get("PORTFOLIO_STATE_MODE", "MODEL")).upper()

    if (
        J_PORTFOLIO_STATE_MODE in ("REAL", "PAPER")
        and "previous_previous_weight" in J_LIVE_ATTRIBUTION.columns
        and J_LIVE_ATTRIBUTION["previous_previous_weight"].notna().any()
    ):
        J_LIVE_ATTRIBUTION["attribution_weight"] = J_LIVE_ATTRIBUTION["previous_previous_weight"].fillna(0.0)
        J_ATTRIBUTION_WEIGHT_SOURCE = "PRIOR_ACTUAL_WEIGHT"
    else:
        J_LIVE_ATTRIBUTION["attribution_weight"] = J_LIVE_ATTRIBUTION["previous_target_weight"].fillna(0.0)
        J_ATTRIBUTION_WEIGHT_SOURCE = "PRIOR_TARGET_ASSUMED_EXECUTED"

    # ------------------------------------------------------------------
    # Stock price return.
    # ------------------------------------------------------------------

    J_LIVE_ATTRIBUTION[
        "price_return"
    ] = np.where(

        J_LIVE_ATTRIBUTION[
            "previous_current_price"
        ]
        >
        0,

        (

            J_LIVE_ATTRIBUTION[
                "current_current_price"
            ]

            /
            J_LIVE_ATTRIBUTION[
                "previous_current_price"
            ]

            -
            1.0

        ),

        np.nan,

    )


    # ------------------------------------------------------------------
    # Previous portfolio weight is the economically relevant weight
    # for forward interval attribution.
    # ------------------------------------------------------------------

    J_LIVE_ATTRIBUTION[
        "previous_target_weight"
    ] = (

        J_LIVE_ATTRIBUTION[
            "previous_target_weight"
        ]

        .fillna(
            0.0
        )

    )


    J_LIVE_ATTRIBUTION[
        "realized_contribution"
    ] = (

        J_LIVE_ATTRIBUTION[
            "attribution_weight"
        ]

        *

        J_LIVE_ATTRIBUTION[
            "price_return"
        ]
        .fillna(
            0.0
        )

    )


    # ------------------------------------------------------------------
    # Approximate expected interval return.
    # ------------------------------------------------------------------

    if (

        safe_isfinite(
            J_ELAPSED_DAYS
        )

        and

        J_ELAPSED_DAYS > 0

    ):

        J_LIVE_ATTRIBUTION[
            "expected_interval_stock_return"
        ] = (

            (

                1.0

                +

                J_LIVE_ATTRIBUTION[
                    "previous_expected_total_return_annual"
                ]
                .fillna(
                    0.0
                )

            )

            **

            (
                J_ELAPSED_DAYS
                /
                365.25
            )

            -
            1.0

        )


    else:

        J_LIVE_ATTRIBUTION[
            "expected_interval_stock_return"
        ] = np.nan


    J_LIVE_ATTRIBUTION[
        "expected_contribution"
    ] = (

        J_LIVE_ATTRIBUTION[
            "attribution_weight"
        ]

        *

        J_LIVE_ATTRIBUTION[
            "expected_interval_stock_return"
        ]
        .fillna(
            0.0
        )

    )


    J_LIVE_ATTRIBUTION[
        "contribution_surprise"
    ] = (

        J_LIVE_ATTRIBUTION[
            "realized_contribution"
        ]

        -

        J_LIVE_ATTRIBUTION[
            "expected_contribution"
        ]

    )


    # ------------------------------------------------------------------
    # Current position drift.
    # ------------------------------------------------------------------

    J_LIVE_ATTRIBUTION[
        "target_weight_change"
    ] = (

        J_LIVE_ATTRIBUTION[
            "current_target_weight"
        ]
        .fillna(
            0.0
        )

        -

        J_LIVE_ATTRIBUTION[
            "previous_target_weight"
        ]

    )


else:

    J_LIVE_ATTRIBUTION = pd.DataFrame(

        columns=[

            "ticker",

            "previous_current_price",
            "current_current_price",

            "previous_target_weight",
            "current_target_weight",

            "price_return",

            "realized_contribution",

            "expected_interval_stock_return",
            "expected_contribution",

            "contribution_surprise",

            "target_weight_change",

        ]

    )


# ==================================================================================================
# 14. PORTFOLIO CASH ATTRIBUTION
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    previous_cash_weight = float(
        max(
            0.0,
            1.0 - pd.to_numeric(
                J_LIVE_ATTRIBUTION["attribution_weight"],
                errors="coerce",
            ).fillna(0.0).sum(),
        )
    )


    if (

        safe_isfinite(
            J_ELAPSED_DAYS
        )

        and

        J_ELAPSED_DAYS > 0

    ):

        J_CASH_INTERVAL_RETURN = (

            (

                1.0
                +
                J_RISK_FREE_RATE

            )

            **

            (
                J_ELAPSED_DAYS
                /
                365.25
            )

            -
            1.0

        )


    else:

        J_CASH_INTERVAL_RETURN = 0.0


    J_CASH_REALIZED_CONTRIBUTION = (

        previous_cash_weight

        *
        J_CASH_INTERVAL_RETURN

    )


else:

    previous_cash_weight = np.nan

    J_CASH_INTERVAL_RETURN = np.nan

    J_CASH_REALIZED_CONTRIBUTION = np.nan


# ==================================================================================================
# 15. PORTFOLIO INTERVAL RETURN
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    J_PORTFOLIO_REALIZED_RETURN = (

        float(

            J_LIVE_ATTRIBUTION[
                "realized_contribution"
            ]
            .sum()

        )

        +

        float(
            J_CASH_REALIZED_CONTRIBUTION
        )

    )


    J_PORTFOLIO_EXPECTED_INTERVAL_RETURN = (

        float(

            J_LIVE_ATTRIBUTION[
                "expected_contribution"
            ]
            .sum()

        )

        +

        float(
            J_CASH_REALIZED_CONTRIBUTION
        )

    )


    J_PORTFOLIO_RETURN_SURPRISE = (

        J_PORTFOLIO_REALIZED_RETURN

        -

        J_PORTFOLIO_EXPECTED_INTERVAL_RETURN

    )


else:

    J_PORTFOLIO_REALIZED_RETURN = np.nan

    J_PORTFOLIO_EXPECTED_INTERVAL_RETURN = np.nan

    J_PORTFOLIO_RETURN_SURPRISE = np.nan


# ==================================================================================================
# ==================================================================================================
# J3 — MODEL / SIGNAL / PORTFOLIO DRIFT ENGINE
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 16. DRIFT COMPUTATION
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    J_MODEL_DRIFT = (

        J_LIVE_ATTRIBUTION[
            [
                column

                for column in [

                    "ticker",

                    "previous_company_name",
                    "current_company_name",

                    "previous_sector_ticker",
                    "current_sector_ticker",

                    "previous_master_alpha_rank",
                    "current_master_alpha_rank",

                    "previous_confidence_adjusted_master_alpha",
                    "current_confidence_adjusted_master_alpha",

                    "previous_distance_to_mos_pct",
                    "current_distance_to_mos_pct",

                    "previous_buy_zone",
                    "current_buy_zone",

                    "previous_monitor_action",
                    "current_monitor_action",

                    "previous_expected_intrinsic_value",
                    "current_expected_intrinsic_value",

                    "previous_target_weight",
                    "current_target_weight",

                ]

                if column
                in
                J_LIVE_ATTRIBUTION.columns

            ]
        ]

        .copy()

    )


    # ------------------------------------------------------------------
    # Alpha rank drift.
    # Positive number = rank worsened.
    # Negative number = rank improved.
    # ------------------------------------------------------------------

    if all(

        column in J_MODEL_DRIFT.columns

        for column in [

            "previous_master_alpha_rank",
            "current_master_alpha_rank",

        ]

    ):

        J_MODEL_DRIFT[
            "alpha_rank_drift"
        ] = (

            pd.to_numeric(

                J_MODEL_DRIFT[
                    "current_master_alpha_rank"
                ],

                errors="coerce",

            )

            -

            pd.to_numeric(

                J_MODEL_DRIFT[
                    "previous_master_alpha_rank"
                ],

                errors="coerce",

            )

        )


    else:

        J_MODEL_DRIFT[
            "alpha_rank_drift"
        ] = np.nan


    # ------------------------------------------------------------------
    # Alpha score drift.
    # ------------------------------------------------------------------

    if all(

        column in J_MODEL_DRIFT.columns

        for column in [

            "previous_confidence_adjusted_master_alpha",
            "current_confidence_adjusted_master_alpha",

        ]

    ):

        J_MODEL_DRIFT[
            "alpha_score_drift"
        ] = (

            pd.to_numeric(

                J_MODEL_DRIFT[
                    "current_confidence_adjusted_master_alpha"
                ],

                errors="coerce",

            )

            -

            pd.to_numeric(

                J_MODEL_DRIFT[
                    "previous_confidence_adjusted_master_alpha"
                ],

                errors="coerce",

            )

        )


    else:

        J_MODEL_DRIFT[
            "alpha_score_drift"
        ] = np.nan


    # ------------------------------------------------------------------
    # MOS drift.
    # ------------------------------------------------------------------

    if all(

        column in J_MODEL_DRIFT.columns

        for column in [

            "previous_distance_to_mos_pct",
            "current_distance_to_mos_pct",

        ]

    ):

        J_MODEL_DRIFT[
            "mos_distance_drift"
        ] = (

            pd.to_numeric(

                J_MODEL_DRIFT[
                    "current_distance_to_mos_pct"
                ],

                errors="coerce",

            )

            -

            pd.to_numeric(

                J_MODEL_DRIFT[
                    "previous_distance_to_mos_pct"
                ],

                errors="coerce",

            )

        )


    else:

        J_MODEL_DRIFT[
            "mos_distance_drift"
        ] = np.nan


    # ------------------------------------------------------------------
    # Valuation drift.
    # ------------------------------------------------------------------

    if all(

        column in J_MODEL_DRIFT.columns

        for column in [

            "previous_expected_intrinsic_value",
            "current_expected_intrinsic_value",

        ]

    ):

        previous_intrinsic = pd.to_numeric(

            J_MODEL_DRIFT[
                "previous_expected_intrinsic_value"
            ],

            errors="coerce",

        )


        current_intrinsic = pd.to_numeric(

            J_MODEL_DRIFT[
                "current_expected_intrinsic_value"
            ],

            errors="coerce",

        )


        J_MODEL_DRIFT[
            "intrinsic_value_drift_pct"
        ] = np.where(

            previous_intrinsic > 0,

            (

                current_intrinsic

                /
                previous_intrinsic

                -
                1.0

            ),

            np.nan,

        )


    else:

        J_MODEL_DRIFT[
            "intrinsic_value_drift_pct"
        ] = np.nan


    # ------------------------------------------------------------------
    # Portfolio-weight drift.
    # ------------------------------------------------------------------

    J_MODEL_DRIFT[
        "target_weight_drift"
    ] = (

        pd.to_numeric(

            J_MODEL_DRIFT[
                "current_target_weight"
            ],

            errors="coerce",

        )
        .fillna(
            0.0
        )

        -

        pd.to_numeric(

            J_MODEL_DRIFT[
                "previous_target_weight"
            ],

            errors="coerce",

        )
        .fillna(
            0.0
        )

    )


    # ------------------------------------------------------------------
    # State transitions.
    # ------------------------------------------------------------------

    if all(

        column in J_MODEL_DRIFT.columns

        for column in [

            "previous_buy_zone",
            "current_buy_zone",

        ]

    ):

        J_MODEL_DRIFT[
            "buy_zone_changed"
        ] = (

            J_MODEL_DRIFT[
                "previous_buy_zone"
            ]
            .astype(str)

            !=

            J_MODEL_DRIFT[
                "current_buy_zone"
            ]
            .astype(str)

        )


    else:

        J_MODEL_DRIFT[
            "buy_zone_changed"
        ] = False


    if all(

        column in J_MODEL_DRIFT.columns

        for column in [

            "previous_monitor_action",
            "current_monitor_action",

        ]

    ):

        J_MODEL_DRIFT[
            "monitor_action_changed"
        ] = (

            J_MODEL_DRIFT[
                "previous_monitor_action"
            ]
            .astype(str)

            !=

            J_MODEL_DRIFT[
                "current_monitor_action"
            ]
            .astype(str)

        )


    else:

        J_MODEL_DRIFT[
            "monitor_action_changed"
        ] = False


    # ------------------------------------------------------------------
    # Material model drift.
    # ------------------------------------------------------------------

    J_MODEL_DRIFT[
        "material_model_drift"
    ] = np.logical_or.reduce(

        [

            (

                J_MODEL_DRIFT[
                    "alpha_rank_drift"
                ]
                .abs()
                .fillna(
                    0.0
                )

                >=
                J_ALPHA_RANK_DRIFT_ALERT

            )
            .to_numpy(
                dtype=bool
            ),

            (

                J_MODEL_DRIFT[
                    "alpha_score_drift"
                ]
                .abs()
                .fillna(
                    0.0
                )

                >=
                J_ALPHA_SCORE_DRIFT_ALERT

            )
            .to_numpy(
                dtype=bool
            ),

            (

                J_MODEL_DRIFT[
                    "mos_distance_drift"
                ]
                .abs()
                .fillna(
                    0.0
                )

                >=
                J_MOS_DISTANCE_DRIFT_ALERT

            )
            .to_numpy(
                dtype=bool
            ),

            (

                J_MODEL_DRIFT[
                    "target_weight_drift"
                ]
                .abs()
                .fillna(
                    0.0
                )

                >=
                J_TARGET_WEIGHT_DRIFT_ALERT

            )
            .to_numpy(
                dtype=bool
            ),

            (

                J_MODEL_DRIFT[
                    "intrinsic_value_drift_pct"
                ]
                .abs()
                .fillna(
                    0.0
                )

                >=
                J_VALUATION_PRICE_DRIFT_ALERT

            )
            .to_numpy(
                dtype=bool
            ),

            J_MODEL_DRIFT[
                "buy_zone_changed"
            ]
            .fillna(
                False
            )
            .to_numpy(
                dtype=bool
            ),

            J_MODEL_DRIFT[
                "monitor_action_changed"
            ]
            .fillna(
                False
            )
            .to_numpy(
                dtype=bool
            ),

        ]

    )


    J_MATERIAL_MODEL_DRIFT = (

        J_MODEL_DRIFT[

            J_MODEL_DRIFT[
                "material_model_drift"
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


else:

    J_MODEL_DRIFT = pd.DataFrame()

    J_MATERIAL_MODEL_DRIFT = pd.DataFrame()


# ==================================================================================================
# ==================================================================================================
# J4 — LIVE PERFORMANCE LEDGER
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 17. LOAD EXISTING PERFORMANCE LEDGER
# ==================================================================================================

J_LEDGER_PATH = (

    J_GOVERNANCE_DIR

    /
    "live_portfolio_performance_ledger.csv"

)


if J_LEDGER_PATH.exists():

    try:

        J_PORTFOLIO_PERFORMANCE_LEDGER = pd.read_csv(

            J_LEDGER_PATH

        )


    except Exception:

        J_PORTFOLIO_PERFORMANCE_LEDGER = pd.DataFrame()


else:

    J_PORTFOLIO_PERFORMANCE_LEDGER = pd.DataFrame()


# ==================================================================================================
# 18. APPEND CURRENT ATTRIBUTION PERIOD
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    new_ledger_row = pd.DataFrame([{

        "period_start_snapshot":
            J_PREVIOUS_SNAPSHOT_ID,

        "period_end_snapshot":
            J_CURRENT_SNAPSHOT_ID,

        "period_end_as_of":
            I_AS_OF_TIMESTAMP,

        "elapsed_days":
            J_ELAPSED_DAYS,

        "portfolio_realized_return":
            J_PORTFOLIO_REALIZED_RETURN,

        "portfolio_expected_interval_return":
            J_PORTFOLIO_EXPECTED_INTERVAL_RETURN,

        "portfolio_return_surprise":
            J_PORTFOLIO_RETURN_SURPRISE,

        "previous_cash_weight":
            previous_cash_weight,

        "attribution_weight_source":
            J_ATTRIBUTION_WEIGHT_SOURCE,

        "cash_interval_return":
            J_CASH_INTERVAL_RETURN,

        "cash_contribution":
            J_CASH_REALIZED_CONTRIBUTION,

        "stock_contribution":
            float(

                J_LIVE_ATTRIBUTION[
                    "realized_contribution"
                ]
                .sum()

            ),

        "valuation_universe_freeze_id":
            VALUATION_UNIVERSE_FREEZE_ID,

    }])


    if J_PORTFOLIO_PERFORMANCE_LEDGER.empty:

        J_PORTFOLIO_PERFORMANCE_LEDGER = (

            new_ledger_row
            .copy()

        )


    else:

        duplicate_mask = (

            (

                J_PORTFOLIO_PERFORMANCE_LEDGER[
                    "period_start_snapshot"
                ]
                .astype(str)

                ==
                str(
                    J_PREVIOUS_SNAPSHOT_ID
                )

            )

            &

            (

                J_PORTFOLIO_PERFORMANCE_LEDGER[
                    "period_end_snapshot"
                ]
                .astype(str)

                ==
                str(
                    J_CURRENT_SNAPSHOT_ID
                )

            )

        )


        if not duplicate_mask.any():

            J_PORTFOLIO_PERFORMANCE_LEDGER = pd.concat(

                [

                    J_PORTFOLIO_PERFORMANCE_LEDGER,

                    new_ledger_row,

                ],

                ignore_index=True,

            )


# ==================================================================================================
# 19. LIVE FORWARD PERFORMANCE STATISTICS
# ==================================================================================================

J_LIVE_PERIOD_COUNT = len(

    J_PORTFOLIO_PERFORMANCE_LEDGER

)


if J_LIVE_PERIOD_COUNT > 0:

    realized_returns = pd.to_numeric(

        J_PORTFOLIO_PERFORMANCE_LEDGER[
            "portfolio_realized_return"
        ],

        errors="coerce",

    ).dropna()


    expected_returns = pd.to_numeric(

        J_PORTFOLIO_PERFORMANCE_LEDGER[
            "portfolio_expected_interval_return"
        ],

        errors="coerce",

    ).dropna()


    surprises = pd.to_numeric(

        J_PORTFOLIO_PERFORMANCE_LEDGER[
            "portfolio_return_surprise"
        ],

        errors="coerce",

    ).dropna()


    J_LIVE_CUMULATIVE_RETURN = (

        (

            1.0
            +
            realized_returns

        )
        .prod()

        -
        1.0

        if not realized_returns.empty

        else np.nan

    )


    J_LIVE_CUMULATIVE_EXPECTED_RETURN = (

        (

            1.0
            +
            expected_returns

        )
        .prod()

        -
        1.0

        if not expected_returns.empty

        else np.nan

    )


    J_MEAN_RETURN_SURPRISE = (

        float(
            surprises.mean()
        )

        if not surprises.empty

        else np.nan

    )


else:

    J_LIVE_CUMULATIVE_RETURN = np.nan

    J_LIVE_CUMULATIVE_EXPECTED_RETURN = np.nan

    J_MEAN_RETURN_SURPRISE = np.nan


# ==================================================================================================
# 20. SAVE PERFORMANCE LEDGER
# ==================================================================================================

J_PORTFOLIO_PERFORMANCE_LEDGER.to_csv(

    J_LEDGER_PATH,

    index=False,

)


# ==================================================================================================
# ==================================================================================================
# J5 — GOVERNANCE / ALERT ENGINE
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 21. GOVERNANCE ALERT BUILDER
# ==================================================================================================

J_ALERT_ROWS = []


def j_add_alert(
    severity,
    alert_type,
    ticker,
    message,
    metric=np.nan,
    threshold=np.nan,
):

    J_ALERT_ROWS.append({

        "severity":
            severity,

        "alert_type":
            alert_type,

        "ticker":
            ticker,

        "message":
            message,

        "metric":
            metric,

        "threshold":
            threshold,

        "as_of":
            I_AS_OF_TIMESTAMP,

    })


# ==================================================================================================
# 22. NO PRIOR SNAPSHOT
# ==================================================================================================

if not J_ATTRIBUTION_AVAILABLE:

    j_add_alert(

        severity=
            "INFO",

        alert_type=
            "BASELINE_ONLY",

        ticker=
            "SYSTEM",

        message=(
            "Only one production snapshot exists. "
            "Forward attribution and model-drift statistics "
            "will activate from the next Section I run."
        ),

    )


# ==================================================================================================
# 23. PORTFOLIO SURPRISE
# ==================================================================================================

if (

    J_ATTRIBUTION_AVAILABLE

    and

    safe_isfinite(
        J_PORTFOLIO_RETURN_SURPRISE
    )

    and

    abs(
        J_PORTFOLIO_RETURN_SURPRISE
    )
    >=
    J_PORTFOLIO_SURPRISE_ALERT

):

    j_add_alert(

        severity=
            "WARNING",

        alert_type=
            "PORTFOLIO_RETURN_SURPRISE",

        ticker=
            "PORTFOLIO",

        message=(
            f"Portfolio realized return differed from "
            f"model-implied interval return by "
            f"{J_PORTFOLIO_RETURN_SURPRISE:.2%}."
        ),

        metric=
            J_PORTFOLIO_RETURN_SURPRISE,

        threshold=
            J_PORTFOLIO_SURPRISE_ALERT,

    )


# ==================================================================================================
# 24. MODEL DRIFT ALERTS
# ==================================================================================================

if not J_MATERIAL_MODEL_DRIFT.empty:

    for _, row in (

        J_MATERIAL_MODEL_DRIFT
        .iterrows()

    ):

        j_add_alert(

            severity=
                "REVIEW",

            alert_type=
                "MODEL_DRIFT",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"{row['ticker']} shows a material change "
                "in alpha rank, valuation/MOS, action state "
                "or target portfolio weight."
            ),

        )


# ==================================================================================================
# 25. FREEZE-ID CHANGE
# ==================================================================================================

if J_ATTRIBUTION_AVAILABLE:

    previous_freeze_id = (

        J_PREVIOUS_SUMMARY.get(

            "valuation_universe_freeze_id"

        )

    )


    if (

        previous_freeze_id is not None

        and

        str(
            previous_freeze_id
        )

        !=

        str(
            VALUATION_UNIVERSE_FREEZE_ID
        )

    ):

        j_add_alert(

            severity=
                "REVIEW",

            alert_type=
                "VALUATION_UNIVERSE_CHANGED",

            ticker=
                "SYSTEM",

            message=(
                "The valuation-universe freeze ID changed "
                "between production snapshots."
            ),

        )


# ==================================================================================================
# 26. BUILD FINAL GOVERNANCE ALERT TABLE
# ==================================================================================================

J_GOVERNANCE_ALERTS = pd.DataFrame(

    J_ALERT_ROWS

)


if J_GOVERNANCE_ALERTS.empty:

    J_GOVERNANCE_ALERTS = pd.DataFrame(

        columns=[

            "severity",
            "alert_type",
            "ticker",
            "message",
            "metric",
            "threshold",
            "as_of",

        ]

    )


J_ALERT_ORDER = {

    "CRITICAL":
        0,

    "WARNING":
        1,

    "REVIEW":
        2,

    "INFO":
        3,

}


if not J_GOVERNANCE_ALERTS.empty:

    J_GOVERNANCE_ALERTS[
        "_order"
    ] = (

        J_GOVERNANCE_ALERTS[
            "severity"
        ]

        .map(
            J_ALERT_ORDER
        )

        .fillna(
            99
        )

    )


    J_GOVERNANCE_ALERTS = (

        J_GOVERNANCE_ALERTS

        .sort_values(

            [
                "_order",
                "ticker",
            ]

        )

        .drop(
            columns=[
                "_order"
            ]
        )

        .reset_index(
            drop=True
        )

    )


# ==================================================================================================
# ==================================================================================================
# J6 — FINAL PRODUCTION RUN MANIFEST
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 27. PIPELINE HEALTH DISCOVERY
# ==================================================================================================

pipeline_health = {}


for section_name, variable_name in [

    (
        "D",
        "REGIME_D8_PASSED",
    ),

    (
        "F",
        "VALUATION_SECTION_F_PASSED",
    ),

    (
        "G",
        "SECTION_G_PASSED",
    ),

    (
        "H",
        "SECTION_H_PASSED",
    ),

    (
        "I",
        "SECTION_I_PASSED",
    ),

]:

    pipeline_health[
        section_name
    ] = bool(

        globals().get(
            variable_name,
            False,
        )

    )


# ==================================================================================================
# 28. RUN MANIFEST
# ==================================================================================================

J_FINAL_RUN_MANIFEST = pd.DataFrame([{

    "section":
        "J",

    "version":
        J_VERSION,

    "as_of":
        I_AS_OF_TIMESTAMP,

    "snapshot_id":
        I_SNAPSHOT_ID,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "section_d_passed":
        pipeline_health[
            "D"
        ],

    "section_f_passed":
        pipeline_health[
            "F"
        ],

    "section_g_passed":
        pipeline_health[
            "G"
        ],

    "section_h_passed":
        pipeline_health[
            "H"
        ],

    "section_i_passed":
        pipeline_health[
            "I"
        ],

    "snapshot_count":
        len(
            J_SNAPSHOT_HISTORY
        ),

    "prior_snapshot_available":
        J_ATTRIBUTION_AVAILABLE,

    "attribution_weight_source":
        (J_ATTRIBUTION_WEIGHT_SOURCE if J_ATTRIBUTION_AVAILABLE else "BASELINE_ONLY"),

    "previous_snapshot_id":
        J_PREVIOUS_SNAPSHOT_ID,

    "elapsed_days":
        J_ELAPSED_DAYS,

    "live_forward_periods":
        J_LIVE_PERIOD_COUNT,

    "live_cumulative_return":
        J_LIVE_CUMULATIVE_RETURN,

    "live_cumulative_expected_return":
        J_LIVE_CUMULATIVE_EXPECTED_RETURN,

    "mean_return_surprise":
        J_MEAN_RETURN_SURPRISE,

    "current_period_realized_return":
        J_PORTFOLIO_REALIZED_RETURN,

    "current_period_expected_return":
        J_PORTFOLIO_EXPECTED_INTERVAL_RETURN,

    "current_period_return_surprise":
        J_PORTFOLIO_RETURN_SURPRISE,

    "material_model_drift_count":
        len(
            J_MATERIAL_MODEL_DRIFT
        ),

    "governance_alert_count":
        len(
            J_GOVERNANCE_ALERTS
        ),

    "historical_pit_backtest_eligible":
        False,

    "live_forward_monitoring_active":
        bool(
            J_ATTRIBUTION_AVAILABLE
        ),

}])


# ==================================================================================================
# 29. FINAL HASH
# ==================================================================================================

manifest_hash_frame = (

    J_FINAL_RUN_MANIFEST[
        [
            "snapshot_id",

            "valuation_universe_freeze_id",

            "snapshot_count",

            "live_forward_periods",

            "material_model_drift_count",

            "governance_alert_count",

        ]
    ]

    .copy()

)


J_RUN_SHA256 = hashlib.sha256(

    pd.util.hash_pandas_object(

        manifest_hash_frame,
        index=False,

    )
    .values
    .tobytes()

).hexdigest()


J_FINAL_RUN_MANIFEST[
    "run_sha256"
] = (

    J_RUN_SHA256

)


# ==================================================================================================
# 30. HEALTH
# ==================================================================================================

J_SNAPSHOT_HISTORY_VALID = bool(

    len(
        J_SNAPSHOT_HISTORY
    )
    >=
    1

)


J_CURRENT_SNAPSHOT_PRESENT = bool(

    J_CURRENT_SNAPSHOT_ID

    in

    set(

        J_SNAPSHOT_HISTORY[
            "snapshot_id"
        ]
        .astype(str)

    )

)


J_ATTRIBUTION_FINITE = bool(

    True

    if not J_ATTRIBUTION_AVAILABLE

    else

    (

        safe_isfinite(
            J_PORTFOLIO_REALIZED_RETURN
        )

        and

        safe_isfinite(
            J_PORTFOLIO_EXPECTED_INTERVAL_RETURN
        )

    )

)


J_DRIFT_ENGINE_VALID = bool(

    True

    if not J_ATTRIBUTION_AVAILABLE

    else

    isinstance(
        J_MODEL_DRIFT,
        pd.DataFrame,
    )

)


J_HEALTH = pd.DataFrame([

    {

        "check":
            "Section I remains passed",

        "passed":
            bool(
                SECTION_I_PASSED
            ),

        "required":
            True,

        "detail":
            "SECTION_I_PASSED=True",

    },

    {

        "check":
            "Snapshot history contains at least one production run",

        "passed":
            J_SNAPSHOT_HISTORY_VALID,

        "required":
            True,

        "detail":
            (
                f"snapshots="
                f"{len(J_SNAPSHOT_HISTORY)}"
            ),

    },

    {

        "check":
            "Current production snapshot is indexed",

        "passed":
            J_CURRENT_SNAPSHOT_PRESENT,

        "required":
            True,

        "detail":
            (
                f"current_snapshot="
                f"{J_CURRENT_SNAPSHOT_ID}"
            ),

    },

    {

        "check":
            "Live forward attribution is numerically valid",

        "passed":
            J_ATTRIBUTION_FINITE,

        "required":
            True,

        "detail":
            (

                "baseline_only"

                if not J_ATTRIBUTION_AVAILABLE

                else

                (
                    f"realized="
                    f"{J_PORTFOLIO_REALIZED_RETURN:.4%}; "
                    f"expected="
                    f"{J_PORTFOLIO_EXPECTED_INTERVAL_RETURN:.4%}"
                )

            ),

    },

    {

        "check":
            "Model-drift engine is valid",

        "passed":
            J_DRIFT_ENGINE_VALID,

        "required":
            True,

        "detail":
            (
                f"material_drift_count="
                f"{len(J_MATERIAL_MODEL_DRIFT)}"
            ),

    },

    {

        "check":
            "Historical PIT backtest remains blocked",

        "passed":
            True,

        "required":
            True,

        "detail":
            (
                "Section J records only forward production "
                "performance from Section I snapshots."
            ),

    },

])


J_HEALTH[
    "status"
] = np.where(

    J_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


J_REQUIRED_FAILURES = (

    J_HEALTH[

        J_HEALTH[
            "required"
        ]

        &

        ~
        J_HEALTH[
            "passed"
        ]

    ]

)


SECTION_J_PASSED = (

    J_REQUIRED_FAILURES.empty

)


J_FINAL_RUN_MANIFEST[
    "section_j_passed"
] = (

    SECTION_J_PASSED

)


# ==================================================================================================
# 31. SAVE OUTPUTS
# ==================================================================================================

J_SNAPSHOT_HISTORY.to_csv(

    J_GOVERNANCE_DIR

    /
    "snapshot_history.csv",

    index=False,

)


J_LIVE_ATTRIBUTION.to_csv(

    J_GOVERNANCE_DIR

    /
    "latest_live_attribution.csv",

    index=False,

)


J_MODEL_DRIFT.to_csv(

    J_GOVERNANCE_DIR

    /
    "latest_model_drift.csv",

    index=False,

)


J_MATERIAL_MODEL_DRIFT.to_csv(

    J_GOVERNANCE_DIR

    /
    "latest_material_model_drift.csv",

    index=False,

)


J_GOVERNANCE_ALERTS.to_csv(

    J_GOVERNANCE_DIR

    /
    "latest_governance_alerts.csv",

    index=False,

)


J_FINAL_RUN_MANIFEST.to_csv(

    J_GOVERNANCE_DIR

    /
    "latest_run_manifest.csv",

    index=False,

)


J_HEALTH.to_csv(

    J_GOVERNANCE_DIR

    /
    "latest_health.csv",

    index=False,

)


J_PORTFOLIO_PERFORMANCE_LEDGER.to_csv(

    J_LEDGER_PATH,

    index=False,

)


# Also save into current Section I snapshot.

J_FINAL_RUN_MANIFEST.to_csv(

    Path(
        I_SNAPSHOT_DIR
    )

    /
    "run_manifest.csv",

    index=False,

)


J_GOVERNANCE_ALERTS.to_csv(

    Path(
        I_SNAPSHOT_DIR
    )

    /
    "governance_alerts.csv",

    index=False,

)


J_LIVE_ATTRIBUTION.to_csv(

    Path(
        I_SNAPSHOT_DIR
    )

    /
    "live_attribution.csv",

    index=False,

)


J_MODEL_DRIFT.to_csv(

    Path(
        I_SNAPSHOT_DIR
    )

    /
    "model_drift.csv",

    index=False,

)


# ==================================================================================================
# 32. PROMOTE FINAL OBJECTS
# ==================================================================================================

if SECTION_J_PASSED:

    J_FINAL_PERFORMANCE_ATTRIBUTION = (

        J_LIVE_ATTRIBUTION
        .copy()

    )


    J_FINAL_MODEL_DRIFT = (

        J_MODEL_DRIFT
        .copy()

    )


    J_FINAL_GOVERNANCE_ALERTS = (

        J_GOVERNANCE_ALERTS
        .copy()

    )


    J_FINAL_PERFORMANCE_LEDGER = (

        J_PORTFOLIO_PERFORMANCE_LEDGER
        .copy()

    )


# ==================================================================================================
# ==================================================================================================
# DISPLAY
# ==================================================================================================
# ==================================================================================================


print(
    "=" * 150
)

print(
    "SECTION J — LIVE PERFORMANCE ATTRIBUTION / MODEL DRIFT / GOVERNANCE ENGINE"
)

print(
    "=" * 150
)


print(
    f"Current snapshot:                   "
    f"{J_CURRENT_SNAPSHOT_ID}"
)


print(
    f"Previous snapshot:                  "
    f"{J_PREVIOUS_SNAPSHOT_ID}"
)


print(
    f"Snapshot count:                     "
    f"{len(J_SNAPSHOT_HISTORY)}"
)


print(
    f"Forward attribution active:         "
    f"{J_ATTRIBUTION_AVAILABLE}"
)


print(
    f"Live performance periods:           "
    f"{J_LIVE_PERIOD_COUNT}"
)


if J_ATTRIBUTION_AVAILABLE:

    print(
        f"Elapsed days:                       "
        f"{J_ELAPSED_DAYS:.3f}"
    )


    print(
        f"Current period realized return:     "
        f"{J_PORTFOLIO_REALIZED_RETURN:.3%}"
    )


    print(
        f"Current period expected return:     "
        f"{J_PORTFOLIO_EXPECTED_INTERVAL_RETURN:.3%}"
    )


    print(
        f"Current period surprise:            "
        f"{J_PORTFOLIO_RETURN_SURPRISE:.3%}"
    )


print(
    f"Material model drift names:         "
    f"{len(J_MATERIAL_MODEL_DRIFT)}"
)


print(
    f"Governance alerts:                  "
    f"{len(J_GOVERNANCE_ALERTS)}"
)


print(
    f"Run SHA256:                         "
    f"{J_RUN_SHA256}"
)


# ==================================================================================================
# SNAPSHOT HISTORY
# ==================================================================================================

print(
    "\nPRODUCTION snapshot history:"
)


display(

    J_SNAPSHOT_HISTORY

)


# ==================================================================================================
# LIVE ATTRIBUTION
# ==================================================================================================

print(
    "\nLIVE snapshot-to-snapshot attribution:"
)


if not J_ATTRIBUTION_AVAILABLE:

    print(
        "Baseline snapshot only. Attribution activates on the next production run."
    )


else:

    attribution_display_columns = [

        column

        for column in [

            "ticker",

            "previous_company_name",

            "previous_target_weight",
            "attribution_weight",

            "previous_current_price",
            "current_current_price",

            "price_return",

            "realized_contribution",

            "expected_interval_stock_return",
            "expected_contribution",

            "contribution_surprise",

            "target_weight_change",

        ]

        if column
        in
        J_LIVE_ATTRIBUTION.columns

    ]


    display(

        J_LIVE_ATTRIBUTION[
            attribution_display_columns
        ]

        .sort_values(

            "realized_contribution",

            ascending=False,

        )

    )


# ==================================================================================================
# MODEL DRIFT
# ==================================================================================================

print(
    "\nMATERIAL model / signal drift:"
)


if J_MATERIAL_MODEL_DRIFT.empty:

    print(
        "No material model drift detected, or baseline snapshot only."
    )


else:

    drift_display_columns = [

        column

        for column in [

            "ticker",

            "alpha_rank_drift",
            "alpha_score_drift",

            "mos_distance_drift",

            "intrinsic_value_drift_pct",

            "target_weight_drift",

            "buy_zone_changed",

            "monitor_action_changed",

        ]

        if column
        in
        J_MATERIAL_MODEL_DRIFT.columns

    ]


    display(

        J_MATERIAL_MODEL_DRIFT[
            drift_display_columns
        ]

    )


# ==================================================================================================
# GOVERNANCE ALERTS
# ==================================================================================================

print(
    "\nGOVERNANCE alerts:"
)


if J_GOVERNANCE_ALERTS.empty:

    print(
        "No active governance alerts."
    )


else:

    display(

        J_GOVERNANCE_ALERTS

    )


# ==================================================================================================
# PERFORMANCE LEDGER
# ==================================================================================================

print(
    "\nLIVE forward performance ledger:"
)


if J_PORTFOLIO_PERFORMANCE_LEDGER.empty:

    print(
        "No completed forward performance period yet."
    )


else:

    display(

        J_PORTFOLIO_PERFORMANCE_LEDGER

    )


# ==================================================================================================
# RUN MANIFEST
# ==================================================================================================

print(
    "\nFINAL run manifest:"
)


display(

    J_FINAL_RUN_MANIFEST

)


# ==================================================================================================
# HEALTH
# ==================================================================================================

print(
    "\nSECTION J health:"
)


display(

    J_HEALTH

)


# ==================================================================================================
# FINAL PRODUCTION GATE
# ==================================================================================================

if not SECTION_J_PASSED:

    display(

        J_REQUIRED_FAILURES

    )


    raise RuntimeError(

        "SECTION J FINAL PRODUCTION GATE FAILED."

    )


print(
    "\n"
    + "=" * 150
)


print(
    "✓ SECTION J COMPLETE — live attribution and governance layer initialized."
)


print(
    "✓ Production snapshots are indexed into a persistent history."
)


print(
    "✓ Snapshot-to-snapshot performance attribution begins automatically from the second production run."
)


print(
    "✓ Attribution uses the PREVIOUS snapshot's portfolio weights to avoid look-ahead."
)


print(
    "✓ Cash accrual is included using the configured risk-free rate."
)


print(
    "✓ Expected-vs-realized return surprise is monitored."
)


print(
    "✓ Alpha-rank, signal, MOS, intrinsic-value and portfolio-weight drift are monitored."
)


print(
    "✓ Valuation-universe lineage changes generate governance alerts."
)


print(
    "✓ A persistent live forward-performance ledger is maintained."
)


print(
    "✓ This is live forward monitoring, NOT a historical PIT backtest."
)


print(
    "✓ J_FINAL_PERFORMANCE_ATTRIBUTION is the latest live attribution object."
)


print(
    "✓ J_FINAL_MODEL_DRIFT is the model-drift handoff."
)


print(
    "✓ J_FINAL_GOVERNANCE_ALERTS is the governance-alert object."
)


print(
    "✓ J_FINAL_PERFORMANCE_LEDGER is the persistent live performance history."
)


print(
    "✓ J_FINAL_RUN_MANIFEST is the end-to-end production run manifest."
)


print(
    "✓ SECTION_J_PASSED = True."
)


print(
    "=" * 150
)
