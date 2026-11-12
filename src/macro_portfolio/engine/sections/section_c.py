# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 21 =====
# ============================================================
# SECTION C — FEATURE ENGINE
# CELL C1 — FEATURE STORAGE
# ============================================================

NATIVE_FEATURE_DIR = (
    FEATURE_DATA_DIR / "native"
)

REGIME_FEATURE_DIR = (
    FEATURE_DATA_DIR / "regime"
)


NATIVE_FEATURE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

REGIME_FEATURE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


REGIME_FEATURE_HISTORY_PATH = (
    REGIME_FEATURE_DIR
    /
    "regime_feature_history.parquet"
)

LIVE_FEATURE_SNAPSHOT_PATH = (
    REGIME_FEATURE_DIR
    /
    "live_feature_snapshot.parquet"
)


print("✓ Feature directories initialized.")

print(
    f"Native features: {NATIVE_FEATURE_DIR}"
)

print(
    f"Regime features: {REGIME_FEATURE_DIR}"
)

# ===== ORIGINAL NOTEBOOK CELL 22 =====
# ============================================================
# CELL C2 — FREQUENCY / LOOKBACK DEFINITIONS
# ============================================================

FREQUENCY_PERIODS = {

    "daily": {
        "1m": 21,
        "3m": 63,
        "6m": 126,
        "12m": 252,
        "1y": 252,
        "3y": 756,
        "5y": 1260,
        "10y": 2520,
        "annualization": 252,
    },

    "weekly": {
        "1m": 4,
        "3m": 13,
        "6m": 26,
        "12m": 52,
        "1y": 52,
        "3y": 156,
        "5y": 260,
        "10y": 520,
        "annualization": 52,
    },

    "monthly": {
        "1m": 1,
        "3m": 3,
        "6m": 6,
        "12m": 12,
        "1y": 12,
        "3y": 36,
        "5y": 60,
        "10y": 120,
        "annualization": 12,
    },

    "quarterly": {
        "1m": 1,
        "3m": 1,
        "6m": 2,
        "12m": 4,
        "1y": 4,
        "3y": 12,
        "5y": 20,
        "10y": 40,
        "annualization": 4,
    },
}


def get_frequency_periods(
    frequency: str
) -> dict:

    if frequency not in FREQUENCY_PERIODS:

        raise ValueError(
            f"Unsupported frequency: {frequency}"
        )

    return FREQUENCY_PERIODS[
        frequency
    ]


print("✓ Frequency conventions initialized.")

# ===== ORIGINAL NOTEBOOK CELL 23 =====
# ============================================================
# CELL C3 — STATISTICAL FEATURE HELPERS
# ============================================================


def rolling_zscore(
    series: pd.Series,
    window: int,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """
    Rolling z-score using information available
    up to each observation.
    """

    if min_periods is None:

        min_periods = max(
            8,
            int(window * 0.50)
        )


    rolling_mean = (
        series
        .rolling(
            window=window,
            min_periods=min_periods
        )
        .mean()
    )


    rolling_std = (
        series
        .rolling(
            window=window,
            min_periods=min_periods
        )
        .std(ddof=0)
    )


    z = (
        series - rolling_mean
    ) / rolling_std.replace(
        0,
        np.nan
    )


    return z

def get_manifest_record(
    series_id: str
) -> pd.Series:
    """
    Return one Master Data Dictionary record.
    """

    match = DATA_MANIFEST[
        DATA_MANIFEST["series_id"]
        ==
        series_id
    ]

    if match.empty:
        raise KeyError(
            f"{series_id} not found in DATA_MANIFEST."
        )

    return match.iloc[0]


def expanding_zscore(
    series: pd.Series,
    min_periods: int = 20,
) -> pd.Series:
    """
    Expanding z-score.
    Useful later as a robustness alternative.
    """

    mean = (
        series
        .expanding(
            min_periods=min_periods
        )
        .mean()
    )


    std = (
        series
        .expanding(
            min_periods=min_periods
        )
        .std(ddof=0)
    )


    return (
        series - mean
    ) / std.replace(
        0,
        np.nan
    )


def safe_pct_change(
    series: pd.Series,
    periods: int,
) -> pd.Series:
    """
    Percentage change with protection from zero denominators.
    """

    lagged = series.shift(
        periods
    )


    valid = (
        lagged.abs()
        >
        1e-12
    )


    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float
    )


    result.loc[valid] = (

        series.loc[valid]
        /
        lagged.loc[valid]
        -
        1

    )


    return result


print("✓ Statistical helper functions initialized.")

# ===== ORIGINAL NOTEBOOK CELL 24 =====
# ============================================================
# CELL C4 — FRED NATIVE FEATURE ENGINE
# ============================================================


def build_fred_features(
    series_id: str,
    frequency: str,
) -> pd.DataFrame:
    """
    Generate native-frequency features for a FRED series.
    """

    df = load_existing_series(
        dataset="fred",
        series_id=series_id
    )


    if df.empty:

        return pd.DataFrame()


    df = df.copy()


    df["date"] = pd.to_datetime(
        df["date"]
    )


    df = (
        df
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )


    value = pd.to_numeric(
        df["value"],
        errors="coerce"
    )


    periods = get_frequency_periods(
        frequency
    )


    features = pd.DataFrame(
        {
            "date": df["date"],
            "series_id": series_id,
            "value": value,
        }
    )


    # --------------------------------------------------------
    # Absolute changes
    # --------------------------------------------------------

    features["delta_1m"] = (
        value
        -
        value.shift(
            periods["1m"]
        )
    )


    features["delta_3m"] = (
        value
        -
        value.shift(
            periods["3m"]
        )
    )


    features["delta_6m"] = (
        value
        -
        value.shift(
            periods["6m"]
        )
    )


    features["delta_12m"] = (
        value
        -
        value.shift(
            periods["12m"]
        )
    )


    # --------------------------------------------------------
    # Percentage changes
    # --------------------------------------------------------

    features["pct_1m"] = safe_pct_change(
        value,
        periods["1m"]
    )


    features["pct_3m"] = safe_pct_change(
        value,
        periods["3m"]
    )


    features["pct_6m"] = safe_pct_change(
        value,
        periods["6m"]
    )


    features["yoy_pct"] = safe_pct_change(
        value,
        periods["12m"]
    )


    # Convert percentage changes into %
    for column in [
        "pct_1m",
        "pct_3m",
        "pct_6m",
        "yoy_pct",
    ]:

        features[column] *= 100


    # --------------------------------------------------------
    # Raw-value z-scores
    # --------------------------------------------------------

    features["value_z_5y"] = rolling_zscore(

        value,

        window=periods["5y"]

    )


    features["value_z_10y"] = rolling_zscore(

        value,

        window=periods["10y"]

    )


    # --------------------------------------------------------
    # Feature-specific z-scores
    # --------------------------------------------------------

    for feature in [
        "delta_3m",
        "pct_3m",
        "yoy_pct",
    ]:

        features[
            f"{feature}_z_5y"
        ] = rolling_zscore(

            features[feature],

            window=periods["5y"]

        )


    return features


print("✓ FRED native feature engine initialized.")

# ===== ORIGINAL NOTEBOOK CELL 25 =====
# ============================================================
# CELL C5 — MARKET NATIVE FEATURE ENGINE
# ============================================================


def build_market_features(
    series_id: str,
    frequency: str = "daily",
) -> pd.DataFrame:
    """
    Generate price, return, volatility and drawdown
    features for market series.
    """

    df = load_existing_series(
        dataset="market",
        series_id=series_id
    )


    if df.empty:

        return pd.DataFrame()


    df = df.copy()


    df["date"] = pd.to_datetime(
        df["date"]
    )


    df = (
        df
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )


    periods = get_frequency_periods(
        frequency
    )


    # Prefer adjusted close when available
    if (
        "adj_close" in df.columns
        and
        df["adj_close"].notna().any()
    ):

        price = pd.to_numeric(
            df["adj_close"],
            errors="coerce"
        )

    else:

        price = pd.to_numeric(
            df["close"],
            errors="coerce"
        )


    features = pd.DataFrame(
        {
            "date": df["date"],
            "series_id": series_id,
            "price": price,
        }
    )


    # --------------------------------------------------------
    # Daily return
    # --------------------------------------------------------

    features["ret_1d"] = (
        price.pct_change()
    )


    # --------------------------------------------------------
    # Total returns
    # --------------------------------------------------------

    features["ret_1m"] = (
        price.pct_change(
            periods["1m"]
        )
        *
        100
    )


    features["ret_3m"] = (
        price.pct_change(
            periods["3m"]
        )
        *
        100
    )


    features["ret_6m"] = (
        price.pct_change(
            periods["6m"]
        )
        *
        100
    )


    features["ret_12m"] = (
        price.pct_change(
            periods["12m"]
        )
        *
        100
    )


    # --------------------------------------------------------
    # Realized volatility
    # --------------------------------------------------------

    annualization = (
        periods["annualization"]
    )


    features["vol_1m"] = (

        features["ret_1d"]

        .rolling(
            periods["1m"]
        )

        .std(ddof=0)

        *
        np.sqrt(
            annualization
        )

        *
        100

    )


    features["vol_3m"] = (

        features["ret_1d"]

        .rolling(
            periods["3m"]
        )

        .std(ddof=0)

        *
        np.sqrt(
            annualization
        )

        *
        100

    )


    # --------------------------------------------------------
    # Rolling 12M drawdown
    # --------------------------------------------------------

    rolling_peak = (

        price

        .rolling(
            periods["12m"],
            min_periods=max(
                20,
                int(
                    periods["12m"]
                    *
                    0.25
                )
            )
        )

        .max()

    )


    features["drawdown_12m"] = (

        price
        /
        rolling_peak
        -
        1

    ) * 100


    # --------------------------------------------------------
    # Momentum z-score
    # --------------------------------------------------------

    features[
        "ret_3m_z_5y"
    ] = rolling_zscore(

        features["ret_3m"],

        window=periods["5y"]

    )


    return features


print("✓ Market native feature engine initialized.")

# ===== ORIGINAL NOTEBOOK CELL 26 =====
# ============================================================
# CELL C6 — GENERATE ALL NATIVE FEATURES
# ============================================================


def get_native_feature_path(
    dataset: str,
    series_id: str
) -> Path:

    filename = (
        f"{dataset}_"
        f"{safe_filename(series_id)}"
        f".parquet"
    )

    return (
        NATIVE_FEATURE_DIR
        /
        filename
    )


native_feature_summary = []


for _, row in DATA_MANIFEST[
    DATA_MANIFEST["enabled"]
].iterrows():

    dataset = row["dataset"]
    series_id = row["series_id"]
    frequency = row["frequency"]


    try:

        if dataset == "fred":

            feature_df = build_fred_features(
                series_id=series_id,
                frequency=frequency
            )


        elif dataset == "market":

            feature_df = build_market_features(
                series_id=series_id,
                frequency=frequency
            )


        else:

            continue


        if feature_df.empty:

            logger.warning(
                f"No features generated for "
                f"{dataset}:{series_id}"
            )

            continue


        feature_path = (
            get_native_feature_path(
                dataset,
                series_id
            )
        )


        feature_df.to_parquet(
            feature_path,
            index=False
        )


        native_feature_summary.append(
            {
                "dataset": dataset,
                "series_id": series_id,
                "rows": len(feature_df),
                "first_date":
                    feature_df["date"].min(),
                "last_date":
                    feature_df["date"].max(),
                "columns":
                    len(feature_df.columns),
            }
        )


        logger.info(
            f"Features {dataset}:{series_id} | "
            f"{len(feature_df):,} rows"
        )


    except Exception as exc:

        logger.error(
            f"Feature generation failed for "
            f"{dataset}:{series_id}: "
            f"{exc}"
        )


NATIVE_FEATURE_SUMMARY = pd.DataFrame(
    native_feature_summary
)


print(
    f"✓ Native features generated for "
    f"{len(NATIVE_FEATURE_SUMMARY)} series."
)


display(
    NATIVE_FEATURE_SUMMARY
    .head(10)
)

# ===== ORIGINAL NOTEBOOK CELL 27 =====
# ============================================================
# SECTION C.1 — MACRO STATE + MOMENTUM ENGINE
# CELL C12 — LONG-RUN STANDARDIZATION HELPERS
# ============================================================


MIN_STATE_HISTORY = {

    "daily": 1260,       # ~5 years
    "weekly": 260,       # ~5 years
    "monthly": 60,       # 5 years
    "quarterly": 20,     # 5 years

}


MIN_MOMENTUM_HISTORY = {

    "daily": 756,        # ~3 years
    "weekly": 156,
    "monthly": 36,
    "quarterly": 12,

}


def expanding_standardize(
    series: pd.Series,
    min_periods: int,
) -> pd.Series:
    """
    Expanding z-score.

    Unlike the previous 5-year rolling z-score,
    this preserves a longer-run economic reference point.
    """

    series = pd.to_numeric(
        series,
        errors="coerce"
    )


    expanding_mean = (

        series

        .expanding(
            min_periods=min_periods
        )

        .mean()

    )


    expanding_std = (

        series

        .expanding(
            min_periods=min_periods
        )

        .std(ddof=0)

        .replace(
            0,
            np.nan
        )

    )


    return (

        (
            series
            -
            expanding_mean
        )

        /
        expanding_std

    )


def classify_momentum(
    score: float
) -> str:
    """
    Generic directional momentum label.
    """

    if pd.isna(score):
        return "Unavailable"

    if score >= 1.0:
        return "Accelerating strongly"

    elif score >= 0.25:
        return "Accelerating"

    elif score <= -1.0:
        return "Decelerating strongly"

    elif score <= -0.25:
        return "Decelerating"

    else:
        return "Stable"


print(
    "✓ Long-run state/momentum helpers initialized."
)

# ===== ORIGINAL NOTEBOOK CELL 28 =====
# ============================================================
# CELL C13 — STATE / MOMENTUM COMPONENT SPECIFICATION
# ============================================================


MACRO_COMPONENT_SPECS = pd.DataFrame(

    [

        # ====================================================
        # GROWTH
        # Positive = stronger growth
        # ====================================================

        ["growth", "GDPC1",  "yoy_pct",  +1, 1.00, "6m"],
        ["growth", "INDPRO", "yoy_pct",  +1, 1.00, "3m"],
        ["growth", "RSAFS",  "yoy_pct",  +1, 0.75, "3m"],
        ["growth", "PAYEMS", "yoy_pct",  +1, 1.00, "3m"],

        # Lower unemployment = stronger growth
        ["growth", "UNRATE", "value",    -1, 1.00, "3m"],

        # Lower claims = stronger growth
        ["growth", "ICSA",   "value",    -1, 1.00, "3m"],

        ["growth", "JTSJOL", "yoy_pct",  +1, 0.75, "3m"],
        ["growth", "PERMIT", "yoy_pct",  +1, 0.75, "3m"],
        ["growth", "HOUST",  "yoy_pct",  +1, 0.75, "3m"],


        # ====================================================
        # INFLATION
        # Positive = more inflation pressure
        # ====================================================

        ["inflation", "CPIAUCSL",
         "yoy_pct", +1, 1.00, "3m"],

        ["inflation", "CPILFESL",
         "yoy_pct", +1, 1.25, "3m"],

        ["inflation", "PCEPI",
         "yoy_pct", +1, 1.00, "3m"],

        ["inflation", "PCEPILFE",
         "yoy_pct", +1, 1.50, "3m"],

        ["inflation", "PPIACO",
         "yoy_pct", +1, 0.50, "3m"],

        ["inflation", "CES0500000003",
         "yoy_pct", +1, 0.75, "3m"],

        ["inflation", "ECIWAG",
         "yoy_pct", +1, 0.75, "6m"],

        ["inflation", "T10YIE",
         "value", +1, 0.50, "3m"],


        # ====================================================
        # RATES / POLICY
        # Positive = tighter rate environment
        # ====================================================

        ["rates", "DFF",
         "value", +1, 0.50, "3m"],

        ["rates", "DGS2",
         "value", +1, 1.00, "3m"],

        ["rates", "DGS10",
         "value", +1, 0.75, "3m"],

        # Real yield gets high weight
        ["rates", "DFII10",
         "value", +1, 1.50, "3m"],

        # More inversion = tighter conditions
        ["rates", "T10Y2Y",
         "value", -1, 0.75, "3m"],

        ["rates", "T10Y3M",
         "value", -1, 0.75, "3m"],


        # ====================================================
        # LIQUIDITY
        # Positive = easier liquidity
        # ====================================================

        ["liquidity", "WALCL",
         "yoy_pct", +1, 1.00, "3m"],

        ["liquidity", "RRPONTSYD",
         "value", -1, 0.75, "3m"],

        ["liquidity", "WTREGEN",
         "value", -1, 0.75, "3m"],

        ["liquidity", "M2SL",
         "yoy_pct", +1, 1.00, "3m"],

        ["liquidity", "NFCI",
         "value", -1, 1.25, "3m"],


        # ====================================================
        # CREDIT STRESS
        # Positive = worse credit environment
        # ====================================================

        ["credit_stress", "BAMLH0A0HYM2",
         "value", +1, 1.50, "1m"],

        ["credit_stress", "BAMLC0A0CM",
         "value", +1, 0.75, "1m"],

        ["credit_stress", "DRTSCILM",
         "value", +1, 1.00, "3m"],

        ["credit_stress", "TOTLL",
         "yoy_pct", -1, 0.50, "3m"],


        # ====================================================
        # MARKET
        # Positive = stronger risk appetite
        # ====================================================

        ["market", "SPY",
         "ret_12m", +1, 1.25, "3m"],

        ["market", "RSP",
         "ret_12m", +1, 0.75, "3m"],

        ["market", "IWM",
         "ret_12m", +1, 0.75, "3m"],

        ["market", "HYG",
         "ret_12m", +1, 0.75, "3m"],

        ["market", "VIXCLS",
         "value", -1, 1.00, "1m"],

        ["market", "HG=F",
         "ret_6m", +1, 0.50, "3m"],

    ],

    columns=[
        "factor",
        "series_id",
        "state_feature",
        "direction",
        "weight",
        "momentum_horizon",
    ]

)


display(
    MACRO_COMPONENT_SPECS
)


print(
    f"✓ {len(MACRO_COMPONENT_SPECS)} "
    f"state/momentum components defined."
)

# ===== ORIGINAL NOTEBOOK CELL 29 =====
# ============================================================
# CELL C14 — COMPONENT STATE + MOMENTUM ENGINE
# ============================================================
#
# Purpose:
#   Build state, momentum and acceleration scores for each
#   macro component.
#
# Important treatment:
#   - Normal series use the standard long-history thresholds.
#   - LIVE_ONLY series use shorter minimum histories so that
#     current/live indicators such as HY/IG OAS can contribute
#     to today's macro signal.
#   - LIVE_ONLY does NOT make those series historically
#     backtest-safe.
# ============================================================


# ------------------------------------------------------------
# LIVE-ONLY HISTORY REQUIREMENTS
# ------------------------------------------------------------
#
# These are deliberately shorter than the standard thresholds
# defined in C12.
#
# Example:
#   HY / IG OAS currently have ~3 years of history.
#   Requiring 5 years would make their live signal unusable.
# ------------------------------------------------------------

LIVE_ONLY_MIN_STATE_HISTORY = {

    "daily": 504,       # ~2 trading years
    "weekly": 104,      # ~2 years
    "monthly": 24,      # 2 years
    "quarterly": 8,     # 2 years

}


LIVE_ONLY_MIN_MOMENTUM_HISTORY = {

    "daily": 252,       # ~1 trading year
    "weekly": 52,       # ~1 year
    "monthly": 12,      # 1 year
    "quarterly": 4,     # 1 year

}


# ============================================================
# 1. LOAD NATIVE FEATURES
# ============================================================

def load_native_features_for_series(
    series_id: str
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load the native feature file for one series and return
    both the feature dataframe and its manifest metadata.
    """

    manifest_row = get_manifest_record(
        series_id
    )


    dataset = manifest_row[
        "dataset"
    ]


    feature_path = get_native_feature_path(
        dataset,
        series_id
    )


    if not feature_path.exists():

        raise FileNotFoundError(
            f"Native feature file missing: "
            f"{series_id}"
        )


    df = pd.read_parquet(
        feature_path
    )


    if "date" not in df.columns:

        raise KeyError(
            f"{series_id}: date column missing."
        )


    df["date"] = pd.to_datetime(
        df["date"]
    )


    df = (
        df
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )


    return (
        df,
        manifest_row
    )


# ============================================================
# 2. HISTORY-THRESHOLD HELPER
# ============================================================

def get_component_history_requirements(
    manifest_row: pd.Series,
    frequency: str,
) -> Tuple[int, int, str]:
    """
    Select history requirements based on the series' usage
    scope.

    Returns
    -------
    state_min_periods
    momentum_min_periods
    history_mode
    """

    usage_scope = str(
        manifest_row.get(
            "usage_scope",
            "LIVE_AND_HISTORY"
        )
    )


    if usage_scope == "LIVE_ONLY":

        state_min_periods = (
            LIVE_ONLY_MIN_STATE_HISTORY[
                frequency
            ]
        )

        momentum_min_periods = (
            LIVE_ONLY_MIN_MOMENTUM_HISTORY[
                frequency
            ]
        )

        history_mode = "LIVE_ONLY_SHORT_HISTORY"


    else:

        state_min_periods = (
            MIN_STATE_HISTORY[
                frequency
            ]
        )

        momentum_min_periods = (
            MIN_MOMENTUM_HISTORY[
                frequency
            ]
        )

        history_mode = "STANDARD_LONG_HISTORY"


    return (
        state_min_periods,
        momentum_min_periods,
        history_mode,
    )


# ============================================================
# 3. BUILD STATE / MOMENTUM / ACCELERATION
# ============================================================

def build_component_state_momentum(
    spec: pd.Series
) -> pd.DataFrame:
    """
    Build state, momentum and acceleration signals for one
    macro component.
    """

    # --------------------------------------------------------
    # Specification
    # --------------------------------------------------------

    series_id = spec[
        "series_id"
    ]


    feature_name = spec[
        "state_feature"
    ]


    direction = float(
        spec[
            "direction"
        ]
    )


    factor = spec[
        "factor"
    ]


    weight = float(
        spec[
            "weight"
        ]
    )


    momentum_horizon = spec[
        "momentum_horizon"
    ]


    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    df, manifest_row = (
        load_native_features_for_series(
            series_id
        )
    )


    frequency = manifest_row[
        "frequency"
    ]


    if frequency not in MIN_STATE_HISTORY:

        raise ValueError(
            f"{series_id}: unsupported frequency "
            f"{frequency}"
        )


    if feature_name not in df.columns:

        raise KeyError(
            f"{series_id}: "
            f"{feature_name} unavailable."
        )


    periods = get_frequency_periods(
        frequency
    )


    if momentum_horizon not in periods:

        raise KeyError(
            f"{series_id}: unsupported momentum "
            f"horizon {momentum_horizon}"
        )


    momentum_periods = periods[
        momentum_horizon
    ]


    # --------------------------------------------------------
    # Select history requirements
    # --------------------------------------------------------

    (
        state_min_periods,
        momentum_min_periods,
        history_mode,
    ) = get_component_history_requirements(

        manifest_row,
        frequency,

    )


    # --------------------------------------------------------
    # Base dataframe
    # --------------------------------------------------------

    result = pd.DataFrame(
        {
            "date":
                df["date"],

            "raw_state":
                pd.to_numeric(
                    df[
                        feature_name
                    ],
                    errors="coerce"
                ),
        }
    )


    # ========================================================
    # STATE
    #
    # Positive/negative interpretation is controlled by
    # direction in MACRO_COMPONENT_SPECS.
    # ========================================================

    result[
        "state_score"
    ] = (

        expanding_standardize(

            result[
                "raw_state"
            ],

            min_periods=(
                state_min_periods
            )

        )

        *
        direction

    )


    result[
        "state_score"
    ] = (

        result[
            "state_score"
        ]

        .clip(
            lower=-3,
            upper=3
        )

    )


    # ========================================================
    # MOMENTUM
    #
    # Change in the underlying economic state variable over
    # the component-specific horizon.
    # ========================================================

    result[
        "raw_momentum"
    ] = (

        result[
            "raw_state"
        ]

        -

        result[
            "raw_state"
        ]
        .shift(
            momentum_periods
        )

    )


    result[
        "momentum_score"
    ] = (

        expanding_standardize(

            result[
                "raw_momentum"
            ],

            min_periods=(
                momentum_min_periods
            )

        )

        *
        direction

    )


    result[
        "momentum_score"
    ] = (

        result[
            "momentum_score"
        ]

        .clip(
            lower=-3,
            upper=3
        )

    )


    # ========================================================
    # ACCELERATION
    #
    # Measures whether momentum itself is improving or
    # deteriorating.
    # ========================================================

    shorter_horizon = max(

        1,

        int(
            momentum_periods
            /
            2
        )

    )


    result[
        "raw_acceleration"
    ] = (

        result[
            "raw_momentum"
        ]

        -

        result[
            "raw_momentum"
        ]
        .shift(
            shorter_horizon
        )

    )


    result[
        "acceleration_score"
    ] = (

        expanding_standardize(

            result[
                "raw_acceleration"
            ],

            min_periods=(
                momentum_min_periods
            )

        )

        *
        direction

    )


    result[
        "acceleration_score"
    ] = (

        result[
            "acceleration_score"
        ]

        .clip(
            lower=-3,
            upper=3
        )

    )


    # ========================================================
    # METADATA
    # ========================================================

    result[
        "factor"
    ] = factor


    result[
        "series_id"
    ] = series_id


    result[
        "feature"
    ] = feature_name


    result[
        "direction"
    ] = direction


    result[
        "weight"
    ] = weight


    result[
        "frequency"
    ] = frequency


    result[
        "momentum_horizon"
    ] = momentum_horizon


    result[
        "pit_required"
    ] = bool(
        manifest_row.get(
            "pit_required",
            False
        )
    )


    result[
        "usage_scope"
    ] = str(
        manifest_row.get(
            "usage_scope",
            "LIVE_AND_HISTORY"
        )
    )


    # --------------------------------------------------------
    # Audit metadata
    # --------------------------------------------------------

    result[
        "history_mode"
    ] = history_mode


    result[
        "state_min_periods"
    ] = state_min_periods


    result[
        "momentum_min_periods"
    ] = momentum_min_periods


    # Optional governance field
    if "backtest_ready" in manifest_row.index:

        result[
            "backtest_ready"
        ] = bool(
            manifest_row[
                "backtest_ready"
            ]
        )


    return result


# ============================================================
# 4. GENERATE ALL COMPONENT HISTORIES
# ============================================================

component_frames = []

component_errors = []


for _, spec in (
    MACRO_COMPONENT_SPECS
    .iterrows()
):

    try:

        component_df = (
            build_component_state_momentum(
                spec
            )
        )


        component_frames.append(
            component_df
        )


        logger.info(

            f"Macro component generated | "
            f"{spec['series_id']} | "
            f"{spec['factor']}"

        )


    except Exception as exc:

        component_errors.append(
            {
                "series_id":
                    spec[
                        "series_id"
                    ],

                "factor":
                    spec[
                        "factor"
                    ],

                "error":
                    str(exc),
            }
        )


        logger.error(

            f"State/momentum generation failed "
            f"for {spec['series_id']}: "
            f"{exc}"

        )


# ------------------------------------------------------------
# Hard failure if nothing was generated
# ------------------------------------------------------------

if not component_frames:

    raise RuntimeError(
        "No macro component histories were generated."
    )


MACRO_COMPONENT_HISTORY = (
    pd.concat(
        component_frames,
        ignore_index=True
    )
)


MACRO_COMPONENT_HISTORY[
    "date"
] = pd.to_datetime(

    MACRO_COMPONENT_HISTORY[
        "date"
    ]

)


# ============================================================
# 5. C14 QA
# ============================================================

expected_components = (
    MACRO_COMPONENT_SPECS[
        "series_id"
    ]
    .nunique()
)


generated_components = (
    MACRO_COMPONENT_HISTORY[
        "series_id"
    ]
    .nunique()
)


# Components that have at least one valid LIVE state score
valid_live_state_components = (

    MACRO_COMPONENT_HISTORY

    .dropna(
        subset=[
            "state_score"
        ]
    )

    [
        "series_id"
    ]

    .nunique()

)


print(
    "=" * 70
)

print(
    "C14 — MACRO COMPONENT ENGINE"
)

print(
    "=" * 70
)


print(
    f"Rows generated:              "
    f"{len(MACRO_COMPONENT_HISTORY):,}"
)

print(
    f"Components specified:        "
    f"{expected_components}"
)

print(
    f"Components generated:        "
    f"{generated_components}"
)

print(
    f"Components with valid state: "
    f"{valid_live_state_components}"
)


# ------------------------------------------------------------
# Show LIVE_ONLY diagnostics
# ------------------------------------------------------------

live_only_diagnostic = (

    MACRO_COMPONENT_HISTORY[
        MACRO_COMPONENT_HISTORY[
            "usage_scope"
        ]
        ==
        "LIVE_ONLY"
    ]

    .dropna(
        subset=[
            "state_score"
        ]
    )

    .sort_values(
        "date"
    )

    .groupby(
        "series_id",
        as_index=False
    )

    .tail(1)

)


if not live_only_diagnostic.empty:

    print(
        "\nLIVE_ONLY components:"
    )

    display(

        live_only_diagnostic[
            [
                "series_id",
                "factor",
                "date",
                "state_score",
                "momentum_score",
                "acceleration_score",
                "history_mode",
                "state_min_periods",
                "momentum_min_periods",
            ]
        ]

    )


# ------------------------------------------------------------
# Display any generation failures
# ------------------------------------------------------------

if component_errors:

    COMPONENT_ERRORS = pd.DataFrame(
        component_errors
    )

    print(
        "\n⚠ Component generation errors:"
    )

    display(
        COMPONENT_ERRORS
    )

else:

    print(
        "\n✓ No component generation errors."
    )


# ------------------------------------------------------------
# Final status
# ------------------------------------------------------------

if generated_components == expected_components:

    logger.info(
        "C14 PASSED — all macro components generated."
    )

    print(
        "\n✓ C14 COMPLETE — "
        "all specified macro components generated."
    )

else:

    logger.warning(
        "C14 completed with missing components."
    )

    print(
        "\n⚠ C14 COMPLETE WITH WARNINGS — "
        f"{generated_components}/"
        f"{expected_components} components generated."
    )

# ===== ORIGINAL NOTEBOOK CELL 30 =====
# ============================================================
# CELL C15 — CURRENT COMPONENT SNAPSHOT
# ============================================================


# ------------------------------------------------------------
# 1. DEFINE MARKET EOD AS-OF DATE
# ------------------------------------------------------------
#
# Anchor all market-based signals to the latest completed
# SPY trading session so that futures / cross-asset series
# do not use a newer date than U.S. equities.
# ------------------------------------------------------------

spy_feature_path = get_native_feature_path(
    "market",
    "SPY"
)


if not spy_feature_path.exists():

    raise FileNotFoundError(
        f"SPY native feature file missing: "
        f"{spy_feature_path}"
    )


spy_features = pd.read_parquet(
    spy_feature_path
)


spy_features["date"] = pd.to_datetime(
    spy_features["date"]
)


MARKET_AS_OF_DATE = (

    spy_features[
        "date"
    ]

    .dropna()

    .max()

)


if pd.isna(
    MARKET_AS_OF_DATE
):

    raise RuntimeError(
        "Unable to determine MARKET_AS_OF_DATE "
        "from SPY features."
    )


print(
    f"Market EOD as-of date: "
    f"{MARKET_AS_OF_DATE.date()}"
)


# ------------------------------------------------------------
# 2. START FROM VALID COMPONENT STATE SCORES
# ------------------------------------------------------------

snapshot_source = (

    MACRO_COMPONENT_HISTORY

    .dropna(
        subset=[
            "state_score"
        ]
    )

    .copy()

)


snapshot_source[
    "date"
] = pd.to_datetime(

    snapshot_source[
        "date"
    ]

)


# ------------------------------------------------------------
# 3. ALIGN MARKET FACTOR TO ONE COMMON EOD DATE
# ------------------------------------------------------------
#
# Non-market macro series retain their own latest available
# release/observation date.
#
# Market series are capped at MARKET_AS_OF_DATE.
# ------------------------------------------------------------

market_mask = (

    snapshot_source[
        "factor"
    ]

    ==
    "market"

)


non_market_source = (

    snapshot_source[
        ~market_mask
    ]

    .copy()

)


market_source = (

    snapshot_source[
        market_mask
        &
        (
            snapshot_source[
                "date"
            ]
            <=
            MARKET_AS_OF_DATE
        )
    ]

    .copy()

)


snapshot_source = pd.concat(

    [
        non_market_source,
        market_source,
    ],

    ignore_index=True

)


# ------------------------------------------------------------
# 4. SELECT LATEST VALID OBSERVATION PER COMPONENT
# ------------------------------------------------------------

CURRENT_COMPONENTS = (

    snapshot_source

    .sort_values(
        [
            "factor",
            "series_id",
            "date",
        ]
    )

    .groupby(
        [
            "factor",
            "series_id",
        ],
        as_index=False
    )

    .tail(1)

    .reset_index(
        drop=True
    )

)


# ------------------------------------------------------------
# 5. MERGE DISPLAY METADATA
# ------------------------------------------------------------

manifest_display_columns = [
    "series_id",
    "name",
    "priority",
]


optional_manifest_columns = [
    "usage_scope",
    "backtest_ready",
    "pit_required",
]


for column in optional_manifest_columns:

    if column in DATA_MANIFEST.columns:

        manifest_display_columns.append(
            column
        )


manifest_display = (

    DATA_MANIFEST[
        manifest_display_columns
    ]

    .drop_duplicates(
        subset=[
            "series_id"
        ],
        keep="last"
    )

)


# Avoid duplicate metadata columns if C14 already added them
columns_to_merge = [

    column

    for column in manifest_display.columns

    if (
        column == "series_id"
        or
        column not in CURRENT_COMPONENTS.columns
    )

]


CURRENT_COMPONENTS = (

    CURRENT_COMPONENTS.merge(

        manifest_display[
            columns_to_merge
        ],

        on="series_id",

        how="left"

    )

)


# ------------------------------------------------------------
# 6. SNAPSHOT QA
# ------------------------------------------------------------

expected_components = (

    MACRO_COMPONENT_SPECS[
        "series_id"
    ]

    .nunique()

)


actual_components = (

    CURRENT_COMPONENTS[
        "series_id"
    ]

    .nunique()

)


market_dates_used = (

    CURRENT_COMPONENTS.loc[

        CURRENT_COMPONENTS[
            "factor"
        ]
        ==
        "market",

        "date"

    ]

    .dropna()

)


market_date_check = (

    market_dates_used
    <=
    MARKET_AS_OF_DATE

).all()


print(
    "\n"
    + "=" * 72
)

print(
    "CURRENT MACRO COMPONENT SNAPSHOT"
)

print(
    "=" * 72
)


print(
    f"Components expected: "
    f"{expected_components}"
)

print(
    f"Components available: "
    f"{actual_components}"
)

print(
    f"Market EOD aligned:   "
    f"{'✓ YES' if market_date_check else '✗ NO'}"
)


# ------------------------------------------------------------
# 7. DISPLAY SNAPSHOT
# ------------------------------------------------------------

display_columns = [

    "factor",
    "series_id",
    "name",
    "date",
    "raw_state",
    "state_score",
    "raw_momentum",
    "momentum_score",
    "acceleration_score",
    "weight",

]


for optional_column in [

    "usage_scope",
    "history_mode",

]:

    if optional_column in CURRENT_COMPONENTS.columns:

        display_columns.append(
            optional_column
        )


display(

    CURRENT_COMPONENTS[
        display_columns
    ]

    .sort_values(
        [
            "factor",
            "series_id"
        ]
    )

    .reset_index(
        drop=True
    )

)


# ------------------------------------------------------------
# 8. FINAL STATUS
# ------------------------------------------------------------

if (
    actual_components
    ==
    expected_components
    and
    market_date_check
):

    logger.info(
        "C15 PASSED — current component snapshot complete "
        "and market data aligned."
    )

    print(
        "\n✓ C15 COMPLETE — "
        "current component snapshot is healthy."
    )

else:

    logger.warning(
        f"C15 completed with warnings | "
        f"{actual_components}/"
        f"{expected_components} components | "
        f"market_alignment={market_date_check}"
    )

    print(
        "\n⚠ C15 COMPLETE WITH WARNINGS."
    )

# ===== ORIGINAL NOTEBOOK CELL 31 =====
# ============================================================
# CELL C16 — ECONOMICALLY ALIGNED INFLATION STATE
# ============================================================
#
# Purpose:
#   Build the inflation-level diagnostic using ONE COMMON
#   reference month across CPI and PCE series.
#
# This prevents mixing, for example:
#   August CPI + July PCE
# in the same composite inflation number.
#
# The latest individual releases are preserved separately.
# ============================================================


# ------------------------------------------------------------
# 1. INFLATION SERIES CONFIGURATION
# ------------------------------------------------------------

INFLATION_SERIES = {

    "Headline CPI": {
        "series_id": "CPIAUCSL",
        "weight": 0.20,
    },

    "Core CPI": {
        "series_id": "CPILFESL",
        "weight": 0.25,
    },

    "Headline PCE": {
        "series_id": "PCEPI",
        "weight": 0.20,
    },

    "Core PCE": {
        "series_id": "PCEPILFE",
        "weight": 0.35,
    },

}


# ------------------------------------------------------------
# 2. GENERAL NATIVE-FEATURE LOADER
# ------------------------------------------------------------

def load_native_feature_frame(
    series_id: str
) -> pd.DataFrame:
    """
    Load the native feature dataframe for one series.
    """

    manifest_row = get_manifest_record(
        series_id
    )

    dataset = manifest_row[
        "dataset"
    ]

    feature_path = get_native_feature_path(
        dataset,
        series_id
    )


    if not feature_path.exists():

        raise FileNotFoundError(
            f"Native feature file missing: "
            f"{series_id}"
        )


    df = pd.read_parquet(
        feature_path
    )


    if "date" not in df.columns:

        raise KeyError(
            f"{series_id}: date column missing."
        )


    df["date"] = pd.to_datetime(
        df["date"]
    )


    df = (

        df

        .sort_values(
            "date"
        )

        .drop_duplicates(
            subset=[
                "date"
            ],
            keep="last"
        )

        .reset_index(
            drop=True
        )

    )


    return df


# ------------------------------------------------------------
# 3. LATEST VALUE HELPER
# ------------------------------------------------------------
#
# Keep this helper because later cells such as monetary-policy
# diagnostics also use it.
# ------------------------------------------------------------

def latest_native_value(
    series_id: str,
    feature: str
) -> float:
    """
    Return the latest valid value of a native feature.
    """

    df = load_native_feature_frame(
        series_id
    )


    if feature not in df.columns:

        raise KeyError(
            f"{series_id}: "
            f"{feature} unavailable."
        )


    valid = (

        df[
            [
                "date",
                feature,
            ]
        ]

        .dropna(
            subset=[
                feature
            ]
        )

        .sort_values(
            "date"
        )

    )


    if valid.empty:

        return np.nan


    return float(
        valid.iloc[-1][
            feature
        ]
    )


# ------------------------------------------------------------
# 4. LATEST OBSERVATION HELPER
# ------------------------------------------------------------

def latest_native_observation(
    series_id: str,
    feature: str
) -> dict:
    """
    Return latest feature value and observation date.
    """

    df = load_native_feature_frame(
        series_id
    )


    if feature not in df.columns:

        raise KeyError(
            f"{series_id}: "
            f"{feature} unavailable."
        )


    valid = (

        df[
            [
                "date",
                feature,
            ]
        ]

        .dropna(
            subset=[
                feature
            ]
        )

        .sort_values(
            "date"
        )

    )


    if valid.empty:

        return {
            "date": pd.NaT,
            "value": np.nan,
        }


    latest_row = (
        valid.iloc[-1]
    )


    return {

        "date":
            pd.Timestamp(
                latest_row[
                    "date"
                ]
            ),

        "value":
            float(
                latest_row[
                    feature
                ]
            ),

    }


# ============================================================
# 5. FIND LATEST AVAILABLE MONTH FOR EACH SERIES
# ============================================================

latest_release_rows = []


for name, config in (
    INFLATION_SERIES.items()
):

    series_id = config[
        "series_id"
    ]


    latest_obs = (
        latest_native_observation(
            series_id,
            "yoy_pct"
        )
    )


    latest_release_rows.append(
        {
            "name":
                name,

            "series_id":
                series_id,

            "weight":
                config[
                    "weight"
                ],

            "latest_date":
                latest_obs[
                    "date"
                ],

            "latest_month":
                (
                    latest_obs[
                        "date"
                    ].to_period("M")

                    if pd.notna(
                        latest_obs[
                            "date"
                        ]
                    )

                    else pd.NaT
                ),

            "latest_yoy":
                latest_obs[
                    "value"
                ],
        }
    )


INFLATION_LATEST_RELEASES = (
    pd.DataFrame(
        latest_release_rows
    )
)


if (
    INFLATION_LATEST_RELEASES[
        "latest_month"
    ]
    .isna()
    .any()
):

    missing = (

        INFLATION_LATEST_RELEASES.loc[
            INFLATION_LATEST_RELEASES[
                "latest_month"
            ]
            .isna(),
            "series_id"
        ]
        .tolist()

    )

    raise RuntimeError(
        f"Missing inflation observations: "
        f"{missing}"
    )


# ============================================================
# 6. COMMON INFLATION REFERENCE MONTH
# ============================================================
#
# Example:
#
#   CPI       August
#   Core CPI  August
#   PCE       July
#   Core PCE  July
#
# Common month = July.
# ============================================================

INFLATION_COMMON_MONTH = min(

    INFLATION_LATEST_RELEASES[
        "latest_month"
    ]

)


INFLATION_REFERENCE_DATE = (
    INFLATION_COMMON_MONTH
    .to_timestamp()
)


# ============================================================
# 7. EXTRACT ALL FOUR SERIES AT THE SAME MONTH
# ============================================================

aligned_rows = []


for name, config in (
    INFLATION_SERIES.items()
):

    series_id = config[
        "series_id"
    ]


    df = load_native_feature_frame(
        series_id
    )


    if "yoy_pct" not in df.columns:

        raise KeyError(
            f"{series_id}: "
            f"yoy_pct unavailable."
        )


    temp = (

        df[
            [
                "date",
                "yoy_pct",
            ]
        ]

        .dropna(
            subset=[
                "yoy_pct"
            ]
        )

        .copy()

    )


    temp[
        "month"
    ] = (

        temp[
            "date"
        ]

        .dt.to_period(
            "M"
        )

    )


    common_month_data = (

        temp[
            temp[
                "month"
            ]
            ==
            INFLATION_COMMON_MONTH
        ]

        .sort_values(
            "date"
        )

    )


    if common_month_data.empty:

        raise RuntimeError(
            f"{series_id}: no inflation data "
            f"for common reference month "
            f"{INFLATION_COMMON_MONTH}."
        )


    selected = (
        common_month_data
        .iloc[-1]
    )


    aligned_rows.append(
        {
            "name":
                name,

            "series_id":
                series_id,

            "weight":
                config[
                    "weight"
                ],

            "reference_month":
                INFLATION_COMMON_MONTH,

            "observation_date":
                selected[
                    "date"
                ],

            "yoy_pct":
                float(
                    selected[
                        "yoy_pct"
                    ]
                ),
        }
    )


INFLATION_ALIGNED_TABLE = (
    pd.DataFrame(
        aligned_rows
    )
)


# ============================================================
# 8. VALIDATE WEIGHTS
# ============================================================

INFLATION_WEIGHT_SUM = float(

    INFLATION_ALIGNED_TABLE[
        "weight"
    ]
    .sum()

)


if not np.isclose(
    INFLATION_WEIGHT_SUM,
    1.0
):

    raise ValueError(
        f"Inflation weights must sum to 1. "
        f"Current sum: "
        f"{INFLATION_WEIGHT_SUM:.4f}"
    )


# ============================================================
# 9. ALIGNED INFLATION VALUES
# ============================================================

inflation_aligned = {

    row[
        "name"
    ]:
        row[
            "yoy_pct"
        ]

    for _, row in (
        INFLATION_ALIGNED_TABLE
        .iterrows()
    )

}


# Backward-compatible name used by later cells.
# IMPORTANT:
# This now contains COMMON-MONTH values,
# not independently latest values.
inflation_latest = (
    inflation_aligned.copy()
)


# ============================================================
# 10. COMPOSITE INFLATION LEVEL
# ============================================================

INFLATION_LEVEL = float(

    np.average(

        INFLATION_ALIGNED_TABLE[
            "yoy_pct"
        ],

        weights=(
            INFLATION_ALIGNED_TABLE[
                "weight"
            ]
        )

    )

)


# ============================================================
# 11. ECONOMIC INFLATION LABEL
# ============================================================

def classify_inflation_level(
    inflation: float
) -> str:
    """
    Economically anchored inflation-state label.
    """

    if pd.isna(
        inflation
    ):

        return "Unavailable"


    if inflation < 1.5:

        return "Low"


    elif inflation < 2.5:

        return "Near target"


    elif inflation < 3.5:

        return "Elevated"


    else:

        return "High"


INFLATION_LEVEL_LABEL = (

    classify_inflation_level(
        INFLATION_LEVEL
    )

)


# ============================================================
# 12. IDENTIFY NEWER INDIVIDUAL RELEASES
# ============================================================

INFLATION_LATEST_RELEASES[
    "newer_than_common_month"
] = (

    INFLATION_LATEST_RELEASES[
        "latest_month"
    ]

    >
    INFLATION_COMMON_MONTH

)


# ============================================================
# 13. DISPLAY FINAL DIAGNOSTICS
# ============================================================

print(
    "=" * 70
)

print(
    "INFLATION STATE — ALIGNED"
)

print(
    "=" * 70
)


print(
    f"Common reference month: "
    f"{INFLATION_COMMON_MONTH}"
)


print(
    "\nAligned inflation readings:"
)


display(

    INFLATION_ALIGNED_TABLE[
        [
            "name",
            "series_id",
            "reference_month",
            "yoy_pct",
            "weight",
        ]
    ]

)


print(
    f"\nComposite inflation: "
    f"{INFLATION_LEVEL:.2f}%"
)


print(
    f"Inflation state:     "
    f"{INFLATION_LEVEL_LABEL}"
)


# ------------------------------------------------------------
# Latest release information
# ------------------------------------------------------------

print(
    "\nLatest available inflation releases:"
)


display(

    INFLATION_LATEST_RELEASES[
        [
            "name",
            "series_id",
            "latest_month",
            "latest_yoy",
            "newer_than_common_month",
        ]
    ]

)


# ------------------------------------------------------------
# Show newer releases separately
# ------------------------------------------------------------

newer_releases = (

    INFLATION_LATEST_RELEASES[
        INFLATION_LATEST_RELEASES[
            "newer_than_common_month"
        ]
    ]

)


if not newer_releases.empty:

    print(
        "\nLatest releases newer than the "
        "common composite month:"
    )


    for _, row in (
        newer_releases.iterrows()
    ):

        print(

            f"  {row['name']:<15} | "
            f"{row['latest_month']} | "
            f"{row['latest_yoy']:.2f}%"

        )


else:

    print(
        "\n✓ All four inflation series "
        "are aligned to the latest month."
    )


print(
    "\n✓ C16 COMPLETE — "
    "inflation state uses one common reference month."
)

# ===== ORIGINAL NOTEBOOK CELL 32 =====
# ============================================================
# CELL C17 — MONETARY POLICY STANCE
# ============================================================
#
# Purpose:
#   Separate three related but different concepts:
#
#   1. Effective Fed Funds Rate
#   2. Ex-post real policy rate
#          = Fed Funds - Core PCE YoY
#   3. Market real rate
#          = 10Y Treasury real yield
#
# Important:
#   Fed Funds - Core PCE is an EX-POST real policy-rate proxy.
#   It is not yet a full policy-gap estimate because we have
#   not incorporated r* (neutral real interest rate).
# ============================================================


# ------------------------------------------------------------
# 1. LOAD LATEST POLICY / INFLATION OBSERVATIONS
# ------------------------------------------------------------

FED_FUNDS_OBS = (
    latest_native_observation(
        "DFF",
        "value"
    )
)


CORE_PCE_OBS = (
    latest_native_observation(
        "PCEPILFE",
        "yoy_pct"
    )
)


REAL_10Y_OBS = (
    latest_native_observation(
        "DFII10",
        "value"
    )
)


# ------------------------------------------------------------
# 2. EXTRACT VALUES
# ------------------------------------------------------------

FED_FUNDS_RATE = float(
    FED_FUNDS_OBS[
        "value"
    ]
)


CORE_PCE_YOY = float(
    CORE_PCE_OBS[
        "value"
    ]
)


REAL_10Y_YIELD = float(
    REAL_10Y_OBS[
        "value"
    ]
)


# ------------------------------------------------------------
# 3. OBSERVATION DATES
# ------------------------------------------------------------

FED_FUNDS_DATE = (
    FED_FUNDS_OBS[
        "date"
    ]
)


CORE_PCE_DATE = (
    CORE_PCE_OBS[
        "date"
    ]
)


REAL_10Y_DATE = (
    REAL_10Y_OBS[
        "date"
    ]
)


# ------------------------------------------------------------
# 4. VALIDATE INPUTS
# ------------------------------------------------------------

required_policy_values = {

    "Fed Funds":
        FED_FUNDS_RATE,

    "Core PCE":
        CORE_PCE_YOY,

    "10Y real yield":
        REAL_10Y_YIELD,

}


missing_policy_values = [

    name

    for name, value
    in required_policy_values.items()

    if not safe_isfinite(
        value
    )

]


if missing_policy_values:

    raise RuntimeError(
        "Missing monetary-policy inputs: "
        f"{missing_policy_values}"
    )


# ============================================================
# 5. EX-POST REAL POLICY RATE
# ============================================================
#
# This is:
#
#       nominal policy rate - realized inflation
#
# It is useful as a live policy diagnostic, but it is NOT
# equivalent to:
#
#       real policy rate - neutral real rate (r*)
#
# That policy-gap framework will be added later.
# ============================================================

EX_POST_REAL_POLICY_RATE = (

    FED_FUNDS_RATE
    -
    CORE_PCE_YOY

)




# ============================================================
# 6. POLICY-STANCE CLASSIFICATION
# ============================================================
#
# These thresholds are heuristic PM diagnostics.
#
# They are NOT an official Federal Reserve classification
# and should not be interpreted as estimates of r*.
# ============================================================

def classify_policy_stance(
    ex_post_real_rate: float
) -> str:
    """
    Classify the ex-post real policy-rate proxy.

    Positive values imply policy is restrictive relative
    to realized inflation; negative values imply
    accommodative conditions.

    This does not adjust for r*.
    """

    if pd.isna(
        ex_post_real_rate
    ):

        return "Unavailable"


    if ex_post_real_rate <= -1.0:

        return "Highly accommodative"


    elif ex_post_real_rate < 0.0:

        return "Accommodative"


    elif ex_post_real_rate < 1.0:

        return "Mildly restrictive"


    elif ex_post_real_rate < 2.0:

        return "Restrictive"


    else:

        return "Highly restrictive"


POLICY_STANCE = (
    classify_policy_stance(
        EX_POST_REAL_POLICY_RATE
    )
)


# ============================================================
# 7. POLICY DIAGNOSTIC TABLE
# ============================================================

POLICY_DIAGNOSTICS = pd.DataFrame(

    [

        {
            "metric":
                "Effective Fed Funds Rate",

            "value":
                FED_FUNDS_RATE,

            "date":
                FED_FUNDS_DATE,

            "units":
                "%",
        },

        {
            "metric":
                "Core PCE YoY",

            "value":
                CORE_PCE_YOY,

            "date":
                CORE_PCE_DATE,

            "units":
                "%",
        },

        {
            "metric":
                "Ex-post real policy rate",

            "value":
                EX_POST_REAL_POLICY_RATE,

            "date":
                min(
                    FED_FUNDS_DATE,
                    CORE_PCE_DATE
                ),

            "units":
                "%",
        },

        {
            "metric":
                "10Y Treasury real yield",

            "value":
                REAL_10Y_YIELD,

            "date":
                REAL_10Y_DATE,

            "units":
                "%",
        },

    ]

)


# ============================================================
# 8. DISPLAY
# ============================================================

print(
    "=" * 70
)

print(
    "MONETARY POLICY DIAGNOSTICS"
)

print(
    "=" * 70
)


display(
    POLICY_DIAGNOSTICS
)


print(
    f"\nFed Funds:                "
    f"{FED_FUNDS_RATE:.2f}%"
)


print(
    f"Core PCE YoY:             "
    f"{CORE_PCE_YOY:.2f}%"
)


print(
    f"Ex-post real policy rate: "
    f"{EX_POST_REAL_POLICY_RATE:+.2f}%"
)


print(
    f"10Y real yield:           "
    f"{REAL_10Y_YIELD:.2f}%"
)


print(
    f"\nPolicy stance:            "
    f"{POLICY_STANCE}"
)


print(
    "\n✓ C17 COMPLETE — "
    "monetary-policy diagnostics are healthy."
)


# ===== ORIGINAL NOTEBOOK CELL 33 =====
# ============================================================
# CELL C18 — FACTOR AGGREGATION
# ============================================================


def weighted_score(
    df: pd.DataFrame,
    score_column: str
) -> float:

    valid = df.dropna(
        subset=[
            score_column,
            "weight"
        ]
    )


    if valid.empty:

        return np.nan


    weights = (
        valid["weight"]
        /
        valid["weight"]
        .sum()
    )


    return float(

        np.sum(

            valid[
                score_column
            ]

            *
            weights

        )

    )


factor_rows = []


for factor, group in (
    CURRENT_COMPONENTS
    .groupby("factor")
):

    factor_rows.append(
        {
            "factor": factor,

            "state_score":
                weighted_score(
                    group,
                    "state_score"
                ),

            "momentum_score":
                weighted_score(
                    group,
                    "momentum_score"
                ),

            "acceleration_score":
                weighted_score(
                    group,
                    "acceleration_score"
                ),
        }
    )


MACRO_FACTOR_STATE = (
    pd.DataFrame(
        factor_rows
    )
)


for column in [
    "state_score",
    "momentum_score",
    "acceleration_score",
]:

    MACRO_FACTOR_STATE[
        column
    ] = (

        MACRO_FACTOR_STATE[
            column
        ]

        .clip(
            -3,
            3
        )

    )


display(
    MACRO_FACTOR_STATE
)

# ===== ORIGINAL NOTEBOOK CELL 34 =====
# ============================================================
# CELL C19 — PM INTERPRETATION LABELS
# ============================================================


def generic_state_label(
    score: float
) -> str:

    if pd.isna(score):
        return "Unavailable"

    if score >= 1.0:
        return "Very strong"

    elif score >= 0.25:
        return "Strong"

    elif score <= -1.0:
        return "Very weak"

    elif score <= -0.25:
        return "Weak"

    else:
        return "Neutral"


def credit_state_label(
    score: float
) -> str:

    if pd.isna(score):
        return "Unavailable"

    if score >= 1.0:
        return "Severe stress"

    elif score >= 0.25:
        return "Elevated stress"

    elif score <= -1.0:
        return "Very low stress"

    elif score <= -0.25:
        return "Low stress"

    else:
        return "Normal"


def liquidity_state_label(
    score: float
) -> str:

    if pd.isna(score):
        return "Unavailable"

    if score >= 1.0:
        return "Highly supportive"

    elif score >= 0.25:
        return "Supportive"

    elif score <= -1.0:
        return "Very tight"

    elif score <= -0.25:
        return "Tight"

    else:
        return "Neutral"


def market_state_label(
    score: float
) -> str:

    if pd.isna(score):
        return "Unavailable"

    if score >= 1.0:
        return "Strong risk-on"

    elif score >= 0.25:
        return "Risk-on"

    elif score <= -1.0:
        return "Strong risk-off"

    elif score <= -0.25:
        return "Risk-off"

    else:
        return "Neutral"


def factor_state_label(
    factor: str,
    score: float
) -> str:

    if factor == "credit_stress":

        return credit_state_label(
            score
        )

    elif factor == "liquidity":

        return liquidity_state_label(
            score
        )

    elif factor == "market":

        return market_state_label(
            score
        )

    else:

        return generic_state_label(
            score
        )


MACRO_FACTOR_STATE[
    "statistical_state"
] = (

    MACRO_FACTOR_STATE.apply(

        lambda row:

        factor_state_label(
            row["factor"],
            row["state_score"]
        ),

        axis=1

    )

)


MACRO_FACTOR_STATE[
    "momentum"
] = (

    MACRO_FACTOR_STATE[
        "momentum_score"
    ]

    .apply(
        classify_momentum
    )

)


MACRO_FACTOR_STATE[
    "acceleration"
] = (

    MACRO_FACTOR_STATE[
        "acceleration_score"
    ]

    .apply(
        classify_momentum
    )

)


display(
    MACRO_FACTOR_STATE
)

# ===== ORIGINAL NOTEBOOK CELL 35 =====
# ============================================================
# CELL C20 — PM MACRO STATE DASHBOARD
# ============================================================


PM_MACRO_STATE = (
    MACRO_FACTOR_STATE.copy()
)


# ============================================================
# Economic label overrides
# ============================================================

PM_MACRO_STATE[
    "pm_state"
] = (

    PM_MACRO_STATE[
        "statistical_state"
    ]

)


# ------------------------------------------------------------
# Inflation
# ------------------------------------------------------------

PM_MACRO_STATE.loc[

    PM_MACRO_STATE[
        "factor"
    ]
    ==
    "inflation",

    "pm_state"

] = INFLATION_LEVEL_LABEL


# ------------------------------------------------------------
# Rates
# ------------------------------------------------------------

PM_MACRO_STATE.loc[

    PM_MACRO_STATE[
        "factor"
    ]
    ==
    "rates",

    "pm_state"

] = POLICY_STANCE


# ------------------------------------------------------------
# Rename factors for PM display
# ------------------------------------------------------------

DISPLAY_NAMES = {

    "growth":
        "Growth",

    "inflation":
        "Inflation",

    "rates":
        "Monetary policy",

    "liquidity":
        "Liquidity",

    "credit_stress":
        "Credit stress",

    "market":
        "Market risk appetite",

}


PM_MACRO_STATE[
    "macro_block"
] = (

    PM_MACRO_STATE[
        "factor"
    ]

    .map(
        DISPLAY_NAMES
    )

)


PM_MACRO_STATE = (
    PM_MACRO_STATE[
        [
            "macro_block",
            "pm_state",
            "state_score",
            "momentum",
            "momentum_score",
            "acceleration",
            "acceleration_score",
        ]
    ]
)


print(
    "=" * 82
)

print(
    "PM MACRO STATE DASHBOARD"
)

print(
    "=" * 82
)


display(
    PM_MACRO_STATE
)

# ===== ORIGINAL NOTEBOOK CELL 36 =====
# ============================================================
# SECTION C.2 — FINAL PM ENHANCEMENTS
# CELL C21 — ALIGNED SHORT-TERM INFLATION IMPULSE
# ============================================================
#
# Purpose:
#   Measure whether inflation is reaccelerating or
#   disinflating over the short term.
#
# Critical rule:
#   ALL CPI/PCE series use the SAME reference month defined
#   in C16:
#
#       INFLATION_COMMON_MONTH
#
# Therefore we do NOT mix:
#       August CPI
#   with
#       July PCE
#
# Core outputs preserved for downstream cells:
#
#   INFLATION_3M_ANN
#   INFLATION_6M_ANN
#   INFLATION_12M
#   INFLATION_IMPULSE_GAP
#   INFLATION_IMPULSE_LABEL
#   INFLATION_IMPULSE_SCORE
# ============================================================


# ============================================================
# 1. INFLATION BASKET
# ============================================================
#
# Keep exactly the same weights as the economically anchored
# inflation composite from C16.
# ============================================================

if "INFLATION_SERIES" not in globals():
    raise RuntimeError(
        "INFLATION_SERIES is unavailable. Run corrected C16 before C21."
    )


INFLATION_BASKET = {
    config["series_id"]: float(config["weight"])
    for config in INFLATION_SERIES.values()
}


if len(INFLATION_BASKET) != len(INFLATION_SERIES):
    raise ValueError(
        "Inflation series IDs must be unique in INFLATION_SERIES."
    )


# ------------------------------------------------------------
# Validate basket
# ------------------------------------------------------------

if not np.isclose(
    sum(
        INFLATION_BASKET.values()
    ),
    1.0
):

    raise ValueError(
        "INFLATION_BASKET weights must sum to 1."
    )


# ------------------------------------------------------------
# Validate C16 dependency
# ------------------------------------------------------------

if "INFLATION_COMMON_MONTH" not in globals():

    raise RuntimeError(
        "INFLATION_COMMON_MONTH is unavailable. "
        "Run corrected C16 before C21."
    )


if pd.isna(
    INFLATION_COMMON_MONTH
):

    raise RuntimeError(
        "INFLATION_COMMON_MONTH is invalid."
    )


# ============================================================
# 2. RAW MONTHLY PRICE-INDEX LOADER
# ============================================================

def load_monthly_price_index(
    series_id: str
) -> pd.DataFrame:
    """
    Load one FRED monthly price-index series and construct
    a unique monthly time index.
    """

    df = load_existing_series(

        dataset="fred",
        series_id=series_id

    ).copy()


    if df.empty:

        raise RuntimeError(
            f"{series_id}: raw series is empty."
        )


    required_columns = {
        "date",
        "value",
    }


    missing_columns = (

        required_columns
        -
        set(
            df.columns
        )

    )


    if missing_columns:

        raise KeyError(
            f"{series_id}: missing columns "
            f"{sorted(missing_columns)}"
        )


    df["date"] = pd.to_datetime(
        df["date"]
    )


    df["value"] = pd.to_numeric(
        df["value"],
        errors="coerce"
    )


    df = (

        df

        .dropna(
            subset=[
                "date",
                "value",
            ]
        )

        .sort_values(
            "date"
        )

        .copy()

    )


    # Monthly identifier
    df[
        "month"
    ] = (

        df[
            "date"
        ]

        .dt.to_period(
            "M"
        )

    )


    # In case a provider ever returns multiple rows for
    # the same month, retain the latest observation.
    df = (

        df

        .groupby(
            "month",
            as_index=False
        )

        .tail(1)

        .sort_values(
            "month"
        )

        .reset_index(
            drop=True
        )

    )


    return df


# ============================================================
# 3. ANNUALIZED CHANGE AT A FIXED REFERENCE MONTH
# ============================================================
#
# Formula:
#
#              P_t
#   [ ---------------- ]^(12 / h) - 1
#           P_(t-h)
#
# Example:
#
#   h = 3:
#
#       (P_t / P_(t-3))^4 - 1
#
# This is different from simply taking the latest available
# observation of each series.
# ============================================================

def annualized_index_change_at_month(
    series_id: str,
    months: int,
    reference_month
) -> dict:
    """
    Calculate an annualized h-month inflation rate ending at
    one specified common reference month.
    """

    if months <= 0:

        raise ValueError(
            "months must be positive."
        )


    reference_month = pd.Period(
        reference_month,
        freq="M"
    )


    lag_month = (
        reference_month
        -
        months
    )


    df = load_monthly_price_index(
        series_id
    )


    current_rows = (

        df[
            df[
                "month"
            ]
            ==
            reference_month
        ]

    )


    lagged_rows = (

        df[
            df[
                "month"
            ]
            ==
            lag_month
        ]

    )


    if current_rows.empty:

        raise RuntimeError(
            f"{series_id}: no observation for "
            f"{reference_month}."
        )


    if lagged_rows.empty:

        raise RuntimeError(
            f"{series_id}: no observation for "
            f"{lag_month}."
        )


    current_value = float(

        current_rows
        .iloc[-1][
            "value"
        ]

    )


    lagged_value = float(

        lagged_rows
        .iloc[-1][
            "value"
        ]

    )


    if (
        current_value <= 0
        or
        lagged_value <= 0
    ):

        raise ValueError(
            f"{series_id}: price index must be positive."
        )


    annualized = (

        (
            current_value
            /
            lagged_value
        )

        **
        (
            12.0
            /
            months
        )

        -
        1.0

    ) * 100.0


    return {

        "series_id":
            series_id,

        "reference_month":
            reference_month,

        "lag_month":
            lag_month,

        "months":
            months,

        "current_value":
            current_value,

        "lagged_value":
            lagged_value,

        "annualized_rate":
            float(
                annualized
            ),

    }


# ============================================================
# 4. COMMON-MONTH 12M INFLATION HELPER
# ============================================================
#
# Use the already validated/aligned C16 table rather than
# calling latest_native_value(), because latest_native_value()
# could return a newer CPI month than PCE.
# ============================================================

def get_aligned_yoy_inflation(
    series_id: str
) -> float:
    """
    Return C16 YoY inflation for the common reference month.
    """

    if "INFLATION_ALIGNED_TABLE" not in globals():

        raise RuntimeError(
            "INFLATION_ALIGNED_TABLE unavailable. "
            "Run corrected C16 first."
        )


    match = (

        INFLATION_ALIGNED_TABLE[
            INFLATION_ALIGNED_TABLE[
                "series_id"
            ]
            ==
            series_id
        ]

    )


    if match.empty:

        raise KeyError(
            f"{series_id}: missing from "
            f"INFLATION_ALIGNED_TABLE."
        )


    value = float(

        match
        .iloc[-1][
            "yoy_pct"
        ]

    )


    if not safe_isfinite(
        value
    ):

        raise RuntimeError(
            f"{series_id}: aligned YoY inflation invalid."
        )


    return value


# ============================================================
# 5. BUILD ALIGNED INFLATION IMPULSE TABLE
# ============================================================

inflation_impulse_rows = []


for series_id, weight in (
    INFLATION_BASKET.items()
):


    result_3m = (
        annualized_index_change_at_month(

            series_id=series_id,
            months=3,
            reference_month=INFLATION_COMMON_MONTH,

        )
    )


    result_6m = (
        annualized_index_change_at_month(

            series_id=series_id,
            months=6,
            reference_month=INFLATION_COMMON_MONTH,

        )
    )


    inflation_12m = (
        get_aligned_yoy_inflation(
            series_id
        )
    )


    inflation_impulse_rows.append(

        {

            "series_id":
                series_id,

            "weight":
                float(
                    weight
                ),

            "reference_month":
                INFLATION_COMMON_MONTH,

            "inflation_3m_ann":
                result_3m[
                    "annualized_rate"
                ],

            "inflation_6m_ann":
                result_6m[
                    "annualized_rate"
                ],

            "inflation_12m":
                inflation_12m,

        }

    )


INFLATION_IMPULSE_TABLE = (
    pd.DataFrame(
        inflation_impulse_rows
    )
)


# ============================================================
# 6. VALIDATE IMPULSE TABLE
# ============================================================

required_impulse_columns = [

    "inflation_3m_ann",
    "inflation_6m_ann",
    "inflation_12m",

]


if (

    INFLATION_IMPULSE_TABLE[
        required_impulse_columns
    ]

    .isna()

    .any()

    .any()

):

    raise RuntimeError(
        "Inflation impulse table contains missing values."
    )


if not (

    safe_isfinite(

        INFLATION_IMPULSE_TABLE[
            required_impulse_columns
        ]

        .to_numpy(
            dtype=float
        )

    )

    .all()

):

    raise RuntimeError(
        "Inflation impulse table contains "
        "non-finite values."
    )


# ============================================================
# 7. WEIGHTED COMPOSITE
# ============================================================

impulse_weights = (

    INFLATION_IMPULSE_TABLE[
        "weight"
    ]

    .to_numpy(
        dtype=float
    )

)


INFLATION_3M_ANN = float(

    np.average(

        INFLATION_IMPULSE_TABLE[
            "inflation_3m_ann"
        ],

        weights=impulse_weights

    )

)


INFLATION_6M_ANN = float(

    np.average(

        INFLATION_IMPULSE_TABLE[
            "inflation_6m_ann"
        ],

        weights=impulse_weights

    )

)


INFLATION_12M = float(

    np.average(

        INFLATION_IMPULSE_TABLE[
            "inflation_12m"
        ],

        weights=impulse_weights

    )

)


# ------------------------------------------------------------
# C16 consistency check
# ------------------------------------------------------------
#
# The 12M weighted basket should equal the inflation level
# calculated in C16 because both now use identical:
#
#   - reference month
#   - constituent series
#   - weights
# ------------------------------------------------------------

if "INFLATION_LEVEL" in globals():

    if not np.isclose(

        INFLATION_12M,
        INFLATION_LEVEL,

        atol=1e-8,
        rtol=1e-8,

    ):

        raise RuntimeError(

            "C16/C21 inflation mismatch: "
            f"C16={INFLATION_LEVEL:.6f}, "
            f"C21={INFLATION_12M:.6f}"

        )


# ============================================================
# 8. SHORT-TERM INFLATION IMPULSE
# ============================================================
#
# Compare recent annualized inflation with the underlying
# 12-month inflation rate.
#
# Positive:
#   recent inflation is running hotter than the 12M trend.
#
# Negative:
#   recent inflation is running cooler than the 12M trend.
# ============================================================

INFLATION_IMPULSE_GAP = (

    INFLATION_3M_ANN
    -
    INFLATION_12M

)


# ------------------------------------------------------------
# Additional 3M-vs-6M diagnostic
# ------------------------------------------------------------

INFLATION_3M_6M_GAP = (

    INFLATION_3M_ANN
    -
    INFLATION_6M_ANN

)


# ============================================================
# 9. CLASSIFY INFLATION IMPULSE
# ============================================================

def classify_inflation_impulse(
    gap: float
) -> str:
    """
    Classify short-term inflation impulse from the difference
    between 3M annualized inflation and 12M inflation.

    Thresholds are PM heuristics, not official policy levels.
    """

    if pd.isna(
        gap
    ):

        return "Unavailable"


    if gap >= 0.75:

        return "Reaccelerating strongly"


    elif gap >= 0.20:

        return "Reaccelerating"


    elif gap <= -0.75:

        return "Disinflating strongly"


    elif gap <= -0.20:

        return "Disinflating"


    else:

        return "Stable"


INFLATION_IMPULSE_LABEL = (

    classify_inflation_impulse(
        INFLATION_IMPULSE_GAP
    )

)


# ============================================================
# 10. NUMERIC IMPULSE SCORE FOR REGIME ENGINE
# ============================================================
#
# 1 percentage point of impulse gap ≈ score of 1.
#
# Clip extreme observations to avoid one inflation print
# dominating the downstream regime engine.
# ============================================================

INFLATION_IMPULSE_SCORE = float(

    np.clip(

        INFLATION_IMPULSE_GAP
        /
        1.0,

        -2.0,
        2.0,

    )

)


# ============================================================
# 11. SUMMARY TABLE
# ============================================================

INFLATION_IMPULSE_SUMMARY = pd.DataFrame(

    [

        {
            "metric":
                "3M annualized inflation",

            "value":
                INFLATION_3M_ANN,
        },

        {
            "metric":
                "6M annualized inflation",

            "value":
                INFLATION_6M_ANN,
        },

        {
            "metric":
                "12M inflation",

            "value":
                INFLATION_12M,
        },

        {
            "metric":
                "3M minus 12M impulse",

            "value":
                INFLATION_IMPULSE_GAP,
        },

        {
            "metric":
                "3M minus 6M impulse",

            "value":
                INFLATION_3M_6M_GAP,
        },

    ]

)


# ============================================================
# 12. DISPLAY
# ============================================================

print(
    "=" * 72
)

print(
    "SHORT-TERM INFLATION IMPULSE — ALIGNED"
)

print(
    "=" * 72
)


print(
    f"Common reference month: "
    f"{INFLATION_COMMON_MONTH}"
)


print(
    "\nComponent inflation signals:"
)


display(

    INFLATION_IMPULSE_TABLE[
        [
            "series_id",
            "weight",
            "reference_month",
            "inflation_3m_ann",
            "inflation_6m_ann",
            "inflation_12m",
        ]
    ]

)


print(
    "\nComposite inflation impulse:"
)


display(
    INFLATION_IMPULSE_SUMMARY
)


print(
    f"\n3M annualized:   "
    f"{INFLATION_3M_ANN:.2f}%"
)


print(
    f"6M annualized:   "
    f"{INFLATION_6M_ANN:.2f}%"
)


print(
    f"12M inflation:   "
    f"{INFLATION_12M:.2f}%"
)


print(
    f"3M - 12M gap:    "
    f"{INFLATION_IMPULSE_GAP:+.2f} pp"
)


print(
    f"3M - 6M gap:     "
    f"{INFLATION_3M_6M_GAP:+.2f} pp"
)


print(
    f"Short-term view: "
    f"{INFLATION_IMPULSE_LABEL}"
)


print(
    f"Impulse score:   "
    f"{INFLATION_IMPULSE_SCORE:+.3f}"
)


print(
    "\n✓ C21 COMPLETE — "
    "inflation impulse is aligned to one common month."
)


# ===== ORIGINAL NOTEBOOK CELL 37 =====
# ============================================================
# CELL C22 — MONETARY POLICY MULTI-LENS VIEW
# ============================================================
#
# Separate:
#   1. historical rate level versus its own distribution,
#   2. ex-post real policy stance,
#   3. rate momentum,
#   4. market-implied 10Y real yield.
# ============================================================


def classify_rate_tightness(score: float) -> str:
    if pd.isna(score):
        return "Unavailable"
    if score >= 1.25:
        return "Very high"
    if score >= 0.50:
        return "High"
    if score <= -1.25:
        return "Very low"
    if score <= -0.50:
        return "Low"
    return "Normal"


rates_rows = MACRO_FACTOR_STATE[
    MACRO_FACTOR_STATE["factor"] == "rates"
]

if len(rates_rows) != 1:
    raise RuntimeError(
        "Expected exactly one aggregated rates-factor row."
    )

rates_factor_row = rates_rows.iloc[0]


HISTORICAL_RATE_TIGHTNESS = classify_rate_tightness(
    rates_factor_row["state_score"]
)


MONETARY_POLICY_VIEW = pd.DataFrame(
    [
        {
            "metric": "Historical rate tightness",
            "value": HISTORICAL_RATE_TIGHTNESS,
            "numeric": float(rates_factor_row["state_score"]),
        },
        {
            "metric": "Ex-post real policy stance",
            "value": POLICY_STANCE,
            "numeric": float(EX_POST_REAL_POLICY_RATE),
        },
        {
            "metric": "Rate momentum",
            "value": classify_momentum(
                rates_factor_row["momentum_score"]
            ),
            "numeric": float(rates_factor_row["momentum_score"]),
        },
        {
            "metric": "10Y real yield",
            "value": f"{REAL_10Y_YIELD:.2f}%",
            "numeric": float(REAL_10Y_YIELD),
        },
    ]
)


display(MONETARY_POLICY_VIEW)


# ===== ORIGINAL NOTEBOOK CELL 38 =====
# ============================================================
# CELL C23 — MACRO FACTOR CONFIDENCE ENGINE
# ============================================================
#
# Confidence has three interpretable dimensions:
#   1. component agreement,
#   2. data freshness,
#   3. intended signal coverage.
#
# Coverage and freshness are multiplicative penalties. This
# prevents a factor from receiving "High" confidence when a
# meaningful share of its intended signals is missing or stale.
# ============================================================


def calculate_factor_confidence(
    factor: str,
    group: pd.DataFrame,
) -> dict:
    """Calculate live confidence for one macro factor."""

    expected_specs = MACRO_COMPONENT_SPECS[
        MACRO_COMPONENT_SPECS["factor"] == factor
    ].copy()

    expected_components = int(
        expected_specs["series_id"].nunique()
    )

    expected_weight = float(
        expected_specs["weight"].sum()
    )

    valid = (
        group
        .dropna(subset=["state_score", "weight", "date", "frequency"])
        .drop_duplicates(subset=["series_id"], keep="last")
        .copy()
    )

    actual_components = int(
        valid["series_id"].nunique()
    )

    actual_weight = float(
        valid["weight"].sum()
    ) if not valid.empty else 0.0


    # --------------------------------------------------------
    # Coverage — weight-based, not merely component-count-based
    # --------------------------------------------------------

    coverage_score = (
        actual_weight / expected_weight
        if expected_weight > 0
        else 0.0
    )

    coverage_score = float(
        np.clip(coverage_score, 0.0, 1.0)
    )


    if valid.empty:
        return {
            "factor": factor,
            "expected_components": expected_components,
            "actual_components": 0,
            "expected_weight": expected_weight,
            "actual_weight": 0.0,
            "agreement_score": 0.0,
            "freshness_score": 0.0,
            "coverage_score": 0.0,
            "confidence_score": 0.0,
        }


    # --------------------------------------------------------
    # Normalized component weights
    # --------------------------------------------------------

    normalized_weights = (
        valid["weight"].astype(float)
        / valid["weight"].astype(float).sum()
    )


    # --------------------------------------------------------
    # Agreement — lower cross-component dispersion is better
    # --------------------------------------------------------

    factor_mean = float(
        np.average(
            valid["state_score"].astype(float),
            weights=normalized_weights,
        )
    )

    dispersion = float(
        np.sqrt(
            np.average(
                (
                    valid["state_score"].astype(float)
                    - factor_mean
                ) ** 2,
                weights=normalized_weights,
            )
        )
    )

    agreement_score = float(
        np.clip(np.exp(-dispersion), 0.0, 1.0)
    )


    # --------------------------------------------------------
    # Freshness — weight-aware and frequency-aware
    # --------------------------------------------------------

    today = pd.Timestamp.today().normalize()
    freshness_values = []

    for _, row in valid.iterrows():
        age_days = int(
            (
                today
                - pd.Timestamp(row["date"]).normalize()
            ).days
        )

        allowed_lag = int(
            MAX_OBSERVATION_LAG_DAYS.get(
                row["frequency"],
                90,
            )
        )

        if allowed_lag <= 0:
            freshness = 0.0
        elif age_days <= allowed_lag:
            freshness = 1.0
        else:
            # Linear decay from 1 to 0 over one additional
            # allowed-lag window.
            freshness = max(
                0.0,
                1.0
                - (
                    (age_days - allowed_lag)
                    / allowed_lag
                ),
            )

        freshness_values.append(float(freshness))

    freshness_score = float(
        np.average(
            np.asarray(freshness_values, dtype=float),
            weights=normalized_weights,
        )
    )

    freshness_score = float(
        np.clip(freshness_score, 0.0, 1.0)
    )


    # --------------------------------------------------------
    # Composite confidence
    # --------------------------------------------------------
    #
    # Agreement is the core conviction measure. Coverage and
    # freshness act as multiplicative penalties.
    # --------------------------------------------------------

    confidence_score = float(
        agreement_score
        * np.sqrt(
            freshness_score
            * coverage_score
        )
    )

    confidence_score = float(
        np.clip(confidence_score, 0.0, 1.0)
    )


    return {
        "factor": factor,
        "expected_components": expected_components,
        "actual_components": actual_components,
        "expected_weight": expected_weight,
        "actual_weight": actual_weight,
        "agreement_score": agreement_score,
        "freshness_score": freshness_score,
        "coverage_score": coverage_score,
        "confidence_score": confidence_score,
    }


confidence_rows = []

for factor, group in CURRENT_COMPONENTS.groupby("factor"):
    confidence_rows.append(
        calculate_factor_confidence(
            factor,
            group,
        )
    )


MACRO_CONFIDENCE = pd.DataFrame(
    confidence_rows
).sort_values("factor").reset_index(drop=True)


EXPECTED_FACTORS = set(
    MACRO_COMPONENT_SPECS["factor"].unique()
)

ACTUAL_CONFIDENCE_FACTORS = set(
    MACRO_CONFIDENCE["factor"].unique()
)

if ACTUAL_CONFIDENCE_FACTORS != EXPECTED_FACTORS:
    missing = sorted(
        EXPECTED_FACTORS - ACTUAL_CONFIDENCE_FACTORS
    )
    raise RuntimeError(
        "Confidence engine missing factor(s): "
        f"{missing}"
    )


def confidence_label(score: float) -> str:
    if pd.isna(score):
        return "Unavailable"
    if score >= 0.80:
        return "High"
    if score >= 0.60:
        return "Medium"
    return "Low"


MACRO_CONFIDENCE["confidence"] = (
    MACRO_CONFIDENCE["confidence_score"]
    .apply(confidence_label)
)


display(
    MACRO_CONFIDENCE[
        [
            "factor",
            "expected_components",
            "actual_components",
            "coverage_score",
            "agreement_score",
            "freshness_score",
            "confidence_score",
            "confidence",
        ]
    ]
)


# ===== ORIGINAL NOTEBOOK CELL 39 =====
# Runtime dependency gate: C24 consumes outputs produced earlier in Section C.
require_objects(
    globals(),
    ["PM_MACRO_STATE", "MACRO_CONFIDENCE", "INFLATION_IMPULSE_LABEL", "HISTORICAL_RATE_TIGHTNESS", "REGIME_FEATURE_DIR"],
    stage="C24 final PM macro dashboard",
)

# ============================================================
# CELL C24 — FINAL PM MACRO DASHBOARD V2
# ============================================================

BLOCK_TO_FACTOR = {

    "Growth":
        "growth",

    "Inflation":
        "inflation",

    "Monetary policy":
        "rates",

    "Liquidity":
        "liquidity",

    "Credit stress":
        "credit_stress",

    "Market risk appetite":
        "market",

}


PM_MACRO_STATE_V2 = (
    PM_MACRO_STATE.copy()
)


PM_MACRO_STATE_V2[
    "factor"
] = (

    PM_MACRO_STATE_V2[
        "macro_block"
    ]

    .map(
        BLOCK_TO_FACTOR
    )

)


PM_MACRO_STATE_V2 = (
    PM_MACRO_STATE_V2.merge(

        MACRO_CONFIDENCE[
            [
                "factor",
                "confidence_score",
                "confidence",
            ]
        ],

        on="factor",

        how="left"

    )
)


# ------------------------------------------------------------
# Add special PM diagnostics
# ------------------------------------------------------------

PM_MACRO_STATE_V2[
    "short_term_signal"
] = ""


PM_MACRO_STATE_V2.loc[

    PM_MACRO_STATE_V2[
        "factor"
    ]
    ==
    "inflation",

    "short_term_signal"

] = INFLATION_IMPULSE_LABEL


PM_MACRO_STATE_V2.loc[

    PM_MACRO_STATE_V2[
        "factor"
    ]
    ==
    "rates",

    "short_term_signal"

] = (
    f"Rate level: "
    f"{HISTORICAL_RATE_TIGHTNESS}"
)


# ------------------------------------------------------------
# Final display
# ------------------------------------------------------------

PM_MACRO_STATE_V2 = (
    PM_MACRO_STATE_V2[
        [
            "macro_block",
            "pm_state",
            "state_score",
            "momentum",
            "momentum_score",
            "acceleration",
            "acceleration_score",
            "short_term_signal",
            "confidence",
            "confidence_score",
        ]
    ]
)


FINAL_PM_MACRO_PATH = (
    REGIME_FEATURE_DIR
    /
    "pm_macro_state_live.parquet"
)


PM_MACRO_STATE_V2.to_parquet(
    FINAL_PM_MACRO_PATH,
    index=False
)


print(
    "=" * 105
)

print(
    "FINAL PM MACRO STATE — LIVE"
)

print(
    "=" * 105
)


display(
    PM_MACRO_STATE_V2
)

# ===== ORIGINAL NOTEBOOK CELL 40 =====
# Runtime dependency gate: the Section C production freeze may only run after C16-C24.
require_objects(
    globals(),
    ["MACRO_COMPONENT_SPECS", "MACRO_COMPONENT_HISTORY", "CURRENT_COMPONENTS", "INFLATION_ALIGNED_TABLE", "INFLATION_COMMON_MONTH", "INFLATION_LEVEL", "INFLATION_12M", "MACRO_CONFIDENCE", "PM_MACRO_STATE_V2", "FINAL_DATA_AUDIT", "DATA_MANIFEST"],
    stage="C25 Section C production gate",
)

# ============================================================
# CELL C25 — FINAL SECTION C PRODUCTION GATE
# ============================================================
#
# This is the freeze gate for Sections A–C. Section D should
# not run unless every check below passes in a fresh runtime.
# ============================================================


# ------------------------------------------------------------
# 1. EXPECTED COUNTS
# ------------------------------------------------------------

EXPECTED_COMPONENTS = int(
    MACRO_COMPONENT_SPECS["series_id"].nunique()
)

GENERATED_COMPONENTS = int(
    MACRO_COMPONENT_HISTORY["series_id"].nunique()
)

CURRENT_COMPONENT_COUNT = int(
    CURRENT_COMPONENTS["series_id"].nunique()
)

EXPECTED_FACTOR_COUNT = int(
    MACRO_COMPONENT_SPECS["factor"].nunique()
)


# ------------------------------------------------------------
# 2. LIVE-ONLY CREDIT CHECK
# ------------------------------------------------------------

required_live_only = set(LIVE_ONLY_SERIES)
current_series = set(CURRENT_COMPONENTS["series_id"])

live_only_present = required_live_only.issubset(
    current_series
)


# ------------------------------------------------------------
# 3. MARKET EOD ALIGNMENT
# ------------------------------------------------------------

market_component_dates = CURRENT_COMPONENTS.loc[
    CURRENT_COMPONENTS["factor"] == "market",
    "date",
]

market_eod_aligned = bool(
    (market_component_dates <= MARKET_AS_OF_DATE).all()
)


# ------------------------------------------------------------
# 4. INFLATION CONSISTENCY
# ------------------------------------------------------------

inflation_reference_months = set(
    INFLATION_ALIGNED_TABLE["reference_month"]
)

inflation_common_month_aligned = (
    len(inflation_reference_months) == 1
    and next(iter(inflation_reference_months))
    == INFLATION_COMMON_MONTH
)

inflation_c16_c21_consistent = bool(
    np.isclose(
        INFLATION_LEVEL,
        INFLATION_12M,
        atol=1e-8,
        rtol=1e-8,
    )
)


# ------------------------------------------------------------
# 5. CONFIDENCE / SCORE VALIDATION
# ------------------------------------------------------------

confidence_complete = (
    MACRO_CONFIDENCE["factor"].nunique()
    == EXPECTED_FACTOR_COUNT
    and MACRO_CONFIDENCE["confidence_score"].notna().all()
    and MACRO_CONFIDENCE["confidence_score"].between(0, 1).all()
)

final_scores_finite = bool(
    safe_isfinite(
        PM_MACRO_STATE_V2[
            [
                "state_score",
                "momentum_score",
                "acceleration_score",
                "confidence_score",
            ]
        ].to_numpy(dtype=float)
    ).all()
)


# ------------------------------------------------------------
# 6. SECTION B / GOVERNANCE CHECKS
# ------------------------------------------------------------

section_b_core_clear = bool(
    not (
        (FINAL_DATA_AUDIT["final_status"] == "⚠ REVIEW")
        & (FINAL_DATA_AUDIT["priority"] == "core")
    ).any()
)

backtest_guard_active = bool(
    not DATA_MANIFEST["backtest_ready"].any()
)


# ------------------------------------------------------------
# 7. FINAL CHECK TABLE
# ------------------------------------------------------------

section_c_checks = {
    "Section B core data clear": section_b_core_clear,
    "All component histories generated": (
        GENERATED_COMPONENTS == EXPECTED_COMPONENTS
    ),
    "All current components available": (
        CURRENT_COMPONENT_COUNT == EXPECTED_COMPONENTS
    ),
    "LIVE_ONLY credit spreads present": live_only_present,
    "All macro factors aggregated": (
        MACRO_FACTOR_STATE["factor"].nunique()
        == EXPECTED_FACTOR_COUNT
    ),
    "Final PM dashboard has all factors": (
        len(PM_MACRO_STATE_V2) == EXPECTED_FACTOR_COUNT
    ),
    "Market signals respect SPY EOD": market_eod_aligned,
    "Inflation uses one common month": inflation_common_month_aligned,
    "C16/C21 inflation composites match": inflation_c16_c21_consistent,
    "Confidence engine complete and bounded": confidence_complete,
    "Final PM scores finite": final_scores_finite,
    "Historical backtest guard active": backtest_guard_active,
}


SECTION_C_HEALTH = pd.DataFrame(
    {
        "check": list(section_c_checks.keys()),
        "passed": list(section_c_checks.values()),
    }
)

SECTION_C_HEALTH["status"] = np.where(
    SECTION_C_HEALTH["passed"],
    "✓ PASS",
    "✗ FAIL",
)


SECTION_C_HEALTH_PATH = (
    REGIME_FEATURE_DIR / "section_c_health.parquet"
)

SECTION_C_HEALTH.to_parquet(
    SECTION_C_HEALTH_PATH,
    index=False,
)


print("=" * 78)
print("SECTION C — PRODUCTION GATE")
print("=" * 78)

display(
    SECTION_C_HEALTH[["check", "status"]]
)

print(
    f"\nComponents: "
    f"{CURRENT_COMPONENT_COUNT}/{EXPECTED_COMPONENTS} current | "
    f"{GENERATED_COMPONENTS}/{EXPECTED_COMPONENTS} histories"
)

print(
    f"Macro factors: "
    f"{MACRO_FACTOR_STATE['factor'].nunique()}/"
    f"{EXPECTED_FACTOR_COUNT}"
)

print(
    f"Market EOD: {MARKET_AS_OF_DATE.date()}"
)

print(
    f"Inflation common month: {INFLATION_COMMON_MONTH}"
)


if all(section_c_checks.values()):
    logger.info(
        "SECTION C PASSED — A–C production foundation is healthy."
    )
    print(
        "\n✓ SECTION C PRODUCTION GATE PASSED — "
        "A–C can be frozen before Section D."
    )
else:
    failed_checks = SECTION_C_HEALTH.loc[
        ~SECTION_C_HEALTH["passed"],
        "check",
    ].tolist()

    logger.error(
        "SECTION C FAILED — "
        + "; ".join(failed_checks)
    )

    raise RuntimeError(
        "SECTION C NOT READY — failed checks: "
        + "; ".join(failed_checks)
    )

