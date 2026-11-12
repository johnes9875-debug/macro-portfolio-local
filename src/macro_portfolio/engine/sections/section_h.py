# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.

from scipy import stats as scipy_stats


# ===== ORIGINAL NOTEBOOK CELL 88 =====
# ==================================================================================================
# SECTION H — PORTFOLIO MONITORING / DASHBOARD ENGINE
#
# H1 — PORTFOLIO + BUY-ZONE MONITOR
# H2 — ALERT / REBALANCE ENGINE
# H3 — HISTORICAL REPLAY + STRESS TEST ENGINE
# H4 — PLOTLY DASHBOARD
# H5 — FINAL SECTION H FREEZE
#
# Prerequisite:
#
#       SECTION_G_PASSED == True
#
# Main final outputs:
#
#       H_FINAL_MONITORING_SNAPSHOT
#       H_FINAL_ALERTS
#       H_FINAL_STRESS_TESTS
#       H_FINAL_PORTFOLIO_DASHBOARD
#       H_FINAL_SUMMARY
#
# ==================================================================================================


# ==================================================================================================
# 1. IMPORTS
# ==================================================================================================

from pathlib import Path

import hashlib
import math
import warnings

import numpy as np
import pandas as pd

import plotly.graph_objects as go

from plotly.subplots import make_subplots


warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
)


# ==================================================================================================
# 2. VALIDATE UPSTREAM
# ==================================================================================================

required_h_objects = [

    "SECTION_G_PASSED",

    "G_FINAL_PORTFOLIO_WEIGHTS",
    "G_FINAL_PORTFOLIO_SUMMARY",
    "G_FINAL_TRADE_PLAN",
    "G_FINAL_RISK_SUMMARY",
    "G_FINAL_RISK_CONTRIBUTION",

    "G1_FINAL_ALPHA_HANDOFF",

    "G3_RESEARCH_RETURNS_ALIGNED",
    "G3_RISK_MODEL_HANDOFF",
    "G3_RESEARCH_TICKERS",

    "VALUATION_UNIVERSE_FREEZE_ID",

    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",

]


missing_h_objects = [

    obj

    for obj in required_h_objects

    if obj not in globals()

]


if missing_h_objects:

    raise RuntimeError(

        "Section H requires completed Section G objects. Missing: "
        f"{missing_h_objects}"

    )


if not bool(
    SECTION_G_PASSED
):

    raise RuntimeError(

        "Section G production gate did not pass."

    )


# ==================================================================================================
# 3. VERSION
# ==================================================================================================

H_VERSION = "1.0.0"


# ==================================================================================================
# 4. GENERAL CONFIGURATION
# ==================================================================================================

def h_cfg(
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


H_NAV = float(

    globals().get(

        "G6_NAV",

        h_cfg(
            [
                "portfolio",
                "initial_nav",
            ],
            1_000_000.0,
        ),

    )

)


H_MAX_STOCK_WEIGHT = float(

    globals().get(

        "G4_MAX_STOCK_WEIGHT",

        h_cfg(
            [
                "portfolio",
                "max_stock",
            ],
            0.10,
        ),

    )

)


H_MAX_SECTOR_WEIGHT = float(

    globals().get(

        "G4_MAX_SECTOR_WEIGHT",

        h_cfg(
            [
                "portfolio",
                "max_sector",
            ],
            0.30,
        ),

    )

)


H_RISK_FREE_RATE = float(

    globals().get(

        "G2_RISK_FREE_RATE",

        globals().get(
            "F4_RISK_FREE_RATE",
            0.0,
        ),

    )

)


H_TRADING_DAYS = int(

    globals().get(
        "G3_TRADING_DAYS",
        252,
    )

)


# ==================================================================================================
# 5. MONITORING POLICY
# ==================================================================================================

# ------------------------------------------------------------
# Distance ABOVE MOS threshold.
#
# Example:
#
#       0.03 = current price is 3% above buy threshold.
# ------------------------------------------------------------

H_NEAR_BUY_ZONE = float(cfg(["monitoring", "near_buy_zone"], 0.05))

H_WATCH_BUY_ZONE = float(cfg(["monitoring", "watch_buy_zone"], 0.10))


# ------------------------------------------------------------
# Portfolio concentration alerts.
# ------------------------------------------------------------

H_STOCK_CAP_ALERT_RATIO = float(cfg(["monitoring", "stock_cap_alert_ratio"], 0.95))

H_SECTOR_CAP_ALERT_RATIO = float(cfg(["monitoring", "sector_cap_alert_ratio"], 0.95))


# ------------------------------------------------------------
# Risk contribution alert.
# ------------------------------------------------------------

H_RISK_CONTRIBUTION_ALERT = float(cfg(["monitoring", "risk_contribution_alert"], 0.30))


# ------------------------------------------------------------
# Cash alert.
# ------------------------------------------------------------

H_HIGH_CASH_ALERT = float(cfg(["monitoring", "high_cash_alert"], 0.50))


# ------------------------------------------------------------
# Liquidity.
# ------------------------------------------------------------

H_LIQUIDITY_FAIL_TEXT = "FAIL"


# ------------------------------------------------------------
# Market-beta stress scenarios.
# ------------------------------------------------------------

H_MARKET_SHOCKS = dict(
    cfg(
        ["monitoring", "market_shocks"],
        {
            "MARKET_UP_10": 0.10,
            "MARKET_DOWN_5": -0.05,
            "MARKET_DOWN_10": -0.10,
            "MARKET_DOWN_20": -0.20,
        },
    )
)


# ==================================================================================================
# 6. MONITOR TIMESTAMP
# ==================================================================================================

H_AS_OF_TIMESTAMP = pd.Timestamp.now(

    tz="Asia/Singapore"

)


H_AS_OF_DATE = (

    H_AS_OF_TIMESTAMP
    .date()

)


# ==================================================================================================
# ==================================================================================================
# H1 — MASTER PORTFOLIO + BUY-ZONE MONITOR
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 7. START FROM FULL G1 RESEARCH UNIVERSE
# ==================================================================================================

H_MONITOR = (

    G1_FINAL_ALPHA_HANDOFF
    .copy()

)


H_MONITOR[
    "ticker"
] = (

    H_MONITOR[
        "ticker"
    ]
    .astype(str)

)


H_EXPECTED_UNIVERSE_COUNT = len(

    H_MONITOR

)


# ==================================================================================================
# 8. ATTACH FINAL TARGET PORTFOLIO WEIGHTS
# ==================================================================================================

portfolio_weight_columns = [

    column

    for column in [

        "ticker",

        "previous_weight",
        "target_weight",
        "delta_weight",

        "expected_total_return_annual",

    ]

    if column
    in
    G_FINAL_PORTFOLIO_WEIGHTS.columns

]


H_WEIGHT_INPUT = (

    G_FINAL_PORTFOLIO_WEIGHTS[

        G_FINAL_PORTFOLIO_WEIGHTS[
            "ticker"
        ]
        .astype(str)
        !=
        "CASH"

    ][
        portfolio_weight_columns
    ]

    .copy()

)


H_WEIGHT_INPUT[
    "ticker"
] = (

    H_WEIGHT_INPUT[
        "ticker"
    ]
    .astype(str)

)


H_WEIGHT_INPUT = (

    H_WEIGHT_INPUT

    .drop_duplicates(
        subset=[
            "ticker"
        ]
    )

)


H_MONITOR = (

    H_MONITOR

    .merge(

        H_WEIGHT_INPUT,

        on="ticker",

        how="left",

        validate="one_to_one",

        suffixes=(
            "",
            "_portfolio",
        ),

    )

)


for column in [

    "previous_weight",
    "target_weight",
    "delta_weight",

]:

    if column not in H_MONITOR.columns:

        H_MONITOR[
            column
        ] = 0.0


    H_MONITOR[
        column
    ] = (

        pd.to_numeric(

            H_MONITOR[
                column
            ],

            errors="coerce",

        )

        .fillna(
            0.0
        )

    )


# ==================================================================================================
# 9. ATTACH STOCK RISK METRICS
# ==================================================================================================

risk_attach_columns = [

    column

    for column in [

        "ticker",

        "valuation_beta",

        "optimizer_volatility_annual",

        "downside_volatility_annual",

        "maximum_drawdown",

        "historical_var_99_daily",

        "historical_cvar_99_daily",

        "average_correlation",

        "expected_return_to_risk",

        "expected_return_to_downside_risk",

    ]

    if column
    in
    G3_RISK_MODEL_HANDOFF.columns

]


H_RISK_INPUT = (

    G3_RISK_MODEL_HANDOFF[
        risk_attach_columns
    ]

    .copy()

    .drop_duplicates(
        subset=[
            "ticker"
        ]
    )

)


H_MONITOR = (

    H_MONITOR

    .merge(

        H_RISK_INPUT,

        on="ticker",

        how="left",

        validate="one_to_one",

    )

)


# ==================================================================================================
# 10. ATTACH RISK CONTRIBUTION
# ==================================================================================================

H_RISK_CONTRIBUTION_INPUT = (

    G_FINAL_RISK_CONTRIBUTION[
        [
            column

            for column in [

                "ticker",
                "component_risk",
                "risk_contribution_share",

            ]

            if column
            in
            G_FINAL_RISK_CONTRIBUTION.columns
        ]
    ]

    .copy()

)


if not H_RISK_CONTRIBUTION_INPUT.empty:

    H_MONITOR = (

        H_MONITOR

        .merge(

            H_RISK_CONTRIBUTION_INPUT,

            on="ticker",

            how="left",

            validate="one_to_one",

        )

    )


for column in [

    "component_risk",
    "risk_contribution_share",

]:

    if column not in H_MONITOR.columns:

        H_MONITOR[
            column
        ] = 0.0


    H_MONITOR[
        column
    ] = (

        pd.to_numeric(

            H_MONITOR[
                column
            ],

            errors="coerce",

        )

        .fillna(
            0.0
        )

    )


# ==================================================================================================
# 11. ATTACH TRADE / LIQUIDITY INFORMATION
# ==================================================================================================

trade_attach_columns = [

    column

    for column in [

        "ticker",

        "action",

        "trade_notional",

        "estimated_transaction_cost",

        "trade_pct_adv",

        "liquidity_check",

    ]

    if column
    in
    G_FINAL_TRADE_PLAN.columns

]


H_TRADE_INPUT = (

    G_FINAL_TRADE_PLAN[

        G_FINAL_TRADE_PLAN[
            "ticker"
        ]
        .astype(str)
        !=
        "CASH"

    ][
        trade_attach_columns
    ]

    .copy()

    .drop_duplicates(
        subset=[
            "ticker"
        ]
    )

)


H_MONITOR = (

    H_MONITOR

    .merge(

        H_TRADE_INPUT,

        on="ticker",

        how="left",

        validate="one_to_one",

    )

)


# ==================================================================================================
# 12. CURRENT PORTFOLIO FLAGS
# ==================================================================================================

H_MONITOR[
    "is_target_holding"
] = (

    H_MONITOR[
        "target_weight"
    ]

    >
    1e-10

)


H_MONITOR[
    "target_notional"
] = (

    H_MONITOR[
        "target_weight"
    ]

    *
    H_NAV

)


# ==================================================================================================
# 13. PRICE / MOS NUMERIC NORMALIZATION
# ==================================================================================================

for column in [

    "current_price",
    "mos_price_threshold",
    "expected_intrinsic_value",
    "expected_upside_pct",

]:

    if column in H_MONITOR.columns:

        H_MONITOR[
            column
        ] = pd.to_numeric(

            H_MONITOR[
                column
            ],

            errors="coerce",

        )


# ==================================================================================================
# 14. DISTANCE TO MOS
# ==================================================================================================

H_MONITOR[
    "distance_to_mos_pct"
] = np.where(

    (

        H_MONITOR[
            "current_price"
        ]
        >
        0

    )

    &

    (

        H_MONITOR[
            "mos_price_threshold"
        ]
        >
        0

    ),

    (

        H_MONITOR[
            "current_price"
        ]

        /
        H_MONITOR[
            "mos_price_threshold"
        ]

        -
        1.0

    ),

    np.nan,

)


# ==================================================================================================
# 15. PRICE / FAIR-VALUE GAP
# ==================================================================================================

H_MONITOR[
    "price_to_intrinsic_gap"
] = np.where(

    (

        H_MONITOR[
            "expected_intrinsic_value"
        ]
        >
        0

    ),

    (

        H_MONITOR[
            "current_price"
        ]

        /
        H_MONITOR[
            "expected_intrinsic_value"
        ]

        -
        1.0

    ),

    np.nan,

)


# ==================================================================================================
# 16. BUY-ZONE CLASSIFICATION
# ==================================================================================================

def h_buy_zone(
    row
):

    if not bool(

        row[
            "research_ranking_eligible"
        ]

    ):

        return (
            "BLOCKED_PROVISIONAL"
        )


    distance = row[
        "distance_to_mos_pct"
    ]


    if pd.isna(
        distance
    ):

        return (
            "PRICE_OR_MOS_UNAVAILABLE"
        )


    if distance <= 0:

        return (
            "BUY_ZONE"
        )


    if distance <= H_NEAR_BUY_ZONE:

        return (
            "NEAR_BUY_ZONE_0_5"
        )


    if distance <= H_WATCH_BUY_ZONE:

        return (
            "WATCH_BUY_ZONE_5_10"
        )


    return (
        "ABOVE_BUY_ZONE"
    )


H_MONITOR[
    "buy_zone"
] = (

    H_MONITOR

    .apply(

        h_buy_zone,

        axis=1,

    )

)


# ==================================================================================================
# 17. SECTOR TARGET EXPOSURE
# ==================================================================================================

H_SECTOR_MONITOR = (

    H_MONITOR

    .groupby(
        "sector_ticker",
        as_index=False,
    )

    .agg(

        target_weight=(

            "target_weight",
            "sum",

        ),

        stock_count=(

            "is_target_holding",
            "sum",

        ),

    )

)


H_SECTOR_MONITOR[
    "sector_cap"
] = (

    H_MAX_SECTOR_WEIGHT

)


H_SECTOR_MONITOR[
    "sector_headroom"
] = (

    H_MAX_SECTOR_WEIGHT

    -
    H_SECTOR_MONITOR[
        "target_weight"
    ]

)


H_SECTOR_MONITOR[
    "sector_utilization"
] = np.where(

    H_MAX_SECTOR_WEIGHT > 0,

    H_SECTOR_MONITOR[
        "target_weight"
    ]

    /
    H_MAX_SECTOR_WEIGHT,

    np.nan,

)


H_SECTOR_HEADROOM_MAP = (

    H_SECTOR_MONITOR

    .set_index(
        "sector_ticker"
    )[
        "sector_headroom"
    ]

    .to_dict()

)


# ==================================================================================================
# 18. STOCK CAPACITY
# ==================================================================================================

H_MONITOR[
    "stock_headroom"
] = (

    H_MAX_STOCK_WEIGHT

    -
    H_MONITOR[
        "target_weight"
    ]

)


H_MONITOR[
    "sector_headroom"
] = (

    H_MONITOR[
        "sector_ticker"
    ]

    .map(
        H_SECTOR_HEADROOM_MAP
    )

    .fillna(
        H_MAX_SECTOR_WEIGHT
    )

)


H_MONITOR[
    "maximum_additional_weight"
] = (

    np.minimum(

        H_MONITOR[
            "stock_headroom"
        ],

        H_MONITOR[
            "sector_headroom"
        ],

    )

    .clip(
        lower=0.0
    )

)


H_MONITOR[
    "maximum_additional_notional"
] = (

    H_MONITOR[
        "maximum_additional_weight"
    ]

    *
    H_NAV

)


# ==================================================================================================
# 19. MONITOR ACTION
# ==================================================================================================

def h_monitor_action(
    row
):

    eligible = bool(

        row[
            "research_ranking_eligible"
        ]

    )


    holding = bool(

        row[
            "is_target_holding"
        ]

    )


    buy_zone = str(

        row[
            "buy_zone"
        ]

    )


    add_capacity = float(

        row[
            "maximum_additional_weight"
        ]

    )


    if not eligible:

        return (
            "BLOCKED"
        )


    if holding:

        if buy_zone == "BUY_ZONE":

            if add_capacity > 1e-6:

                return (
                    "HOLD_ADD_ELIGIBLE"
                )


            return (
                "HOLD_CAP_REACHED"
            )


        return (
            "HOLD_NO_ADD"
        )


    if buy_zone == "BUY_ZONE":

        if add_capacity > 1e-6:

            return (
                "ENTRY_ELIGIBLE"
            )


        return (
            "ENTRY_BLOCKED_BY_CAP"
        )


    if buy_zone == "NEAR_BUY_ZONE_0_5":

        return (
            "WATCH_CLOSE"
        )


    if buy_zone == "WATCH_BUY_ZONE_5_10":

        return (
            "WATCH_NEAR"
        )


    return (
        "WATCH"
    )


H_MONITOR[
    "monitor_action"
] = (

    H_MONITOR

    .apply(

        h_monitor_action,

        axis=1,

    )

)


# ==================================================================================================
# 20. PORTFOLIO STATUS
# ==================================================================================================

H_MONITOR[
    "portfolio_status"
] = np.where(

    H_MONITOR[
        "is_target_holding"
    ],

    "HELD",

    np.where(

        H_MONITOR[
            "research_ranking_eligible"
        ],

        "WATCHLIST",

        "PROVISIONAL_BLOCKED",

    )

)


# ==================================================================================================
# 21. PRIORITY SCORE FOR MONITORING
# ==================================================================================================
#
# Higher = more relevant today.
#
# Uses:
#
#   confidence-adjusted alpha
#   closeness to MOS
#
# This is a monitoring priority only.
# It does NOT alter portfolio weights.
# ==================================================================================================

H_MONITOR[
    "mos_proximity_score"
] = (

    1.0

    -

    (

        H_MONITOR[
            "distance_to_mos_pct"
        ]

        /
        0.20

    )

)


H_MONITOR[
    "mos_proximity_score"
] = (

    H_MONITOR[
        "mos_proximity_score"
    ]

    .clip(
        lower=-1.0,
        upper=1.0,
    )

)


H_MONITOR[
    "monitor_priority_score"
] = (

    0.65

    *
    pd.to_numeric(

        H_MONITOR[
            "confidence_adjusted_master_alpha"
        ],

        errors="coerce",

    )
    .fillna(
        0.0
    )

    +

    0.35

    *
    H_MONITOR[
        "mos_proximity_score"
    ]
    .fillna(
        -1.0
    )

)


# ==================================================================================================
# ==================================================================================================
# H2 — ALERT / REBALANCE ENGINE
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 22. ALERT BUILDER
# ==================================================================================================

H_ALERT_ROWS = []


def h_add_alert(
    severity,
    alert_type,
    ticker,
    message,
    metric=np.nan,
    threshold=np.nan,
):

    H_ALERT_ROWS.append({

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
            H_AS_OF_TIMESTAMP,

    })


# ==================================================================================================
# 23. CASH ALERT
# ==================================================================================================

H_CASH_WEIGHT = float(

    G_FINAL_PORTFOLIO_WEIGHTS.loc[

        G_FINAL_PORTFOLIO_WEIGHTS[
            "ticker"
        ]
        .astype(str)
        ==
        "CASH",

        "target_weight",

    ]
    .iloc[0]

)


if H_CASH_WEIGHT >= H_HIGH_CASH_ALERT:

    h_add_alert(

        severity=
            "INFO",

        alert_type=
            "HIGH_CASH",

        ticker=
            "PORTFOLIO",

        message=(
            f"Cash allocation is {H_CASH_WEIGHT:.1%}, "
            "indicating substantial undeployed capital."
        ),

        metric=
            H_CASH_WEIGHT,

        threshold=
            H_HIGH_CASH_ALERT,

    )


# ==================================================================================================
# 24. STOCK CAP ALERTS
# ==================================================================================================

stock_cap_alert_threshold = (

    H_MAX_STOCK_WEIGHT

    *
    H_STOCK_CAP_ALERT_RATIO

)


for _, row in (

    H_MONITOR[

        H_MONITOR[
            "is_target_holding"
        ]

    ]

    .iterrows()

):

    if (

        row[
            "target_weight"
        ]

        >=
        stock_cap_alert_threshold

    ):

        h_add_alert(

            severity=
                "INFO",

            alert_type=
                "STOCK_CAP_UTILIZATION",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"{row['ticker']} target weight "
                f"{row['target_weight']:.1%} is near/at "
                f"the {H_MAX_STOCK_WEIGHT:.1%} stock cap."
            ),

            metric=
                row[
                    "target_weight"
                ],

            threshold=
                H_MAX_STOCK_WEIGHT,

        )


# ==================================================================================================
# 25. SECTOR CAP ALERTS
# ==================================================================================================

sector_alert_threshold = (

    H_MAX_SECTOR_WEIGHT

    *
    H_SECTOR_CAP_ALERT_RATIO

)


for _, row in (

    H_SECTOR_MONITOR
    .iterrows()

):

    if (

        row[
            "target_weight"
        ]

        >=
        sector_alert_threshold

    ):

        h_add_alert(

            severity=
                "WARNING",

            alert_type=
                "SECTOR_CAP_UTILIZATION",

            ticker=
                row[
                    "sector_ticker"
                ],

            message=(
                f"{row['sector_ticker']} allocation "
                f"{row['target_weight']:.1%} is near/at "
                f"the {H_MAX_SECTOR_WEIGHT:.1%} sector cap."
            ),

            metric=
                row[
                    "target_weight"
                ],

            threshold=
                H_MAX_SECTOR_WEIGHT,

        )


# ==================================================================================================
# 26. RISK CONTRIBUTION ALERTS
# ==================================================================================================

for _, row in (

    H_MONITOR[

        H_MONITOR[
            "is_target_holding"
        ]

    ]

    .iterrows()

):

    if (

        row[
            "risk_contribution_share"
        ]

        >=
        H_RISK_CONTRIBUTION_ALERT

    ):

        h_add_alert(

            severity=
                "WARNING",

            alert_type=
                "RISK_CONCENTRATION",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"{row['ticker']} contributes "
                f"{row['risk_contribution_share']:.1%} "
                "of portfolio volatility."
            ),

            metric=
                row[
                    "risk_contribution_share"
                ],

            threshold=
                H_RISK_CONTRIBUTION_ALERT,

        )


# ==================================================================================================
# 27. VALUATION REVIEW ALERTS
# ==================================================================================================

if (

    "valuation_review_required"
    in
    H_MONITOR.columns

):

    for _, row in (

        H_MONITOR[

            H_MONITOR[
                "is_target_holding"
            ]

            &

            H_MONITOR[
                "valuation_review_required"
            ]
            .fillna(False)

        ]

        .iterrows()

    ):

        h_add_alert(

            severity=
                "WARNING",

            alert_type=
                "VALUATION_REVIEW",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"{row['ticker']} is held but remains flagged "
                "for valuation-model review."
            ),

        )


# ==================================================================================================
# 28. LIQUIDITY ALERTS
# ==================================================================================================

if (

    "liquidity_check"
    in
    H_MONITOR.columns

):

    for _, row in (

        H_MONITOR[

            H_MONITOR[
                "liquidity_check"
            ]
            ==
            H_LIQUIDITY_FAIL_TEXT

        ]

        .iterrows()

    ):

        h_add_alert(

            severity=
                "CRITICAL",

            alert_type=
                "LIQUIDITY_LIMIT",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"{row['ticker']} trade exceeds the configured "
                "ADV participation limit."
            ),

            metric=
                row.get(
                    "trade_pct_adv",
                    np.nan,
                ),

        )


# ==================================================================================================
# 29. WATCHLIST NEAR MOS ALERTS
# ==================================================================================================

for _, row in (

    H_MONITOR[

        (

            ~
            H_MONITOR[
                "is_target_holding"
            ]

        )

        &

        (

            H_MONITOR[
                "buy_zone"
            ]
            ==
            "NEAR_BUY_ZONE_0_5"

        )

    ]

    .iterrows()

):

    h_add_alert(

        severity=
            "INFO",

        alert_type=
            "NEAR_MOS_ENTRY",

        ticker=
            row[
                "ticker"
            ],

        message=(
            f"{row['ticker']} is only "
            f"{row['distance_to_mos_pct']:.1%} above its "
            f"Current CONFIG-driven MOS entry threshold (base={float(cfg(['valuation', 'mos_base'], 0.15)):.0%})."
        ),

        metric=
            row[
                "distance_to_mos_pct"
            ],

        threshold=
            H_NEAR_BUY_ZONE,

    )


# ==================================================================================================
# 30. NEGATIVE EXPECTED-RETURN HOLDING ALERT
# ==================================================================================================

if (

    "expected_total_return_annual"
    in
    H_MONITOR.columns

):

    for _, row in (

        H_MONITOR[

            H_MONITOR[
                "is_target_holding"
            ]

            &

            (

                H_MONITOR[
                    "expected_total_return_annual"
                ]

                <
                H_RISK_FREE_RATE

            )

        ]

        .iterrows()

    ):

        h_add_alert(

            severity=
                "WARNING",

            alert_type=
                "RETURN_BELOW_CASH",

            ticker=
                row[
                    "ticker"
                ],

            message=(
                f"{row['ticker']} expected return "
                f"{row['expected_total_return_annual']:.1%} "
                f"is below cash return {H_RISK_FREE_RATE:.1%}."
            ),

            metric=
                row[
                    "expected_total_return_annual"
                ],

            threshold=
                H_RISK_FREE_RATE,

        )


# ==================================================================================================
# 31. ALERT TABLE
# ==================================================================================================

H_ALERTS = pd.DataFrame(

    H_ALERT_ROWS

)


if H_ALERTS.empty:

    H_ALERTS = pd.DataFrame(

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


severity_order = {

    "CRITICAL":
        0,

    "WARNING":
        1,

    "INFO":
        2,

}


H_ALERTS[
    "_severity_order"
] = (

    H_ALERTS[
        "severity"
    ]

    .map(
        severity_order
    )

    .fillna(
        99
    )

)


H_ALERTS = (

    H_ALERTS

    .sort_values(

        [
            "_severity_order",
            "ticker",
        ]

    )

    .drop(
        columns=[
            "_severity_order"
        ]
    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# ==================================================================================================
# H3 — HISTORICAL REPLAY + STRESS TEST ENGINE
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 32. TARGET WEIGHT VECTOR
# ==================================================================================================

H_WEIGHT_MAP = (

    H_MONITOR

    .set_index(
        "ticker"
    )[
        "target_weight"
    ]

    .to_dict()

)


H_RESEARCH_WEIGHT_VECTOR = np.array(

    [

        float(

            H_WEIGHT_MAP.get(

                ticker,
                0.0,

            )

        )

        for ticker
        in G3_RESEARCH_TICKERS

    ],

    dtype=float,

)


# ==================================================================================================
# 33. DAILY CASH RETURN
# ==================================================================================================

H_DAILY_CASH_RETURN = (

    (

        1.0
        +
        H_RISK_FREE_RATE

    )

    **

    (

        1.0
        /
        H_TRADING_DAYS

    )

    -
    1.0

)


# ==================================================================================================
# 34. HISTORICAL PORTFOLIO REPLAY
# ==================================================================================================
#
# IMPORTANT:
#
# This is a BACKCAST using today's target weights.
#
# It is NOT realized strategy performance and NOT an alpha
# backtest.
# ==================================================================================================

H_BACKCAST_DAILY_RETURNS = (

    G3_RESEARCH_RETURNS_ALIGNED[
        G3_RESEARCH_TICKERS
    ]
    .values

    @

    H_RESEARCH_WEIGHT_VECTOR

)


H_BACKCAST_DAILY_RETURNS = (

    H_BACKCAST_DAILY_RETURNS

    +

    H_CASH_WEIGHT

    *
    H_DAILY_CASH_RETURN

)


H_BACKCAST = pd.DataFrame({

    "date":

        G3_RESEARCH_RETURNS_ALIGNED.index,

    "daily_return":

        H_BACKCAST_DAILY_RETURNS,

})


H_BACKCAST = (

    H_BACKCAST

    .set_index(
        "date"
    )

)


# ==================================================================================================
# 35. CUMULATIVE WEALTH / DRAWDOWN
# ==================================================================================================

H_BACKCAST[
    "wealth"
] = (

    (

        1.0

        +

        H_BACKCAST[
            "daily_return"
        ]

    )

    .cumprod()

)


H_BACKCAST[
    "running_peak"
] = (

    H_BACKCAST[
        "wealth"
    ]
    .cummax()

)


H_BACKCAST[
    "drawdown"
] = (

    H_BACKCAST[
        "wealth"
    ]

    /
    H_BACKCAST[
        "running_peak"
    ]

    -
    1.0

)


# ==================================================================================================
# 36. ROLLING RETURNS
# ==================================================================================================

def h_rolling_compound_return(
    series,
    window,
):

    return (

        (

            1.0
            +
            series

        )

        .rolling(
            window
        )

        .apply(

            np.prod,

            raw=True,

        )

        -
        1.0

    )


H_BACKCAST[
    "rolling_5d_return"
] = (

    h_rolling_compound_return(

        H_BACKCAST[
            "daily_return"
        ],

        5,

    )

)


H_BACKCAST[
    "rolling_20d_return"
] = (

    h_rolling_compound_return(

        H_BACKCAST[
            "daily_return"
        ],

        20,

    )

)


# ==================================================================================================
# 37. WORST HISTORICAL WINDOWS
# ==================================================================================================

H_WORST_1D = float(

    H_BACKCAST[
        "daily_return"
    ]
    .min()

)


H_WORST_5D = float(

    H_BACKCAST[
        "rolling_5d_return"
    ]
    .min()

)


H_WORST_20D = float(

    H_BACKCAST[
        "rolling_20d_return"
    ]
    .min()

)


H_BACKCAST_MAX_DRAWDOWN = float(

    H_BACKCAST[
        "drawdown"
    ]
    .min()

)


# ==================================================================================================
# 38. PORTFOLIO BETA
# ==================================================================================================

H_BETA_MAP = (

    H_MONITOR

    .set_index(
        "ticker"
    )[
        "valuation_beta"
    ]

    .to_dict()

)


H_PORTFOLIO_BETA = float(

    sum(

        H_WEIGHT_MAP.get(

            ticker,
            0.0,

        )

        *

        g_beta

        for ticker, g_beta
        in [

            (

                ticker,

                float(

                    H_BETA_MAP.get(

                        ticker,
                        0.0,

                    )

                ),

            )

            for ticker
            in H_WEIGHT_MAP

            if pd.notna(

                H_BETA_MAP.get(

                    ticker,
                    np.nan,

                )

            )

        ]

    )

)


# ==================================================================================================
# 39. BETA STRESS TESTS
# ==================================================================================================

stress_rows = []


for scenario_name, market_shock in (

    H_MARKET_SHOCKS.items()

):

    estimated_portfolio_return = (

        H_PORTFOLIO_BETA

        *
        market_shock

    )


    estimated_pnl = (

        estimated_portfolio_return

        *
        H_NAV

    )


    stress_rows.append({

        "scenario":
            scenario_name,

        "scenario_type":
            "BETA_MARKET_SHOCK",

        "market_shock":
            market_shock,

        "portfolio_beta":
            H_PORTFOLIO_BETA,

        "estimated_portfolio_return":
            estimated_portfolio_return,

        "estimated_pnl":
            estimated_pnl,

        "interpretation":
            "Linear beta-only stress; excludes nonlinear/sector-specific effects.",

    })


# ==================================================================================================
# 40. HISTORICAL REPLAY STRESS ROWS
# ==================================================================================================

for scenario_name, portfolio_return in [

    (
        "HISTORICAL_REPLAY_WORST_1D",
        H_WORST_1D,
    ),

    (
        "HISTORICAL_REPLAY_WORST_5D",
        H_WORST_5D,
    ),

    (
        "HISTORICAL_REPLAY_WORST_20D",
        H_WORST_20D,
    ),

    (
        "HISTORICAL_REPLAY_MAX_DRAWDOWN",
        H_BACKCAST_MAX_DRAWDOWN,
    ),

]:

    stress_rows.append({

        "scenario":
            scenario_name,

        "scenario_type":
            "CURRENT_WEIGHT_HISTORICAL_REPLAY",

        "market_shock":
            np.nan,

        "portfolio_beta":
            H_PORTFOLIO_BETA,

        "estimated_portfolio_return":
            portfolio_return,

        "estimated_pnl":
            portfolio_return
            *
            H_NAV,

        "interpretation":
            (
                "Historical replay using current target weights; "
                "not realized strategy performance."
            ),

    })


H_STRESS_TESTS = pd.DataFrame(

    stress_rows

)


# ==================================================================================================
# 41. PORTFOLIO EXPECTED METRICS
# ==================================================================================================

H_G_SUMMARY = (

    G_FINAL_PORTFOLIO_SUMMARY
    .iloc[0]
    .to_dict()

)


H_EXPECTED_RETURN = float(

    H_G_SUMMARY[
        "expected_return_gross"
    ]

)


H_EXPECTED_NET_RETURN = float(

    H_G_SUMMARY[
        "expected_return_net_first_year"
    ]

)


H_EXPECTED_VOLATILITY = float(

    H_G_SUMMARY[
        "expected_volatility"
    ]

)


H_STRESS_VOLATILITY = float(

    H_G_SUMMARY[
        "stress_volatility"
    ]

)


H_EXPECTED_SHARPE = float(

    H_G_SUMMARY[
        "expected_sharpe"
    ]

)


H_EXPECTED_SORTINO = float(

    H_G_SUMMARY[
        "expected_sortino"
    ]

)


H_EXPECTED_CALMAR = float(

    H_G_SUMMARY[
        "expected_calmar"
    ]

)


H_MC_PROBABILITY_OF_LOSS = float(

    H_G_SUMMARY[
        "monte_carlo_probability_of_loss"
    ]

)


# ==================================================================================================
# 42. DASHBOARD WATCHLIST
# ==================================================================================================

H_BUY_WATCHLIST = (

    H_MONITOR[

        H_MONITOR[
            "research_ranking_eligible"
        ]

    ][
        [
            "ticker",
            "company_name",

            "sector_ticker",

            "current_price",
            "mos_price_threshold",
            "expected_intrinsic_value",

            "distance_to_mos_pct",

            "buy_zone",

            "monitor_action",

            "master_alpha_rank",
            "confidence_adjusted_master_alpha",

            "target_weight",

            "maximum_additional_weight",
            "maximum_additional_notional",

        ]
    ]

    .copy()

    .sort_values(

        [
            "distance_to_mos_pct",
            "master_alpha_rank",
        ],

        ascending=[
            True,
            True,
        ],

    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# 43. CURRENT HOLDING MONITOR
# ==================================================================================================

H_HOLDING_MONITOR = (

    H_MONITOR[

        H_MONITOR[
            "is_target_holding"
        ]

    ]

    .copy()

    .sort_values(

        "target_weight",

        ascending=False,

    )

    .reset_index(
        drop=True
    )

)


# ==================================================================================================
# ==================================================================================================
# H4 — PLOTLY DASHBOARD
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 44. DASHBOARD DIRECTORY
# ==================================================================================================

H_DASHBOARD_DIR = (

    Path(
        STOCK_OUTPUT_DIR
    )

    /
    "dashboard"

)


H_DASHBOARD_DIR.mkdir(

    parents=True,
    exist_ok=True,

)


H_DASHBOARD_HTML = (

    H_DASHBOARD_DIR

    /
    "portfolio_monitor_dashboard.html"

)


# ==================================================================================================
# 45. PREPARE DASHBOARD TABLES
# ==================================================================================================

dashboard_weights = (

    G_FINAL_PORTFOLIO_WEIGHTS[
        [
            "ticker",
            "target_weight",
        ]
    ]

    .copy()

    .sort_values(

        "target_weight",

        ascending=False,

    )

)


dashboard_sector = (

    H_SECTOR_MONITOR

    .sort_values(

        "target_weight",

        ascending=False,

    )

)


dashboard_risk = (

    H_HOLDING_MONITOR[
        [
            "ticker",
            "risk_contribution_share",
        ]
    ]

    .copy()

    .sort_values(

        "risk_contribution_share",

        ascending=False,

    )

)


dashboard_mos = (

    H_BUY_WATCHLIST

    .head(
        15
    )

    .copy()

)


# ==================================================================================================
# 46. CREATE DASHBOARD
# ==================================================================================================

H_DASHBOARD = make_subplots(

    rows=3,
    cols=2,

    subplot_titles=(

        "Target portfolio weights",

        "Sector allocation",

        "Portfolio risk contribution",

        "Closest stocks to MOS buy threshold",

        "Current-weight historical drawdown replay",

        "Held stocks: expected return vs volatility",

    ),

    vertical_spacing=
        0.10,

    horizontal_spacing=
        0.10,

)


# ==================================================================================================
# 47. PORTFOLIO WEIGHTS
# ==================================================================================================

H_DASHBOARD.add_trace(

    go.Bar(

        x=
            dashboard_weights[
                "ticker"
            ],

        y=
            100.0
            *
            dashboard_weights[
                "target_weight"
            ],

        name=
            "Weight",

        text=
            (
                100.0
                *
                dashboard_weights[
                    "target_weight"
                ]
            )
            .round(
                1
            ),

        texttemplate=
            "%{text:.1f}%",

        hovertemplate=
            "%{x}: %{y:.2f}%<extra></extra>",

    ),

    row=1,
    col=1,

)


# ==================================================================================================
# 48. SECTOR ALLOCATION
# ==================================================================================================

H_DASHBOARD.add_trace(

    go.Bar(

        x=
            dashboard_sector[
                "sector_ticker"
            ],

        y=
            100.0
            *
            dashboard_sector[
                "target_weight"
            ],

        name=
            "Sector",

        text=
            (
                100.0
                *
                dashboard_sector[
                    "target_weight"
                ]
            )
            .round(
                1
            ),

        texttemplate=
            "%{text:.1f}%",

        hovertemplate=
            "%{x}: %{y:.2f}%<extra></extra>",

    ),

    row=1,
    col=2,

)


# ==================================================================================================
# 49. RISK CONTRIBUTION
# ==================================================================================================

H_DASHBOARD.add_trace(

    go.Bar(

        x=
            dashboard_risk[
                "ticker"
            ],

        y=
            100.0
            *
            dashboard_risk[
                "risk_contribution_share"
            ],

        name=
            "Risk contribution",

        text=
            (
                100.0
                *
                dashboard_risk[
                    "risk_contribution_share"
                ]
            )
            .round(
                1
            ),

        texttemplate=
            "%{text:.1f}%",

        hovertemplate=
            "%{x}: %{y:.2f}%<extra></extra>",

    ),

    row=2,
    col=1,

)


# ==================================================================================================
# 50. DISTANCE TO MOS
# ==================================================================================================

H_DASHBOARD.add_trace(

    go.Bar(

        x=
            dashboard_mos[
                "ticker"
            ],

        y=
            100.0
            *
            dashboard_mos[
                "distance_to_mos_pct"
            ],

        name=
            "Distance to MOS",

        text=
            (
                100.0
                *
                dashboard_mos[
                    "distance_to_mos_pct"
                ]
            )
            .round(
                1
            ),

        texttemplate=
            "%{text:.1f}%",

        hovertemplate=(
            "%{x}<br>"
            "Distance to MOS: %{y:.2f}%"
            "<extra></extra>"
        ),

    ),

    row=2,
    col=2,

)


H_DASHBOARD.add_hline(

    y=0.0,

    row=2,
    col=2,

)


# ==================================================================================================
# 51. DRAWDOWN REPLAY
# ==================================================================================================

H_DASHBOARD.add_trace(

    go.Scatter(

        x=
            H_BACKCAST.index,

        y=
            100.0
            *
            H_BACKCAST[
                "drawdown"
            ],

        mode=
            "lines",

        name=
            "Drawdown",

        hovertemplate=(
            "%{x}<br>"
            "Drawdown: %{y:.2f}%"
            "<extra></extra>"
        ),

    ),

    row=3,
    col=1,

)


# ==================================================================================================
# 52. EXPECTED RETURN VS RISK
# ==================================================================================================

if not H_HOLDING_MONITOR.empty:

    H_DASHBOARD.add_trace(

        go.Scatter(

            x=
                100.0
                *
                H_HOLDING_MONITOR[
                    "optimizer_volatility_annual"
                ],

            y=
                100.0
                *
                H_HOLDING_MONITOR[
                    "expected_total_return_annual"
                ],

            mode=
                "markers+text",

            text=
                H_HOLDING_MONITOR[
                    "ticker"
                ],

            textposition=
                "top center",

            marker=dict(

                size=
                    12
                    +
                    50
                    *
                    H_HOLDING_MONITOR[
                        "target_weight"
                    ],

            ),

            name=
                "Holdings",

            hovertemplate=(
                "%{text}<br>"
                "Volatility: %{x:.2f}%<br>"
                "Expected return: %{y:.2f}%"
                "<extra></extra>"
            ),

        ),

        row=3,
        col=2,

    )


# ==================================================================================================
# 53. DASHBOARD LAYOUT
# ==================================================================================================

H_DASHBOARD.update_yaxes(

    title_text=
        "Weight (%)",

    row=1,
    col=1,

)


H_DASHBOARD.update_yaxes(

    title_text=
        "Weight (%)",

    row=1,
    col=2,

)


H_DASHBOARD.update_yaxes(

    title_text=
        "Risk contribution (%)",

    row=2,
    col=1,

)


H_DASHBOARD.update_yaxes(

    title_text=
        "Distance (%)",

    row=2,
    col=2,

)


H_DASHBOARD.update_yaxes(

    title_text=
        "Drawdown (%)",

    row=3,
    col=1,

)


H_DASHBOARD.update_xaxes(

    title_text=
        "Volatility (%)",

    row=3,
    col=2,

)


H_DASHBOARD.update_yaxes(

    title_text=
        "Expected return (%)",

    row=3,
    col=2,

)


H_DASHBOARD.update_layout(

    title=(

        "Macro Portfolio — Monitoring Dashboard"
        "<br>"
        f"<sup>"
        f"As of {H_AS_OF_TIMESTAMP.strftime('%Y-%m-%d %H:%M %Z')} | "
        f"Expected return {H_EXPECTED_RETURN:.2%} | "
        f"Vol {H_EXPECTED_VOLATILITY:.2%} | "
        f"Sharpe {H_EXPECTED_SHARPE:.2f} | "
        f"Cash {H_CASH_WEIGHT:.2%}"
        f"</sup>"

    ),

    height=
        1250,

    showlegend=
        False,

    template=
        "plotly_white",

)


# ==================================================================================================
# 54. SAVE DASHBOARD
# ==================================================================================================

H_DASHBOARD.write_html(

    H_DASHBOARD_HTML,

    include_plotlyjs=
        "cdn",

    full_html=
        True,

)


H_DASHBOARD_EXISTS = (

    H_DASHBOARD_HTML.exists()

)


# ==================================================================================================
# ==================================================================================================
# H5 — FINAL SECTION H FREEZE
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 55. FINAL MONITORING SNAPSHOT
# ==================================================================================================

H_FINAL_MONITORING_SNAPSHOT = (

    H_MONITOR[
        [
            "ticker",
            "company_name",

            "sector_ticker",
            "allocation_bucket",

            "portfolio_status",

            "current_price",

            "mos_price_threshold",
            "expected_intrinsic_value",

            "distance_to_mos_pct",
            "price_to_intrinsic_gap",

            "buy_zone",
            "monitor_action",

            "previous_weight",
            "target_weight",
            "delta_weight",

            "target_notional",

            "stock_headroom",
            "sector_headroom",

            "maximum_additional_weight",
            "maximum_additional_notional",

            "expected_total_return_annual",

            "optimizer_volatility_annual",
            "downside_volatility_annual",

            "maximum_drawdown",
            "historical_cvar_99_daily",

            "risk_contribution_share",

            "valuation_beta",

            "master_alpha_rank",
            "confidence_adjusted_master_alpha",

            "monitor_priority_score",

            "research_ranking_eligible",
            "valuation_review_required",

        ]
    ]

    .copy()

)


# ==================================================================================================
# 56. FINAL ALERTS
# ==================================================================================================

H_FINAL_ALERTS = (

    H_ALERTS
    .copy()

)


# ==================================================================================================
# 57. FINAL STRESS TESTS
# ==================================================================================================

H_FINAL_STRESS_TESTS = (

    H_STRESS_TESTS
    .copy()

)


# ==================================================================================================
# 58. HOLDING COUNT / WATCHLIST COUNT
# ==================================================================================================

H_HOLDING_COUNT = int(

    H_FINAL_MONITORING_SNAPSHOT[
        "target_weight"
    ]
    .gt(
        1e-10
    )
    .sum()

)


H_BUY_ZONE_COUNT = int(

    (

        H_FINAL_MONITORING_SNAPSHOT[
            "buy_zone"
        ]
        ==
        "BUY_ZONE"

    )
    .sum()

)


H_NEAR_BUY_COUNT = int(

    (

        H_FINAL_MONITORING_SNAPSHOT[
            "buy_zone"
        ]
        ==
        "NEAR_BUY_ZONE_0_5"

    )
    .sum()

)


H_ALERT_COUNT = len(

    H_FINAL_ALERTS

)


H_WARNING_COUNT = int(

    H_FINAL_ALERTS[
        "severity"
    ]
    .isin(
        [
            "WARNING",
            "CRITICAL",
        ]
    )
    .sum()

)


# ==================================================================================================
# 59. HEALTH CHECKS
# ==================================================================================================

H_MONITOR_COVERAGE_VALID = bool(

    len(
        H_FINAL_MONITORING_SNAPSHOT
    )

    ==
    H_EXPECTED_UNIVERSE_COUNT

)


H_WEIGHT_SUM = float(

    H_FINAL_MONITORING_SNAPSHOT[
        "target_weight"
    ]
    .sum()

    +
    H_CASH_WEIGHT

)


H_WEIGHT_SUM_VALID = bool(

    np.isclose(

        H_WEIGHT_SUM,

        1.0,

        atol=1e-7,
        rtol=1e-7,

    )

)


H_BLOCKED_HOLDING_COUNT = int(

    (

        (

            H_FINAL_MONITORING_SNAPSHOT[
                "target_weight"
            ]

            >
            1e-10

        )

        &

        (

            ~
            H_FINAL_MONITORING_SNAPSHOT[
                "research_ranking_eligible"
            ]

        )

    )
    .sum()

)


H_STRESS_VALID = bool(

    safe_isfinite(

        H_FINAL_STRESS_TESTS[
            "estimated_portfolio_return"
        ]

    )
    .all()

)


H_SECTION_HEALTH = pd.DataFrame([

    {

        "check":
            "Section G remains passed",

        "passed":
            bool(
                SECTION_G_PASSED
            ),

        "required":
            True,

        "detail":
            "SECTION_G_PASSED=True",

    },

    {

        "check":
            "Full research universe covered by monitor",

        "passed":
            H_MONITOR_COVERAGE_VALID,

        "required":
            True,

        "detail":
            (
                f"coverage="
                f"{len(H_FINAL_MONITORING_SNAPSHOT)}/"
                f"{H_EXPECTED_UNIVERSE_COUNT}"
            ),

    },

    {

        "check":
            "Portfolio weights reconcile including cash",

        "passed":
            H_WEIGHT_SUM_VALID,

        "required":
            True,

        "detail":
            (
                f"weight_sum="
                f"{H_WEIGHT_SUM:.8f}"
            ),

    },

    {

        "check":
            "No provisional company is held",

        "passed":
            H_BLOCKED_HOLDING_COUNT
            ==
            0,

        "required":
            True,

        "detail":
            (
                f"violations="
                f"{H_BLOCKED_HOLDING_COUNT}"
            ),

    },

    {

        "check":
            "Stress-test outputs are finite",

        "passed":
            H_STRESS_VALID,

        "required":
            True,

        "detail":
            (
                f"scenarios="
                f"{len(H_FINAL_STRESS_TESTS)}"
            ),

    },

    {

        "check":
            "Dashboard HTML successfully created",

        "passed":
            H_DASHBOARD_EXISTS,

        "required":
            True,

        "detail":
            str(
                H_DASHBOARD_HTML
            ),

    },

    {

        "check":
            "Historical replay remains explicitly non-backtest",

        "passed":
            True,

        "required":
            True,

        "detail":
            (
                "current-weight historical replay only; "
                "no historical alpha-performance claim"
            ),

    },

])


H_SECTION_HEALTH[
    "status"
] = np.where(

    H_SECTION_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


H_REQUIRED_FAILURES = (

    H_SECTION_HEALTH[

        H_SECTION_HEALTH[
            "required"
        ]

        &

        ~
        H_SECTION_HEALTH[
            "passed"
        ]

    ]

)


SECTION_H_PASSED = (

    H_REQUIRED_FAILURES.empty

)


# ==================================================================================================
# 60. HASH FINAL MONITOR
# ==================================================================================================

H_HASH_FRAME = (

    H_FINAL_MONITORING_SNAPSHOT[
        [
            "ticker",

            "current_price",
            "mos_price_threshold",

            "buy_zone",

            "target_weight",

            "maximum_additional_weight",

            "monitor_action",

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


H_MONITOR_SHA256 = hashlib.sha256(

    pd.util.hash_pandas_object(

        H_HASH_FRAME,
        index=False,

    )
    .values
    .tobytes()

).hexdigest()


# ==================================================================================================
# 61. FINAL SUMMARY
# ==================================================================================================

H_FINAL_SUMMARY = pd.DataFrame([{

    "section":
        "H",

    "version":
        H_VERSION,

    "as_of":
        H_AS_OF_TIMESTAMP,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "monitor_sha256":
        H_MONITOR_SHA256,

    "research_universe":
        H_EXPECTED_UNIVERSE_COUNT,

    "stock_holdings":
        H_HOLDING_COUNT,

    "cash_weight":
        H_CASH_WEIGHT,

    "buy_zone_names":
        H_BUY_ZONE_COUNT,

    "near_buy_zone_names":
        H_NEAR_BUY_COUNT,

    "alerts":
        H_ALERT_COUNT,

    "warning_or_critical_alerts":
        H_WARNING_COUNT,

    "portfolio_beta":
        H_PORTFOLIO_BETA,

    "expected_return":
        H_EXPECTED_RETURN,

    "expected_net_return":
        H_EXPECTED_NET_RETURN,

    "expected_volatility":
        H_EXPECTED_VOLATILITY,

    "stress_volatility":
        H_STRESS_VOLATILITY,

    "expected_sharpe":
        H_EXPECTED_SHARPE,

    "expected_sortino":
        H_EXPECTED_SORTINO,

    "expected_calmar":
        H_EXPECTED_CALMAR,

    "monte_carlo_probability_of_loss":
        H_MC_PROBABILITY_OF_LOSS,

    "historical_replay_worst_1d":
        H_WORST_1D,

    "historical_replay_worst_5d":
        H_WORST_5D,

    "historical_replay_worst_20d":
        H_WORST_20D,

    "historical_replay_max_drawdown":
        H_BACKCAST_MAX_DRAWDOWN,

    "dashboard_path":
        str(
            H_DASHBOARD_HTML
        ),

    "historical_alpha_backtest_eligible":
        False,

    "section_h_passed":
        SECTION_H_PASSED,

}])


# ==================================================================================================
# 62. SAVE SECTION H OUTPUTS
# ==================================================================================================

H_FINAL_MONITORING_SNAPSHOT.to_parquet(

    STOCK_MODEL_DIR
    /
    "h_final_monitoring_snapshot.parquet",

    index=False,

)


H_FINAL_MONITORING_SNAPSHOT.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_final_monitoring_snapshot.csv",

    index=False,

)


H_BUY_WATCHLIST.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_buy_watchlist.csv",

    index=False,

)


H_HOLDING_MONITOR.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_holding_monitor.csv",

    index=False,

)


H_SECTOR_MONITOR.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_sector_monitor.csv",

    index=False,

)


H_FINAL_ALERTS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_alerts.csv",

    index=False,

)


H_FINAL_STRESS_TESTS.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_stress_tests.csv",

    index=False,

)


H_BACKCAST.to_parquet(

    STOCK_MODEL_DIR
    /
    "h_current_weight_historical_replay.parquet",

)


H_BACKCAST.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_current_weight_historical_replay.csv",

)


H_SECTION_HEALTH.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_health.csv",

    index=False,

)


H_FINAL_SUMMARY.to_csv(

    STOCK_OUTPUT_DIR
    /
    "h_final_summary.csv",

    index=False,

)


# ==================================================================================================
# 63. PROMOTE FINAL H OBJECTS
# ==================================================================================================

if SECTION_H_PASSED:

    H_FINAL_PORTFOLIO_DASHBOARD = (

        H_DASHBOARD

    )


    H_FINAL_BUY_WATCHLIST = (

        H_BUY_WATCHLIST
        .copy()

    )


    H_FINAL_HOLDING_MONITOR = (

        H_HOLDING_MONITOR
        .copy()

    )


    H_FINAL_SECTOR_MONITOR = (

        H_SECTOR_MONITOR
        .copy()

    )


# ==================================================================================================
# ==================================================================================================
# DISPLAY — SECTION H
# ==================================================================================================
# ==================================================================================================


# ==================================================================================================
# 64. HEADER
# ==================================================================================================

print(
    "=" * 150
)

print(
    "SECTION H — PORTFOLIO MONITORING / DASHBOARD ENGINE"
)

print(
    "=" * 150
)


print(
    f"As of:                              "
    f"{H_AS_OF_TIMESTAMP}"
)


print(
    f"Research universe:                  "
    f"{H_EXPECTED_UNIVERSE_COUNT}"
)


print(
    f"Current stock holdings:             "
    f"{H_HOLDING_COUNT}"
)


print(
    f"Cash allocation:                    "
    f"{H_CASH_WEIGHT:.2%}"
)


print(
    f"Portfolio beta:                     "
    f"{H_PORTFOLIO_BETA:.3f}"
)


print(
    f"Expected return:                    "
    f"{H_EXPECTED_RETURN:.2%}"
)


print(
    f"Expected volatility:                "
    f"{H_EXPECTED_VOLATILITY:.2%}"
)


print(
    f"Expected Sharpe:                    "
    f"{H_EXPECTED_SHARPE:.3f}"
)


print(
    f"Buy-zone names:                     "
    f"{H_BUY_ZONE_COUNT}"
)


print(
    f"Near-buy-zone names:                "
    f"{H_NEAR_BUY_COUNT}"
)


print(
    f"Alerts:                             "
    f"{H_ALERT_COUNT}"
)


print(
    f"Warning / critical alerts:          "
    f"{H_WARNING_COUNT}"
)


print(
    f"Dashboard:                          "
    f"{H_DASHBOARD_HTML}"
)


# ==================================================================================================
# 65. CURRENT HOLDINGS
# ==================================================================================================

print(
    "\nCURRENT portfolio monitor:"
)


display(

    H_HOLDING_MONITOR[
        [
            "ticker",
            "company_name",

            "sector_ticker",

            "current_price",
            "mos_price_threshold",
            "expected_intrinsic_value",

            "distance_to_mos_pct",

            "target_weight",

            "risk_contribution_share",

            "expected_total_return_annual",

            "optimizer_volatility_annual",

            "maximum_additional_weight",

            "buy_zone",
            "monitor_action",
        ]
    ]

)


# ==================================================================================================
# 66. BUY WATCHLIST
# ==================================================================================================

print(
    "\nBUY / MOS watchlist:"
)


display(

    H_BUY_WATCHLIST[
        [
            "ticker",
            "company_name",

            "sector_ticker",

            "current_price",
            "mos_price_threshold",

            "distance_to_mos_pct",

            "buy_zone",
            "monitor_action",

            "master_alpha_rank",

            "confidence_adjusted_master_alpha",

            "target_weight",

            "maximum_additional_weight",
            "maximum_additional_notional",
        ]
    ]

    .head(
        20
    )

)


# ==================================================================================================
# 67. SECTOR MONITOR
# ==================================================================================================

print(
    "\nSECTOR exposure monitor:"
)


display(

    H_SECTOR_MONITOR

    .sort_values(

        "target_weight",

        ascending=False,

    )

)


# ==================================================================================================
# 68. ALERTS
# ==================================================================================================

print(
    "\nPORTFOLIO alerts:"
)


if H_FINAL_ALERTS.empty:

    print(
        "No active alerts."
    )


else:

    display(

        H_FINAL_ALERTS

    )


# ==================================================================================================
# 69. STRESS TESTS
# ==================================================================================================

print(
    "\nSTRESS / historical replay tests:"
)


display(

    H_FINAL_STRESS_TESTS[
        [
            "scenario",
            "scenario_type",

            "market_shock",
            "portfolio_beta",

            "estimated_portfolio_return",
            "estimated_pnl",

            "interpretation",
        ]
    ]

)


# ==================================================================================================
# 70. HISTORICAL REPLAY SUMMARY
# ==================================================================================================

print(
    "\nCurrent-weight historical replay:"
)


H_REPLAY_SUMMARY = pd.DataFrame([{

    "worst_1d":
        H_WORST_1D,

    "worst_5d":
        H_WORST_5D,

    "worst_20d":
        H_WORST_20D,

    "maximum_drawdown":
        H_BACKCAST_MAX_DRAWDOWN,

}])


display(

    H_REPLAY_SUMMARY

)


# ==================================================================================================
# 71. HEALTH
# ==================================================================================================

print(
    "\nSECTION H health:"
)


display(

    H_SECTION_HEALTH

)


print(
    "\nSECTION H summary:"
)


display(

    H_FINAL_SUMMARY

)


# ==================================================================================================
# 72. DISPLAY DASHBOARD
# ==================================================================================================

H_AUTO_SHOW_DASHBOARD = bool(
    cfg(["monitoring", "auto_show_dashboard"], False)
)

if H_AUTO_SHOW_DASHBOARD:
    H_DASHBOARD.show()
else:
    print("Dashboard rendering skipped (monitoring.auto_show_dashboard=False). HTML output was still generated.")


# ==================================================================================================
# 73. FINAL PRODUCTION GATE
# ==================================================================================================

if not SECTION_H_PASSED:

    display(

        H_REQUIRED_FAILURES

    )


    raise RuntimeError(

        "SECTION H FINAL PRODUCTION GATE FAILED."

    )


print(
    "\n"
    + "=" * 150
)


print(
    "✓ SECTION H COMPLETE AND FROZEN."
)


print(
    "✓ Portfolio holdings, cash, sector exposure and risk contributions are monitored."
)


print(
    "✓ Every ranking-eligible company has a live MOS / buy-zone status."
)


print(
    "✓ Stock and sector capacity-to-add are calculated before any future purchase."
)


print(
    "✓ Portfolio concentration, valuation-review, liquidity and near-entry alerts are generated."
)


print(
    "✓ Historical risk replay uses current target weights and is explicitly NOT treated as strategy backtesting."
)


print(
    "✓ Market-shock stress tests use the portfolio's current weighted beta."
)


print(
    "✓ Plotly monitoring dashboard has been saved as HTML."
)


print(
    "✓ H_FINAL_MONITORING_SNAPSHOT is the main monitoring table."
)


print(
    "✓ H_FINAL_BUY_WATCHLIST is the live buy-price / MOS watchlist."
)


print(
    "✓ H_FINAL_ALERTS is the portfolio alert object."
)


print(
    "✓ H_FINAL_STRESS_TESTS is the stress-testing handoff."
)


print(
    "✓ H_FINAL_PORTFOLIO_DASHBOARD is the interactive dashboard object."
)


print(
    "✓ SECTION_H_PASSED = True."
)


print(
    "=" * 150
)


# ===== ORIGINAL NOTEBOOK CELL 89 =====
# ==================================================================================================
# CELL H5 — EXECUTION COCKPIT DASHBOARD V1.0.0
# ==================================================================================================
H5_VERSION = "1.0.0"
H5_DASHBOARD_DIR = Path(STOCK_OUTPUT_DIR) / "dashboard"
H5_DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
H5_EXECUTION_DASHBOARD_HTML = H5_DASHBOARD_DIR / "execution_cockpit.html"
trade_cols = [c for c in [
    "ticker", "company_name", "previous_weight", "target_weight", "delta_weight",
    "action", "trade_required", "trade_notional", "estimated_transaction_cost",
    "trade_pct_adv", "liquidity_check"
] if c in G_FINAL_TRADE_PLAN.columns]
monitor_cols = [c for c in [
    "ticker", "current_price", "mos_price_threshold", "distance_to_mos_pct",
    "buy_zone", "risk_contribution_share", "sector_ticker"
] if c in H_FINAL_MONITORING_SNAPSHOT.columns]
H5_EXECUTION_SHEET = G_FINAL_TRADE_PLAN[trade_cols].copy().merge(
    H_FINAL_MONITORING_SNAPSHOT[monitor_cols].drop_duplicates("ticker"),
    on="ticker", how="left", validate="many_to_one"
)
H5_EXECUTION_SHEET = H5_EXECUTION_SHEET[H5_EXECUTION_SHEET["ticker"].astype(str) != "CASH"].copy()

def h5_numeric_series(frame, column, default=np.nan):
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)

H5_EXECUTION_SHEET["abs_trade_notional"] = h5_numeric_series(
    H5_EXECUTION_SHEET, "trade_notional", 0.0
).fillna(0.0).abs()
_h5_current_price = h5_numeric_series(H5_EXECUTION_SHEET, "current_price", np.nan)
H5_EXECUTION_SHEET["estimated_shares"] = np.where(
    _h5_current_price > 0,
    H5_EXECUTION_SHEET["abs_trade_notional"] / _h5_current_price,
    np.nan,
)
H5_EXECUTION_SHEET = H5_EXECUTION_SHEET.sort_values(["trade_required", "abs_trade_notional"], ascending=[False, False]).reset_index(drop=True)
H5_EXECUTION_SHEET.to_csv(H5_DASHBOARD_DIR / "execution_trade_sheet.csv", index=False)
if "G9_PATH_MC_RETURNS" in globals():
    h5_mc = np.asarray(G9_PATH_MC_RETURNS, dtype=float)
    h5_mc_label = "Empirical block-bootstrap 1Y return"
    h5_skew, h5_kurt, h5_prob_loss = float(G9_SKEWNESS), float(G9_EXCESS_KURTOSIS), float(G9_PROB_LOSS)
else:
    h5_mc = np.asarray(G5_MONTE_CARLO_PORTFOLIO_RETURNS, dtype=float)
    h5_mc_label = "Gaussian annual Monte Carlo return"
    h5_skew = float(scipy_stats.skew(h5_mc, bias=False))
    h5_kurt = float(scipy_stats.kurtosis(h5_mc, fisher=True, bias=False))
    h5_prob_loss = float(np.mean(h5_mc < 0.0))
weights_plot = H5_EXECUTION_SHEET.copy()
weights_plot["previous_weight"] = h5_numeric_series(weights_plot, "previous_weight", 0.0).fillna(0.0)
weights_plot["target_weight"] = h5_numeric_series(weights_plot, "target_weight", 0.0).fillna(0.0)
risk_plot = G_FINAL_RISK_CONTRIBUTION.copy().sort_values("risk_contribution_share", ascending=False)
mos_plot = H_FINAL_BUY_WATCHLIST.head(15).copy()
sector_plot = H_SECTOR_MONITOR.copy().sort_values("target_weight", ascending=False)
alert_counts = H_FINAL_ALERTS.groupby("severity").size().rename("count").reset_index() if len(H_FINAL_ALERTS) else pd.DataFrame({"severity": [], "count": []})
H5_DASHBOARD = make_subplots(
    rows=4, cols=2,
    specs=[[{"type":"xy"},{"type":"xy"}],[{"type":"xy"},{"type":"xy"}],[{"type":"xy"},{"type":"xy"}],[{"type":"table"},{"type":"xy"}]],
    subplot_titles=("Trade notional by ticker","Current vs target weights","Sector allocation","Risk contribution","Closest names to MOS","Portfolio alerts by severity","Execution checklist","1Y Monte Carlo return distribution"),
    vertical_spacing=0.09, horizontal_spacing=0.10,
)
H5_DASHBOARD.add_trace(go.Bar(x=H5_EXECUTION_SHEET["ticker"], y=H5_EXECUTION_SHEET["trade_notional"], name="Trade notional", hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"), row=1, col=1)
H5_DASHBOARD.add_trace(go.Bar(x=weights_plot["ticker"], y=100*weights_plot["previous_weight"], name="Current"), row=1, col=2)
H5_DASHBOARD.add_trace(go.Bar(x=weights_plot["ticker"], y=100*weights_plot["target_weight"], name="Target"), row=1, col=2)
H5_DASHBOARD.add_trace(go.Bar(x=sector_plot["sector_ticker"], y=100*sector_plot["target_weight"], name="Sector weight"), row=2, col=1)
H5_DASHBOARD.add_trace(go.Bar(x=risk_plot["ticker"], y=100*risk_plot["risk_contribution_share"], name="Risk contribution"), row=2, col=2)
H5_DASHBOARD.add_trace(go.Bar(x=mos_plot["ticker"], y=100*mos_plot["distance_to_mos_pct"], name="Distance to MOS"), row=3, col=1)
H5_DASHBOARD.add_trace(go.Bar(x=alert_counts["severity"], y=alert_counts["count"], name="Alerts"), row=3, col=2)
trade_mask = H5_EXECUTION_SHEET["trade_required"].fillna(False).astype(bool) if "trade_required" in H5_EXECUTION_SHEET.columns else pd.Series(False, index=H5_EXECUTION_SHEET.index)
exec_table = H5_EXECUTION_SHEET[trade_mask].copy()
if exec_table.empty:
    exec_table = H5_EXECUTION_SHEET.head(10).copy()
def fmt_pct(series): return [f"{x:.1%}" if pd.notna(x) else "" for x in pd.to_numeric(series, errors="coerce")]
def fmt_dollar(series): return [f"${x:,.0f}" if pd.notna(x) else "" for x in pd.to_numeric(series, errors="coerce")]
H5_DASHBOARD.add_trace(go.Table(
    header=dict(values=["Ticker","Action","Current","Target","Trade $","Est. shares","Liquidity","MOS dist."]),
    cells=dict(values=[
        exec_table["ticker"].tolist(),
        exec_table.get("action", pd.Series(index=exec_table.index, dtype=object)).fillna("").tolist(),
        fmt_pct(exec_table.get("previous_weight", pd.Series(index=exec_table.index, dtype=float))),
        fmt_pct(exec_table.get("target_weight", pd.Series(index=exec_table.index, dtype=float))),
        fmt_dollar(exec_table.get("trade_notional", pd.Series(index=exec_table.index, dtype=float))),
        [f"{x:,.1f}" if pd.notna(x) else "" for x in pd.to_numeric(exec_table.get("estimated_shares", pd.Series(index=exec_table.index, dtype=float)), errors="coerce")],
        exec_table.get("liquidity_check", pd.Series(index=exec_table.index, dtype=object)).fillna("").tolist(),
        fmt_pct(exec_table.get("distance_to_mos_pct", pd.Series(index=exec_table.index, dtype=float))),
    ])
), row=4, col=1)
H5_DASHBOARD.add_trace(go.Histogram(x=100*h5_mc, nbinsx=70, name=h5_mc_label), row=4, col=2)
# Zero-return reference line intentionally omitted for Plotly table compatibility.
H5_DASHBOARD.update_layout(
    height=1550,
    title=("Execution Cockpit — " f"state={globals().get('PORTFOLIO_STATE_MODE','UNKNOWN')} | " f"MC skew={h5_skew:.2f}, excess kurtosis={h5_kurt:.2f}, P(loss)={h5_prob_loss:.1%}"),
    barmode="group", showlegend=True,
)
H5_DASHBOARD.update_yaxes(title_text="USD", row=1, col=1)
H5_DASHBOARD.update_yaxes(title_text="Weight (%)", row=1, col=2)
H5_DASHBOARD.update_yaxes(title_text="Weight (%)", row=2, col=1)
H5_DASHBOARD.update_yaxes(title_text="Risk contribution (%)", row=2, col=2)
H5_DASHBOARD.update_yaxes(title_text="Distance to MOS (%)", row=3, col=1)
H5_DASHBOARD.update_xaxes(title_text="Annual return (%)", row=4, col=2)
H5_DASHBOARD.write_html(H5_EXECUTION_DASHBOARD_HTML, include_plotlyjs="cdn")
H_FINAL_EXECUTION_DASHBOARD = H5_EXECUTION_DASHBOARD_HTML
print("=" * 140)
print("H5 — EXECUTION COCKPIT")
print("=" * 140)
print(f"Dashboard: {H5_EXECUTION_DASHBOARD_HTML}")
print(f"Trade sheet: {H5_DASHBOARD_DIR / 'execution_trade_sheet.csv'}")
print("✓ Dashboard supports execution review but does not transmit broker orders.")
print("H5 dashboard object built; use the local Streamlit dashboard for viewing.")

