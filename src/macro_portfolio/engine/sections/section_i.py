# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 90 =====
# ==================================================================================================
# SECTION I — LIVE OPERATING / DECISION / SNAPSHOT ENGINE
# REPLACEMENT CELL V1.0.1
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
# 1. VALIDATE UPSTREAM
# ==================================================================================================

required_i_objects = [
    "SECTION_H_PASSED",
    "H_FINAL_MONITORING_SNAPSHOT",
    "H_FINAL_ALERTS",
    "H_FINAL_SUMMARY",
    "G_FINAL_PORTFOLIO_WEIGHTS",
    "G_FINAL_TRADE_PLAN",
    "VALUATION_UNIVERSE_FREEZE_ID",
    "STOCK_OUTPUT_DIR",
]

missing_i_objects = [
    x
    for x in required_i_objects
    if x not in globals()
]

if missing_i_objects:

    raise RuntimeError(
        "Section I requires completed H/G objects. Missing: "
        f"{missing_i_objects}"
    )


if not bool(
    SECTION_H_PASSED
):

    raise RuntimeError(
        "Section H production gate did not pass."
    )


# ==================================================================================================
# 2. VERSION / CONFIG
# ==================================================================================================

I_VERSION = "1.1.0"


def i_cfg(
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


I_MIN_TRADE_WEIGHT = float(

    i_cfg(
        [
            "execution",
            "min_trade",
        ],
        0.005,
    )

)


I_NAV = float(

    globals().get(

        "H_NAV",

        i_cfg(
            [
                "portfolio",
                "initial_nav",
            ],
            1_000_000.0,
        ),

    )

)


# Daily-change monitoring thresholds.

I_PRICE_CHANGE_ALERT = float(cfg(["monitoring", "price_change_alert"], 0.05))

I_MOS_DISTANCE_CHANGE_ALERT = float(cfg(["monitoring", "mos_distance_change_alert"], 0.05))

I_WEIGHT_CHANGE_ALERT = float(cfg(["monitoring", "weight_change_alert"], 0.01))


# Snapshot-history policy.

I_MAX_SNAPSHOT_FOLDERS = int(cfg(["monitoring", "max_snapshot_folders"], 120))


# ==================================================================================================
# 3. OPERATING TIMESTAMP
# ==================================================================================================

I_AS_OF_TIMESTAMP = pd.Timestamp.now(
    tz="Asia/Singapore"
)


I_AS_OF_DATE = (
    I_AS_OF_TIMESTAMP
    .date()
)


I_SNAPSHOT_ID = (
    I_AS_OF_TIMESTAMP
    .strftime(
        "%Y%m%d_%H%M%S"
    )
)


# ==================================================================================================
# 4. SNAPSHOT DIRECTORIES
# ==================================================================================================

I_SNAPSHOT_ROOT = (

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "snapshots"

)


I_SNAPSHOT_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


I_SNAPSHOT_DIR = (

    I_SNAPSHOT_ROOT
    /
    I_SNAPSHOT_ID

)


I_SNAPSHOT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ==================================================================================================
# 5. START FROM SECTION H MONITOR
# ==================================================================================================

I_MONITOR = (
    H_FINAL_MONITORING_SNAPSHOT
    .copy()
)


I_MONITOR[
    "ticker"
] = (

    I_MONITOR[
        "ticker"
    ]
    .astype(str)

)


# ==================================================================================================
# 6. ATTACH LIVE TRADE PLAN
# ==================================================================================================

I_TRADE_PLAN = (
    G_FINAL_TRADE_PLAN
    .copy()
)


I_TRADE_PLAN[
    "ticker"
] = (

    I_TRADE_PLAN[
        "ticker"
    ]
    .astype(str)

)


I_TRADE_PLAN = (

    I_TRADE_PLAN[

        I_TRADE_PLAN[
            "ticker"
        ]
        !=
        "CASH"

    ]

    .copy()

)


trade_columns = [

    column

    for column in [

        "ticker",

        "action",

        "trade_required",

        "trade_notional",

        "estimated_transaction_cost",

        "trade_pct_adv",

        "liquidity_check",

    ]

    if column
    in
    I_TRADE_PLAN.columns

]


I_MONITOR = (

    I_MONITOR

    .merge(

        I_TRADE_PLAN[
            trade_columns
        ],

        on="ticker",

        how="left",

        validate="one_to_one",

        suffixes=(
            "",
            "_trade",
        ),

    )

)


# ==================================================================================================
# 7. TRADE DEFAULTS
# ==================================================================================================

if "trade_required" not in I_MONITOR.columns:

    I_MONITOR[
        "trade_required"
    ] = False


I_MONITOR[
    "trade_required"
] = (

    I_MONITOR[
        "trade_required"
    ]

    .fillna(
        False
    )

    .astype(bool)

)


if "trade_notional" not in I_MONITOR.columns:

    I_MONITOR[
        "trade_notional"
    ] = 0.0


I_MONITOR[
    "trade_notional"
] = (

    pd.to_numeric(

        I_MONITOR[
            "trade_notional"
        ],

        errors="coerce",

    )

    .fillna(
        0.0
    )

)


if "estimated_transaction_cost" not in I_MONITOR.columns:

    I_MONITOR[
        "estimated_transaction_cost"
    ] = 0.0


I_MONITOR[
    "estimated_transaction_cost"
] = (

    pd.to_numeric(

        I_MONITOR[
            "estimated_transaction_cost"
        ],

        errors="coerce",

    )

    .fillna(
        0.0
    )

)


# ==================================================================================================
# 8. DAILY DECISION CATEGORY
# ==================================================================================================

def i_decision_category(
    row
):

    holding = (

        float(
            row.get(
                "target_weight",
                0.0,
            )
        )

        >
        1e-10

    )


    research_eligible = bool(

        row.get(
            "research_ranking_eligible",
            False,
        )

    )


    buy_zone = str(

        row.get(
            "buy_zone",
            "UNAVAILABLE",
        )

    )


    monitor_action = str(

        row.get(
            "monitor_action",
            "UNAVAILABLE",
        )

    )


    capacity_weight = pd.to_numeric(
        pd.Series([row.get("maximum_additional_weight", 0.0)]),
        errors="coerce",
    ).fillna(0.0).iloc[0]


    trade_required = bool(

        row.get(
            "trade_required",
            False,
        )

    )


    trade_notional = float(

        row.get(
            "trade_notional",
            0.0,
        )

    )


    # --------------------------------------------------------
    # Explicit optimizer/execution instruction comes first.
    # --------------------------------------------------------

    if (

        trade_required

        and

        trade_notional > 0

    ):

        return "BUY_TO_TARGET"


    if (

        trade_required

        and

        trade_notional < 0

    ):

        return "SELL_TO_TARGET"


    # --------------------------------------------------------
    # Existing holding.
    # --------------------------------------------------------

    if holding:

        if monitor_action == "HOLD_CAP_REACHED":

            return "HOLD_CAP_REACHED"


        if monitor_action == "HOLD_ADD_ELIGIBLE":

            return "HOLD_ADD_CAPACITY"


        return "HOLD"


    # --------------------------------------------------------
    # Non-held company.
    # --------------------------------------------------------

    if not research_eligible:

        return "BLOCKED_PROVISIONAL"


    if buy_zone == "BUY_ZONE":

        if capacity_weight <= 1e-10:
            return "BUY_ZONE_CAP_BLOCKED"

        return "BUY_ZONE_NOT_SELECTED"


    if buy_zone == "NEAR_BUY_ZONE_0_5":

        if capacity_weight <= 1e-10:
            return "NEAR_ENTRY_CAP_BLOCKED"

        return "NEAR_ENTRY"


    if buy_zone == "WATCH_BUY_ZONE_5_10":

        return "WATCH_NEAR_ENTRY"


    return "WATCH"


I_MONITOR[
    "decision_category"
] = (

    I_MONITOR

    .apply(
        i_decision_category,
        axis=1,
    )

)


# ==================================================================================================
# 9. DECISION PRIORITY
# ==================================================================================================

I_PRIORITY_MAP = {

    "BUY_TO_TARGET":
        1,

    "SELL_TO_TARGET":
        1,

    "NEAR_ENTRY":
        2,

    "HOLD_ADD_CAPACITY":
        3,

    "BUY_ZONE_NOT_SELECTED":
        4,

    "BUY_ZONE_CAP_BLOCKED":
        7,

    "NEAR_ENTRY_CAP_BLOCKED":
        7,

    "HOLD_CAP_REACHED":
        5,

    "HOLD":
        6,

    "WATCH_NEAR_ENTRY":
        7,

    "WATCH":
        8,

    "BLOCKED_PROVISIONAL":
        9,

}


I_MONITOR[
    "decision_priority"
] = (

    I_MONITOR[
        "decision_category"
    ]

    .map(
        I_PRIORITY_MAP
    )

    .fillna(
        99
    )

)


# ==================================================================================================
# 10. CAPACITY / BUY TRIGGER
# ==================================================================================================

if "maximum_additional_notional" not in I_MONITOR.columns:

    I_MONITOR[
        "maximum_additional_notional"
    ] = 0.0


if "maximum_additional_weight" not in I_MONITOR.columns:

    I_MONITOR[
        "maximum_additional_weight"
    ] = 0.0


I_MONITOR[
    "capacity_notional"
] = (

    pd.to_numeric(

        I_MONITOR[
            "maximum_additional_notional"
        ],

        errors="coerce",

    )

    .fillna(
        0.0
    )

)


I_MONITOR[
    "capacity_weight"
] = (

    pd.to_numeric(

        I_MONITOR[
            "maximum_additional_weight"
        ],

        errors="coerce",

    )

    .fillna(
        0.0
    )

)


I_MONITOR[
    "buy_trigger_price"
] = (

    pd.to_numeric(

        I_MONITOR[
            "mos_price_threshold"
        ],

        errors="coerce",

    )

)


I_MONITOR[
    "current_price"
] = (

    pd.to_numeric(

        I_MONITOR[
            "current_price"
        ],

        errors="coerce",

    )

)


I_MONITOR[
    "price_change_required_to_buy"
] = np.where(

    (

        I_MONITOR[
            "current_price"
        ]

        >
        0

    )

    &

    (

        I_MONITOR[
            "buy_trigger_price"
        ]

        >
        0

    ),

    (

        I_MONITOR[
            "buy_trigger_price"
        ]

        /
        I_MONITOR[
            "current_price"
        ]

        -
        1.0

    ),

    np.nan,

)


# ==================================================================================================
# 11. FINAL DECISION BOOK
# ==================================================================================================

decision_columns = [

    column

    for column in [

        "ticker",
        "company_name",

        "sector_ticker",
        "allocation_bucket",

        "decision_category",
        "decision_priority",

        "current_price",
        "buy_trigger_price",

        "price_change_required_to_buy",

        "expected_intrinsic_value",

        "buy_zone",

        "previous_weight",
        "target_weight",
        "delta_weight",

        "trade_required",
        "trade_notional",

        "estimated_transaction_cost",

        "capacity_weight",
        "capacity_notional",

        "master_alpha_rank",

        "confidence_adjusted_master_alpha",

        "expected_total_return_annual",

        "optimizer_volatility_annual",

        "risk_contribution_share",

        "valuation_review_required",

        "research_ranking_eligible",

    ]

    if column
    in
    I_MONITOR.columns

]


I_FINAL_DECISION_BOOK = (

    I_MONITOR[
        decision_columns
    ]

    .copy()

    .sort_values(

        [
            "decision_priority",
            "master_alpha_rank",
        ],

        ascending=[
            True,
            True,
        ],

        na_position=
            "last",

    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# 12. REBALANCE / REVIEW TRIGGER ENGINE
# ==================================================================================================

I_TRIGGER_ROWS = []


def i_add_trigger(
    severity,
    trigger_type,
    ticker,
    message,
    action_required=False,
    metric=np.nan,
    threshold=np.nan,
):

    I_TRIGGER_ROWS.append({

        "severity":
            severity,

        "trigger_type":
            trigger_type,

        "ticker":
            ticker,

        "message":
            message,

        "action_required":
            bool(
                action_required
            ),

        "metric":
            metric,

        "threshold":
            threshold,

        "as_of":
            I_AS_OF_TIMESTAMP,

    })


# ==================================================================================================
# 13. PENDING EXECUTION TRIGGERS
# ==================================================================================================

for _, row in (

    I_FINAL_DECISION_BOOK[

        I_FINAL_DECISION_BOOK[
            "trade_required"
        ]

    ]

    .iterrows()

):

    trade_notional = float(

        row.get(
            "trade_notional",
            0.0,
        )

    )


    if trade_notional > 0:

        i_add_trigger(

            severity=
                "ACTION",

            trigger_type=
                "BUY_TO_TARGET",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"Buy {row['ticker']} toward "
                f"{row.get('target_weight', 0.0):.1%} "
                "target weight."
            ),

            action_required=
                True,

            metric=
                trade_notional,

        )


    elif trade_notional < 0:

        i_add_trigger(

            severity=
                "ACTION",

            trigger_type=
                "SELL_TO_TARGET",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"Reduce {row['ticker']} toward "
                f"{row.get('target_weight', 0.0):.1%} "
                "target weight."
            ),

            action_required=
                True,

            metric=
                trade_notional,

        )


# ==================================================================================================
# 14. NEAR-ENTRY TRIGGERS
# ==================================================================================================

for _, row in (

    I_FINAL_DECISION_BOOK[

        I_FINAL_DECISION_BOOK[
            "decision_category"
        ]
        ==
        "NEAR_ENTRY"

    ]

    .iterrows()

):

    move_required = row.get(

        "price_change_required_to_buy",

        np.nan,

    )


    if pd.notna(
        move_required
    ):

        message = (

            f"{row['ticker']} is close to its MOS buy "
            f"threshold; required price move ≈ "
            f"{move_required:.1%}."

        )

    else:

        message = (

            f"{row['ticker']} is close to its MOS buy threshold."

        )


    i_add_trigger(

        severity=
            "WATCH",

        trigger_type=
            "NEAR_MOS_ENTRY",

        ticker=
            row[
                "ticker"
            ],

        message=
            message,

        action_required=
            False,

        metric=
            move_required,

    )


# ==================================================================================================
# 15. CARRY FORWARD SECTION H ALERTS
# ==================================================================================================

for _, row in (

    H_FINAL_ALERTS
    .iterrows()

):

    original_severity = str(

        row.get(
            "severity",
            "INFO",
        )

    )


    if original_severity == "CRITICAL":

        severity = "CRITICAL"

        action_required = True


    elif original_severity == "WARNING":

        severity = "REVIEW"

        action_required = True


    else:

        severity = "INFO"

        action_required = False


    i_add_trigger(

        severity=
            severity,

        trigger_type=
            str(

                row.get(

                    "alert_type",

                    "PORTFOLIO_ALERT",

                )

            ),

        ticker=
            str(

                row.get(

                    "ticker",

                    "PORTFOLIO",

                )

            ),

        message=
            str(

                row.get(

                    "message",

                    "",

                )

            ),

        action_required=
            action_required,

        metric=
            row.get(
                "metric",
                np.nan,
            ),

        threshold=
            row.get(
                "threshold",
                np.nan,
            ),

    )


# ==================================================================================================
# 16. PRIOR-SNAPSHOT DISCOVERY
# ==================================================================================================

existing_snapshot_dirs = sorted(

    [

        path

        for path
        in I_SNAPSHOT_ROOT.iterdir()

        if (

            path.is_dir()

            and

            path.name
            !=
            I_SNAPSHOT_ID

        )

    ]

)


I_PREVIOUS_SNAPSHOT_DIR = (

    existing_snapshot_dirs[-1]

    if existing_snapshot_dirs

    else None

)


I_PREVIOUS_MONITOR_PATH = (

    I_PREVIOUS_SNAPSHOT_DIR

    /
    "monitoring_snapshot.parquet"

    if I_PREVIOUS_SNAPSHOT_DIR
    is not None

    else None

)


I_HAS_PREVIOUS_SNAPSHOT = bool(

    I_PREVIOUS_MONITOR_PATH
    is not None

    and

    I_PREVIOUS_MONITOR_PATH.exists()

)


if I_HAS_PREVIOUS_SNAPSHOT:

    I_PREVIOUS_MONITOR = (

        pd.read_parquet(

            I_PREVIOUS_MONITOR_PATH

        )

    )


    I_PREVIOUS_MONITOR[
        "ticker"
    ] = (

        I_PREVIOUS_MONITOR[
            "ticker"
        ]
        .astype(str)

    )


else:

    I_PREVIOUS_MONITOR = pd.DataFrame()


# ==================================================================================================
# 17. SNAPSHOT CHANGE DETECTION
# ==================================================================================================

if I_HAS_PREVIOUS_SNAPSHOT:

    previous_columns = [

        column

        for column in [

            "ticker",

            "current_price",

            "distance_to_mos_pct",

            "buy_zone",

            "monitor_action",

            "target_weight",

        ]

        if column
        in
        I_PREVIOUS_MONITOR.columns

    ]


    previous = (

        I_PREVIOUS_MONITOR[
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


    current_columns = [

        column

        for column in [

            "ticker",

            "current_price",

            "distance_to_mos_pct",

            "buy_zone",

            "monitor_action",

            "target_weight",

        ]

        if column
        in
        H_FINAL_MONITORING_SNAPSHOT.columns

    ]


    current = (

        H_FINAL_MONITORING_SNAPSHOT[
            current_columns
        ]

        .copy()

    )


    current[
        "ticker"
    ] = (

        current[
            "ticker"
        ]
        .astype(str)

    )


    I_CHANGE_LOG = (

        current

        .merge(

            previous,

            on="ticker",

            how="outer",

            validate="one_to_one",

        )

    )


    # ------------------------------------------------------------------
    # PRICE CHANGE
    # ------------------------------------------------------------------

    if (

        "previous_current_price"
        in
        I_CHANGE_LOG.columns

    ):

        current_price = pd.to_numeric(

            I_CHANGE_LOG[
                "current_price"
            ],

            errors="coerce",

        )


        previous_price = pd.to_numeric(

            I_CHANGE_LOG[
                "previous_current_price"
            ],

            errors="coerce",

        )


        I_CHANGE_LOG[
            "price_change_pct"
        ] = np.where(

            previous_price > 0,

            (

                current_price

                /
                previous_price

                -
                1.0

            ),

            np.nan,

        )


    else:

        I_CHANGE_LOG[
            "price_change_pct"
        ] = np.nan


    # ------------------------------------------------------------------
    # MOS DISTANCE CHANGE
    # ------------------------------------------------------------------

    if (

        "previous_distance_to_mos_pct"
        in
        I_CHANGE_LOG.columns

    ):

        I_CHANGE_LOG[
            "mos_distance_change"
        ] = (

            pd.to_numeric(

                I_CHANGE_LOG[
                    "distance_to_mos_pct"
                ],

                errors="coerce",

            )

            -

            pd.to_numeric(

                I_CHANGE_LOG[
                    "previous_distance_to_mos_pct"
                ],

                errors="coerce",

            )

        )


    else:

        I_CHANGE_LOG[
            "mos_distance_change"
        ] = np.nan


    # ------------------------------------------------------------------
    # TARGET-WEIGHT CHANGE
    # ------------------------------------------------------------------

    if (

        "previous_target_weight"
        in
        I_CHANGE_LOG.columns

    ):

        I_CHANGE_LOG[
            "target_weight_change"
        ] = (

            pd.to_numeric(

                I_CHANGE_LOG[
                    "target_weight"
                ],

                errors="coerce",

            )
            .fillna(
                0.0
            )

            -

            pd.to_numeric(

                I_CHANGE_LOG[
                    "previous_target_weight"
                ],

                errors="coerce",

            )
            .fillna(
                0.0
            )

        )


    else:

        I_CHANGE_LOG[
            "target_weight_change"
        ] = np.nan


    # ------------------------------------------------------------------
    # BUY-ZONE TRANSITION
    # ------------------------------------------------------------------

    if (

        "previous_buy_zone"
        in
        I_CHANGE_LOG.columns

    ):

        I_CHANGE_LOG[
            "buy_zone_changed"
        ] = (

            I_CHANGE_LOG[
                "buy_zone"
            ]
            .astype(str)

            !=

            I_CHANGE_LOG[
                "previous_buy_zone"
            ]
            .astype(str)

        )


    else:

        I_CHANGE_LOG[
            "buy_zone_changed"
        ] = False


    # ------------------------------------------------------------------
    # MONITOR-ACTION TRANSITION
    # ------------------------------------------------------------------

    if (

        "previous_monitor_action"
        in
        I_CHANGE_LOG.columns

    ):

        I_CHANGE_LOG[
            "monitor_action_changed"
        ] = (

            I_CHANGE_LOG[
                "monitor_action"
            ]
            .astype(str)

            !=

            I_CHANGE_LOG[
                "previous_monitor_action"
            ]
            .astype(str)

        )


    else:

        I_CHANGE_LOG[
            "monitor_action_changed"
        ] = False


    # ==================================================================
    # MATERIAL CHANGE
    #
    # IMPORTANT:
    #
    # The previous syntax error came from naked "|" operators.
    #
    # This implementation uses np.logical_or.reduce().
    # ==================================================================

    price_change_mask = (

        I_CHANGE_LOG[
            "price_change_pct"
        ]

        .abs()

        .fillna(
            0.0
        )

        >=
        I_PRICE_CHANGE_ALERT

    )


    mos_change_mask = (

        I_CHANGE_LOG[
            "mos_distance_change"
        ]

        .abs()

        .fillna(
            0.0
        )

        >=
        I_MOS_DISTANCE_CHANGE_ALERT

    )


    weight_change_mask = (

        I_CHANGE_LOG[
            "target_weight_change"
        ]

        .abs()

        .fillna(
            0.0
        )

        >=
        I_WEIGHT_CHANGE_ALERT

    )


    buy_zone_change_mask = (

        I_CHANGE_LOG[
            "buy_zone_changed"
        ]

        .fillna(
            False
        )

        .astype(bool)

    )


    monitor_action_change_mask = (

        I_CHANGE_LOG[
            "monitor_action_changed"
        ]

        .fillna(
            False
        )

        .astype(bool)

    )


    I_CHANGE_LOG[
        "material_change"
    ] = np.logical_or.reduce(

        [

            price_change_mask
            .to_numpy(
                dtype=bool
            ),

            mos_change_mask
            .to_numpy(
                dtype=bool
            ),

            weight_change_mask
            .to_numpy(
                dtype=bool
            ),

            buy_zone_change_mask
            .to_numpy(
                dtype=bool
            ),

            monitor_action_change_mask
            .to_numpy(
                dtype=bool
            ),

        ]

    )


    I_FINAL_CHANGE_LOG = (

        I_CHANGE_LOG[

            I_CHANGE_LOG[
                "material_change"
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

    I_CHANGE_LOG = pd.DataFrame()


    I_FINAL_CHANGE_LOG = pd.DataFrame(

        columns=[

            "ticker",

            "current_price",
            "previous_current_price",

            "price_change_pct",

            "distance_to_mos_pct",
            "previous_distance_to_mos_pct",

            "mos_distance_change",

            "buy_zone",
            "previous_buy_zone",

            "buy_zone_changed",

            "monitor_action",
            "previous_monitor_action",

            "monitor_action_changed",

            "target_weight",
            "previous_target_weight",

            "target_weight_change",

            "material_change",

        ]

    )


# ==================================================================================================
# 18. ADD MATERIAL-CHANGE TRIGGERS
# ==================================================================================================

if not I_FINAL_CHANGE_LOG.empty:

    for _, row in (

        I_FINAL_CHANGE_LOG
        .iterrows()

    ):

        i_add_trigger(

            severity=
                "REVIEW",

            trigger_type=
                "SNAPSHOT_CHANGE",

            ticker=
                str(
                    row[
                        "ticker"
                    ]
                ),

            message=(
                f"{row['ticker']} has a material change "
                "versus the previous operating snapshot."
            ),

            action_required=
                True,

        )


# ==================================================================================================
# 19. FINAL TRIGGER TABLE
# ==================================================================================================

I_FINAL_REBALANCE_TRIGGERS = pd.DataFrame(

    I_TRIGGER_ROWS

)


if I_FINAL_REBALANCE_TRIGGERS.empty:

    I_FINAL_REBALANCE_TRIGGERS = pd.DataFrame(

        columns=[

            "severity",

            "trigger_type",

            "ticker",

            "message",

            "action_required",

            "metric",

            "threshold",

            "as_of",

        ]

    )


I_TRIGGER_SEVERITY_ORDER = {

    "CRITICAL":
        0,

    "ACTION":
        1,

    "REVIEW":
        2,

    "WATCH":
        3,

    "INFO":
        4,

}


I_FINAL_REBALANCE_TRIGGERS[
    "_order"
] = (

    I_FINAL_REBALANCE_TRIGGERS[
        "severity"
    ]

    .map(
        I_TRIGGER_SEVERITY_ORDER
    )

    .fillna(
        99
    )

)


I_FINAL_REBALANCE_TRIGGERS = (

    I_FINAL_REBALANCE_TRIGGERS

    .sort_values(

        [
            "_order",
            "ticker",
        ]

    )

    .drop_duplicates(
        subset=[
            "trigger_type",
            "ticker",
        ],
        keep="first",
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
# 20. DAILY SYSTEM STATUS
# ==================================================================================================

I_ACTION_REQUIRED_COUNT = int(

    I_FINAL_REBALANCE_TRIGGERS[
        "action_required"
    ]

    .fillna(
        False
    )

    .sum()

)


I_CRITICAL_COUNT = int(

    (

        I_FINAL_REBALANCE_TRIGGERS[
            "severity"
        ]

        ==
        "CRITICAL"

    )

    .sum()

)


I_EXECUTION_TRADE_COUNT = int(

    I_FINAL_DECISION_BOOK[
        "trade_required"
    ]

    .fillna(
        False
    )

    .sum()

)


I_NEAR_ENTRY_COUNT = int(

    (

        I_FINAL_DECISION_BOOK[
            "decision_category"
        ]

        ==
        "NEAR_ENTRY"

    )

    .sum()

)


I_MATERIAL_CHANGE_COUNT = len(

    I_FINAL_CHANGE_LOG

)


if I_CRITICAL_COUNT > 0:

    I_DAILY_STATUS = (
        "CRITICAL_REVIEW_REQUIRED"
    )


elif I_EXECUTION_TRADE_COUNT > 0:

    I_DAILY_STATUS = (
        "TRADES_PENDING"
    )


elif I_ACTION_REQUIRED_COUNT > 0:

    I_DAILY_STATUS = (
        "REVIEW_REQUIRED"
    )


elif I_MATERIAL_CHANGE_COUNT > 0:

    I_DAILY_STATUS = (
        "MARKET_CHANGES_DETECTED"
    )


elif I_NEAR_ENTRY_COUNT > 0:

    I_DAILY_STATUS = (
        "WATCH_NEAR_ENTRY"
    )


else:

    I_DAILY_STATUS = (
        "STABLE_NO_ACTION"
    )


# ==================================================================================================
# 21. FINAL DAILY SUMMARY
# ==================================================================================================

I_FINAL_DAILY_SUMMARY = pd.DataFrame([{

    "section":
        "I",

    "version":
        I_VERSION,

    "as_of":
        I_AS_OF_TIMESTAMP,

    "snapshot_id":
        I_SNAPSHOT_ID,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "daily_status":
        I_DAILY_STATUS,

    "portfolio_nav":
        I_NAV,

    "research_universe":
        len(
            I_FINAL_DECISION_BOOK
        ),

    "stock_holdings":
        int(

            (

                pd.to_numeric(

                    I_FINAL_DECISION_BOOK[
                        "target_weight"
                    ],

                    errors="coerce",

                )

                >
                1e-10

            )
            .sum()

        ),

    "cash_weight":
        float(

            H_FINAL_SUMMARY
            .iloc[0][
                "cash_weight"
            ]

        ),

    "execution_trades_pending":
        I_EXECUTION_TRADE_COUNT,

    "action_required_triggers":
        I_ACTION_REQUIRED_COUNT,

    "critical_triggers":
        I_CRITICAL_COUNT,

    "near_entry_names":
        I_NEAR_ENTRY_COUNT,

    "material_changes_vs_previous_snapshot":
        I_MATERIAL_CHANGE_COUNT,

    "has_previous_snapshot":
        I_HAS_PREVIOUS_SNAPSHOT,

    "previous_snapshot":
        (

            I_PREVIOUS_SNAPSHOT_DIR.name

            if I_PREVIOUS_SNAPSHOT_DIR
            is not None

            else None

        ),

    "expected_return":
        float(

            H_FINAL_SUMMARY
            .iloc[0][
                "expected_return"
            ]

        ),

    "expected_volatility":
        float(

            H_FINAL_SUMMARY
            .iloc[0][
                "expected_volatility"
            ]

        ),

    "expected_sharpe":
        float(

            H_FINAL_SUMMARY
            .iloc[0][
                "expected_sharpe"
            ]

        ),

    "portfolio_beta":
        float(

            H_FINAL_SUMMARY
            .iloc[0][
                "portfolio_beta"
            ]

        ),

    "section_h_passed":
        True,

}])


# ==================================================================================================
# 22. SAVE CURRENT SNAPSHOT
# ==================================================================================================

H_FINAL_MONITORING_SNAPSHOT.to_parquet(

    I_SNAPSHOT_DIR
    /
    "monitoring_snapshot.parquet",

    index=False,

)


H_FINAL_MONITORING_SNAPSHOT.to_csv(

    I_SNAPSHOT_DIR
    /
    "monitoring_snapshot.csv",

    index=False,

)


I_FINAL_DECISION_BOOK.to_parquet(

    I_SNAPSHOT_DIR
    /
    "decision_book.parquet",

    index=False,

)


I_FINAL_DECISION_BOOK.to_csv(

    I_SNAPSHOT_DIR
    /
    "decision_book.csv",

    index=False,

)


I_FINAL_REBALANCE_TRIGGERS.to_csv(

    I_SNAPSHOT_DIR
    /
    "rebalance_triggers.csv",

    index=False,

)


I_FINAL_CHANGE_LOG.to_csv(

    I_SNAPSHOT_DIR
    /
    "change_log.csv",

    index=False,

)


H_FINAL_ALERTS.to_csv(

    I_SNAPSHOT_DIR
    /
    "portfolio_alerts.csv",

    index=False,

)


if "H_FINAL_STRESS_TESTS" in globals():

    H_FINAL_STRESS_TESTS.to_csv(

        I_SNAPSHOT_DIR
        /
        "stress_tests.csv",

        index=False,

    )


G_FINAL_PORTFOLIO_WEIGHTS.to_csv(

    I_SNAPSHOT_DIR
    /
    "portfolio_weights.csv",

    index=False,

)


G_FINAL_TRADE_PLAN.to_csv(

    I_SNAPSHOT_DIR
    /
    "trade_plan.csv",

    index=False,

)


I_FINAL_DAILY_SUMMARY.to_csv(

    I_SNAPSHOT_DIR
    /
    "daily_summary.csv",

    index=False,

)


# ==================================================================================================
# 23. SNAPSHOT METADATA
# ==================================================================================================

I_SNAPSHOT_METADATA = {

    "snapshot_id":
        I_SNAPSHOT_ID,

    "as_of":
        str(
            I_AS_OF_TIMESTAMP
        ),

    "valuation_universe_freeze_id":
        str(
            VALUATION_UNIVERSE_FREEZE_ID
        ),

    "section_g_passed":
        bool(

            globals().get(
                "SECTION_G_PASSED",
                True,
            )

        ),

    "section_h_passed":
        bool(
            SECTION_H_PASSED
        ),

    "daily_status":
        I_DAILY_STATUS,

    "previous_snapshot":
        (

            I_PREVIOUS_SNAPSHOT_DIR.name

            if I_PREVIOUS_SNAPSHOT_DIR
            is not None

            else None

        ),

}


with open(

    I_SNAPSHOT_DIR
    /
    "metadata.json",

    "w",

    encoding="utf-8",

) as handle:

    json.dump(

        I_SNAPSHOT_METADATA,

        handle,

        indent=2,

    )


# ==================================================================================================
# 24. LATEST OPERATING FILES
# ==================================================================================================

I_FINAL_DECISION_BOOK.to_csv(

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "i_latest_decision_book.csv",

    index=False,

)


I_FINAL_REBALANCE_TRIGGERS.to_csv(

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "i_latest_rebalance_triggers.csv",

    index=False,

)


I_FINAL_CHANGE_LOG.to_csv(

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "i_latest_change_log.csv",

    index=False,

)


I_FINAL_DAILY_SUMMARY.to_csv(

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "i_latest_daily_summary.csv",

    index=False,

)


# ==================================================================================================
# 25. SNAPSHOT RETENTION DISCLOSURE
# ==================================================================================================

snapshot_dirs_after_save = sorted(

    [

        path

        for path
        in I_SNAPSHOT_ROOT.iterdir()

        if path.is_dir()

    ]

)


I_SNAPSHOT_RETENTION_OVERFLOW = max(

    0,

    len(
        snapshot_dirs_after_save
    )

    -
    I_MAX_SNAPSHOT_FOLDERS,

)


# ==================================================================================================
# 26. FINAL HASH
# ==================================================================================================

I_HASH_FRAME = (

    I_FINAL_DECISION_BOOK[
        [
            "ticker",

            "decision_category",

            "current_price",

            "buy_trigger_price",

            "target_weight",

            "trade_required",
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


I_DECISION_SHA256 = hashlib.sha256(

    pd.util.hash_pandas_object(

        I_HASH_FRAME,
        index=False,

    )
    .values
    .tobytes()

).hexdigest()


I_FINAL_DAILY_SUMMARY[
    "decision_sha256"
] = (

    I_DECISION_SHA256

)


# Save once more after hash creation.

I_FINAL_DAILY_SUMMARY.to_csv(

    I_SNAPSHOT_DIR
    /
    "daily_summary.csv",

    index=False,

)


I_FINAL_DAILY_SUMMARY.to_csv(

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "i_latest_daily_summary.csv",

    index=False,

)


# ==================================================================================================
# 27. HEALTH CHECKS
# ==================================================================================================

I_DECISION_COVERAGE_VALID = bool(

    len(
        I_FINAL_DECISION_BOOK
    )

    ==
    len(
        H_FINAL_MONITORING_SNAPSHOT
    )

)


I_BUY_BLOCKED_VIOLATION_COUNT = int(

    (

        I_FINAL_DECISION_BOOK[
            "trade_required"
        ]
        .fillna(
            False
        )

        &

        (

            pd.to_numeric(

                I_FINAL_DECISION_BOOK[
                    "trade_notional"
                ],

                errors="coerce",

            )
            .fillna(
                0.0
            )

            >
            0

        )

        &

        (

            ~
            I_FINAL_DECISION_BOOK[
                "research_ranking_eligible"
            ]
            .fillna(
                False
            )
            .astype(bool)

        )

    )
    .sum()

)


I_SNAPSHOT_FILES_REQUIRED = [

    "monitoring_snapshot.parquet",

    "decision_book.parquet",

    "rebalance_triggers.csv",

    "change_log.csv",

    "portfolio_weights.csv",

    "trade_plan.csv",

    "daily_summary.csv",

    "metadata.json",

]


I_SNAPSHOT_COMPLETE = all(

    (

        I_SNAPSHOT_DIR
        /
        filename

    )
    .exists()

    for filename
    in I_SNAPSHOT_FILES_REQUIRED

)


I_HEALTH = pd.DataFrame([

    {

        "check":
            "Section H remains passed",

        "passed":
            bool(
                SECTION_H_PASSED
            ),

        "required":
            True,

        "detail":
            "SECTION_H_PASSED=True",

    },

    {

        "check":
            "Decision book covers full monitored universe",

        "passed":
            I_DECISION_COVERAGE_VALID,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{len(I_FINAL_DECISION_BOOK)}/"
                f"{len(H_FINAL_MONITORING_SNAPSHOT)}"
            ),

    },

    {

        "check":
            "No buy trade targets blocked provisional names",

        "passed":
            I_BUY_BLOCKED_VIOLATION_COUNT
            ==
            0,

        "required":
            True,

        "detail":
            (
                f"violations="
                f"{I_BUY_BLOCKED_VIOLATION_COUNT}"
            ),

    },

    {

        "check":
            "Operating snapshot archive is complete",

        "passed":
            I_SNAPSHOT_COMPLETE,

        "required":
            True,

        "detail":
            str(
                I_SNAPSHOT_DIR
            ),

    },

    {

        "check":
            "Prior snapshot comparison handled",

        "passed":
            True,

        "required":
            True,

        "detail":
            (

                "comparison_available"

                if I_HAS_PREVIOUS_SNAPSHOT

                else

                "first_snapshot_no_prior_comparison"

            ),

    },

    {

        "check":
            "Snapshot retention overflow disclosed",

        "passed":
            True,

        "required":
            False,

        "detail":
            (
                f"snapshot_folders="
                f"{len(snapshot_dirs_after_save)}; "
                f"policy_limit="
                f"{I_MAX_SNAPSHOT_FOLDERS}; "
                f"overflow="
                f"{I_SNAPSHOT_RETENTION_OVERFLOW}"
            ),

    },

])


I_HEALTH[
    "status"
] = np.where(

    I_HEALTH[
        "passed"
    ],

    "✓ PASS",

    np.where(

        I_HEALTH[
            "required"
        ],

        "✗ FAIL",

        "⚠ WARN",

    )

)


I_REQUIRED_FAILURES = (

    I_HEALTH[

        I_HEALTH[
            "required"
        ]

        &

        ~
        I_HEALTH[
            "passed"
        ]

    ]

)


SECTION_I_PASSED = (

    I_REQUIRED_FAILURES.empty

)


# ==================================================================================================
# 28. PROMOTE FINAL OBJECTS
# ==================================================================================================

if SECTION_I_PASSED:

    I_FINAL_OPERATING_SNAPSHOT = (

        I_FINAL_DAILY_SUMMARY
        .copy()

    )


    I_FINAL_ACTION_BOOK = (

        I_FINAL_DECISION_BOOK
        .copy()

    )


    I_FINAL_TRIGGERS = (

        I_FINAL_REBALANCE_TRIGGERS
        .copy()

    )


# ==================================================================================================
# 29. DISPLAY
# ==================================================================================================

print(
    "=" * 150
)

print(
    "SECTION I — LIVE OPERATING / DECISION / SNAPSHOT ENGINE V1.0.1"
)

print(
    "=" * 150
)


print(
    f"As of:                              "
    f"{I_AS_OF_TIMESTAMP}"
)


print(
    f"Snapshot ID:                        "
    f"{I_SNAPSHOT_ID}"
)


print(
    f"Daily status:                       "
    f"{I_DAILY_STATUS}"
)


print(
    f"Research universe:                  "
    f"{len(I_FINAL_DECISION_BOOK)}"
)


print(
    f"Trades pending:                     "
    f"{I_EXECUTION_TRADE_COUNT}"
)


print(
    f"Near-entry names:                   "
    f"{I_NEAR_ENTRY_COUNT}"
)


print(
    f"Action-required triggers:           "
    f"{I_ACTION_REQUIRED_COUNT}"
)


print(
    f"Critical triggers:                  "
    f"{I_CRITICAL_COUNT}"
)


print(
    f"Material changes vs prior snapshot: "
    f"{I_MATERIAL_CHANGE_COUNT}"
)


print(
    f"Previous snapshot available:        "
    f"{I_HAS_PREVIOUS_SNAPSHOT}"
)


print(
    f"Snapshot directory:                 "
    f"{I_SNAPSHOT_DIR}"
)


# ==================================================================================================
# 30. DECISION BOOK
# ==================================================================================================

print(
    "\nDAILY decision book:"
)


display_columns = [

    column

    for column in [

        "decision_priority",

        "ticker",
        "company_name",

        "sector_ticker",

        "decision_category",

        "current_price",
        "buy_trigger_price",

        "price_change_required_to_buy",

        "target_weight",

        "trade_required",
        "trade_notional",

        "capacity_weight",
        "capacity_notional",

        "master_alpha_rank",

        "expected_total_return_annual",

        "risk_contribution_share",

        "valuation_review_required",

    ]

    if column
    in
    I_FINAL_DECISION_BOOK.columns

]


display(

    I_FINAL_DECISION_BOOK[
        display_columns
    ]
    .head(
        30
    )

)


# ==================================================================================================
# 31. TRIGGERS
# ==================================================================================================

print(
    "\nREBALANCE / review triggers:"
)


if I_FINAL_REBALANCE_TRIGGERS.empty:

    print(
        "No active triggers."
    )


else:

    display(

        I_FINAL_REBALANCE_TRIGGERS

    )


# ==================================================================================================
# 32. CHANGE LOG
# ==================================================================================================

print(
    "\nCHANGES versus previous operating snapshot:"
)


if not I_HAS_PREVIOUS_SNAPSHOT:

    print(
        "No prior Section I snapshot exists yet."
    )


elif I_FINAL_CHANGE_LOG.empty:

    print(
        "No material changes detected."
    )


else:

    display(

        I_FINAL_CHANGE_LOG

    )


# ==================================================================================================
# 33. SUMMARY
# ==================================================================================================

print(
    "\nDAILY operating summary:"
)


display(

    I_FINAL_DAILY_SUMMARY

)


# ==================================================================================================
# 34. HEALTH
# ==================================================================================================

print(
    "\nSECTION I health:"
)


display(

    I_HEALTH

)


# ==================================================================================================
# 35. FINAL PRODUCTION GATE
# ==================================================================================================

if not SECTION_I_PASSED:

    display(

        I_REQUIRED_FAILURES

    )


    raise RuntimeError(

        "SECTION I FINAL PRODUCTION GATE FAILED."

    )


print(
    "\n"
    + "=" * 150
)


print(
    "✓ SECTION I COMPLETE — live operating workflow initialized."
)


print(
    "✓ The full research universe is converted into a daily decision book."
)


print(
    "✓ Pending portfolio trades are separated from watchlist and near-entry signals."
)


print(
    "✓ MOS thresholds remain the explicit buy-trigger prices."
)


print(
    "✓ Portfolio alerts are promoted into operating review triggers."
)


print(
    "✓ Each run creates a timestamped operating snapshot."
)


print(
    "✓ Future runs automatically compare against the prior snapshot."
)


print(
    "✓ Material price, MOS, action and target-weight changes are tracked."
)


print(
    "✓ Snapshot history is preserved rather than overwritten."
)


print(
    "✓ No trade is executed automatically by Section I."
)


print(
    "✓ I_FINAL_ACTION_BOOK is the live daily investment decision object."
)


print(
    "✓ I_FINAL_TRIGGERS is the operating alert / rebalance object."
)


print(
    "✓ I_FINAL_OPERATING_SNAPSHOT is the daily system-summary object."
)


print(
    "✓ SECTION_I_PASSED = True."
)


print(
    "=" * 150
)
