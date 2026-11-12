# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 41 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D1 — REGIME INPUT SNAPSHOT + GOVERNANCE
# ============================================================
#
# Purpose:
#   Convert the completed Section C macro dashboard into one
#   clean, auditable input layer for regime classification.
#
# IMPORTANT:
#   Section D is LIVE-ONLY for now.
#
#   We do NOT construct historical regime labels until the
#   point-in-time / release-date / ALFRED layer is complete.
# ============================================================


# ============================================================
# 1. SECTION C PRODUCTION-GATE CHECK
# ============================================================

if "SECTION_C_HEALTH" not in globals():

    raise RuntimeError(
        "SECTION_C_HEALTH is unavailable. "
        "Run Section C through C25 first."
    )


if not bool(
    SECTION_C_HEALTH[
        "passed"
    ].all()
):

    failed_checks = (

        SECTION_C_HEALTH.loc[
            ~SECTION_C_HEALTH[
                "passed"
            ],
            "check",
        ]

        .tolist()

    )

    raise RuntimeError(
        "Section D cannot run because "
        "Section C failed: "
        + "; ".join(
            failed_checks
        )
    )


# ============================================================
# 2. HISTORICAL BACKTEST GOVERNANCE
# ============================================================

REGIME_MODE = "LIVE_ONLY"


if "backtest_ready" not in DATA_MANIFEST.columns:

    raise RuntimeError(
        "DATA_MANIFEST is missing backtest_ready."
    )


if bool(
    DATA_MANIFEST[
        "backtest_ready"
    ].any()
):

    raise RuntimeError(
        "Historical regime modelling is blocked until "
        "the PIT / vintage-data layer is explicitly enabled."
    )


# ============================================================
# 3. REQUIRED MACRO BLOCKS
# ============================================================

REQUIRED_REGIME_BLOCKS = [

    "Growth",
    "Inflation",
    "Monetary policy",
    "Liquidity",
    "Credit stress",
    "Market risk appetite",

]


available_blocks = set(

    PM_MACRO_STATE_V2[
        "macro_block"
    ]

)


missing_blocks = [

    block

    for block in REQUIRED_REGIME_BLOCKS

    if block not in available_blocks

]


if missing_blocks:

    raise RuntimeError(
        "Missing regime macro blocks: "
        f"{missing_blocks}"
    )


if (

    PM_MACRO_STATE_V2[
        "macro_block"
    ]
    .duplicated()
    .any()

):

    duplicates = (

        PM_MACRO_STATE_V2.loc[
            PM_MACRO_STATE_V2[
                "macro_block"
            ]
            .duplicated(
                keep=False
            ),
            "macro_block",
        ]

        .tolist()

    )

    raise RuntimeError(
        "Duplicate macro blocks detected: "
        f"{duplicates}"
    )


# ============================================================
# 4. HELPER — GET ONE PM MACRO BLOCK
# ============================================================

def get_regime_block(
    macro_block: str
) -> pd.Series:
    """
    Return one row from PM_MACRO_STATE_V2.
    """

    match = (

        PM_MACRO_STATE_V2[
            PM_MACRO_STATE_V2[
                "macro_block"
            ]
            ==
            macro_block
        ]

    )


    if len(match) != 1:

        raise RuntimeError(
            f"{macro_block}: expected exactly one row, "
            f"found {len(match)}."
        )


    return (
        match.iloc[0]
    )


# ============================================================
# 5. CLEAN FACTOR SNAPSHOT
# ============================================================

regime_factor_rows = []


for block in REQUIRED_REGIME_BLOCKS:

    row = get_regime_block(
        block
    )


    regime_factor_rows.append(

        {

            "macro_block":
                block,

            "pm_state":
                row[
                    "pm_state"
                ],

            "state_score":
                float(
                    row[
                        "state_score"
                    ]
                ),

            "momentum_score":
                float(
                    row[
                        "momentum_score"
                    ]
                ),

            "acceleration_score":
                float(
                    row[
                        "acceleration_score"
                    ]
                ),

            "momentum":
                row[
                    "momentum"
                ],

            "acceleration":
                row[
                    "acceleration"
                ],

            "short_term_signal":
                row[
                    "short_term_signal"
                ],

            "confidence":
                row[
                    "confidence"
                ],

            "confidence_score":
                float(
                    row[
                        "confidence_score"
                    ]
                ),

        }

    )


REGIME_FACTOR_SNAPSHOT = (

    pd.DataFrame(
        regime_factor_rows
    )

)


# ============================================================
# 6. CONFIDENCE-ADJUSTED SCORES
# ============================================================
#
# Preserve both:
#
#   raw signal
#   confidence-adjusted signal
#
# We do NOT replace the raw score.
# ============================================================

for score_column in [

    "state_score",
    "momentum_score",
    "acceleration_score",

]:

    adjusted_column = (
        f"confidence_adjusted_"
        f"{score_column}"
    )


    REGIME_FACTOR_SNAPSHOT[
        adjusted_column
    ] = (

        REGIME_FACTOR_SNAPSHOT[
            score_column
        ]

        *

        REGIME_FACTOR_SNAPSHOT[
            "confidence_score"
        ]

    )


# ============================================================
# 7. EXTRACT CORE FACTORS
# ============================================================

growth = get_regime_block(
    "Growth"
)

inflation = get_regime_block(
    "Inflation"
)

policy = get_regime_block(
    "Monetary policy"
)

liquidity = get_regime_block(
    "Liquidity"
)

credit = get_regime_block(
    "Credit stress"
)

market = get_regime_block(
    "Market risk appetite"
)


# ============================================================
# 8. LIVE REGIME VECTOR
# ============================================================
#
# Economic regime:
#
#   Growth
#   Inflation
#
# Policy / financial-condition overlays:
#
#   Monetary policy
#   Liquidity
#   Credit
#   Market risk appetite
#
# Anchored diagnostics:
#
#   Actual inflation level
#   Inflation impulse
#   Ex-post real policy rate
#   10Y real yield
# ============================================================

LIVE_REGIME_VECTOR = pd.DataFrame(

    [

        {

            # --------------------------------------------
            # System metadata
            # --------------------------------------------

            "regime_mode":
                REGIME_MODE,

            "market_as_of_date":
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ),

            "inflation_reference_month":
                str(
                    INFLATION_COMMON_MONTH
                ),


            # --------------------------------------------
            # Growth
            # --------------------------------------------

            "growth_state":
                float(
                    growth[
                        "state_score"
                    ]
                ),

            "growth_momentum":
                float(
                    growth[
                        "momentum_score"
                    ]
                ),

            "growth_acceleration":
                float(
                    growth[
                        "acceleration_score"
                    ]
                ),

            "growth_confidence":
                float(
                    growth[
                        "confidence_score"
                    ]
                ),


            # --------------------------------------------
            # Inflation — statistical factor
            # --------------------------------------------

            "inflation_state":
                float(
                    inflation[
                        "state_score"
                    ]
                ),

            "inflation_momentum":
                float(
                    inflation[
                        "momentum_score"
                    ]
                ),

            "inflation_acceleration":
                float(
                    inflation[
                        "acceleration_score"
                    ]
                ),

            "inflation_confidence":
                float(
                    inflation[
                        "confidence_score"
                    ]
                ),


            # --------------------------------------------
            # Inflation — economically anchored
            # --------------------------------------------

            "inflation_level_pct":
                float(
                    INFLATION_LEVEL
                ),

            "inflation_3m_ann_pct":
                float(
                    INFLATION_3M_ANN
                ),

            "inflation_6m_ann_pct":
                float(
                    INFLATION_6M_ANN
                ),

            "inflation_12m_pct":
                float(
                    INFLATION_12M
                ),

            "inflation_impulse_gap_pp":
                float(
                    INFLATION_IMPULSE_GAP
                ),

            "inflation_impulse_score":
                float(
                    INFLATION_IMPULSE_SCORE
                ),


            # --------------------------------------------
            # Monetary policy
            # --------------------------------------------

            "policy_state":
                float(
                    policy[
                        "state_score"
                    ]
                ),

            "policy_momentum":
                float(
                    policy[
                        "momentum_score"
                    ]
                ),

            "policy_acceleration":
                float(
                    policy[
                        "acceleration_score"
                    ]
                ),

            "policy_confidence":
                float(
                    policy[
                        "confidence_score"
                    ]
                ),

            "fed_funds_rate_pct":
                float(
                    FED_FUNDS_RATE
                ),

            "core_pce_yoy_pct":
                float(
                    CORE_PCE_YOY
                ),

            "ex_post_real_policy_rate_pct":
                float(
                    EX_POST_REAL_POLICY_RATE
                ),

            "real_10y_yield_pct":
                float(
                    REAL_10Y_YIELD
                ),


            # --------------------------------------------
            # Liquidity
            # --------------------------------------------

            "liquidity_state":
                float(
                    liquidity[
                        "state_score"
                    ]
                ),

            "liquidity_momentum":
                float(
                    liquidity[
                        "momentum_score"
                    ]
                ),

            "liquidity_acceleration":
                float(
                    liquidity[
                        "acceleration_score"
                    ]
                ),

            "liquidity_confidence":
                float(
                    liquidity[
                        "confidence_score"
                    ]
                ),


            # --------------------------------------------
            # Credit stress
            # --------------------------------------------

            "credit_stress_state":
                float(
                    credit[
                        "state_score"
                    ]
                ),

            "credit_stress_momentum":
                float(
                    credit[
                        "momentum_score"
                    ]
                ),

            "credit_stress_acceleration":
                float(
                    credit[
                        "acceleration_score"
                    ]
                ),

            "credit_stress_confidence":
                float(
                    credit[
                        "confidence_score"
                    ]
                ),


            # --------------------------------------------
            # Market risk appetite
            # --------------------------------------------

            "market_state":
                float(
                    market[
                        "state_score"
                    ]
                ),

            "market_momentum":
                float(
                    market[
                        "momentum_score"
                    ]
                ),

            "market_acceleration":
                float(
                    market[
                        "acceleration_score"
                    ]
                ),

            "market_confidence":
                float(
                    market[
                        "confidence_score"
                    ]
                ),

        }

    ]

)


# ============================================================
# 9. SANITY CHECKS
# ============================================================

score_columns = [

    "growth_state",
    "growth_momentum",
    "growth_acceleration",

    "inflation_state",
    "inflation_momentum",
    "inflation_acceleration",

    "policy_state",
    "policy_momentum",
    "policy_acceleration",

    "liquidity_state",
    "liquidity_momentum",
    "liquidity_acceleration",

    "credit_stress_state",
    "credit_stress_momentum",
    "credit_stress_acceleration",

    "market_state",
    "market_momentum",
    "market_acceleration",

]


confidence_columns = [

    "growth_confidence",
    "inflation_confidence",
    "policy_confidence",
    "liquidity_confidence",
    "credit_stress_confidence",
    "market_confidence",

]


if not safe_isfinite(

    LIVE_REGIME_VECTOR[
        score_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite regime factor score detected."
    )


if not (

    LIVE_REGIME_VECTOR[
        confidence_columns
    ]

    .apply(
        lambda column:
        column.between(
            0.0,
            1.0
        ).all()
    )

    .all()

):

    raise RuntimeError(
        "Regime confidence score outside [0, 1]."
    )


anchored_columns = [

    "inflation_level_pct",
    "inflation_3m_ann_pct",
    "inflation_6m_ann_pct",
    "inflation_12m_pct",
    "inflation_impulse_gap_pp",
    "inflation_impulse_score",
    "fed_funds_rate_pct",
    "core_pce_yoy_pct",
    "ex_post_real_policy_rate_pct",
    "real_10y_yield_pct",

]


if not safe_isfinite(

    LIVE_REGIME_VECTOR[
        anchored_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite anchored macro diagnostic detected."
    )


# ============================================================
# 10. SAVE LIVE REGIME INPUTS
# ============================================================

REGIME_FACTOR_SNAPSHOT_PATH = (

    REGIME_MODEL_DIR
    /
    "live_regime_factor_snapshot.parquet"

)


LIVE_REGIME_VECTOR_PATH = (

    REGIME_MODEL_DIR
    /
    "live_regime_vector.parquet"

)


REGIME_FACTOR_SNAPSHOT.to_parquet(

    REGIME_FACTOR_SNAPSHOT_PATH,
    index=False

)


LIVE_REGIME_VECTOR.to_parquet(

    LIVE_REGIME_VECTOR_PATH,
    index=False

)


# ============================================================
# 11. DISPLAY
# ============================================================

print(
    "=" * 82
)

print(
    "SECTION D — LIVE REGIME ENGINE"
)

print(
    "=" * 82
)


print(
    f"Mode:                  "
    f"{REGIME_MODE}"
)

print(
    f"Market as-of date:     "
    f"{MARKET_AS_OF_DATE.date()}"
)

print(
    f"Inflation ref. month:  "
    f"{INFLATION_COMMON_MONTH}"
)


print(
    "\nFactor snapshot:"
)


display(

    REGIME_FACTOR_SNAPSHOT[
        [
            "macro_block",
            "pm_state",
            "state_score",
            "momentum_score",
            "acceleration_score",
            "confidence_score",
            "confidence",
        ]
    ]

)


print(
    "\nAnchored diagnostics:"
)


display(

    LIVE_REGIME_VECTOR[
        [
            "inflation_level_pct",
            "inflation_3m_ann_pct",
            "inflation_6m_ann_pct",
            "inflation_impulse_gap_pp",
            "ex_post_real_policy_rate_pct",
            "real_10y_yield_pct",
        ]
    ]

)


print(
    "\n✓ D1 COMPLETE — "
    "live regime input layer is ready."
)

# ===== ORIGINAL NOTEBOOK CELL 42 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D2 — PROBABILISTIC ECONOMIC REGIME
#           + FINANCIAL CONDITIONS OVERLAY
# ============================================================
#
# Architecture:
#
#   ECONOMIC REGIME
#       Growth × Inflation
#
#   FINANCIAL CONDITIONS OVERLAY
#       Monetary policy
#       Liquidity
#       Credit stress
#       Market risk appetite
#
# Important:
#   - Economic regime and financial conditions are NOT mixed
#     into one score.
#   - Probabilities are deliberately flattened when confidence
#     is low.
#   - No historical training/backtest is performed here.
# ============================================================


# ============================================================
# 1. VALIDATE D1
# ============================================================

required_d1_objects = [

    "REGIME_FACTOR_SNAPSHOT",
    "LIVE_REGIME_VECTOR",
    "REGIME_MODE",

]

missing_d1_objects = [

    obj
    for obj in required_d1_objects
    if obj not in globals()

]

if missing_d1_objects:

    raise RuntimeError(
        "D2 requires D1 first. Missing: "
        f"{missing_d1_objects}"
    )


if REGIME_MODE != "LIVE_ONLY":

    raise RuntimeError(
        "D2 is currently designed for LIVE_ONLY mode."
    )


# ============================================================
# 2. MODEL PARAMETERS
# ============================================================
#
# These are transparent economic priors.
#
# They are NOT statistically optimized parameters yet.
# ============================================================

GROWTH_SIGNAL_WEIGHTS = {

    "state": 0.60,
    "momentum": 0.30,
    "acceleration": 0.10,

}


INFLATION_SIGNAL_WEIGHTS = {

    "level": 0.65,
    "impulse": 0.35,

}


FINANCIAL_CONDITION_WEIGHTS = {

    "Monetary policy": 0.30,
    "Liquidity": 0.20,
    "Credit stress": 0.25,
    "Market risk appetite": 0.25,

}


# Direction convention:
#
# +1 = higher score is more supportive for equities
# -1 = higher score is more restrictive / negative
FINANCIAL_CONDITION_DIRECTION = {

    "Monetary policy": -1.0,
    "Liquidity": +1.0,
    "Credit stress": -1.0,
    "Market risk appetite": +1.0,

}


INFLATION_TARGET_PCT = 2.0

# 1 percentage point away from target
# corresponds approximately to one standardized unit.
INFLATION_LEVEL_SCALE_PP = 1.0


REGIME_PROTOTYPE_LEVEL = 0.75

REGIME_DISTANCE_SCALE = 0.80


# ============================================================
# 3. VALIDATE PARAMETER WEIGHTS
# ============================================================

if not np.isclose(
    sum(
        GROWTH_SIGNAL_WEIGHTS.values()
    ),
    1.0
):

    raise ValueError(
        "Growth signal weights must sum to 1."
    )


if not np.isclose(
    sum(
        INFLATION_SIGNAL_WEIGHTS.values()
    ),
    1.0
):

    raise ValueError(
        "Inflation signal weights must sum to 1."
    )


if not np.isclose(
    sum(
        FINANCIAL_CONDITION_WEIGHTS.values()
    ),
    1.0
):

    raise ValueError(
        "Financial-condition weights must sum to 1."
    )


# ============================================================
# 4. HELPER — GET ONE D1 FACTOR
# ============================================================

def get_d1_factor(
    macro_block: str
) -> pd.Series:
    """
    Return exactly one factor from REGIME_FACTOR_SNAPSHOT.
    """

    match = (

        REGIME_FACTOR_SNAPSHOT[
            REGIME_FACTOR_SNAPSHOT[
                "macro_block"
            ]
            ==
            macro_block
        ]

    )


    if len(match) != 1:

        raise RuntimeError(
            f"{macro_block}: expected 1 D1 row, "
            f"found {len(match)}."
        )


    return (
        match.iloc[0]
    )


# ============================================================
# 5. HELPER — STATE / MOMENTUM / ACCELERATION COMPOSITE
# ============================================================

def trajectory_score(
    row: pd.Series,
    state_weight: float = 0.60,
    momentum_weight: float = 0.30,
    acceleration_weight: float = 0.10,
) -> float:
    """
    Combine state, momentum and acceleration.

    Positive means improvement / strength according to the
    sign convention already defined in Section C.
    """

    score = (

        state_weight
        *
        float(
            row[
                "state_score"
            ]
        )

        +

        momentum_weight
        *
        float(
            row[
                "momentum_score"
            ]
        )

        +

        acceleration_weight
        *
        float(
            row[
                "acceleration_score"
            ]
        )

    )


    return float(
        score
    )


# ============================================================
# 6. GROWTH AXIS
# ============================================================

growth_row = get_d1_factor(
    "Growth"
)


GROWTH_AXIS_RAW = trajectory_score(

    growth_row,

    state_weight=(
        GROWTH_SIGNAL_WEIGHTS[
            "state"
        ]
    ),

    momentum_weight=(
        GROWTH_SIGNAL_WEIGHTS[
            "momentum"
        ]
    ),

    acceleration_weight=(
        GROWTH_SIGNAL_WEIGHTS[
            "acceleration"
        ]
    ),

)


GROWTH_CONFIDENCE = float(

    growth_row[
        "confidence_score"
    ]

)


# ============================================================
# 7. INFLATION AXIS
# ============================================================
#
# Inflation is anchored economically rather than relying only
# on a historical z-score.
#
# Level:
#
#       actual inflation - 2% target
#
# Impulse:
#
#       3M annualized - 12M inflation
#
# Therefore:
#
#   positive = inflationary pressure
#   negative = disinflationary pressure
# ============================================================

INFLATION_LEVEL_SCORE = float(

    np.clip(

        (
            INFLATION_LEVEL
            -
            INFLATION_TARGET_PCT
        )

        /
        INFLATION_LEVEL_SCALE_PP,

        -2.0,
        2.0,

    )

)


INFLATION_IMPULSE_AXIS = float(

    np.clip(

        INFLATION_IMPULSE_SCORE,

        -2.0,
        2.0,

    )

)


INFLATION_AXIS_RAW = float(

    INFLATION_SIGNAL_WEIGHTS[
        "level"
    ]
    *
    INFLATION_LEVEL_SCORE

    +

    INFLATION_SIGNAL_WEIGHTS[
        "impulse"
    ]
    *
    INFLATION_IMPULSE_AXIS

)


inflation_row = get_d1_factor(
    "Inflation"
)


INFLATION_CONFIDENCE = float(

    inflation_row[
        "confidence_score"
    ]

)


# ============================================================
# 8. ECONOMIC REGIME CONFIDENCE
# ============================================================
#
# Geometric mean penalizes one weak axis more strongly than
# a simple arithmetic average.
# ============================================================

ECONOMIC_REGIME_CONFIDENCE = float(

    np.sqrt(

        GROWTH_CONFIDENCE
        *
        INFLATION_CONFIDENCE

    )

)


# ============================================================
# 9. ECONOMIC REGIME PROTOTYPES
# ============================================================
#
#                 Inflation -
#                       |
#    Slowdown           |       Goldilocks
#                       |
#   --------------------+-------------------- Growth
#                       |
#    Stagflation        |       Reflation
#                       |
#                 Inflation +
#
# Coordinates:
#
#   x = Growth
#   y = Inflation
# ============================================================

ECONOMIC_REGIME_PROTOTYPES = {

    "Goldilocks": {

        "growth":
            +REGIME_PROTOTYPE_LEVEL,

        "inflation":
            -REGIME_PROTOTYPE_LEVEL,

    },

    "Reflation": {

        "growth":
            +REGIME_PROTOTYPE_LEVEL,

        "inflation":
            +REGIME_PROTOTYPE_LEVEL,

    },

    "Disinflationary slowdown": {

        "growth":
            -REGIME_PROTOTYPE_LEVEL,

        "inflation":
            -REGIME_PROTOTYPE_LEVEL,

    },

    "Stagflation": {

        "growth":
            -REGIME_PROTOTYPE_LEVEL,

        "inflation":
            +REGIME_PROTOTYPE_LEVEL,

    },

}


# ============================================================
# 10. DISTANCE-BASED RAW REGIME PROBABILITIES
# ============================================================
#
# Similarity:
#
#             - distance^2
#     exp( -------------------- )
#           2 * sigma^2
#
# This is a transparent probabilistic scoring system,
# not a fitted statistical model.
# ============================================================

regime_probability_rows = []


for regime_name, prototype in (
    ECONOMIC_REGIME_PROTOTYPES.items()
):

    growth_distance = (

        GROWTH_AXIS_RAW
        -
        prototype[
            "growth"
        ]

    )


    inflation_distance = (

        INFLATION_AXIS_RAW
        -
        prototype[
            "inflation"
        ]

    )


    squared_distance = (

        growth_distance ** 2
        +
        inflation_distance ** 2

    )


    similarity = float(

        np.exp(

            -
            squared_distance

            /

            (
                2.0
                *
                REGIME_DISTANCE_SCALE ** 2
            )

        )

    )


    regime_probability_rows.append(

        {

            "regime":
                regime_name,

            "prototype_growth":
                prototype[
                    "growth"
                ],

            "prototype_inflation":
                prototype[
                    "inflation"
                ],

            "distance_squared":
                squared_distance,

            "similarity":
                similarity,

        }

    )


ECONOMIC_REGIME_PROBABILITIES = (

    pd.DataFrame(
        regime_probability_rows
    )

)


similarity_sum = float(

    ECONOMIC_REGIME_PROBABILITIES[
        "similarity"
    ]
    .sum()

)


if (
    not safe_isfinite(
        similarity_sum
    )
    or
    similarity_sum <= 0
):

    raise RuntimeError(
        "Invalid regime similarity total."
    )


ECONOMIC_REGIME_PROBABILITIES[
    "raw_probability"
] = (

    ECONOMIC_REGIME_PROBABILITIES[
        "similarity"
    ]

    /
    similarity_sum

)


# ============================================================
# 11. CONFIDENCE-ADJUSTED REGIME PROBABILITIES
# ============================================================
#
# When confidence falls, probabilities move toward 25% each.
#
# This prevents false precision.
# ============================================================

N_REGIMES = len(
    ECONOMIC_REGIME_PROBABILITIES
)


UNIFORM_REGIME_PROBABILITY = (

    1.0
    /
    N_REGIMES

)


ECONOMIC_REGIME_PROBABILITIES[
    "probability"
] = (

    ECONOMIC_REGIME_CONFIDENCE

    *

    ECONOMIC_REGIME_PROBABILITIES[
        "raw_probability"
    ]

    +

    (
        1.0
        -
        ECONOMIC_REGIME_CONFIDENCE
    )

    *

    UNIFORM_REGIME_PROBABILITY

)


# ------------------------------------------------------------
# Final normalization
# ------------------------------------------------------------

ECONOMIC_REGIME_PROBABILITIES[
    "probability"
] = (

    ECONOMIC_REGIME_PROBABILITIES[
        "probability"
    ]

    /

    ECONOMIC_REGIME_PROBABILITIES[
        "probability"
    ]
    .sum()

)


ECONOMIC_REGIME_PROBABILITIES = (

    ECONOMIC_REGIME_PROBABILITIES

    .sort_values(
        "probability",
        ascending=False
    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 12. ECONOMIC REGIME CONVICTION
# ============================================================

TOP_REGIME = (

    ECONOMIC_REGIME_PROBABILITIES
    .iloc[0][
        "regime"
    ]

)


TOP_REGIME_PROBABILITY = float(

    ECONOMIC_REGIME_PROBABILITIES
    .iloc[0][
        "probability"
    ]

)


SECOND_REGIME_PROBABILITY = float(

    ECONOMIC_REGIME_PROBABILITIES
    .iloc[1][
        "probability"
    ]

)


REGIME_PROBABILITY_MARGIN = (

    TOP_REGIME_PROBABILITY
    -
    SECOND_REGIME_PROBABILITY

)


# ============================================================
# 13. PROBABILITY ENTROPY
# ============================================================

probabilities = (

    ECONOMIC_REGIME_PROBABILITIES[
        "probability"
    ]

    .to_numpy(
        dtype=float
    )

)


REGIME_ENTROPY = float(

    -
    np.sum(

        probabilities
        *
        np.log(
            probabilities
            +
            1e-12
        )

    )

)


MAX_REGIME_ENTROPY = float(

    np.log(
        N_REGIMES
    )

)


NORMALIZED_REGIME_ENTROPY = float(

    REGIME_ENTROPY
    /
    MAX_REGIME_ENTROPY

)


REGIME_CONVICTION_SCORE = float(

    ECONOMIC_REGIME_CONFIDENCE

    *
    (
        1.0
        -
        NORMALIZED_REGIME_ENTROPY
    )

)


# ============================================================
# 14. FINAL ECONOMIC REGIME LABEL
# ============================================================
#
# Do not force a regime when probabilities are too close.
# ============================================================

if (

    TOP_REGIME_PROBABILITY < 0.40

    or

    REGIME_PROBABILITY_MARGIN < 0.10

):

    ECONOMIC_REGIME_LABEL = (
        "Transitional / mixed"
    )

else:

    ECONOMIC_REGIME_LABEL = (
        TOP_REGIME
    )


# ============================================================
# 15. AXIS INTERPRETATION
# ============================================================

def classify_growth_axis(
    value: float
) -> str:

    if value >= 0.35:

        return "Expanding"

    elif value <= -0.35:

        return "Contracting"

    else:

        return "Neutral / transitional"


def classify_inflation_axis(
    value: float
) -> str:

    if value >= 0.35:

        return "Inflationary"

    elif value <= -0.35:

        return "Disinflationary"

    else:

        return "Mixed / near-neutral"


GROWTH_AXIS_LABEL = (
    classify_growth_axis(
        GROWTH_AXIS_RAW
    )
)


INFLATION_AXIS_LABEL = (
    classify_inflation_axis(
        INFLATION_AXIS_RAW
    )
)


# ============================================================
# 16. FINANCIAL CONDITIONS OVERLAY
# ============================================================
#
# Positive overall score:
#       supportive financial conditions
#
# Negative overall score:
#       restrictive / hostile financial conditions
#
# Each component is confidence-adjusted.
# ============================================================

financial_condition_rows = []


for macro_block, factor_weight in (
    FINANCIAL_CONDITION_WEIGHTS.items()
):

    row = get_d1_factor(
        macro_block
    )


    raw_trajectory = trajectory_score(
        row
    )


    confidence = float(

        row[
            "confidence_score"
        ]

    )


    direction = float(

        FINANCIAL_CONDITION_DIRECTION[
            macro_block
        ]

    )


    oriented_score = (

        raw_trajectory
        *
        direction

    )


    confidence_adjusted_score = (

        oriented_score
        *
        confidence

    )


    contribution = (

        confidence_adjusted_score
        *
        factor_weight

    )


    financial_condition_rows.append(

        {

            "macro_block":
                macro_block,

            "weight":
                factor_weight,

            "direction":
                direction,

            "raw_trajectory":
                raw_trajectory,

            "oriented_score":
                oriented_score,

            "confidence_score":
                confidence,

            "confidence_adjusted_score":
                confidence_adjusted_score,

            "contribution":
                contribution,

        }

    )


FINANCIAL_CONDITIONS_TABLE = (

    pd.DataFrame(
        financial_condition_rows
    )

)


FINANCIAL_CONDITIONS_SCORE = float(

    FINANCIAL_CONDITIONS_TABLE[
        "contribution"
    ]
    .sum()

)


# ============================================================
# 17. FINANCIAL CONDITIONS CLASSIFICATION
# ============================================================

def classify_financial_conditions(
    score: float
) -> str:

    if score >= 0.75:

        return "Strongly supportive"

    elif score >= 0.25:

        return "Supportive"

    elif score <= -0.75:

        return "Strongly restrictive"

    elif score <= -0.25:

        return "Restrictive"

    else:

        return "Neutral / mixed"


FINANCIAL_CONDITIONS_LABEL = (

    classify_financial_conditions(
        FINANCIAL_CONDITIONS_SCORE
    )

)


# ============================================================
# 18. SUMMARY OBJECT
# ============================================================

LIVE_REGIME_SUMMARY = pd.DataFrame(

    [

        {

            "regime_mode":
                REGIME_MODE,

            "economic_regime":
                ECONOMIC_REGIME_LABEL,

            "top_regime_candidate":
                TOP_REGIME,

            "top_probability":
                TOP_REGIME_PROBABILITY,

            "probability_margin":
                REGIME_PROBABILITY_MARGIN,

            "regime_confidence":
                ECONOMIC_REGIME_CONFIDENCE,

            "regime_conviction":
                REGIME_CONVICTION_SCORE,

            "growth_axis":
                GROWTH_AXIS_RAW,

            "growth_axis_label":
                GROWTH_AXIS_LABEL,

            "inflation_axis":
                INFLATION_AXIS_RAW,

            "inflation_axis_label":
                INFLATION_AXIS_LABEL,

            "financial_conditions_score":
                FINANCIAL_CONDITIONS_SCORE,

            "financial_conditions":
                FINANCIAL_CONDITIONS_LABEL,

            "market_as_of_date":
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ),

            "inflation_reference_month":
                str(
                    INFLATION_COMMON_MONTH
                ),

        }

    ]

)


# ============================================================
# 19. SANITY CHECKS
# ============================================================

if not np.isclose(

    ECONOMIC_REGIME_PROBABILITIES[
        "probability"
    ]
    .sum(),

    1.0,

    atol=1e-10,

):

    raise RuntimeError(
        "Regime probabilities do not sum to 1."
    )


if not ECONOMIC_REGIME_PROBABILITIES[
    "probability"
].between(
    0.0,
    1.0
).all():

    raise RuntimeError(
        "Invalid regime probability detected."
    )


if not (
    0.0
    <=
    ECONOMIC_REGIME_CONFIDENCE
    <=
    1.0
):

    raise RuntimeError(
        "Economic regime confidence outside [0,1]."
    )


if not safe_isfinite(
    FINANCIAL_CONDITIONS_SCORE
):

    raise RuntimeError(
        "Invalid financial-conditions score."
    )


# ============================================================
# 20. SAVE OUTPUTS
# ============================================================

ECONOMIC_REGIME_PROBABILITIES.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_economic_regime_probabilities.parquet",

    index=False,

)


FINANCIAL_CONDITIONS_TABLE.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_financial_conditions.parquet",

    index=False,

)


LIVE_REGIME_SUMMARY.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_regime_summary.parquet",

    index=False,

)


# ============================================================
# 21. DISPLAY
# ============================================================

print(
    "=" * 82
)

print(
    "D2 — PROBABILISTIC ECONOMIC REGIME"
)

print(
    "=" * 82
)


print(
    f"Growth axis:              "
    f"{GROWTH_AXIS_RAW:+.3f} "
    f"({GROWTH_AXIS_LABEL})"
)


print(
    f"Inflation level score:    "
    f"{INFLATION_LEVEL_SCORE:+.3f}"
)


print(
    f"Inflation impulse score:  "
    f"{INFLATION_IMPULSE_AXIS:+.3f}"
)


print(
    f"Inflation axis:           "
    f"{INFLATION_AXIS_RAW:+.3f} "
    f"({INFLATION_AXIS_LABEL})"
)


print(
    f"Economic confidence:      "
    f"{ECONOMIC_REGIME_CONFIDENCE:.3f}"
)


print(
    "\nRegime probabilities:"
)


display(

    ECONOMIC_REGIME_PROBABILITIES[
        [
            "regime",
            "raw_probability",
            "probability",
            "distance_squared",
        ]
    ]

)


print(
    f"\nTop candidate:            "
    f"{TOP_REGIME}"
)


print(
    f"Top probability:          "
    f"{TOP_REGIME_PROBABILITY:.1%}"
)


print(
    f"Probability margin:       "
    f"{REGIME_PROBABILITY_MARGIN:.1%}"
)


print(
    f"Regime conviction:        "
    f"{REGIME_CONVICTION_SCORE:.3f}"
)


print(
    f"\nFINAL ECONOMIC REGIME:    "
    f"{ECONOMIC_REGIME_LABEL}"
)


print(
    "\n"
    + "=" * 82
)

print(
    "FINANCIAL CONDITIONS OVERLAY"
)

print(
    "=" * 82
)


display(

    FINANCIAL_CONDITIONS_TABLE[
        [
            "macro_block",
            "weight",
            "raw_trajectory",
            "direction",
            "confidence_score",
            "confidence_adjusted_score",
            "contribution",
        ]
    ]

)


print(
    f"\nFinancial conditions score: "
    f"{FINANCIAL_CONDITIONS_SCORE:+.3f}"
)


print(
    f"Financial conditions:       "
    f"{FINANCIAL_CONDITIONS_LABEL}"
)


print(
    "\n"
    + "=" * 82
)

print(
    "LIVE REGIME SUMMARY"
)

print(
    "=" * 82
)


display(
    LIVE_REGIME_SUMMARY
)


print(
    "\n✓ D2 COMPLETE — probabilistic economic regime "
    "and financial-conditions overlay generated."
)

# ===== ORIGINAL NOTEBOOK CELL 43 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D2B — TEMPORAL SMOOTHING + REGIME-CHANGE HYSTERESIS
#            (IMPROVEMENT #1, NON-DESTRUCTIVE OVERLAY) V1.0.0
# ============================================================
#
# Purpose:
#
#   D2 recomputes the economic-regime probability vector from
#   scratch on every run, from that day's macro state alone.
#   A single noisy print in one macro block's momentum or
#   acceleration term can move the same-day probability vector
#   enough to flip the leading regime, even though nothing
#   structural changed -- and because D3 consumes the full
#   probability vector directly to build the sector prior, that
#   noise propagates straight into sector preference and,
#   eventually, into optimizer turnover.
#
# This cell does NOT touch D2's own computation or its own
# sanity checks (both still validate the RAW, same-day vector,
# which remains a correct diagnostic in its own right). Instead
# it sits immediately downstream and, before D3 runs:
#
#   1. Persists each day's RAW probability vector to DuckDB.
#   2. Computes an EWMA-smoothed probability vector using a
#      configurable half-life, and OVERWRITES
#      ECONOMIC_REGIME_PROBABILITIES (and the objects derived
#      from it: TOP_REGIME, TOP_REGIME_PROBABILITY,
#      REGIME_PROBABILITY_MARGIN, REGIME_CONVICTION_SCORE) so
#      every downstream cell transparently uses the smoothed
#      vector without needing to change.
#   3. Requires the smoothed top regime to lead for a minimum
#      number of CONSECUTIVE observations before the
#      human-facing ACTIVE_REGIME_LABEL is allowed to change --
#      a minimum-dwell-time state machine, persisted in DuckDB.
#      A single-day interruption resets the streak; this is
#      deliberately strict.
#   4. Re-saves the smoothed vector to the same parquet path D2
#      wrote to, so persisted artifacts reflect the smoothed
#      (production) view, not the raw same-day view.
#   5. Runs a non-blocking SENSITIVITY DIAGNOSTIC on the two
#      hand-set constants in D2's regime-probability kernel
#      (REGIME_PROTOTYPE_LEVEL, REGIME_DISTANCE_SCALE), showing
#      how much today's raw probability vector would move under
#      a +/-20% perturbation of each. This does not change any
#      production output -- it is a transparency/audit table
#      only, and the first thing to revisit once PIT backtesting
#      can actually fit these constants instead of assuming them.
#
# The RAW vector computed by D2 is preserved unchanged as
# ECONOMIC_REGIME_PROBABILITIES_RAW for anyone who wants to
# inspect the unsmoothed, same-day signal directly.
#
# This is a transparent, non-fitted temporal filter, not a
# statistically optimized parameter -- the half-life and dwell
# count are policy-calibrated defaults, exposed via CONFIG.
# ============================================================


# ============================================================
# 1. VALIDATE D2
# ============================================================

required_d2b_objects = [

    "ECONOMIC_REGIME_PROBABILITIES",
    "N_REGIMES",
    "ECONOMIC_REGIME_CONFIDENCE",
    "MARKET_AS_OF_DATE",
    "REGIME_MODEL_DIR",
    "conn",

    "REGIME_PROTOTYPE_LEVEL",
    "REGIME_DISTANCE_SCALE",
    "ECONOMIC_REGIME_PROTOTYPES",
    "GROWTH_AXIS_RAW",
    "INFLATION_AXIS_RAW",

]

missing_d2b_objects = [

    obj
    for obj in required_d2b_objects
    if obj not in globals()

]

if missing_d2b_objects:

    raise RuntimeError(
        "D2B requires D2 first. Missing: "
        f"{missing_d2b_objects}"
    )


# ============================================================
# 2. CONFIGURATION
# ============================================================

REGIME_SMOOTHING_HALF_LIFE_DAYS = 10.0
REGIME_MIN_DWELL_OBSERVATIONS = 3

if "CONFIG" in globals():

    _d2b_regime_cfg = CONFIG.get("regime", {})

    try:
        REGIME_SMOOTHING_HALF_LIFE_DAYS = float(
            _d2b_regime_cfg.get(
                "smoothing_half_life_days",
                REGIME_SMOOTHING_HALF_LIFE_DAYS,
            )
        )
    except Exception:
        pass

    try:
        REGIME_MIN_DWELL_OBSERVATIONS = int(
            _d2b_regime_cfg.get(
                "min_dwell_observations",
                REGIME_MIN_DWELL_OBSERVATIONS,
            )
        )
    except Exception:
        pass

if REGIME_SMOOTHING_HALF_LIFE_DAYS <= 0:
    raise RuntimeError("Regime smoothing half-life must be positive.")

if REGIME_MIN_DWELL_OBSERVATIONS < 1:
    raise RuntimeError("Regime minimum dwell observations must be >= 1.")

REGIME_SMOOTHING_DECAY = float(
    np.exp(
        np.log(0.5)
        / REGIME_SMOOTHING_HALF_LIFE_DAYS
    )
)


# ============================================================
# 3. PERSIST TODAY'S RAW VECTOR + LOAD PRIOR SMOOTHED VECTOR
# ============================================================

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS regime_probability_history (
        as_of_date DATE,
        regime VARCHAR,
        raw_probability DOUBLE,
        smoothed_probability DOUBLE,
        recorded_at TIMESTAMP,
        PRIMARY KEY (as_of_date, regime)
    )
    """
)

REGIME_AS_OF_DATE = pd.Timestamp(MARKET_AS_OF_DATE).date()

# Preserve the raw, same-day vector before it is overwritten below.
ECONOMIC_REGIME_PROBABILITIES_RAW = (
    ECONOMIC_REGIME_PROBABILITIES.copy()
)

raw_vector = (
    ECONOMIC_REGIME_PROBABILITIES_RAW
    .set_index("regime")["probability"]
)

prior_history = conn.execute(
    """
    SELECT as_of_date, regime, smoothed_probability
    FROM regime_probability_history
    WHERE as_of_date < ?
    ORDER BY as_of_date DESC
    """,
    [REGIME_AS_OF_DATE],
).fetchdf()

if len(prior_history) > 0:

    most_recent_date = prior_history["as_of_date"].max()

    prior_smoothed_vector = (
        prior_history[
            prior_history["as_of_date"] == most_recent_date
        ]
        .set_index("regime")["smoothed_probability"]
    )

else:

    prior_smoothed_vector = None


REGIME_SMOOTHING_COLD_START = bool(
    prior_smoothed_vector is None
    or set(prior_smoothed_vector.index) != set(raw_vector.index)
)

if not REGIME_SMOOTHING_COLD_START:

    smoothed_vector = (
        REGIME_SMOOTHING_DECAY
        * prior_smoothed_vector.reindex(raw_vector.index)
        + (1.0 - REGIME_SMOOTHING_DECAY)
        * raw_vector
    )
    smoothed_vector = smoothed_vector / smoothed_vector.sum()

else:

    # Cold start (first run, or the regime taxonomy changed):
    # nothing usable to smooth against yet.
    smoothed_vector = raw_vector.copy()


# ============================================================
# 4. PERSIST TODAY'S RAW + SMOOTHED VECTOR
# ============================================================

_d2b_history_rows = [
    (
        REGIME_AS_OF_DATE,
        str(regime_name),
        float(raw_vector[regime_name]),
        float(smoothed_vector[regime_name]),
        datetime.now(),
    )
    for regime_name in ECONOMIC_REGIME_PROBABILITIES_RAW["regime"]
]

conn.execute(
    "DELETE FROM regime_probability_history WHERE as_of_date = ?",
    [REGIME_AS_OF_DATE],
)

conn.executemany(
    "INSERT INTO regime_probability_history VALUES (?, ?, ?, ?, ?)",
    _d2b_history_rows,
)


# ============================================================
# 5. OVERWRITE ECONOMIC_REGIME_PROBABILITIES WITH THE SMOOTHED
#    VECTOR -- EVERYTHING DOWNSTREAM (D3 ONWARD) SEES THIS.
# ============================================================

ECONOMIC_REGIME_PROBABILITIES = (
    ECONOMIC_REGIME_PROBABILITIES_RAW
    .drop(columns=["probability"])
    .merge(
        smoothed_vector.rename("probability").reset_index(),
        on="regime",
        how="left",
    )
    .sort_values("probability", ascending=False)
    .reset_index(drop=True)
)

# Re-run D2's own sanity checks on the smoothed vector.
if not np.isclose(
    ECONOMIC_REGIME_PROBABILITIES["probability"].sum(),
    1.0,
    atol=1e-8,
):
    raise RuntimeError(
        "D2B: smoothed regime probabilities do not sum to 1."
    )

if not ECONOMIC_REGIME_PROBABILITIES["probability"].between(0.0, 1.0).all():
    raise RuntimeError(
        "D2B: invalid smoothed regime probability detected."
    )


# ============================================================
# 6. RE-DERIVE TOP_REGIME / MARGIN / ENTROPY / CONVICTION
#    (identical formulas to D2 sections 12-13, applied to the
#    smoothed vector instead of the raw one)
# ============================================================

TOP_REGIME = str(
    ECONOMIC_REGIME_PROBABILITIES.iloc[0]["regime"]
)

TOP_REGIME_PROBABILITY = float(
    ECONOMIC_REGIME_PROBABILITIES.iloc[0]["probability"]
)

SECOND_REGIME_PROBABILITY = float(
    ECONOMIC_REGIME_PROBABILITIES.iloc[1]["probability"]
)

REGIME_PROBABILITY_MARGIN = (
    TOP_REGIME_PROBABILITY
    - SECOND_REGIME_PROBABILITY
)

_d2b_probabilities = (
    ECONOMIC_REGIME_PROBABILITIES["probability"]
    .to_numpy(dtype=float)
)

REGIME_ENTROPY = float(
    -np.sum(
        _d2b_probabilities
        * np.log(_d2b_probabilities + 1e-12)
    )
)

MAX_REGIME_ENTROPY = float(np.log(N_REGIMES))

NORMALIZED_REGIME_ENTROPY = float(
    REGIME_ENTROPY / MAX_REGIME_ENTROPY
)

REGIME_CONVICTION_SCORE = float(
    ECONOMIC_REGIME_CONFIDENCE
    * (1.0 - NORMALIZED_REGIME_ENTROPY)
)

if (
    TOP_REGIME_PROBABILITY < 0.40
    or REGIME_PROBABILITY_MARGIN < 0.10
):
    ECONOMIC_REGIME_LABEL = "Transitional / mixed"
else:
    ECONOMIC_REGIME_LABEL = TOP_REGIME


# ============================================================
# 7. MINIMUM-DWELL HYSTERESIS ON THE ACTIVE REGIME LABEL
# ============================================================
#
# The smoothed top regime must lead by the margin/confidence
# rule above AND persist for REGIME_MIN_DWELL_OBSERVATIONS
# consecutive runs before ACTIVE_REGIME_LABEL is allowed to
# change. A one-day interruption by a different challenger
# resets the streak -- deliberately strict, to protect against
# whipsaw in the human-facing label. Note D3 already consumes
# the smoothed PROBABILITY VECTOR directly (step 5/6 above), so
# this hysteresis layer is a secondary safeguard for reporting
# and any hard label-based gating, not the primary fix.
# ============================================================

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS regime_label_state (
        state_key VARCHAR PRIMARY KEY,
        active_regime VARCHAR,
        candidate_regime VARCHAR,
        candidate_streak INTEGER,
        last_updated_date DATE
    )
    """
)

_d2b_state_row = conn.execute(
    """
    SELECT active_regime, candidate_regime, candidate_streak
    FROM regime_label_state
    WHERE state_key = 'D2_ACTIVE_REGIME'
    """
).fetchone()

_d2b_candidate_top = str(TOP_REGIME)

if _d2b_state_row is None:

    # Cold start: accept today's candidate immediately.
    ACTIVE_REGIME_LABEL = ECONOMIC_REGIME_LABEL
    _d2b_new_candidate = _d2b_candidate_top
    _d2b_new_streak = 1

else:

    _d2b_prev_active, _d2b_prev_candidate, _d2b_prev_streak = (
        _d2b_state_row
    )

    if _d2b_candidate_top == _d2b_prev_active:

        ACTIVE_REGIME_LABEL = _d2b_prev_active
        _d2b_new_candidate = _d2b_candidate_top
        _d2b_new_streak = 1

    elif _d2b_candidate_top == _d2b_prev_candidate:

        _d2b_new_streak = int(_d2b_prev_streak) + 1

        if _d2b_new_streak >= REGIME_MIN_DWELL_OBSERVATIONS:
            ACTIVE_REGIME_LABEL = ECONOMIC_REGIME_LABEL
        else:
            ACTIVE_REGIME_LABEL = _d2b_prev_active

        _d2b_new_candidate = _d2b_candidate_top

    else:

        # A different challenger than yesterday: restart the streak.
        ACTIVE_REGIME_LABEL = _d2b_prev_active
        _d2b_new_candidate = _d2b_candidate_top
        _d2b_new_streak = 1

# "Transitional / mixed" always overrides -- never held hostage
# by the dwell counter.
if ECONOMIC_REGIME_LABEL == "Transitional / mixed":
    ACTIVE_REGIME_LABEL = "Transitional / mixed"

REGIME_LABEL_PENDING_CHANGE = bool(
    ACTIVE_REGIME_LABEL != ECONOMIC_REGIME_LABEL
)

conn.execute(
    """
    INSERT OR REPLACE INTO regime_label_state
    VALUES (?, ?, ?, ?, ?)
    """,
    [
        "D2_ACTIVE_REGIME",
        ACTIVE_REGIME_LABEL,
        _d2b_new_candidate,
        _d2b_new_streak,
        REGIME_AS_OF_DATE,
    ],
)


# ============================================================
# 8. RE-SAVE THE SMOOTHED OUTPUT (overwrites D2's raw parquet)
# ============================================================

ECONOMIC_REGIME_PROBABILITIES.to_parquet(
    REGIME_MODEL_DIR / "live_economic_regime_probabilities.parquet",
    index=False,
)

ECONOMIC_REGIME_PROBABILITIES_RAW.to_parquet(
    REGIME_MODEL_DIR / "live_economic_regime_probabilities_raw.parquet",
    index=False,
)


# ============================================================
# 9. SENSITIVITY DIAGNOSTIC — REGIME KERNEL CONSTANTS
#    (non-blocking; audit-only, does not change any production
#    output above)
# ============================================================
#
# REGIME_PROTOTYPE_LEVEL and REGIME_DISTANCE_SCALE in D2 are
# hand-set constants, not fitted. This table shows how much
# TODAY's raw probability vector would move under a +/-20%
# perturbation of each, one at a time, holding the other fixed.
# A regime call that swings a lot under a plausible +/-20% is a
# fragile call; a regime call that barely moves is robust to
# this particular assumption.
# ============================================================

def d2b_regime_probabilities_for(prototype_level, distance_scale):

    rows = []

    for regime_name, base_prototype in ECONOMIC_REGIME_PROTOTYPES.items():

        sign_growth = np.sign(base_prototype["growth"]) or 1.0
        sign_inflation = np.sign(base_prototype["inflation"]) or 1.0

        prototype_growth = prototype_level * sign_growth
        prototype_inflation = prototype_level * sign_inflation

        growth_distance = GROWTH_AXIS_RAW - prototype_growth
        inflation_distance = INFLATION_AXIS_RAW - prototype_inflation

        squared_distance = (
            growth_distance ** 2
            + inflation_distance ** 2
        )

        similarity = float(
            np.exp(
                -squared_distance
                / (2.0 * distance_scale ** 2)
            )
        )

        rows.append((regime_name, similarity))

    total = sum(s for _, s in rows)

    return {
        name: sim / total
        for name, sim in rows
    }


_d2b_sensitivity_rows = []

_d2b_base_top = TOP_REGIME

for _d2b_param_name, _d2b_base_value in [
    ("REGIME_PROTOTYPE_LEVEL", REGIME_PROTOTYPE_LEVEL),
    ("REGIME_DISTANCE_SCALE", REGIME_DISTANCE_SCALE),
]:

    for _d2b_pct_change in [-0.20, 0.0, +0.20]:

        _d2b_perturbed_value = _d2b_base_value * (1.0 + _d2b_pct_change)

        if _d2b_param_name == "REGIME_PROTOTYPE_LEVEL":
            _d2b_probs = d2b_regime_probabilities_for(
                _d2b_perturbed_value,
                REGIME_DISTANCE_SCALE,
            )
        else:
            _d2b_probs = d2b_regime_probabilities_for(
                REGIME_PROTOTYPE_LEVEL,
                _d2b_perturbed_value,
            )

        _d2b_top_under_perturbation = max(
            _d2b_probs,
            key=_d2b_probs.get,
        )

        _d2b_sensitivity_rows.append(
            {
                "parameter": _d2b_param_name,
                "perturbation": f"{_d2b_pct_change:+.0%}",
                "perturbed_value": round(_d2b_perturbed_value, 4),
                "top_regime": _d2b_top_under_perturbation,
                "top_probability": round(
                    _d2b_probs[_d2b_top_under_perturbation], 4
                ),
                "matches_baseline_top_regime": bool(
                    _d2b_top_under_perturbation == _d2b_base_top
                ),
            }
        )

REGIME_KERNEL_SENSITIVITY = pd.DataFrame(_d2b_sensitivity_rows)

REGIME_KERNEL_SENSITIVITY_STABLE = bool(
    REGIME_KERNEL_SENSITIVITY["matches_baseline_top_regime"].all()
)

REGIME_KERNEL_SENSITIVITY.to_parquet(
    REGIME_MODEL_DIR / "live_regime_kernel_sensitivity.parquet",
    index=False,
)


# ============================================================
# 10. DISPLAY
# ============================================================

print("=" * 82)
print("D2B — TEMPORAL SMOOTHING + REGIME-CHANGE HYSTERESIS")
print("=" * 82)

print(
    f"Smoothing half-life:       "
    f"{REGIME_SMOOTHING_HALF_LIFE_DAYS:.1f} days "
    f"(decay={REGIME_SMOOTHING_DECAY:.4f}/day)"
)

print(
    f"Minimum dwell:             "
    f"{REGIME_MIN_DWELL_OBSERVATIONS} consecutive observations"
)

print(
    f"Cold start (no prior history): {REGIME_SMOOTHING_COLD_START}"
)

print("\nRaw vs smoothed probability:")

display(
    ECONOMIC_REGIME_PROBABILITIES_RAW[["regime", "probability"]]
    .rename(columns={"probability": "raw_probability"})
    .merge(
        ECONOMIC_REGIME_PROBABILITIES[["regime", "probability"]]
        .rename(columns={"probability": "smoothed_probability"}),
        on="regime",
    )
    .sort_values("smoothed_probability", ascending=False)
    .reset_index(drop=True)
)

print(
    f"\nSmoothed top regime:       {TOP_REGIME} "
    f"({TOP_REGIME_PROBABILITY:.1%}, margin {REGIME_PROBABILITY_MARGIN:.1%})"
)

print(
    f"Smoothed regime label:     {ECONOMIC_REGIME_LABEL}"
)

print(
    f"ACTIVE regime label:       {ACTIVE_REGIME_LABEL} "
    f"(pending change: {REGIME_LABEL_PENDING_CHANGE})"
)

print("\nRegime-kernel sensitivity diagnostic (+/-20% one-at-a-time):")

display(REGIME_KERNEL_SENSITIVITY)

print(
    f"\nBaseline top regime stable across all perturbations tested: "
    f"{REGIME_KERNEL_SENSITIVITY_STABLE}"
)

print(
    "\n✓ D2B COMPLETE — ECONOMIC_REGIME_PROBABILITIES now holds the "
    "SMOOTHED vector for D3 onward; ECONOMIC_REGIME_PROBABILITIES_RAW "
    "preserves D2's original same-day computation."
)


# ===== ORIGINAL NOTEBOOK CELL 44 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D3 — SECTOR MACRO PRIOR ENGINE
# ============================================================
#
# Purpose:
#   Translate:
#
#       1. Economic regime probabilities
#       2. Financial-condition components
#
#   into transparent sector-level macro priors.
#
# IMPORTANT:
#   These are NOT final investment recommendations.
#
#   D3 answers:
#
#       "Which sectors should the current macro environment
#        structurally favor or penalize?"
#
#   Later sections will combine these priors with:
#
#       - relative price momentum
#       - breadth
#       - earnings revisions
#       - valuation
#       - idiosyncratic company alpha
#
# Architecture:
#
#   Economic regime probabilities
#               ↓
#        Regime sector prior
#               +
#   Financial-condition overlay
#               ↓
#       Final macro sector prior
# ============================================================


# ============================================================
# 1. VALIDATE D2
# ============================================================

required_d2_objects = [

    "ECONOMIC_REGIME_PROBABILITIES",
    "FINANCIAL_CONDITIONS_TABLE",
    "LIVE_REGIME_SUMMARY",

]


missing_d2_objects = [

    obj

    for obj in required_d2_objects

    if obj not in globals()

]


if missing_d2_objects:

    raise RuntimeError(
        "D3 requires D2 first. Missing: "
        f"{missing_d2_objects}"
    )


# ============================================================
# 2. SECTOR UNIVERSE
# ============================================================

SECTOR_NAMES = (
    DATA_MANIFEST.loc[
        (DATA_MANIFEST["dataset"] == "market")
        & (DATA_MANIFEST["category"] == "sector")
        & (DATA_MANIFEST["enabled"] == True),
        ["series_id", "name"],
    ]
    .drop_duplicates(subset=["series_id"], keep="last")
    .set_index("series_id")["name"]
    .astype(str)
    .to_dict()
)

if not SECTOR_NAMES:
    raise RuntimeError("D3 found no enabled sector ETFs in DATA_MANIFEST.")


SECTOR_TICKERS = list(
    SECTOR_NAMES.keys()
)


# ------------------------------------------------------------
# Check against market manifest
# ------------------------------------------------------------

manifest_sector_tickers = set(

    DATA_MANIFEST.loc[

        (
            DATA_MANIFEST[
                "dataset"
            ]
            ==
            "market"
        )

        &

        (
            DATA_MANIFEST[
                "category"
            ]
            ==
            "sector"
        )

        &

        (
            DATA_MANIFEST[
                "enabled"
            ]
            ==
            True
        ),

        "series_id",

    ]

)


missing_sector_data = [

    ticker

    for ticker in SECTOR_TICKERS

    if ticker not in manifest_sector_tickers

]


if missing_sector_data:

    raise RuntimeError(
        "Missing enabled sector ETFs: "
        f"{missing_sector_data}"
    )


# ============================================================
# 3. ECONOMIC REGIME → SECTOR PRIOR MATRIX
# ============================================================
#
# Score convention:
#
#      +1.0 = strongly favored
#      +0.5 = moderately favored
#       0.0 = neutral
#      -0.5 = moderately challenged
#      -1.0 = strongly challenged
#
# These are transparent ECONOMIC PRIORS.
#
# They are deliberately NOT fitted yet because historical
# regime backtesting remains blocked until the PIT layer.
# ============================================================

SECTOR_REGIME_PRIORS = cfg(
    ["regime", "sector_prior_matrix"],
    None,
)

if not isinstance(SECTOR_REGIME_PRIORS, dict) or not SECTOR_REGIME_PRIORS:
    raise RuntimeError("D3 sector prior matrix is missing from CONFIG.")


# ============================================================
# 4. VALIDATE REGIME PRIOR MATRIX
# ============================================================

expected_regimes = set(

    ECONOMIC_REGIME_PROBABILITIES[
        "regime"
    ]

)


defined_regimes = set(
    SECTOR_REGIME_PRIORS.keys()
)


if expected_regimes != defined_regimes:

    raise RuntimeError(

        "Regime definitions do not match D2. "
        f"Expected={expected_regimes}, "
        f"Defined={defined_regimes}"

    )


for regime, mapping in (
    SECTOR_REGIME_PRIORS.items()
):

    missing = (

        set(
            SECTOR_TICKERS
        )

        -
        set(
            mapping.keys()
        )

    )


    extra = (

        set(
            mapping.keys()
        )

        -
        set(
            SECTOR_TICKERS
        )

    )


    if missing or extra:

        raise RuntimeError(

            f"{regime}: sector mapping mismatch. "
            f"Missing={missing}, Extra={extra}"

        )


# ============================================================
# 5. CREATE REGIME PRIOR MATRIX
# ============================================================

regime_prior_rows = []


for regime, mapping in (
    SECTOR_REGIME_PRIORS.items()
):

    for ticker, prior in (
        mapping.items()
    ):

        regime_prior_rows.append(

            {

                "regime":
                    regime,

                "ticker":
                    ticker,

                "sector":
                    SECTOR_NAMES[
                        ticker
                    ],

                "regime_prior":
                    float(
                        prior
                    ),

            }

        )


SECTOR_REGIME_PRIOR_MATRIX = (

    pd.DataFrame(
        regime_prior_rows
    )

)


# ============================================================
# 6. ATTACH LIVE REGIME PROBABILITIES
# ============================================================

regime_probability_map = (

    ECONOMIC_REGIME_PROBABILITIES

    .set_index(
        "regime"
    )[
        "probability"
    ]

    .to_dict()

)


SECTOR_REGIME_PRIOR_MATRIX[
    "regime_probability"
] = (

    SECTOR_REGIME_PRIOR_MATRIX[
        "regime"
    ]

    .map(
        regime_probability_map
    )

)


if (

    SECTOR_REGIME_PRIOR_MATRIX[
        "regime_probability"
    ]
    .isna()
    .any()

):

    raise RuntimeError(
        "Missing regime probability in sector matrix."
    )


# ============================================================
# 7. PROBABILITY-WEIGHTED ECONOMIC PRIOR
# ============================================================
#
# Do NOT use only the top regime.
#
# Example:
#
#   33% Reflation
#   32% Stagflation
#   18% Goldilocks
#   17% Slowdown
#
# Each sector receives exposure to the FULL distribution.
# ============================================================

SECTOR_REGIME_PRIOR_MATRIX[
    "weighted_prior_contribution"
] = (

    SECTOR_REGIME_PRIOR_MATRIX[
        "regime_prior"
    ]

    *

    SECTOR_REGIME_PRIOR_MATRIX[
        "regime_probability"
    ]

)


ECONOMIC_SECTOR_PRIOR = (

    SECTOR_REGIME_PRIOR_MATRIX

    .groupby(
        [
            "ticker",
            "sector",
        ],
        as_index=False
    )

    .agg(

        economic_prior=(
            "weighted_prior_contribution",
            "sum"
        )

    )

)


# ============================================================
# 8. FINANCIAL-CONDITION SECTOR SENSITIVITIES
# ============================================================
#
# These are NOT sector returns.
#
# They measure how sensitive each sector should be to each
# financial-condition dimension.
#
# Positive sensitivity:
#   benefits when that component is supportive.
#
# Lower sensitivity:
#   relatively insensitive.
# ============================================================

FINANCIAL_CONDITION_SECTOR_SENSITIVITY = cfg(
    ["regime", "financial_condition_sector_sensitivity"],
    None,
)

if (
    not isinstance(FINANCIAL_CONDITION_SECTOR_SENSITIVITY, dict)
    or not FINANCIAL_CONDITION_SECTOR_SENSITIVITY
):
    raise RuntimeError("D3 financial-condition sector sensitivity matrix is missing from CONFIG.")


# ============================================================
# 9. VALIDATE FINANCIAL SENSITIVITIES
# ============================================================

for factor in FINANCIAL_CONDITION_WEIGHTS:

    if (
        factor
        not in
        FINANCIAL_CONDITION_SECTOR_SENSITIVITY
    ):

        raise RuntimeError(
            f"Missing financial sensitivity: {factor}"
        )


    mapped_sectors = set(

        FINANCIAL_CONDITION_SECTOR_SENSITIVITY[
            factor
        ].keys()

    )


    if mapped_sectors != set(
        SECTOR_TICKERS
    ):

        raise RuntimeError(
            f"{factor}: sector sensitivity mismatch."
        )


# ============================================================
# 10. BUILD FINANCIAL-CONDITION OVERLAY
# ============================================================

financial_overlay_rows = []


for _, fc_row in (
    FINANCIAL_CONDITIONS_TABLE.iterrows()
):

    macro_block = (
        fc_row[
            "macro_block"
        ]
    )


    # D2 contribution already incorporates:
    #
    #   factor weight
    #   orientation
    #   confidence
    #
    factor_signal = float(

        fc_row[
            "contribution"
        ]

    )


    for ticker in SECTOR_TICKERS:

        sensitivity = float(

            FINANCIAL_CONDITION_SECTOR_SENSITIVITY[
                macro_block
            ][
                ticker
            ]

        )


        sector_contribution = (

            factor_signal
            *
            sensitivity

        )


        financial_overlay_rows.append(

            {

                "ticker":
                    ticker,

                "sector":
                    SECTOR_NAMES[
                        ticker
                    ],

                "macro_block":
                    macro_block,

                "factor_signal":
                    factor_signal,

                "sensitivity":
                    sensitivity,

                "sector_contribution":
                    sector_contribution,

            }

        )


SECTOR_FINANCIAL_OVERLAY_DETAIL = (

    pd.DataFrame(
        financial_overlay_rows
    )

)


SECTOR_FINANCIAL_OVERLAY = (

    SECTOR_FINANCIAL_OVERLAY_DETAIL

    .groupby(
        [
            "ticker",
            "sector",
        ],
        as_index=False
    )

    .agg(

        financial_overlay=(
            "sector_contribution",
            "sum"
        )

    )

)


# ============================================================
# 11. COMBINE ECONOMIC + FINANCIAL PRIORS
# ============================================================
#
# Economic regime remains the primary driver.
#
# Financial conditions modify, rather than replace,
# the economic-sector prior.
#
# These parameters are transparent priors and are NOT
# optimized/backtested yet.
# ============================================================

ECONOMIC_PRIOR_WEIGHT = float(cfg(["regime", "economic_prior_weight"], 0.75))

FINANCIAL_OVERLAY_WEIGHT = float(cfg(["regime", "financial_overlay_weight"], 0.25))


if not np.isclose(

    ECONOMIC_PRIOR_WEIGHT
    +
    FINANCIAL_OVERLAY_WEIGHT,

    1.0

):

    raise ValueError(
        "Sector prior weights must sum to 1."
    )


LIVE_SECTOR_MACRO_PRIORS = (

    ECONOMIC_SECTOR_PRIOR

    .merge(

        SECTOR_FINANCIAL_OVERLAY,

        on=[
            "ticker",
            "sector",
        ],

        how="left",

    )

)


LIVE_SECTOR_MACRO_PRIORS[
    "macro_prior_raw"
] = (

    ECONOMIC_PRIOR_WEIGHT

    *

    LIVE_SECTOR_MACRO_PRIORS[
        "economic_prior"
    ]

    +

    FINANCIAL_OVERLAY_WEIGHT

    *

    LIVE_SECTOR_MACRO_PRIORS[
        "financial_overlay"
    ]

)


# ============================================================
# 12. CROSS-SECTIONAL STANDARDIZATION
# ============================================================
#
# We care about RELATIVE sector attractiveness.
#
# Therefore calculate a cross-sectional z-score.
# ============================================================

macro_mean = float(

    LIVE_SECTOR_MACRO_PRIORS[
        "macro_prior_raw"
    ]
    .mean()

)


macro_std = float(

    LIVE_SECTOR_MACRO_PRIORS[
        "macro_prior_raw"
    ]
    .std(
        ddof=0
    )

)


if (
    not safe_isfinite(
        macro_std
    )
    or
    macro_std <= 1e-12
):

    LIVE_SECTOR_MACRO_PRIORS[
        "macro_prior_z"
    ] = 0.0


else:

    LIVE_SECTOR_MACRO_PRIORS[
        "macro_prior_z"
    ] = (

        (
            LIVE_SECTOR_MACRO_PRIORS[
                "macro_prior_raw"
            ]

            -
            macro_mean
        )

        /
        macro_std

    )


# ============================================================
# 13. CONVERT TO 0–100 RELATIVE SCORE
# ============================================================

LIVE_SECTOR_MACRO_PRIORS[
    "macro_prior_percentile"
] = (

    LIVE_SECTOR_MACRO_PRIORS[
        "macro_prior_raw"
    ]

    .rank(
        pct=True,
        method="average"
    )

    *
    100.0

)


# ============================================================
# 14. PRIOR LABELS
# ============================================================
#
# Explicitly call these "macro priors".
# They are NOT final portfolio recommendations.
# ============================================================

def classify_sector_macro_prior(
    z_score: float
) -> str:

    if z_score >= 1.0:

        return "Strong positive"

    elif z_score >= 0.35:

        return "Positive"

    elif z_score <= -1.0:

        return "Strong negative"

    elif z_score <= -0.35:

        return "Negative"

    else:

        return "Neutral"


LIVE_SECTOR_MACRO_PRIORS[
    "macro_prior_label"
] = (

    LIVE_SECTOR_MACRO_PRIORS[
        "macro_prior_z"
    ]

    .apply(
        classify_sector_macro_prior
    )

)


# ============================================================
# 15. ADD REGIME METADATA
# ============================================================

LIVE_SECTOR_MACRO_PRIORS[
    "economic_regime"
] = ECONOMIC_REGIME_LABEL


LIVE_SECTOR_MACRO_PRIORS[
    "top_regime_candidate"
] = TOP_REGIME


LIVE_SECTOR_MACRO_PRIORS[
    "top_regime_probability"
] = TOP_REGIME_PROBABILITY


LIVE_SECTOR_MACRO_PRIORS[
    "regime_confidence"
] = ECONOMIC_REGIME_CONFIDENCE


LIVE_SECTOR_MACRO_PRIORS[
    "financial_conditions"
] = FINANCIAL_CONDITIONS_LABEL


LIVE_SECTOR_MACRO_PRIORS[
    "financial_conditions_score"
] = FINANCIAL_CONDITIONS_SCORE


LIVE_SECTOR_MACRO_PRIORS[
    "market_as_of_date"
] = pd.Timestamp(
    MARKET_AS_OF_DATE
)


# ============================================================
# 16. SORT
# ============================================================

LIVE_SECTOR_MACRO_PRIORS = (

    LIVE_SECTOR_MACRO_PRIORS

    .sort_values(
        "macro_prior_raw",
        ascending=False
    )

    .reset_index(
        drop=True
    )

)


LIVE_SECTOR_MACRO_PRIORS[
    "macro_rank"
] = (

    np.arange(
        1,
        len(
            LIVE_SECTOR_MACRO_PRIORS
        )
        +
        1
    )

)


# ============================================================
# 17. SANITY CHECKS
# ============================================================

if len(
    LIVE_SECTOR_MACRO_PRIORS
) != len(
    SECTOR_TICKERS
):

    raise RuntimeError(
        "Incorrect number of sectors in D3."
    )


if (

    LIVE_SECTOR_MACRO_PRIORS[
        "ticker"
    ]
    .duplicated()
    .any()

):

    raise RuntimeError(
        "Duplicate sector ticker detected."
    )


numeric_columns = [

    "economic_prior",
    "financial_overlay",
    "macro_prior_raw",
    "macro_prior_z",
    "macro_prior_percentile",

]


if not safe_isfinite(

    LIVE_SECTOR_MACRO_PRIORS[
        numeric_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite D3 sector score detected."
    )


# ============================================================
# 18. SAVE OUTPUTS
# ============================================================

SECTOR_REGIME_PRIOR_MATRIX.to_parquet(

    REGIME_MODEL_DIR
    /
    "sector_regime_prior_matrix.parquet",

    index=False,

)


SECTOR_FINANCIAL_OVERLAY_DETAIL.to_parquet(

    REGIME_MODEL_DIR
    /
    "sector_financial_overlay_detail.parquet",

    index=False,

)


LIVE_SECTOR_MACRO_PRIORS.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_macro_priors.parquet",

    index=False,

)


# ============================================================
# 19. DISPLAY
# ============================================================

print(
    "=" * 90
)

print(
    "D3 — LIVE SECTOR MACRO PRIORS"
)

print(
    "=" * 90
)


print(
    f"Economic regime:       "
    f"{ECONOMIC_REGIME_LABEL}"
)


print(
    f"Top regime candidate:  "
    f"{TOP_REGIME} "
    f"({TOP_REGIME_PROBABILITY:.1%})"
)


print(
    f"Regime confidence:     "
    f"{ECONOMIC_REGIME_CONFIDENCE:.3f}"
)


print(
    f"Financial conditions:  "
    f"{FINANCIAL_CONDITIONS_LABEL} "
    f"({FINANCIAL_CONDITIONS_SCORE:+.3f})"
)


print(
    "\nSector macro priors:"
)


display(

    LIVE_SECTOR_MACRO_PRIORS[
        [
            "macro_rank",
            "ticker",
            "sector",
            "economic_prior",
            "financial_overlay",
            "macro_prior_raw",
            "macro_prior_z",
            "macro_prior_percentile",
            "macro_prior_label",
        ]
    ]

)


print(
    "\n✓ D3 COMPLETE — "
    "sector macro priors generated."
)

# ===== ORIGINAL NOTEBOOK CELL 45 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D4 — SECTOR MARKET CONFIRMATION ENGINE
# ============================================================
#
# Purpose:
#   Add empirical market evidence to the macro sector priors.
#
# Signals:
#
#   1M relative return vs SPY
#   3M relative return vs SPY
#   6M relative return vs SPY
#   Price vs 50D moving average
#   Price vs 200D moving average
#   3M drawdown from recent high
#
# IMPORTANT:
#   D4 does NOT combine these signals with D3 yet.
#
#   D3 = macro/economic prior
#   D4 = empirical market confirmation
#
#   D5 will combine them.
# ============================================================


# ============================================================
# 1. VALIDATE D3
# ============================================================

required_d3_objects = [
    "LIVE_SECTOR_MACRO_PRIORS",
    "SECTOR_TICKERS",
    "SECTOR_NAMES",
]

missing_d3_objects = [
    obj
    for obj in required_d3_objects
    if obj not in globals()
]

if missing_d3_objects:
    raise RuntimeError(
        "D4 requires D3 first. Missing: "
        f"{missing_d3_objects}"
    )


if "MARKET_AS_OF_DATE" not in globals():
    raise RuntimeError(
        "MARKET_AS_OF_DATE is unavailable."
    )


# ============================================================
# 2. SIGNAL PARAMETERS
# ============================================================

MARKET_SIGNAL_WEIGHTS = {

    "relative_1m": 0.15,
    "relative_3m": 0.30,
    "relative_6m": 0.25,
    "trend_50d": 0.10,
    "trend_200d": 0.15,
    "drawdown_3m": 0.05,

}


if not np.isclose(
    sum(MARKET_SIGNAL_WEIGHTS.values()),
    1.0
):
    raise ValueError(
        "MARKET_SIGNAL_WEIGHTS must sum to 1."
    )


TRADING_WINDOWS = {

    "1m": 21,
    "3m": 63,
    "6m": 126,

}


MIN_REQUIRED_OBSERVATIONS = 201


# ============================================================
# 3. MARKET PRICE LOADER
# ============================================================

def load_market_price_series(
    ticker: str
) -> pd.DataFrame:
    """
    Load adjusted market price history up to MARKET_AS_OF_DATE.
    """

    df = load_existing_series(
        dataset="market",
        series_id=ticker
    ).copy()


    if df.empty:
        raise RuntimeError(
            f"{ticker}: market series is empty."
        )


    if "date" not in df.columns:
        raise KeyError(
            f"{ticker}: date column missing."
        )


    df["date"] = pd.to_datetime(
        df["date"]
    )


    # Prefer adjusted close.
    if (
        "adj_close" in df.columns
        and
        pd.to_numeric(
            df["adj_close"],
            errors="coerce"
        ).notna().any()
    ):

        price_column = "adj_close"

    elif "close" in df.columns:

        price_column = "close"

    else:

        raise KeyError(
            f"{ticker}: neither adj_close nor close available."
        )


    df["price"] = pd.to_numeric(
        df[price_column],
        errors="coerce"
    )


    df = (
        df[
            df["date"]
            <=
            pd.Timestamp(
                MARKET_AS_OF_DATE
            )
        ]

        .dropna(
            subset=[
                "date",
                "price",
            ]
        )

        .sort_values("date")

        .drop_duplicates(
            subset=["date"],
            keep="last"
        )

        .reset_index(drop=True)
    )


    if len(df) < MIN_REQUIRED_OBSERVATIONS:

        raise RuntimeError(
            f"{ticker}: insufficient history "
            f"({len(df)} observations)."
        )


    return df[
        [
            "date",
            "price",
        ]
    ]


# ============================================================
# 4. LOAD SPY BENCHMARK
# ============================================================

SPY_PRICE_HISTORY = (
    load_market_price_series(
        "SPY"
    )
    .rename(
        columns={
            "price": "spy_price"
        }
    )
)


if SPY_PRICE_HISTORY.empty:
    raise RuntimeError(
        "SPY price history unavailable."
    )


# ============================================================
# 5. HELPER — PERIOD RETURN
# ============================================================

def period_return_pct(
    prices: pd.Series,
    periods: int
) -> float:
    """
    Calculate percentage return over N trading observations.
    """

    clean = (
        pd.to_numeric(
            prices,
            errors="coerce"
        )
        .dropna()
    )


    if len(clean) <= periods:
        return np.nan


    current = float(
        clean.iloc[-1]
    )

    previous = float(
        clean.iloc[
            -1 - periods
        ]
    )


    if previous <= 0:
        return np.nan


    return float(
        (
            current
            /
            previous
            -
            1.0
        )
        *
        100.0
    )


# ============================================================
# 6. BUILD RAW MARKET SIGNALS
# ============================================================

sector_market_rows = []


for ticker in SECTOR_TICKERS:

    sector_prices = (
        load_market_price_series(
            ticker
        )
        .rename(
            columns={
                "price": "sector_price"
            }
        )
    )


    # --------------------------------------------------------
    # Align sector and benchmark on identical trading dates
    # --------------------------------------------------------

    aligned = (

        sector_prices.merge(

            SPY_PRICE_HISTORY,

            on="date",

            how="inner",

        )

        .sort_values("date")

        .reset_index(drop=True)

    )


    if len(aligned) < MIN_REQUIRED_OBSERVATIONS:

        raise RuntimeError(
            f"{ticker}: insufficient aligned "
            f"SPY history ({len(aligned)} rows)."
        )


    # --------------------------------------------------------
    # Returns
    # --------------------------------------------------------

    sector_1m = period_return_pct(
        aligned["sector_price"],
        TRADING_WINDOWS["1m"]
    )

    sector_3m = period_return_pct(
        aligned["sector_price"],
        TRADING_WINDOWS["3m"]
    )

    sector_6m = period_return_pct(
        aligned["sector_price"],
        TRADING_WINDOWS["6m"]
    )


    spy_1m = period_return_pct(
        aligned["spy_price"],
        TRADING_WINDOWS["1m"]
    )

    spy_3m = period_return_pct(
        aligned["spy_price"],
        TRADING_WINDOWS["3m"]
    )

    spy_6m = period_return_pct(
        aligned["spy_price"],
        TRADING_WINDOWS["6m"]
    )


    relative_1m = (
        sector_1m
        -
        spy_1m
    )

    relative_3m = (
        sector_3m
        -
        spy_3m
    )

    relative_6m = (
        sector_6m
        -
        spy_6m
    )


    # --------------------------------------------------------
    # Moving-average trends
    # --------------------------------------------------------

    current_price = float(
        aligned[
            "sector_price"
        ].iloc[-1]
    )


    ma_50 = float(
        aligned[
            "sector_price"
        ]
        .tail(50)
        .mean()
    )


    ma_200 = float(
        aligned[
            "sector_price"
        ]
        .tail(200)
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


    trend_200d = (

        (
            current_price
            /
            ma_200
        )
        -
        1.0

    ) * 100.0


    # --------------------------------------------------------
    # 3M drawdown
    # --------------------------------------------------------

    recent_3m_high = float(

        aligned[
            "sector_price"
        ]

        .tail(
            TRADING_WINDOWS[
                "3m"
            ]
        )

        .max()

    )


    drawdown_3m = (

        (
            current_price
            /
            recent_3m_high
        )

        -
        1.0

    ) * 100.0


    sector_market_rows.append(

        {

            "ticker":
                ticker,

            "sector":
                SECTOR_NAMES[
                    ticker
                ],

            "as_of_date":
                aligned[
                    "date"
                ].iloc[-1],

            "current_price":
                current_price,

            "sector_return_1m":
                sector_1m,

            "sector_return_3m":
                sector_3m,

            "sector_return_6m":
                sector_6m,

            "spy_return_1m":
                spy_1m,

            "spy_return_3m":
                spy_3m,

            "spy_return_6m":
                spy_6m,

            "relative_1m":
                relative_1m,

            "relative_3m":
                relative_3m,

            "relative_6m":
                relative_6m,

            "trend_50d":
                trend_50d,

            "trend_200d":
                trend_200d,

            "drawdown_3m":
                drawdown_3m,

        }

    )


SECTOR_MARKET_SIGNALS = (
    pd.DataFrame(
        sector_market_rows
    )
)


# ============================================================
# 7. VALIDATE MARKET DATES
# ============================================================

if (

    SECTOR_MARKET_SIGNALS[
        "as_of_date"
    ]

    >
    pd.Timestamp(
        MARKET_AS_OF_DATE
    )

).any():

    raise RuntimeError(
        "Sector market signal uses data after "
        "MARKET_AS_OF_DATE."
    )


# ============================================================
# 8. CROSS-SECTIONAL STANDARDIZATION
# ============================================================

def cross_sectional_zscore(
    series: pd.Series
) -> pd.Series:
    """
    Standardize one signal across the 11 sectors.

    Scores are clipped to reduce outlier dominance.
    """

    values = pd.to_numeric(
        series,
        errors="coerce"
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

        return pd.Series(
            0.0,
            index=series.index,
            dtype=float
        )


    z = (

        values
        -
        mean_value

    ) / std_value


    return z.clip(
        lower=-2.5,
        upper=2.5
    )


# ============================================================
# 9. STANDARDIZE EACH MARKET SIGNAL
# ============================================================

signal_to_z_column = {

    "relative_1m":
        "z_relative_1m",

    "relative_3m":
        "z_relative_3m",

    "relative_6m":
        "z_relative_6m",

    "trend_50d":
        "z_trend_50d",

    "trend_200d":
        "z_trend_200d",

    "drawdown_3m":
        "z_drawdown_3m",

}


for raw_column, z_column in (
    signal_to_z_column.items()
):

    SECTOR_MARKET_SIGNALS[
        z_column
    ] = cross_sectional_zscore(

        SECTOR_MARKET_SIGNALS[
            raw_column
        ]

    )


# ============================================================
# 10. COMPOSITE TACTICAL MARKET SCORE
# ============================================================
#
# Higher = stronger market confirmation.
#
# Note:
#   drawdown_3m is already oriented correctly:
#
#       -1% > -10%
#
#   so a higher z-score is better.
# ============================================================

SECTOR_MARKET_SIGNALS[
    "market_score_raw"
] = (

    MARKET_SIGNAL_WEIGHTS[
        "relative_1m"
    ]
    *
    SECTOR_MARKET_SIGNALS[
        "z_relative_1m"
    ]

    +

    MARKET_SIGNAL_WEIGHTS[
        "relative_3m"
    ]
    *
    SECTOR_MARKET_SIGNALS[
        "z_relative_3m"
    ]

    +

    MARKET_SIGNAL_WEIGHTS[
        "relative_6m"
    ]
    *
    SECTOR_MARKET_SIGNALS[
        "z_relative_6m"
    ]

    +

    MARKET_SIGNAL_WEIGHTS[
        "trend_50d"
    ]
    *
    SECTOR_MARKET_SIGNALS[
        "z_trend_50d"
    ]

    +

    MARKET_SIGNAL_WEIGHTS[
        "trend_200d"
    ]
    *
    SECTOR_MARKET_SIGNALS[
        "z_trend_200d"
    ]

    +

    MARKET_SIGNAL_WEIGHTS[
        "drawdown_3m"
    ]
    *
    SECTOR_MARKET_SIGNALS[
        "z_drawdown_3m"
    ]

)


# ============================================================
# 11. RE-STANDARDIZE COMPOSITE SCORE
# ============================================================

SECTOR_MARKET_SIGNALS[
    "market_score_z"
] = cross_sectional_zscore(

    SECTOR_MARKET_SIGNALS[
        "market_score_raw"
    ]

)


# ============================================================
# 12. MARKET PERCENTILE + RANK
# ============================================================

SECTOR_MARKET_SIGNALS[
    "market_percentile"
] = (

    SECTOR_MARKET_SIGNALS[
        "market_score_raw"
    ]

    .rank(
        pct=True,
        method="average"
    )

    *
    100.0

)


SECTOR_MARKET_SIGNALS = (

    SECTOR_MARKET_SIGNALS

    .sort_values(
        "market_score_raw",
        ascending=False
    )

    .reset_index(
        drop=True
    )

)


SECTOR_MARKET_SIGNALS[
    "market_rank"
] = (

    np.arange(
        1,
        len(
            SECTOR_MARKET_SIGNALS
        )
        +
        1
    )

)


# ============================================================
# 13. TACTICAL MARKET LABEL
# ============================================================

def classify_market_signal(
    z_score: float
) -> str:

    if z_score >= 1.0:

        return "Strong positive"

    elif z_score >= 0.35:

        return "Positive"

    elif z_score <= -1.0:

        return "Strong negative"

    elif z_score <= -0.35:

        return "Negative"

    else:

        return "Neutral"


SECTOR_MARKET_SIGNALS[
    "market_signal"
] = (

    SECTOR_MARKET_SIGNALS[
        "market_score_z"
    ]

    .apply(
        classify_market_signal
    )

)


# ============================================================
# 14. BASIC TREND FLAGS
# ============================================================

SECTOR_MARKET_SIGNALS[
    "above_50d"
] = (

    SECTOR_MARKET_SIGNALS[
        "trend_50d"
    ]
    >
    0.0

)


SECTOR_MARKET_SIGNALS[
    "above_200d"
] = (

    SECTOR_MARKET_SIGNALS[
        "trend_200d"
    ]
    >
    0.0

)


SECTOR_MARKET_SIGNALS[
    "outperforming_spy_3m"
] = (

    SECTOR_MARKET_SIGNALS[
        "relative_3m"
    ]
    >
    0.0

)


# ============================================================
# 15. SANITY CHECKS
# ============================================================

if len(
    SECTOR_MARKET_SIGNALS
) != len(
    SECTOR_TICKERS
):

    raise RuntimeError(
        "Incorrect number of sectors in D4."
    )


if (

    SECTOR_MARKET_SIGNALS[
        "ticker"
    ]

    .duplicated()
    .any()

):

    raise RuntimeError(
        "Duplicate sector ticker detected in D4."
    )


required_numeric_columns = [

    "relative_1m",
    "relative_3m",
    "relative_6m",
    "trend_50d",
    "trend_200d",
    "drawdown_3m",
    "market_score_raw",
    "market_score_z",
    "market_percentile",

]


if not safe_isfinite(

    SECTOR_MARKET_SIGNALS[
        required_numeric_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite sector market signal detected."
    )


# ============================================================
# 16. SAVE OUTPUT
# ============================================================

SECTOR_MARKET_SIGNALS.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_market_signals.parquet",

    index=False,

)


# ============================================================
# 17. DISPLAY
# ============================================================

print(
    "=" * 96
)

print(
    "D4 — SECTOR MARKET CONFIRMATION"
)

print(
    "=" * 96
)


print(
    f"Market as-of date: "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    "\nRelative performance and trend:"
)


display(

    SECTOR_MARKET_SIGNALS[
        [
            "market_rank",
            "ticker",
            "sector",
            "relative_1m",
            "relative_3m",
            "relative_6m",
            "trend_50d",
            "trend_200d",
            "drawdown_3m",
            "market_score_z",
            "market_percentile",
            "market_signal",
        ]
    ]

)


print(
    "\nTrend confirmation:"
)


display(

    SECTOR_MARKET_SIGNALS[
        [
            "ticker",
            "sector",
            "above_50d",
            "above_200d",
            "outperforming_spy_3m",
        ]
    ]

)


print(
    "\n✓ D4 COMPLETE — "
    "sector market-confirmation signals generated."
)

# ===== ORIGINAL NOTEBOOK CELL 46 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D5 — DYNAMIC MACRO + MARKET SECTOR SIGNAL
# ============================================================
#
# Purpose:
#   Combine:
#
#       D3 = macro sector prior
#       D4 = empirical market confirmation
#
#   into one tactical sector signal.
#
# Core principle:
#
#   When macro regime conviction is weak:
#       market evidence gets more weight.
#
#   When macro regime conviction becomes strong:
#       macro priors receive more weight.
#
# IMPORTANT:
#   This is still a relative sector-selection signal.
#   It is NOT yet portfolio sizing.
# ============================================================


# ============================================================
# 1. VALIDATE REQUIRED OBJECTS
# ============================================================

required_d5_objects = [

    "LIVE_SECTOR_MACRO_PRIORS",
    "SECTOR_MARKET_SIGNALS",
    "REGIME_CONVICTION_SCORE",
    "ECONOMIC_REGIME_CONFIDENCE",
    "FINANCIAL_CONDITIONS_SCORE",

]


missing_d5_objects = [

    obj

    for obj in required_d5_objects

    if obj not in globals()

]


if missing_d5_objects:

    raise RuntimeError(
        "D5 requires D2-D4 first. Missing: "
        f"{missing_d5_objects}"
    )


# ============================================================
# 2. DYNAMIC MACRO / MARKET WEIGHTS
# ============================================================
#
# Macro weight varies from:
#
#       30%  → very low regime conviction
#       60%  → very high regime conviction
#
# Therefore:
#
#       market weight = 1 - macro weight
#
# Current mixed/transitional regimes should naturally lean
# more heavily on actual market confirmation.
# ============================================================

MIN_MACRO_WEIGHT = 0.30

MAX_MACRO_WEIGHT = 0.60


if not (
    0.0
    <=
    REGIME_CONVICTION_SCORE
    <=
    1.0
):

    raise RuntimeError(
        "REGIME_CONVICTION_SCORE must be in [0,1]."
    )


DYNAMIC_MACRO_WEIGHT = float(

    MIN_MACRO_WEIGHT

    +

    (
        MAX_MACRO_WEIGHT
        -
        MIN_MACRO_WEIGHT
    )

    *
    REGIME_CONVICTION_SCORE

)


DYNAMIC_MARKET_WEIGHT = float(

    1.0
    -
    DYNAMIC_MACRO_WEIGHT

)


# ============================================================
# 3. MERGE D3 + D4
# ============================================================

SECTOR_COMBINED_SIGNAL = (

    LIVE_SECTOR_MACRO_PRIORS[
        [
            "ticker",
            "sector",
            "macro_rank",
            "economic_prior",
            "financial_overlay",
            "macro_prior_raw",
            "macro_prior_z",
            "macro_prior_percentile",
            "macro_prior_label",
        ]
    ]

    .merge(

        SECTOR_MARKET_SIGNALS[
            [
                "ticker",
                "sector",
                "market_rank",
                "relative_1m",
                "relative_3m",
                "relative_6m",
                "trend_50d",
                "trend_200d",
                "drawdown_3m",
                "market_score_raw",
                "market_score_z",
                "market_percentile",
                "market_signal",
                "above_50d",
                "above_200d",
                "outperforming_spy_3m",
            ]
        ],

        on=[
            "ticker",
            "sector",
        ],

        how="inner",

        validate="one_to_one",

    )

)


# ============================================================
# 4. VALIDATE MERGE
# ============================================================

if len(
    SECTOR_COMBINED_SIGNAL
) != len(
    SECTOR_TICKERS
):

    raise RuntimeError(
        "D5 sector merge produced incorrect row count."
    )


if (
    SECTOR_COMBINED_SIGNAL[
        "ticker"
    ]
    .duplicated()
    .any()
):

    raise RuntimeError(
        "Duplicate ticker detected in D5."
    )


# ============================================================
# 5. RAW COMBINED SIGNAL
# ============================================================
#
# Both inputs are cross-sectional z-scores.
#
# Therefore they can be combined directly.
# ============================================================

SECTOR_COMBINED_SIGNAL[
    "combined_score_raw"
] = (

    DYNAMIC_MACRO_WEIGHT

    *

    SECTOR_COMBINED_SIGNAL[
        "macro_prior_z"
    ]

    +

    DYNAMIC_MARKET_WEIGHT

    *

    SECTOR_COMBINED_SIGNAL[
        "market_score_z"
    ]

)


# ============================================================
# 6. RE-STANDARDIZE FINAL CROSS-SECTION
# ============================================================

combined_mean = float(

    SECTOR_COMBINED_SIGNAL[
        "combined_score_raw"
    ]
    .mean()

)


combined_std = float(

    SECTOR_COMBINED_SIGNAL[
        "combined_score_raw"
    ]
    .std(
        ddof=0
    )

)


if (
    not safe_isfinite(
        combined_std
    )
    or
    combined_std <= 1e-12
):

    SECTOR_COMBINED_SIGNAL[
        "combined_score_z"
    ] = 0.0


else:

    SECTOR_COMBINED_SIGNAL[
        "combined_score_z"
    ] = (

        SECTOR_COMBINED_SIGNAL[
            "combined_score_raw"
        ]

        -
        combined_mean

    ) / combined_std


SECTOR_COMBINED_SIGNAL[
    "combined_score_z"
] = (

    SECTOR_COMBINED_SIGNAL[
        "combined_score_z"
    ]

    .clip(
        lower=-3.0,
        upper=3.0
    )

)


# ============================================================
# 7. MACRO / MARKET AGREEMENT
# ============================================================
#
# Use modest thresholds so tiny near-zero values are not
# incorrectly treated as positive/negative conviction.
# ============================================================

SIGN_THRESHOLD = 0.35


def signal_direction(
    score: float
) -> str:

    if score >= SIGN_THRESHOLD:

        return "Positive"

    elif score <= -SIGN_THRESHOLD:

        return "Negative"

    else:

        return "Neutral"


SECTOR_COMBINED_SIGNAL[
    "macro_direction"
] = (

    SECTOR_COMBINED_SIGNAL[
        "macro_prior_z"
    ]

    .apply(
        signal_direction
    )

)


SECTOR_COMBINED_SIGNAL[
    "market_direction"
] = (

    SECTOR_COMBINED_SIGNAL[
        "market_score_z"
    ]

    .apply(
        signal_direction
    )

)


# ============================================================
# 8. AGREEMENT CLASSIFICATION
# ============================================================

def classify_macro_market_alignment(
    row: pd.Series
) -> str:

    macro_direction = (
        row[
            "macro_direction"
        ]
    )

    market_direction = (
        row[
            "market_direction"
        ]
    )


    if (
        macro_direction == "Positive"
        and
        market_direction == "Positive"
    ):

        return "Positive confirmation"


    if (
        macro_direction == "Negative"
        and
        market_direction == "Negative"
    ):

        return "Negative confirmation"


    if (
        macro_direction == "Positive"
        and
        market_direction == "Negative"
    ):

        return "Macro positive / market weak"


    if (
        macro_direction == "Negative"
        and
        market_direction == "Positive"
    ):

        return "Market positive / macro headwind"


    if (
        macro_direction == "Neutral"
        and
        market_direction == "Positive"
    ):

        return "Market-led positive"


    if (
        macro_direction == "Positive"
        and
        market_direction == "Neutral"
    ):

        return "Macro-led positive"


    if (
        macro_direction == "Neutral"
        and
        market_direction == "Negative"
    ):

        return "Market-led negative"


    if (
        macro_direction == "Negative"
        and
        market_direction == "Neutral"
    ):

        return "Macro-led negative"


    return "Neutral / mixed"


SECTOR_COMBINED_SIGNAL[
    "macro_market_alignment"
] = (

    SECTOR_COMBINED_SIGNAL

    .apply(
        classify_macro_market_alignment,
        axis=1
    )

)


# ============================================================
# 9. DISAGREEMENT MAGNITUDE
# ============================================================
#
# Larger values indicate bigger macro / market divergence.
# ============================================================

SECTOR_COMBINED_SIGNAL[
    "macro_market_gap"
] = (

    SECTOR_COMBINED_SIGNAL[
        "macro_prior_z"
    ]

    -

    SECTOR_COMBINED_SIGNAL[
        "market_score_z"
    ]

)


SECTOR_COMBINED_SIGNAL[
    "absolute_macro_market_gap"
] = (

    SECTOR_COMBINED_SIGNAL[
        "macro_market_gap"
    ]

    .abs()

)


# ============================================================
# 10. HARD CONFLICT FLAG
# ============================================================
#
# Flag only when:
#
#   macro and market have opposite signs
#
# AND
#
#   both signals have meaningful magnitude.
# ============================================================

HARD_CONFLICT_THRESHOLD = 0.50


SECTOR_COMBINED_SIGNAL[
    "hard_conflict"
] = (

    (
        SECTOR_COMBINED_SIGNAL[
            "macro_prior_z"
        ]

        *

        SECTOR_COMBINED_SIGNAL[
            "market_score_z"
        ]

        <
        0
    )

    &

    (
        SECTOR_COMBINED_SIGNAL[
            "macro_prior_z"
        ]
        .abs()

        >=
        HARD_CONFLICT_THRESHOLD
    )

    &

    (
        SECTOR_COMBINED_SIGNAL[
            "market_score_z"
        ]
        .abs()

        >=
        HARD_CONFLICT_THRESHOLD
    )

)


# ============================================================
# 11. MARKET TREND CONFIRMATION COUNT
# ============================================================
#
# Three simple observable checks:
#
#   price > 50D
#   price > 200D
#   3M relative performance > SPY
# ============================================================

SECTOR_COMBINED_SIGNAL[
    "trend_confirmation_count"
] = (

    SECTOR_COMBINED_SIGNAL[
        [
            "above_50d",
            "above_200d",
            "outperforming_spy_3m",
        ]
    ]

    .astype(int)

    .sum(
        axis=1
    )

)


# ============================================================
# 12. FINAL SIGNAL PERCENTILE
# ============================================================

SECTOR_COMBINED_SIGNAL[
    "combined_percentile"
] = (

    SECTOR_COMBINED_SIGNAL[
        "combined_score_raw"
    ]

    .rank(
        pct=True,
        method="average"
    )

    *
    100.0

)


# ============================================================
# 13. FINAL SIGNAL LABEL
# ============================================================

def classify_combined_sector_signal(
    z_score: float
) -> str:

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


SECTOR_COMBINED_SIGNAL[
    "combined_signal"
] = (

    SECTOR_COMBINED_SIGNAL[
        "combined_score_z"
    ]

    .apply(
        classify_combined_sector_signal
    )

)


# ============================================================
# 14. SORT + FINAL RANK
# ============================================================

SECTOR_COMBINED_SIGNAL = (

    SECTOR_COMBINED_SIGNAL

    .sort_values(
        "combined_score_raw",
        ascending=False
    )

    .reset_index(
        drop=True
    )

)


SECTOR_COMBINED_SIGNAL[
    "combined_rank"
] = (

    np.arange(
        1,
        len(
            SECTOR_COMBINED_SIGNAL
        )
        +
        1
    )

)


# ============================================================
# 15. RANK CHANGES
# ============================================================
#
# Positive macro_to_final_change:
#       final rank improved versus macro rank.
#
# Positive market_to_final_change:
#       final rank improved versus market rank.
# ============================================================

SECTOR_COMBINED_SIGNAL[
    "macro_to_final_change"
] = (

    SECTOR_COMBINED_SIGNAL[
        "macro_rank"
    ]

    -

    SECTOR_COMBINED_SIGNAL[
        "combined_rank"
    ]

)


SECTOR_COMBINED_SIGNAL[
    "market_to_final_change"
] = (

    SECTOR_COMBINED_SIGNAL[
        "market_rank"
    ]

    -

    SECTOR_COMBINED_SIGNAL[
        "combined_rank"
    ]

)


# ============================================================
# 16. ATTACH MODEL METADATA
# ============================================================

SECTOR_COMBINED_SIGNAL[
    "macro_weight"
] = (
    DYNAMIC_MACRO_WEIGHT
)


SECTOR_COMBINED_SIGNAL[
    "market_weight"
] = (
    DYNAMIC_MARKET_WEIGHT
)


SECTOR_COMBINED_SIGNAL[
    "economic_regime"
] = (
    ECONOMIC_REGIME_LABEL
)


SECTOR_COMBINED_SIGNAL[
    "regime_conviction"
] = (
    REGIME_CONVICTION_SCORE
)


SECTOR_COMBINED_SIGNAL[
    "regime_confidence"
] = (
    ECONOMIC_REGIME_CONFIDENCE
)


SECTOR_COMBINED_SIGNAL[
    "financial_conditions"
] = (
    FINANCIAL_CONDITIONS_LABEL
)


SECTOR_COMBINED_SIGNAL[
    "market_as_of_date"
] = pd.Timestamp(
    MARKET_AS_OF_DATE
)


# ============================================================
# 17. SANITY CHECKS
# ============================================================

required_numeric_columns = [

    "macro_prior_z",
    "market_score_z",
    "combined_score_raw",
    "combined_score_z",
    "combined_percentile",
    "absolute_macro_market_gap",

]


if not safe_isfinite(

    SECTOR_COMBINED_SIGNAL[
        required_numeric_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite combined sector signal detected."
    )


if not np.isclose(

    DYNAMIC_MACRO_WEIGHT
    +
    DYNAMIC_MARKET_WEIGHT,

    1.0,

):

    raise RuntimeError(
        "Dynamic macro and market weights do not sum to 1."
    )


if not (

    MIN_MACRO_WEIGHT
    <=
    DYNAMIC_MACRO_WEIGHT
    <=
    MAX_MACRO_WEIGHT

):

    raise RuntimeError(
        "Dynamic macro weight outside allowed range."
    )


# ============================================================
# 18. SAVE OUTPUT
# ============================================================

SECTOR_COMBINED_SIGNAL.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_combined_signal.parquet",

    index=False,

)


# ============================================================
# 19. DISPLAY
# ============================================================

print(
    "=" * 105
)

print(
    "D5 — DYNAMIC MACRO + MARKET SECTOR SIGNAL"
)

print(
    "=" * 105
)


print(
    f"Economic regime:       "
    f"{ECONOMIC_REGIME_LABEL}"
)


print(
    f"Regime confidence:     "
    f"{ECONOMIC_REGIME_CONFIDENCE:.3f}"
)


print(
    f"Regime conviction:     "
    f"{REGIME_CONVICTION_SCORE:.3f}"
)


print(
    f"\nDynamic macro weight:  "
    f"{DYNAMIC_MACRO_WEIGHT:.1%}"
)


print(
    f"Dynamic market weight: "
    f"{DYNAMIC_MARKET_WEIGHT:.1%}"
)


print(
    "\nCombined sector ranking:"
)


display(

    SECTOR_COMBINED_SIGNAL[
        [
            "combined_rank",
            "ticker",
            "sector",
            "macro_rank",
            "market_rank",
            "macro_prior_z",
            "market_score_z",
            "combined_score_z",
            "combined_percentile",
            "combined_signal",
            "macro_market_alignment",
            "hard_conflict",
        ]
    ]

)


print(
    "\nTrend / disagreement diagnostics:"
)


display(

    SECTOR_COMBINED_SIGNAL[
        [
            "ticker",
            "sector",
            "relative_3m",
            "trend_50d",
            "trend_200d",
            "trend_confirmation_count",
            "macro_market_gap",
            "absolute_macro_market_gap",
        ]
    ]

)


print(
    "\n✓ D5 COMPLETE — "
    "dynamic macro + market sector signal generated."
)

# ===== ORIGINAL NOTEBOOK CELL 47 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D6 — SECTOR RISK + RISK-ADJUSTED SIGNAL
# ============================================================
#
# Purpose:
#
#   Add risk information to the D5 tactical sector signal.
#
# Risk diagnostics:
#
#   - Annualized volatility
#   - Downside volatility
#   - Beta to SPY
#   - Correlation to SPY
#   - Maximum drawdown
#   - Annualized return
#   - Annualized excess return vs SPY
#   - Information ratio
#
# Then construct:
#
#       risk_penalty
#
# and modestly adjust the D5 tactical signal.
#
# IMPORTANT:
#
#   D6 does NOT optimize portfolio weights.
#
#   Correlation is diagnostic only at this stage.
#   Portfolio correlation/diversification belongs in the
#   portfolio optimizer later.
# ============================================================


# ============================================================
# 1. VALIDATE D5
# ============================================================

required_d6_objects = [

    "SECTOR_COMBINED_SIGNAL",
    "SECTOR_TICKERS",
    "SECTOR_NAMES",
    "MARKET_AS_OF_DATE",

]


missing_d6_objects = [

    obj

    for obj in required_d6_objects

    if obj not in globals()

]


if missing_d6_objects:

    raise RuntimeError(
        "D6 requires D5 first. Missing: "
        f"{missing_d6_objects}"
    )


if "load_market_price_series" not in globals():

    raise RuntimeError(
        "D6 requires load_market_price_series() "
        "from D4."
    )


# ============================================================
# 2. RISK PARAMETERS
# ============================================================

TRADING_DAYS = 252

RISK_LOOKBACK_DAYS = 252


# ------------------------------------------------------------
# Risk-penalty composition
# ------------------------------------------------------------
#
# Downside volatility receives the largest weight because
# negative volatility matters more for a long-only portfolio.
#
# Correlation is deliberately NOT included here.
# ------------------------------------------------------------

RISK_COMPONENT_WEIGHTS = {

    "volatility": 0.30,
    "downside_volatility": 0.40,
    "max_drawdown": 0.30,

}


if not np.isclose(
    sum(
        RISK_COMPONENT_WEIGHTS.values()
    ),
    1.0
):

    raise ValueError(
        "RISK_COMPONENT_WEIGHTS must sum to 1."
    )


# ------------------------------------------------------------
# Keep risk adjustment modest.
#
# D5 is the alpha/tactical signal.
# D6 should modify it, not replace it.
# ------------------------------------------------------------

RISK_ADJUSTMENT_STRENGTH = 0.20


# ============================================================
# 3. HELPER — CROSS-SECTIONAL Z-SCORE
# ============================================================

def risk_cross_sectional_zscore(
    series: pd.Series
) -> pd.Series:
    """
    Cross-sectional z-score with outlier clipping.
    """

    values = pd.to_numeric(
        series,
        errors="coerce"
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

        return pd.Series(
            0.0,
            index=series.index,
            dtype=float
        )


    z = (

        values
        -
        mean_value

    ) / std_value


    return z.clip(
        lower=-3.0,
        upper=3.0
    )


# ============================================================
# 4. HELPER — ANNUALIZED RETURN
# ============================================================

def annualized_return_from_prices(
    prices: pd.Series
) -> float:
    """
    Annualized percentage return from an adjusted-price series.
    """

    prices = (

        pd.to_numeric(
            prices,
            errors="coerce"
        )

        .dropna()

    )


    if len(
        prices
    ) < 2:

        return np.nan


    start_price = float(
        prices.iloc[0]
    )


    end_price = float(
        prices.iloc[-1]
    )


    periods = (
        len(prices)
        -
        1
    )


    if (
        start_price <= 0
        or
        end_price <= 0
        or
        periods <= 0
    ):

        return np.nan


    annualized_return = (

        (
            end_price
            /
            start_price
        )

        **
        (
            TRADING_DAYS
            /
            periods
        )

        -
        1.0

    )


    return float(
        annualized_return
        *
        100.0
    )


# ============================================================
# 5. HELPER — MAXIMUM DRAWDOWN
# ============================================================

def maximum_drawdown_pct(
    prices: pd.Series
) -> float:
    """
    Maximum peak-to-trough drawdown in percentage terms.

    Output is negative.
    Example:
        -18.5 = -18.5%
    """

    prices = (

        pd.to_numeric(
            prices,
            errors="coerce"
        )

        .dropna()

    )


    if prices.empty:

        return np.nan


    running_peak = (
        prices.cummax()
    )


    drawdown = (

        prices
        /
        running_peak

        -
        1.0

    )


    return float(
        drawdown.min()
        *
        100.0
    )


# ============================================================
# 6. LOAD SPY
# ============================================================

spy_prices = (

    load_market_price_series(
        "SPY"
    )

    .rename(
        columns={
            "price":
                "spy_price"
        }
    )

)


# ============================================================
# 7. BUILD SECTOR RISK METRICS
# ============================================================

sector_risk_rows = []


for ticker in SECTOR_TICKERS:


    # --------------------------------------------------------
    # Load sector price
    # --------------------------------------------------------

    sector_prices = (

        load_market_price_series(
            ticker
        )

        .rename(
            columns={
                "price":
                    "sector_price"
            }
        )

    )


    # --------------------------------------------------------
    # Align with SPY
    # --------------------------------------------------------

    aligned = (

        sector_prices.merge(

            spy_prices,

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


    # Need 252 return observations + initial price.
    aligned = (

        aligned

        .tail(
            RISK_LOOKBACK_DAYS
            +
            1
        )

        .reset_index(
            drop=True
        )

    )


    if len(
        aligned
    ) < (
        RISK_LOOKBACK_DAYS
        +
        1
    ):

        raise RuntimeError(

            f"{ticker}: insufficient risk history. "
            f"Need {RISK_LOOKBACK_DAYS + 1}, "
            f"found {len(aligned)}."

        )


    # ========================================================
    # 8. DAILY RETURNS
    # ========================================================

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


    returns = (

        aligned[
            [
                "sector_return",
                "spy_return",
            ]
        ]

        .dropna()

    )


    if len(
        returns
    ) < RISK_LOOKBACK_DAYS:

        raise RuntimeError(
            f"{ticker}: insufficient return observations."
        )


    sector_returns = (

        returns[
            "sector_return"
        ]

    )


    benchmark_returns = (

        returns[
            "spy_return"
        ]

    )


    # ========================================================
    # 9. ANNUALIZED VOLATILITY
    # ========================================================

    annualized_volatility = float(

        sector_returns.std(
            ddof=1
        )

        *
        np.sqrt(
            TRADING_DAYS
        )

        *
        100.0

    )


    # ========================================================
    # 10. DOWNSIDE DEVIATION
    # ========================================================
    #
    # Uses:
    #
    #   sqrt(mean(min(r, 0)^2)) * sqrt(252)
    #
    # rather than simply std(negative returns).
    # ========================================================

    downside_returns = np.minimum(

        sector_returns.to_numpy(
            dtype=float
        ),

        0.0,

    )


    downside_volatility = float(

        np.sqrt(

            np.mean(

                downside_returns
                **
                2

            )

        )

        *
        np.sqrt(
            TRADING_DAYS
        )

        *
        100.0

    )


    # ========================================================
    # 11. BETA
    # ========================================================

    benchmark_variance = float(

        benchmark_returns.var(
            ddof=1
        )

    )


    if (

        not safe_isfinite(
            benchmark_variance
        )

        or

        benchmark_variance <= 1e-16

    ):

        beta = np.nan


    else:

        covariance = float(

            np.cov(

                sector_returns.to_numpy(
                    dtype=float
                ),

                benchmark_returns.to_numpy(
                    dtype=float
                ),

                ddof=1,

            )[0, 1]

        )


        beta = (

            covariance
            /
            benchmark_variance

        )


    # ========================================================
    # 12. CORRELATION TO SPY
    # ========================================================

    correlation_to_spy = float(

        sector_returns.corr(
            benchmark_returns
        )

    )


    # ========================================================
    # 13. MAXIMUM DRAWDOWN
    # ========================================================

    max_drawdown = (

        maximum_drawdown_pct(

            aligned[
                "sector_price"
            ]

        )

    )


    drawdown_depth = abs(
        max_drawdown
    )


    # ========================================================
    # 14. ANNUALIZED RETURN
    # ========================================================

    annualized_return = (

        annualized_return_from_prices(

            aligned[
                "sector_price"
            ]

        )

    )


    spy_annualized_return = (

        annualized_return_from_prices(

            aligned[
                "spy_price"
            ]

        )

    )


    annualized_excess_return = (

        annualized_return
        -
        spy_annualized_return

    )


    # ========================================================
    # 15. INFORMATION RATIO
    # ========================================================
    #
    # Relative performance per unit of tracking error.
    # ========================================================

    excess_daily_returns = (

        sector_returns
        -
        benchmark_returns

    )


    tracking_error_daily = float(

        excess_daily_returns.std(
            ddof=1
        )

    )


    if (

        not safe_isfinite(
            tracking_error_daily
        )

        or

        tracking_error_daily <= 1e-12

    ):

        information_ratio = np.nan


    else:

        information_ratio = float(

            excess_daily_returns.mean()

            /

            tracking_error_daily

            *

            np.sqrt(
                TRADING_DAYS
            )

        )


    # ========================================================
    # 16. STORE
    # ========================================================

    sector_risk_rows.append(

        {

            "ticker":
                ticker,

            "sector":
                SECTOR_NAMES[
                    ticker
                ],

            "risk_as_of_date":
                aligned[
                    "date"
                ].iloc[-1],

            "annualized_return_pct":
                annualized_return,

            "spy_annualized_return_pct":
                spy_annualized_return,

            "annualized_excess_return_pct":
                annualized_excess_return,

            "annualized_volatility_pct":
                annualized_volatility,

            "downside_volatility_pct":
                downside_volatility,

            "beta_to_spy":
                beta,

            "correlation_to_spy":
                correlation_to_spy,

            "max_drawdown_pct":
                max_drawdown,

            "drawdown_depth_pct":
                drawdown_depth,

            "information_ratio":
                information_ratio,

        }

    )


SECTOR_RISK_METRICS = (

    pd.DataFrame(
        sector_risk_rows
    )

)


# ============================================================
# 17. VALIDATE RAW RISK METRICS
# ============================================================

raw_risk_columns = [

    "annualized_return_pct",
    "annualized_excess_return_pct",
    "annualized_volatility_pct",
    "downside_volatility_pct",
    "beta_to_spy",
    "correlation_to_spy",
    "max_drawdown_pct",
    "drawdown_depth_pct",
    "information_ratio",

]


if not safe_isfinite(

    SECTOR_RISK_METRICS[
        raw_risk_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite D6 risk metric detected."
    )


# ============================================================
# 18. STANDARDIZE RISK COMPONENTS
# ============================================================

SECTOR_RISK_METRICS[
    "z_volatility"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_METRICS[
        "annualized_volatility_pct"
    ]

)


SECTOR_RISK_METRICS[
    "z_downside_volatility"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_METRICS[
        "downside_volatility_pct"
    ]

)


SECTOR_RISK_METRICS[
    "z_drawdown_depth"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_METRICS[
        "drawdown_depth_pct"
    ]

)


SECTOR_RISK_METRICS[
    "z_beta"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_METRICS[
        "beta_to_spy"
    ]

)


SECTOR_RISK_METRICS[
    "z_information_ratio"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_METRICS[
        "information_ratio"
    ]

)

# ============================================================
# 19. COMPOSITE STANDALONE RISK PENALTY
# ============================================================
#
# Higher score = greater standalone sector risk.
#
# Beta and correlation are intentionally EXCLUDED here.
#
# Reason:
#   They describe systematic / portfolio relationships rather
#   than standalone sector risk.
#
# They remain available as diagnostics and will be used later
# in portfolio construction and covariance analysis.
# ============================================================

SECTOR_RISK_METRICS[
    "risk_penalty_raw"
] = (

    RISK_COMPONENT_WEIGHTS[
        "volatility"
    ]

    *
    SECTOR_RISK_METRICS[
        "z_volatility"
    ]

    +

    RISK_COMPONENT_WEIGHTS[
        "downside_volatility"
    ]

    *
    SECTOR_RISK_METRICS[
        "z_downside_volatility"
    ]

    +

    RISK_COMPONENT_WEIGHTS[
        "max_drawdown"
    ]

    *
    SECTOR_RISK_METRICS[
        "z_drawdown_depth"
    ]

)


SECTOR_RISK_METRICS[
    "risk_penalty_z"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_METRICS[
        "risk_penalty_raw"
    ]

)


# ============================================================
# 20. RISK BUCKET
# ============================================================

def classify_sector_risk(
    z_score: float
) -> str:

    if z_score >= 0.75:

        return "High"

    elif z_score <= -0.75:

        return "Low"

    else:

        return "Medium"


SECTOR_RISK_METRICS[
    "risk_bucket"
] = (

    SECTOR_RISK_METRICS[
        "risk_penalty_z"
    ]

    .apply(
        classify_sector_risk
    )

)


# ============================================================
# 21. MERGE D5 SIGNAL WITH D6 RISK
# ============================================================

SECTOR_RISK_ADJUSTED_SIGNAL = (

    SECTOR_COMBINED_SIGNAL

    .merge(

        SECTOR_RISK_METRICS,

        on=[
            "ticker",
            "sector",
        ],

        how="inner",

        validate="one_to_one",

    )

)


if len(
    SECTOR_RISK_ADJUSTED_SIGNAL
) != len(
    SECTOR_TICKERS
):

    raise RuntimeError(
        "D6 merge produced incorrect sector count."
    )


# ============================================================
# 22. RISK-ADJUST D5 SIGNAL
# ============================================================
#
# High-risk sectors receive a modest penalty.
#
# Low-risk sectors receive a modest relative benefit.
#
# D5 remains the primary signal.
# ============================================================

SECTOR_RISK_ADJUSTED_SIGNAL[
    "risk_adjusted_score_raw"
] = (

    SECTOR_RISK_ADJUSTED_SIGNAL[
        "combined_score_z"
    ]

    -

    RISK_ADJUSTMENT_STRENGTH

    *
    SECTOR_RISK_ADJUSTED_SIGNAL[
        "risk_penalty_z"
    ]

)


# ============================================================
# 23. STANDARDIZE RISK-ADJUSTED SCORE
# ============================================================

SECTOR_RISK_ADJUSTED_SIGNAL[
    "risk_adjusted_score_z"
] = risk_cross_sectional_zscore(

    SECTOR_RISK_ADJUSTED_SIGNAL[
        "risk_adjusted_score_raw"
    ]

)


# ============================================================
# 24. RISK-ADJUSTED PERCENTILE
# ============================================================

SECTOR_RISK_ADJUSTED_SIGNAL[
    "risk_adjusted_percentile"
] = (

    SECTOR_RISK_ADJUSTED_SIGNAL[
        "risk_adjusted_score_raw"
    ]

    .rank(
        pct=True,
        method="average"
    )

    *
    100.0

)


# ============================================================
# 25. FINAL RISK-ADJUSTED SIGNAL LABEL
# ============================================================

def classify_risk_adjusted_signal(
    z_score: float
) -> str:

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


SECTOR_RISK_ADJUSTED_SIGNAL[
    "risk_adjusted_signal"
] = (

    SECTOR_RISK_ADJUSTED_SIGNAL[
        "risk_adjusted_score_z"
    ]

    .apply(
        classify_risk_adjusted_signal
    )

)


# ============================================================
# 26. SORT + FINAL D6 RANK
# ============================================================

SECTOR_RISK_ADJUSTED_SIGNAL = (

    SECTOR_RISK_ADJUSTED_SIGNAL

    .sort_values(
        "risk_adjusted_score_raw",
        ascending=False
    )

    .reset_index(
        drop=True
    )

)


SECTOR_RISK_ADJUSTED_SIGNAL[
    "risk_adjusted_rank"
] = (

    np.arange(
        1,
        len(
            SECTOR_RISK_ADJUSTED_SIGNAL
        )
        +
        1
    )

)


# ============================================================
# 27. RANK CHANGE FROM D5
# ============================================================

SECTOR_RISK_ADJUSTED_SIGNAL[
    "risk_rank_change"
] = (

    SECTOR_RISK_ADJUSTED_SIGNAL[
        "combined_rank"
    ]

    -
    SECTOR_RISK_ADJUSTED_SIGNAL[
        "risk_adjusted_rank"
    ]

)


# ============================================================
# 28. SANITY CHECKS
# ============================================================

final_numeric_columns = [

    "risk_penalty_z",
    "risk_adjusted_score_raw",
    "risk_adjusted_score_z",
    "risk_adjusted_percentile",

]


if not safe_isfinite(

    SECTOR_RISK_ADJUSTED_SIGNAL[
        final_numeric_columns
    ]

    .to_numpy(
        dtype=float
    )

).all():

    raise RuntimeError(
        "Non-finite D6 final signal detected."
    )


if (

    SECTOR_RISK_ADJUSTED_SIGNAL[
        "ticker"
    ]

    .duplicated()
    .any()

):

    raise RuntimeError(
        "Duplicate ticker detected in D6."
    )


# ============================================================
# 29. SAVE OUTPUTS
# ============================================================

SECTOR_RISK_METRICS.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_risk_metrics.parquet",

    index=False,

)


SECTOR_RISK_ADJUSTED_SIGNAL.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_risk_adjusted_signal.parquet",

    index=False,

)


# ============================================================
# 30. DISPLAY
# ============================================================

print(
    "=" * 118
)

print(
    "D6 — SECTOR RISK + RISK-ADJUSTED SIGNAL"
)

print(
    "=" * 118
)


print(
    f"Risk lookback:              "
    f"{RISK_LOOKBACK_DAYS} trading days"
)


print(
    f"Risk adjustment strength:   "
    f"{RISK_ADJUSTMENT_STRENGTH:.0%}"
)


print(
    "\nRisk diagnostics:"
)


display(

    SECTOR_RISK_ADJUSTED_SIGNAL[
        [
            "ticker",
            "sector",
            "annualized_return_pct",
            "annualized_excess_return_pct",
            "annualized_volatility_pct",
            "downside_volatility_pct",
            "beta_to_spy",
            "correlation_to_spy",
            "max_drawdown_pct",
            "information_ratio",
            "risk_penalty_z",
            "risk_bucket",
        ]
    ]

)


print(
    "\nRisk-adjusted sector ranking:"
)


display(

    SECTOR_RISK_ADJUSTED_SIGNAL[
        [
            "risk_adjusted_rank",
            "ticker",
            "sector",
            "combined_rank",
            "combined_score_z",
            "risk_penalty_z",
            "risk_adjusted_score_z",
            "risk_adjusted_percentile",
            "risk_adjusted_signal",
            "risk_rank_change",
            "hard_conflict",
        ]
    ]

)


print(
    "\n✓ D6 COMPLETE — "
    "sector risk diagnostics and "
    "risk-adjusted tactical signals generated."
)

# ===== ORIGINAL NOTEBOOK CELL 48 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D7 — SIGNAL QUALITY + SECTOR SELECTION GATE
# ============================================================
#
# Purpose:
#
#   Convert the continuous D6 sector signal into an investable
#   candidate universe.
#
# D7 DOES NOT assign portfolio weights.
#
# It asks:
#
#   1. Is the signal sufficiently strong?
#   2. Does market trend confirm it?
#   3. Do macro and market signals agree?
#   4. Is there a major macro/market conflict?
#   5. Does the risk-adjusted signal still survive?
#
# Output categories:
#
#   STRONG OVERWEIGHT CANDIDATE
#   OVERWEIGHT CANDIDATE
#   TACTICAL POSITIVE / WATCHLIST
#   CONFLICT WATCHLIST
#   NEUTRAL
#   TACTICAL NEGATIVE / WATCHLIST
#   UNDERWEIGHT CANDIDATE
#   STRONG UNDERWEIGHT CANDIDATE
#
# IMPORTANT:
#
#   "Candidate" means eligible for later portfolio
#   construction. It is NOT yet a final allocation.
# ============================================================


# ============================================================
# 1. VALIDATE D6
# ============================================================

required_d7_objects = [

    "SECTOR_RISK_ADJUSTED_SIGNAL",
    "SECTOR_TICKERS",
    "MARKET_AS_OF_DATE",

]


missing_d7_objects = [

    obj
    for obj in required_d7_objects
    if obj not in globals()

]


if missing_d7_objects:

    raise RuntimeError(
        "D7 requires D6 first. Missing: "
        f"{missing_d7_objects}"
    )


# ============================================================
# 2. SELECTION PARAMETERS
# ============================================================
#
# These are transparent decision thresholds.
#
# They are NOT statistically optimized yet.
# ============================================================

STRONG_SIGNAL_THRESHOLD = 1.25

POSITIVE_SIGNAL_THRESHOLD = 0.50

TACTICAL_SIGNAL_THRESHOLD = 0.25


MARKET_CONFIRM_THRESHOLD = 0.20

STRONG_MARKET_CONFIRM_THRESHOLD = 0.75


MIN_POSITIVE_TREND_CONFIRMATIONS = 2

MAX_NEGATIVE_TREND_CONFIRMATIONS = 1


LARGE_DISAGREEMENT_THRESHOLD = 1.25


STRONG_QUALITY_THRESHOLD = 0.70

CANDIDATE_QUALITY_THRESHOLD = 0.55

WATCHLIST_QUALITY_THRESHOLD = 0.40


# ============================================================
# 3. START FROM D6 OUTPUT
# ============================================================

SECTOR_SELECTION_GATE = (

    SECTOR_RISK_ADJUSTED_SIGNAL
    .copy()

)


# ============================================================
# 4. SIGNAL STRENGTH COMPONENTS
# ============================================================
#
# Convert directional signal strength to [0,1].
#
# Positive strength:
#
#       max(z, 0)
#
# Negative strength:
#
#       max(-z, 0)
#
# A ±2 z-score approximately maps to full strength.
# ============================================================

SECTOR_SELECTION_GATE[
    "positive_signal_strength"
] = (

    SECTOR_SELECTION_GATE[
        "risk_adjusted_score_z"
    ]

    .clip(
        lower=0.0
    )

    /
    2.0

).clip(
    upper=1.0
)


SECTOR_SELECTION_GATE[
    "negative_signal_strength"
] = (

    (
        -
        SECTOR_SELECTION_GATE[
            "risk_adjusted_score_z"
        ]
    )

    .clip(
        lower=0.0
    )

    /
    2.0

).clip(
    upper=1.0
)


# ============================================================
# 5. TREND SUPPORT
# ============================================================
#
# Positive candidate:
#   wants price > 50D
#   wants price > 200D
#   wants 3M relative performance > SPY
#
# Negative candidate:
#   wants the opposite.
# ============================================================

SECTOR_SELECTION_GATE[
    "positive_trend_support"
] = (

    SECTOR_SELECTION_GATE[
        "trend_confirmation_count"
    ]

    /
    3.0

)


SECTOR_SELECTION_GATE[
    "negative_trend_support"
] = (

    1.0

    -

    SECTOR_SELECTION_GATE[
        "positive_trend_support"
    ]

)


# ============================================================
# 6. MACRO / MARKET ALIGNMENT SCORES
# ============================================================

POSITIVE_ALIGNMENT_SCORE = {

    "Positive confirmation":
        1.00,

    "Market-led positive":
        0.80,

    "Macro-led positive":
        0.70,

    "Market positive / macro headwind":
        0.40,

    "Macro positive / market weak":
        0.35,

    "Neutral / mixed":
        0.50,

    "Market-led negative":
        0.10,

    "Macro-led negative":
        0.10,

    "Negative confirmation":
        0.00,

}


NEGATIVE_ALIGNMENT_SCORE = {

    "Negative confirmation":
        1.00,

    "Market-led negative":
        0.80,

    "Macro-led negative":
        0.70,

    "Macro positive / market weak":
        0.40,

    "Market positive / macro headwind":
        0.35,

    "Neutral / mixed":
        0.50,

    "Market-led positive":
        0.10,

    "Macro-led positive":
        0.10,

    "Positive confirmation":
        0.00,

}


SECTOR_SELECTION_GATE[
    "positive_alignment_score"
] = (

    SECTOR_SELECTION_GATE[
        "macro_market_alignment"
    ]

    .map(
        POSITIVE_ALIGNMENT_SCORE
    )

)


SECTOR_SELECTION_GATE[
    "negative_alignment_score"
] = (

    SECTOR_SELECTION_GATE[
        "macro_market_alignment"
    ]

    .map(
        NEGATIVE_ALIGNMENT_SCORE
    )

)


if (

    SECTOR_SELECTION_GATE[
        [
            "positive_alignment_score",
            "negative_alignment_score",
        ]
    ]

    .isna()

    .any()

    .any()

):

    unknown_alignment = (

        SECTOR_SELECTION_GATE.loc[

            SECTOR_SELECTION_GATE[
                "positive_alignment_score"
            ]
            .isna(),

            "macro_market_alignment",

        ]

        .unique()

        .tolist()

    )

    raise RuntimeError(
        "Unknown macro/market alignment category: "
        f"{unknown_alignment}"
    )


# ============================================================
# 7. POSITIVE / NEGATIVE QUALITY SCORES
# ============================================================
#
# Quality =
#
#   50% risk-adjusted signal strength
#   30% market-trend confirmation
#   20% macro/market alignment
#
# Risk is not counted again here because D6 already applied
# a standalone risk adjustment.
# ============================================================

SECTOR_SELECTION_GATE[
    "positive_quality_score"
] = (

    0.50
    *
    SECTOR_SELECTION_GATE[
        "positive_signal_strength"
    ]

    +

    0.30
    *
    SECTOR_SELECTION_GATE[
        "positive_trend_support"
    ]

    +

    0.20
    *
    SECTOR_SELECTION_GATE[
        "positive_alignment_score"
    ]

)


SECTOR_SELECTION_GATE[
    "negative_quality_score"
] = (

    0.50
    *
    SECTOR_SELECTION_GATE[
        "negative_signal_strength"
    ]

    +

    0.30
    *
    SECTOR_SELECTION_GATE[
        "negative_trend_support"
    ]

    +

    0.20
    *
    SECTOR_SELECTION_GATE[
        "negative_alignment_score"
    ]

)


# ============================================================
# 8. LARGE DISAGREEMENT FLAG
# ============================================================

SECTOR_SELECTION_GATE[
    "large_macro_market_disagreement"
] = (

    SECTOR_SELECTION_GATE[
        "absolute_macro_market_gap"
    ]

    >=
    LARGE_DISAGREEMENT_THRESHOLD

)


# ============================================================
# 9. MARKET CONFIRMATION FLAGS
# ============================================================

SECTOR_SELECTION_GATE[
    "positive_market_confirmation"
] = (

    (
        SECTOR_SELECTION_GATE[
            "market_score_z"
        ]

        >=
        MARKET_CONFIRM_THRESHOLD
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "trend_confirmation_count"
        ]

        >=
        MIN_POSITIVE_TREND_CONFIRMATIONS
    )

)


SECTOR_SELECTION_GATE[
    "negative_market_confirmation"
] = (

    (
        SECTOR_SELECTION_GATE[
            "market_score_z"
        ]

        <=
        -
        MARKET_CONFIRM_THRESHOLD
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "trend_confirmation_count"
        ]

        <=
        MAX_NEGATIVE_TREND_CONFIRMATIONS
    )

)


# ============================================================
# 10. CANDIDATE GATES
# ============================================================

SECTOR_SELECTION_GATE[
    "strong_overweight_gate"
] = (

    (
        SECTOR_SELECTION_GATE[
            "risk_adjusted_score_z"
        ]

        >=
        STRONG_SIGNAL_THRESHOLD
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "market_score_z"
        ]

        >=
        STRONG_MARKET_CONFIRM_THRESHOLD
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "trend_confirmation_count"
        ]

        >=
        MIN_POSITIVE_TREND_CONFIRMATIONS
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "positive_quality_score"
        ]

        >=
        STRONG_QUALITY_THRESHOLD
    )

    &

    (
        ~SECTOR_SELECTION_GATE[
            "hard_conflict"
        ]
    )

)


SECTOR_SELECTION_GATE[
    "overweight_gate"
] = (

    (
        SECTOR_SELECTION_GATE[
            "risk_adjusted_score_z"
        ]

        >=
        POSITIVE_SIGNAL_THRESHOLD
    )

    &

    SECTOR_SELECTION_GATE[
        "positive_market_confirmation"
    ]

    &

    (
        SECTOR_SELECTION_GATE[
            "positive_quality_score"
        ]

        >=
        CANDIDATE_QUALITY_THRESHOLD
    )

    &

    (
        ~SECTOR_SELECTION_GATE[
            "hard_conflict"
        ]
    )

)


SECTOR_SELECTION_GATE[
    "strong_underweight_gate"
] = (

    (
        SECTOR_SELECTION_GATE[
            "risk_adjusted_score_z"
        ]

        <=
        -
        STRONG_SIGNAL_THRESHOLD
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "market_score_z"
        ]

        <=
        -
        STRONG_MARKET_CONFIRM_THRESHOLD
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "trend_confirmation_count"
        ]

        <=
        MAX_NEGATIVE_TREND_CONFIRMATIONS
    )

    &

    (
        SECTOR_SELECTION_GATE[
            "negative_quality_score"
        ]

        >=
        STRONG_QUALITY_THRESHOLD
    )

    &

    (
        ~SECTOR_SELECTION_GATE[
            "hard_conflict"
        ]
    )

)


SECTOR_SELECTION_GATE[
    "underweight_gate"
] = (

    (
        SECTOR_SELECTION_GATE[
            "risk_adjusted_score_z"
        ]

        <=
        -
        POSITIVE_SIGNAL_THRESHOLD
    )

    &

    SECTOR_SELECTION_GATE[
        "negative_market_confirmation"
    ]

    &

    (
        SECTOR_SELECTION_GATE[
            "negative_quality_score"
        ]

        >=
        CANDIDATE_QUALITY_THRESHOLD
    )

    &

    (
        ~SECTOR_SELECTION_GATE[
            "hard_conflict"
        ]
    )

)


# ============================================================
# 11. FINAL SELECTION STATUS
# ============================================================

def classify_selection_status(
    row: pd.Series
) -> str:
    """
    Convert D7 diagnostics into a candidate status.
    """

    signal = float(
        row[
            "risk_adjusted_score_z"
        ]
    )


    positive_quality = float(
        row[
            "positive_quality_score"
        ]
    )


    negative_quality = float(
        row[
            "negative_quality_score"
        ]
    )


    # --------------------------------------------------------
    # Highest-priority conflict flag
    # --------------------------------------------------------

    if bool(
        row[
            "hard_conflict"
        ]
    ):

        return "CONFLICT WATCHLIST"


    # --------------------------------------------------------
    # Strong positive
    # --------------------------------------------------------

    if bool(
        row[
            "strong_overweight_gate"
        ]
    ):

        return "STRONG OVERWEIGHT CANDIDATE"


    # --------------------------------------------------------
    # Standard positive candidate
    # --------------------------------------------------------

    if bool(
        row[
            "overweight_gate"
        ]
    ):

        return "OVERWEIGHT CANDIDATE"


    # --------------------------------------------------------
    # Strong negative
    # --------------------------------------------------------

    if bool(
        row[
            "strong_underweight_gate"
        ]
    ):

        return "STRONG UNDERWEIGHT CANDIDATE"


    # --------------------------------------------------------
    # Standard negative candidate
    # --------------------------------------------------------

    if bool(
        row[
            "underweight_gate"
        ]
    ):

        return "UNDERWEIGHT CANDIDATE"


    # --------------------------------------------------------
    # Positive but insufficient confirmation
    # --------------------------------------------------------

    if (

        signal
        >=
        TACTICAL_SIGNAL_THRESHOLD

        and

        positive_quality
        >=
        WATCHLIST_QUALITY_THRESHOLD

    ):

        return "TACTICAL POSITIVE / WATCHLIST"


    # --------------------------------------------------------
    # Negative but insufficient confirmation
    # --------------------------------------------------------

    if (

        signal
        <=
        -
        TACTICAL_SIGNAL_THRESHOLD

        and

        negative_quality
        >=
        WATCHLIST_QUALITY_THRESHOLD

    ):

        return "TACTICAL NEGATIVE / WATCHLIST"


    return "NEUTRAL"


SECTOR_SELECTION_GATE[
    "selection_status"
] = (

    SECTOR_SELECTION_GATE

    .apply(
        classify_selection_status,
        axis=1
    )

)


# ============================================================
# 12. INVESTMENT-DIRECTION FIELD
# ============================================================

def selection_direction(
    status: str
) -> str:

    if "OVERWEIGHT" in status:

        return "POSITIVE"

    if "UNDERWEIGHT" in status:

        return "NEGATIVE"

    if "TACTICAL POSITIVE" in status:

        return "POSITIVE"

    if "TACTICAL NEGATIVE" in status:

        return "NEGATIVE"

    if "CONFLICT" in status:

        return "CONFLICT"

    return "NEUTRAL"


SECTOR_SELECTION_GATE[
    "selection_direction"
] = (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .apply(
        selection_direction
    )

)


# ============================================================
# 13. CANDIDATE ELIGIBILITY
# ============================================================

POSITIVE_CANDIDATE_STATUSES = {

    "STRONG OVERWEIGHT CANDIDATE",
    "OVERWEIGHT CANDIDATE",

}


NEGATIVE_CANDIDATE_STATUSES = {

    "STRONG UNDERWEIGHT CANDIDATE",
    "UNDERWEIGHT CANDIDATE",

}


SECTOR_SELECTION_GATE[
    "positive_candidate"
] = (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .isin(
        POSITIVE_CANDIDATE_STATUSES
    )

)


SECTOR_SELECTION_GATE[
    "negative_candidate"
] = (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .isin(
        NEGATIVE_CANDIDATE_STATUSES
    )

)


SECTOR_SELECTION_GATE[
    "watchlist"
] = (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .str.contains(
        "WATCHLIST",
        regex=False
    )

)


# ============================================================
# 14. QUALITY SCORE USED FOR SORTING
# ============================================================

SECTOR_SELECTION_GATE[
    "directional_quality_score"
] = np.where(

    SECTOR_SELECTION_GATE[
        "risk_adjusted_score_z"
    ]
    >=
    0,

    SECTOR_SELECTION_GATE[
        "positive_quality_score"
    ],

    SECTOR_SELECTION_GATE[
        "negative_quality_score"
    ],

)


# ============================================================
# 15. SELECTION PRIORITY
# ============================================================

STATUS_PRIORITY = {

    "STRONG OVERWEIGHT CANDIDATE": 1,

    "OVERWEIGHT CANDIDATE": 2,

    "TACTICAL POSITIVE / WATCHLIST": 3,

    "CONFLICT WATCHLIST": 4,

    "NEUTRAL": 5,

    "TACTICAL NEGATIVE / WATCHLIST": 6,

    "UNDERWEIGHT CANDIDATE": 7,

    "STRONG UNDERWEIGHT CANDIDATE": 8,

}


SECTOR_SELECTION_GATE[
    "status_priority"
] = (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .map(
        STATUS_PRIORITY
    )

)


# ============================================================
# 16. CREATE POSITIVE / NEGATIVE / WATCHLIST TABLES
# ============================================================

POSITIVE_SECTOR_CANDIDATES = (

    SECTOR_SELECTION_GATE[

        SECTOR_SELECTION_GATE[
            "positive_candidate"
        ]

    ]

    .sort_values(

        [
            "positive_quality_score",
            "risk_adjusted_score_z",
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


NEGATIVE_SECTOR_CANDIDATES = (

    SECTOR_SELECTION_GATE[

        SECTOR_SELECTION_GATE[
            "negative_candidate"
        ]

    ]

    .sort_values(

        [
            "negative_quality_score",
            "risk_adjusted_score_z",
        ],

        ascending=[
            False,
            True,
        ],

    )

    .reset_index(
        drop=True
    )

)


SECTOR_WATCHLIST = (

    SECTOR_SELECTION_GATE[

        SECTOR_SELECTION_GATE[
            "watchlist"
        ]

    ]

    .sort_values(

        "directional_quality_score",
        ascending=False

    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 17. OVERALL DISPLAY SORT
# ============================================================

SECTOR_SELECTION_GATE = (

    SECTOR_SELECTION_GATE

    .sort_values(

        [
            "status_priority",
            "risk_adjusted_score_z",
        ],

        ascending=[
            True,
            False,
        ],

    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 18. SANITY CHECKS
# ============================================================

if len(
    SECTOR_SELECTION_GATE
) != len(
    SECTOR_TICKERS
):

    raise RuntimeError(
        "D7 produced incorrect sector count."
    )


if (

    SECTOR_SELECTION_GATE[
        "ticker"
    ]

    .duplicated()

    .any()

):

    raise RuntimeError(
        "Duplicate sector ticker detected in D7."
    )


quality_columns = [

    "positive_quality_score",
    "negative_quality_score",
    "directional_quality_score",

]


if not (

    SECTOR_SELECTION_GATE[
        quality_columns
    ]

    .apply(
        lambda col:
        col.between(
            0.0,
            1.0
        )
        .all()
    )

    .all()

):

    raise RuntimeError(
        "D7 quality score outside [0,1]."
    )


if (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .isna()

    .any()

):

    raise RuntimeError(
        "Missing D7 selection status."
    )


# ============================================================
# 19. SUMMARY COUNTS
# ============================================================

D7_SELECTION_SUMMARY = (

    SECTOR_SELECTION_GATE[
        "selection_status"
    ]

    .value_counts()

    .rename_axis(
        "selection_status"
    )

    .reset_index(
        name="sector_count"
    )

)


# ============================================================
# 20. SAVE OUTPUTS
# ============================================================

SECTOR_SELECTION_GATE.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_selection_gate.parquet",

    index=False,

)


POSITIVE_SECTOR_CANDIDATES.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_positive_sector_candidates.parquet",

    index=False,

)


NEGATIVE_SECTOR_CANDIDATES.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_negative_sector_candidates.parquet",

    index=False,

)


SECTOR_WATCHLIST.to_parquet(

    REGIME_MODEL_DIR
    /
    "live_sector_watchlist.parquet",

    index=False,

)


# ============================================================
# 21. DISPLAY
# ============================================================

print(
    "=" * 120
)

print(
    "D7 — SIGNAL QUALITY + SECTOR SELECTION GATE"
)

print(
    "=" * 120
)


print(
    f"Economic regime:       "
    f"{ECONOMIC_REGIME_LABEL}"
)


print(
    f"Regime conviction:     "
    f"{REGIME_CONVICTION_SCORE:.3f}"
)


print(
    f"Market as-of date:     "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    "\nSelection summary:"
)


display(
    D7_SELECTION_SUMMARY
)


print(
    "\nFull sector gate:"
)


display(

    SECTOR_SELECTION_GATE[
        [
            "ticker",
            "sector",
            "risk_adjusted_rank",
            "risk_adjusted_score_z",
            "market_score_z",
            "macro_prior_z",
            "trend_confirmation_count",
            "positive_quality_score",
            "negative_quality_score",
            "risk_bucket",
            "macro_market_alignment",
            "hard_conflict",
            "selection_status",
        ]
    ]

)


print(
    "\nPositive candidates:"
)


if POSITIVE_SECTOR_CANDIDATES.empty:

    print(
        "No sectors currently pass the positive candidate gate."
    )

else:

    display(

        POSITIVE_SECTOR_CANDIDATES[
            [
                "ticker",
                "sector",
                "risk_adjusted_score_z",
                "positive_quality_score",
                "trend_confirmation_count",
                "risk_bucket",
                "selection_status",
            ]
        ]

    )


print(
    "\nNegative candidates:"
)


if NEGATIVE_SECTOR_CANDIDATES.empty:

    print(
        "No sectors currently pass the negative candidate gate."
    )

else:

    display(

        NEGATIVE_SECTOR_CANDIDATES[
            [
                "ticker",
                "sector",
                "risk_adjusted_score_z",
                "negative_quality_score",
                "trend_confirmation_count",
                "risk_bucket",
                "selection_status",
            ]
        ]

    )


print(
    "\nWatchlist:"
)


if SECTOR_WATCHLIST.empty:

    print(
        "No sectors currently require watchlist treatment."
    )

else:

    display(

        SECTOR_WATCHLIST[
            [
                "ticker",
                "sector",
                "risk_adjusted_score_z",
                "macro_market_gap",
                "hard_conflict",
                "selection_status",
            ]
        ]

    )


print(
    "\n✓ D7 COMPLETE — "
    "sector candidate universe and selection gates generated."
)

# ===== ORIGINAL NOTEBOOK CELL 49 =====
# ============================================================
# SECTION D — LIVE REGIME ENGINE
# CELL D8 — FINAL SECTOR DASHBOARD + PRODUCTION GATE
# ============================================================
#
# Purpose:
#
#   1. Consolidate D1-D7 outputs
#   2. Create the final live sector dashboard
#   3. Run a production-quality health gate
#   4. Prevent later sections from using inconsistent signals
#
# IMPORTANT:
#
#   Section D remains:
#
#       LIVE-ONLY
#       RELATIVE-SECTOR SIGNAL
#       NOT PORTFOLIO WEIGHTS
#
# ============================================================


# ============================================================
# 1. REQUIRED OBJECTS
# ============================================================

required_d8_objects = [

    "REGIME_MODE",
    "LIVE_REGIME_SUMMARY",
    "ECONOMIC_REGIME_PROBABILITIES",
    "FINANCIAL_CONDITIONS_TABLE",

    "LIVE_SECTOR_MACRO_PRIORS",
    "SECTOR_MARKET_SIGNALS",
    "SECTOR_COMBINED_SIGNAL",
    "SECTOR_RISK_ADJUSTED_SIGNAL",
    "SECTOR_SELECTION_GATE",

    "POSITIVE_SECTOR_CANDIDATES",
    "NEGATIVE_SECTOR_CANDIDATES",
    "SECTOR_WATCHLIST",

    "SECTOR_TICKERS",
    "MARKET_AS_OF_DATE",

]


missing_d8_objects = [

    obj

    for obj in required_d8_objects

    if obj not in globals()

]


if missing_d8_objects:

    raise RuntimeError(
        "D8 requires D1-D7 first. Missing: "
        f"{missing_d8_objects}"
    )


# ============================================================
# 2. FINAL DASHBOARD
# ============================================================

FINAL_SECTOR_SIGNAL_DASHBOARD = (

    SECTOR_SELECTION_GATE

    .copy()

    .sort_values(
        "risk_adjusted_rank"
    )

    .reset_index(
        drop=True
    )

)


# ============================================================
# 3. ATTACH GLOBAL REGIME METADATA
# ============================================================

FINAL_SECTOR_SIGNAL_DASHBOARD[
    "regime_mode"
] = REGIME_MODE


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "economic_regime"
] = ECONOMIC_REGIME_LABEL


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "top_regime_candidate"
] = TOP_REGIME


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "top_regime_probability"
] = TOP_REGIME_PROBABILITY


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "regime_confidence"
] = ECONOMIC_REGIME_CONFIDENCE


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "regime_conviction"
] = REGIME_CONVICTION_SCORE


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "financial_conditions"
] = FINANCIAL_CONDITIONS_LABEL


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "financial_conditions_score"
] = FINANCIAL_CONDITIONS_SCORE


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "dynamic_macro_weight"
] = DYNAMIC_MACRO_WEIGHT


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "dynamic_market_weight"
] = DYNAMIC_MARKET_WEIGHT


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "market_as_of_date"
] = pd.Timestamp(
    MARKET_AS_OF_DATE
)


FINAL_SECTOR_SIGNAL_DASHBOARD[
    "inflation_reference_month"
] = str(
    INFLATION_COMMON_MONTH
)


# ============================================================
# 4. FINAL SECTOR VIEW
# ============================================================
#
# Keep only the most decision-relevant fields for the PM view.
# ============================================================

FINAL_SECTOR_PM_VIEW = (

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        [
            "risk_adjusted_rank",
            "ticker",
            "sector",

            "selection_status",

            "macro_rank",
            "market_rank",
            "combined_rank",

            "macro_prior_z",
            "market_score_z",
            "combined_score_z",
            "risk_penalty_z",
            "risk_adjusted_score_z",

            "positive_quality_score",
            "negative_quality_score",

            "trend_confirmation_count",
            "risk_bucket",

            "macro_market_alignment",
            "hard_conflict",

            "relative_1m",
            "relative_3m",
            "relative_6m",

            "trend_50d",
            "trend_200d",

            "annualized_volatility_pct",
            "downside_volatility_pct",
            "max_drawdown_pct",
            "information_ratio",

            "economic_regime",
            "regime_conviction",
            "financial_conditions",

            "market_as_of_date",
        ]
    ]

    .copy()

)


# ============================================================
# 5. ALLOWED SELECTION STATUSES
# ============================================================

ALLOWED_SELECTION_STATUSES = {

    "STRONG OVERWEIGHT CANDIDATE",
    "OVERWEIGHT CANDIDATE",
    "TACTICAL POSITIVE / WATCHLIST",
    "CONFLICT WATCHLIST",
    "NEUTRAL",
    "TACTICAL NEGATIVE / WATCHLIST",
    "UNDERWEIGHT CANDIDATE",
    "STRONG UNDERWEIGHT CANDIDATE",

}


# ============================================================
# 6. HEALTH-CHECK ENGINE
# ============================================================

section_d_checks = []


def add_d8_check(
    check: str,
    passed: bool,
    detail: str
):

    section_d_checks.append(

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


# ============================================================
# 7. CHECK — LIVE-ONLY GOVERNANCE
# ============================================================

add_d8_check(

    "Live-only regime governance",

    REGIME_MODE
    ==
    "LIVE_ONLY",

    f"REGIME_MODE={REGIME_MODE}",

)


# ============================================================
# 8. CHECK — REGIME PROBABILITIES
# ============================================================

regime_probability_sum = float(

    ECONOMIC_REGIME_PROBABILITIES[
        "probability"
    ]
    .sum()

)


add_d8_check(

    "Regime probabilities sum to 1",

    np.isclose(
        regime_probability_sum,
        1.0,
        atol=1e-10
    ),

    f"sum={regime_probability_sum:.10f}",

)


add_d8_check(

    "Four economic regimes present",

    len(
        ECONOMIC_REGIME_PROBABILITIES
    )
    ==
    4,

    (
        f"regime_count="
        f"{len(ECONOMIC_REGIME_PROBABILITIES)}"
    ),

)


# ============================================================
# 9. CHECK — SECTOR COVERAGE THROUGH PIPELINE
# ============================================================

expected_sector_count = len(
    SECTOR_TICKERS
)


pipeline_tables = {

    "D3 macro prior":
        LIVE_SECTOR_MACRO_PRIORS,

    "D4 market confirmation":
        SECTOR_MARKET_SIGNALS,

    "D5 combined signal":
        SECTOR_COMBINED_SIGNAL,

    "D6 risk-adjusted signal":
        SECTOR_RISK_ADJUSTED_SIGNAL,

    "D7 selection gate":
        SECTOR_SELECTION_GATE,

}


for table_name, table in (
    pipeline_tables.items()
):

    actual_count = len(
        table
    )


    add_d8_check(

        f"{table_name} sector coverage",

        actual_count
        ==
        expected_sector_count,

        (
            f"expected={expected_sector_count}, "
            f"actual={actual_count}"
        ),

    )


# ============================================================
# 10. CHECK — UNIQUE FINAL TICKERS
# ============================================================

unique_sector_count = (

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        "ticker"
    ]

    .nunique()

)


add_d8_check(

    "Unique final sector tickers",

    unique_sector_count
    ==
    expected_sector_count,

    (
        f"expected={expected_sector_count}, "
        f"unique={unique_sector_count}"
    ),

)


# ============================================================
# 11. CHECK — EXACT SECTOR UNIVERSE
# ============================================================

final_sector_set = set(

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        "ticker"
    ]

)


expected_sector_set = set(
    SECTOR_TICKERS
)


add_d8_check(

    "Final sector universe matches manifest",

    final_sector_set
    ==
    expected_sector_set,

    (
        f"missing="
        f"{sorted(expected_sector_set - final_sector_set)}, "
        f"extra="
        f"{sorted(final_sector_set - expected_sector_set)}"
    ),

)


# ============================================================
# 12. CHECK — DYNAMIC WEIGHTS
# ============================================================

dynamic_weight_sum = (

    float(
        DYNAMIC_MACRO_WEIGHT
    )

    +

    float(
        DYNAMIC_MARKET_WEIGHT
    )

)


add_d8_check(

    "Dynamic macro/market weights sum to 1",

    np.isclose(
        dynamic_weight_sum,
        1.0,
        atol=1e-10
    ),

    (
        f"macro={DYNAMIC_MACRO_WEIGHT:.4f}, "
        f"market={DYNAMIC_MARKET_WEIGHT:.4f}"
    ),

)


# ============================================================
# 13. CHECK — CONFIDENCE / CONVICTION
# ============================================================

add_d8_check(

    "Regime confidence valid",

    (
        0.0
        <=
        ECONOMIC_REGIME_CONFIDENCE
        <=
        1.0
    ),

    (
        f"confidence="
        f"{ECONOMIC_REGIME_CONFIDENCE:.4f}"
    ),

)


add_d8_check(

    "Regime conviction valid",

    (
        0.0
        <=
        REGIME_CONVICTION_SCORE
        <=
        1.0
    ),

    (
        f"conviction="
        f"{REGIME_CONVICTION_SCORE:.4f}"
    ),

)


# ============================================================
# 14. CHECK — MARKET DATE GOVERNANCE
# ============================================================

latest_sector_signal_date = pd.to_datetime(

    SECTOR_MARKET_SIGNALS[
        "as_of_date"
    ]

).max()


add_d8_check(

    "No sector signal after market cutoff",

    latest_sector_signal_date
    <=
    pd.Timestamp(
        MARKET_AS_OF_DATE
    ),

    (
        f"sector_latest="
        f"{latest_sector_signal_date.date()}, "
        f"cutoff="
        f"{MARKET_AS_OF_DATE.date()}"
    ),

)


# ============================================================
# 15. CHECK — FINAL NUMERIC FIELDS
# ============================================================

critical_numeric_columns = [

    "macro_prior_z",
    "market_score_z",
    "combined_score_z",
    "risk_penalty_z",
    "risk_adjusted_score_z",

    "positive_quality_score",
    "negative_quality_score",

    "annualized_volatility_pct",
    "downside_volatility_pct",
    "max_drawdown_pct",

]


numeric_values = (

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        critical_numeric_columns
    ]

    .to_numpy(
        dtype=float
    )

)


all_numeric_finite = bool(

    safe_isfinite(
        numeric_values
    )
    .all()

)


add_d8_check(

    "Critical sector metrics finite",

    all_numeric_finite,

    (
        f"columns_checked="
        f"{len(critical_numeric_columns)}"
    ),

)


# ============================================================
# 16. CHECK — QUALITY SCORES
# ============================================================

quality_scores_valid = bool(

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        [
            "positive_quality_score",
            "negative_quality_score",
        ]
    ]

    .apply(

        lambda column:

        column.between(
            0.0,
            1.0
        )
        .all()

    )

    .all()

)


add_d8_check(

    "D7 quality scores within [0,1]",

    quality_scores_valid,

    "positive_quality and negative_quality checked",

)


# ============================================================
# 17. CHECK — VALID SELECTION STATUS
# ============================================================

observed_statuses = set(

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        "selection_status"
    ]

)


unknown_statuses = (

    observed_statuses
    -
    ALLOWED_SELECTION_STATUSES

)


add_d8_check(

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


# ============================================================
# 18. CHECK — CANDIDATE CONSISTENCY
# ============================================================

positive_consistent = bool(

    POSITIVE_SECTOR_CANDIDATES[
        "selection_status"
    ]

    .isin(
        POSITIVE_CANDIDATE_STATUSES
    )

    .all()

)


negative_consistent = bool(

    NEGATIVE_SECTOR_CANDIDATES[
        "selection_status"
    ]

    .isin(
        NEGATIVE_CANDIDATE_STATUSES
    )

    .all()

)


add_d8_check(

    "Positive candidate table consistent",

    positive_consistent,

    (
        f"positive_candidates="
        f"{len(POSITIVE_SECTOR_CANDIDATES)}"
    ),

)


add_d8_check(

    "Negative candidate table consistent",

    negative_consistent,

    (
        f"negative_candidates="
        f"{len(NEGATIVE_SECTOR_CANDIDATES)}"
    ),

)


# ============================================================
# 19. CHECK — RANK UNIQUENESS
# ============================================================

rank_unique = bool(

    FINAL_SECTOR_SIGNAL_DASHBOARD[
        "risk_adjusted_rank"
    ]

    .nunique()

    ==
    expected_sector_count

)


add_d8_check(

    "Risk-adjusted ranks unique",

    rank_unique,

    (
        f"unique_ranks="
        f"{FINAL_SECTOR_SIGNAL_DASHBOARD['risk_adjusted_rank'].nunique()}"
    ),

)


# ============================================================
# 20. BUILD SECTION D HEALTH TABLE
# ============================================================

SECTION_D_HEALTH = (

    pd.DataFrame(
        section_d_checks
    )

)


SECTION_D_HEALTH[
    "status"
] = np.where(

    SECTION_D_HEALTH[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


SECTION_D_PASSED = bool(

    SECTION_D_HEALTH[
        "passed"
    ]

    .all()

)


# ============================================================
# 21. SECTION D SUMMARY
# ============================================================

SECTION_D_SUMMARY = pd.DataFrame(

    [

        {

            "regime_mode":
                REGIME_MODE,

            "economic_regime":
                ECONOMIC_REGIME_LABEL,

            "top_regime_candidate":
                TOP_REGIME,

            "top_regime_probability":
                TOP_REGIME_PROBABILITY,

            "regime_confidence":
                ECONOMIC_REGIME_CONFIDENCE,

            "regime_conviction":
                REGIME_CONVICTION_SCORE,

            "financial_conditions":
                FINANCIAL_CONDITIONS_LABEL,

            "financial_conditions_score":
                FINANCIAL_CONDITIONS_SCORE,

            "macro_weight":
                DYNAMIC_MACRO_WEIGHT,

            "market_weight":
                DYNAMIC_MARKET_WEIGHT,

            "positive_candidates":
                len(
                    POSITIVE_SECTOR_CANDIDATES
                ),

            "negative_candidates":
                len(
                    NEGATIVE_SECTOR_CANDIDATES
                ),

            "watchlist_count":
                len(
                    SECTOR_WATCHLIST
                ),

            "hard_conflict_count":
                int(

                    FINAL_SECTOR_SIGNAL_DASHBOARD[
                        "hard_conflict"
                    ]

                    .sum()

                ),

            "market_as_of_date":
                pd.Timestamp(
                    MARKET_AS_OF_DATE
                ),

            "section_d_passed":
                SECTION_D_PASSED,

        }

    ]

)


# ============================================================
# 22. OUTPUT DIRECTORY
# ============================================================

if "OUTPUTS_DIR" in globals():

    SECTION_D_DASHBOARD_DIR = (

        Path(
            OUTPUTS_DIR
        )

        /
        "dashboard"

    )

else:

    SECTION_D_DASHBOARD_DIR = (

        Path(
            REGIME_MODEL_DIR
        )

    )


SECTION_D_DASHBOARD_DIR.mkdir(

    parents=True,
    exist_ok=True,

)


# ============================================================
# 23. SAVE FINAL SECTION D OUTPUTS
# ============================================================

FINAL_SECTOR_SIGNAL_DASHBOARD.to_parquet(

    REGIME_MODEL_DIR
    /
    "final_live_sector_signal_dashboard.parquet",

    index=False,

)


FINAL_SECTOR_PM_VIEW.to_parquet(

    SECTION_D_DASHBOARD_DIR
    /
    "final_live_sector_pm_view.parquet",

    index=False,

)


FINAL_SECTOR_PM_VIEW.to_csv(

    SECTION_D_DASHBOARD_DIR
    /
    "final_live_sector_pm_view.csv",

    index=False,

)


SECTION_D_HEALTH.to_csv(

    SECTION_D_DASHBOARD_DIR
    /
    "section_d_health.csv",

    index=False,

)


SECTION_D_SUMMARY.to_csv(

    SECTION_D_DASHBOARD_DIR
    /
    "section_d_summary.csv",

    index=False,

)


# ============================================================
# 24. DISPLAY
# ============================================================

print(
    "=" * 120
)

print(
    "D8 — FINAL SECTION D DASHBOARD + PRODUCTION GATE"
)

print(
    "=" * 120
)


print(
    f"Regime mode:             "
    f"{REGIME_MODE}"
)


print(
    f"Economic regime:         "
    f"{ECONOMIC_REGIME_LABEL}"
)


print(
    f"Top regime candidate:    "
    f"{TOP_REGIME} "
    f"({TOP_REGIME_PROBABILITY:.1%})"
)


print(
    f"Regime confidence:       "
    f"{ECONOMIC_REGIME_CONFIDENCE:.3f}"
)


print(
    f"Regime conviction:       "
    f"{REGIME_CONVICTION_SCORE:.3f}"
)


print(
    f"Financial conditions:    "
    f"{FINANCIAL_CONDITIONS_LABEL} "
    f"({FINANCIAL_CONDITIONS_SCORE:+.3f})"
)


print(
    f"Macro / market weights:  "
    f"{DYNAMIC_MACRO_WEIGHT:.1%} / "
    f"{DYNAMIC_MARKET_WEIGHT:.1%}"
)


print(
    f"Market as-of date:       "
    f"{MARKET_AS_OF_DATE.date()}"
)


print(
    "\nFinal PM sector dashboard:"
)


display(

    FINAL_SECTOR_PM_VIEW[
        [
            "risk_adjusted_rank",
            "ticker",
            "sector",
            "selection_status",

            "macro_prior_z",
            "market_score_z",
            "risk_adjusted_score_z",

            "positive_quality_score",
            "negative_quality_score",

            "trend_confirmation_count",
            "risk_bucket",
            "macro_market_alignment",
            "hard_conflict",
        ]
    ]

)


print(
    "\nSection D health checks:"
)


display(

    SECTION_D_HEALTH[
        [
            "status",
            "check",
            "detail",
        ]
    ]

)


print(
    "\nSection D summary:"
)


display(
    SECTION_D_SUMMARY
)


# ============================================================
# 25. PRODUCTION GATE
# ============================================================

if not SECTION_D_PASSED:

    failed_d8_checks = (

        SECTION_D_HEALTH.loc[

            ~SECTION_D_HEALTH[
                "passed"
            ],

            [
                "check",
                "detail",
            ],

        ]

    )


    display(
        failed_d8_checks
    )


    raise RuntimeError(

        "SECTION D PRODUCTION GATE FAILED. "
        "Do not proceed to the next section."

    )


print(
    "\n"
    + "=" * 120
)


print(
    "✓ SECTION D PRODUCTION GATE PASSED"
)


print(
    "✓ Regime engine validated"
)


print(
    "✓ Sector macro priors validated"
)


print(
    "✓ Market confirmation validated"
)


print(
    "✓ Risk adjustment validated"
)


print(
    "✓ Sector selection gates validated"
)


print(
    "✓ Section D is ready for downstream use"
)


print(
    "=" * 120
)
