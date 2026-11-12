# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 11 =====
# ============================================================
# SECTION B — CORE DATA ENGINE
# CELL B1 — DATA SOURCE DIRECTORIES
# ============================================================

# ------------------------------------------------------------
# Raw source directories
# ------------------------------------------------------------

FRED_RAW_DIR = RAW_DATA_DIR / "fred"
MARKET_RAW_DIR = RAW_DATA_DIR / "market"

FRED_RAW_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MARKET_RAW_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Curated source directories
# ------------------------------------------------------------

MACRO_CURATED_DIR = CURATED_DATA_DIR / "macro"
MARKET_CURATED_DIR = CURATED_DATA_DIR / "market"

MACRO_CURATED_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MARKET_CURATED_DIR.mkdir(
    parents=True,
    exist_ok=True
)


print("✓ Section B data directories ready.")

print(f"FRED raw:       {FRED_RAW_DIR}")
print(f"Market raw:     {MARKET_RAW_DIR}")
print(f"Macro curated:  {MACRO_CURATED_DIR}")
print(f"Market curated: {MARKET_CURATED_DIR}")

# ===== ORIGINAL NOTEBOOK CELL 12 =====
# ============================================================
# CELL B2 — MASTER DATA DICTIONARY
# ============================================================

# ------------------------------------------------------------
# FRED / macro-economic series
# ------------------------------------------------------------

fred_manifest = [

    # ========================================================
    # GROWTH / LABOUR
    # ========================================================

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "GDPC1",
        "name": "Real GDP",
        "frequency": "quarterly",
        "units": "Billions chained 2017 USD",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "INDPRO",
        "name": "Industrial Production Index",
        "frequency": "monthly",
        "units": "Index",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "RSAFS",
        "name": "Retail Sales",
        "frequency": "monthly",
        "units": "USD millions",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "PAYEMS",
        "name": "Nonfarm Payrolls",
        "frequency": "monthly",
        "units": "Thousands",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "UNRATE",
        "name": "Unemployment Rate",
        "frequency": "monthly",
        "units": "Percent",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "ICSA",
        "name": "Initial Jobless Claims",
        "frequency": "weekly",
        "units": "Number",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "JTSJOL",
        "name": "Job Openings",
        "frequency": "monthly",
        "units": "Thousands",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "PERMIT",
        "name": "Building Permits",
        "frequency": "monthly",
        "units": "Thousands annual rate",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "growth",
        "series_id": "HOUST",
        "name": "Housing Starts",
        "frequency": "monthly",
        "units": "Thousands annual rate",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },


    # ========================================================
    # INFLATION
    # ========================================================

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "CPIAUCSL",
        "name": "Consumer Price Index",
        "frequency": "monthly",
        "units": "Index",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "CPILFESL",
        "name": "Core CPI",
        "frequency": "monthly",
        "units": "Index",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "PCEPI",
        "name": "PCE Price Index",
        "frequency": "monthly",
        "units": "Index",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "PCEPILFE",
        "name": "Core PCE Price Index",
        "frequency": "monthly",
        "units": "Index",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "PPIACO",
        "name": "Producer Price Index — All Commodities",
        "frequency": "monthly",
        "units": "Index",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "CES0500000003",
        "name": "Average Hourly Earnings — Private",
        "frequency": "monthly",
        "units": "USD per hour",
        "priority": "core",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "inflation",
        "series_id": "ECIWAG",
        "name": "Employment Cost Index — Wages",
        "frequency": "quarterly",
        "units": "Index",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },


    # ========================================================
    # MONETARY POLICY / RATES
    # ========================================================

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "DFF",
        "name": "Effective Federal Funds Rate",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "DGS2",
        "name": "US Treasury 2Y Yield",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "DGS10",
        "name": "US Treasury 10Y Yield",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "DFII10",
        "name": "US 10Y Real Yield",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "T10Y2Y",
        "name": "10Y minus 2Y Treasury Spread",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "T10Y3M",
        "name": "10Y minus 3M Treasury Spread",
        "frequency": "daily",
        "units": "Percent",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "rates",
        "series_id": "T10YIE",
        "name": "10Y Breakeven Inflation Rate",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # LIQUIDITY / FINANCIAL CONDITIONS
    # ========================================================

    {
        "dataset": "fred",
        "category": "liquidity",
        "series_id": "WALCL",
        "name": "Federal Reserve Total Assets",
        "frequency": "weekly",
        "units": "USD millions",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "liquidity",
        "series_id": "RRPONTSYD",
        "name": "Overnight Reverse Repo",
        "frequency": "daily",
        "units": "USD billions",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "liquidity",
        "series_id": "WTREGEN",
        "name": "US Treasury General Account",
        "frequency": "weekly",
        "units": "USD millions",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "liquidity",
        "series_id": "M2SL",
        "name": "M2 Money Supply",
        "frequency": "monthly",
        "units": "USD billions",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "liquidity",
        "series_id": "NFCI",
        "name": "Chicago Fed National Financial Conditions Index",
        "frequency": "weekly",
        "units": "Index",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # CREDIT
    # ========================================================

    {
        "dataset": "fred",
        "category": "credit",
        "series_id": "BAMLH0A0HYM2",
        "name": "US High Yield Option-Adjusted Spread",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "credit",
        "series_id": "BAMLC0A0CM",
        "name": "US Investment Grade Option-Adjusted Spread",
        "frequency": "daily",
        "units": "Percent",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "credit",
        "series_id": "DRTSCILM",
        "name": "Banks Tightening C&I Loan Standards",
        "frequency": "quarterly",
        "units": "Net percent",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },

    {
        "dataset": "fred",
        "category": "credit",
        "series_id": "TOTLL",
        "name": "Loans and Leases in Bank Credit",
        "frequency": "weekly",
        "units": "USD billions",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # FISCAL
    # ========================================================

    {
        "dataset": "fred",
        "category": "fiscal",
        "series_id": "GFDEGDQ188S",
        "name": "US Federal Debt to GDP",
        "frequency": "quarterly",
        "units": "Percent of GDP",
        "priority": "secondary",
        "pit_required": True,
        "enabled": True,
    },


    # ========================================================
    # VOLATILITY
    # ========================================================

    {
        "dataset": "fred",
        "category": "volatility",
        "series_id": "VIXCLS",
        "name": "CBOE VIX",
        "frequency": "daily",
        "units": "Index",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # FX
    # ========================================================

    {
        "dataset": "fred",
        "category": "fx",
        "series_id": "DEXCHUS",
        "name": "USD/CNY — Chinese Yuan per USD",
        "frequency": "daily",
        "units": "CNY per USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },
]


# ------------------------------------------------------------
# Market / cross-asset series
# ------------------------------------------------------------

market_manifest = [

    # ========================================================
    # BROAD EQUITY
    # ========================================================

    {
        "dataset": "market",
        "category": "equity",
        "series_id": "SPY",
        "name": "S&P 500 ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "equity",
        "series_id": "RSP",
        "name": "S&P 500 Equal Weight ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "equity",
        "series_id": "QQQ",
        "name": "Nasdaq 100 ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "equity",
        "series_id": "IWM",
        "name": "Russell 2000 ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # US SECTORS
    # ========================================================

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLB",
        "name": "Materials",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLC",
        "name": "Communication Services",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLE",
        "name": "Energy",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLF",
        "name": "Financials",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLI",
        "name": "Industrials",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLK",
        "name": "Technology",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLP",
        "name": "Consumer Staples",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLRE",
        "name": "Real Estate",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLU",
        "name": "Utilities",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLV",
        "name": "Healthcare",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "sector",
        "series_id": "XLY",
        "name": "Consumer Discretionary",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # CREDIT MARKET
    # ========================================================

    {
        "dataset": "market",
        "category": "credit",
        "series_id": "HYG",
        "name": "High Yield Corporate Bond ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "credit",
        "series_id": "LQD",
        "name": "Investment Grade Corporate Bond ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # DURATION
    # ========================================================

    {
        "dataset": "market",
        "category": "rates",
        "series_id": "TLT",
        "name": "20+ Year Treasury ETF",
        "frequency": "daily",
        "units": "USD",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # COMMODITIES
    # ========================================================

    {
        "dataset": "market",
        "category": "commodity",
        "series_id": "CL=F",
        "name": "WTI Crude Oil",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "commodity",
        "series_id": "GC=F",
        "name": "Gold",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "commodity",
        "series_id": "HG=F",
        "name": "Copper",
        "frequency": "daily",
        "units": "USD",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },


    # ========================================================
    # FX
    # ========================================================

    {
        "dataset": "market",
        "category": "fx",
        "series_id": "DX-Y.NYB",
        "name": "US Dollar Index",
        "frequency": "daily",
        "units": "Index",
        "priority": "core",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "fx",
        "series_id": "JPY=X",
        "name": "USDJPY",
        "frequency": "daily",
        "units": "JPY per USD",
        "priority": "secondary",
        "pit_required": False,
        "enabled": True,
    },

    {
        "dataset": "market",
        "category": "fx",
        "series_id": "CNH=X",
        "name": "USDCNH",
        "frequency": "daily",
        "units": "CNH per USD",
        "priority": "secondary",
        "pit_required": False,
        "enabled": False,
    },

]


# ------------------------------------------------------------
# Combine into one Master Data Dictionary
# ------------------------------------------------------------

DATA_MANIFEST = pd.DataFrame(
    fred_manifest + market_manifest
)


# Common metadata
DATA_MANIFEST["historical_start"] = (
    CONFIG["data"]["historical_start"]
)

DATA_MANIFEST["source"] = np.where(
    DATA_MANIFEST["dataset"] == "fred",
    "FRED",
    "Yahoo Finance"
)


# Order columns
DATA_MANIFEST = DATA_MANIFEST[
    [
        "dataset",
        "category",
        "series_id",
        "name",
        "source",
        "frequency",
        "units",
        "priority",
        "pit_required",
        "enabled",
        "historical_start",
    ]
]

# ============================================================
# DATA GOVERNANCE
# ============================================================

DATA_MANIFEST["usage_scope"] = "LIVE_AND_HISTORY"
DATA_MANIFEST["data_note"] = ""

# Point-in-time datasets are NOT yet backtest-ready
# until we build the ALFRED vintage layer.
DATA_MANIFEST["pit_ready"] = (
    ~DATA_MANIFEST["pit_required"]
)

# Conservative production gate:
# historical strategy backtests remain disabled until the
# dedicated point-in-time / availability layer certifies that
# each input was observable at the decision timestamp.
DATA_MANIFEST["backtest_ready"] = False

# ICE credit spread history is currently limited.
LIVE_ONLY_SERIES = [
    "BAMLH0A0HYM2",
    "BAMLC0A0CM",
]

DATA_MANIFEST.loc[
    DATA_MANIFEST["series_id"].isin(LIVE_ONLY_SERIES),
    "usage_scope"
] = "LIVE_ONLY"

DATA_MANIFEST.loc[
    DATA_MANIFEST["series_id"].isin(LIVE_ONLY_SERIES),
    "data_note"
] = (
    "Short historical coverage; usable for live monitoring "
    "but not full-history regime backtest."
)

# Disabled CNH series
DATA_MANIFEST.loc[
    DATA_MANIFEST["series_id"] == "CNH=X",
    "usage_scope"
] = "DISABLED"

DATA_MANIFEST.loc[
    DATA_MANIFEST["series_id"] == "CNH=X",
    "data_note"
] = (
    "Yahoo historical retrieval unreliable. "
    "DEXCHUS used as core China FX proxy."
)

# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------

assert DATA_MANIFEST["series_id"].is_unique, (
    "Duplicate series IDs detected."
)

assert DATA_MANIFEST["enabled"].notna().all(), (
    "Missing enabled flags detected."
)


# ------------------------------------------------------------
# Save persistent copies
# ------------------------------------------------------------

MANIFEST_CSV_PATH = (
    CONFIG_DIR / "master_data_dictionary.csv"
)

MANIFEST_PARQUET_PATH = (
    CONFIG_DIR / "master_data_dictionary.parquet"
)


DATA_MANIFEST.to_csv(
    MANIFEST_CSV_PATH,
    index=False
)

DATA_MANIFEST.to_parquet(
    MANIFEST_PARQUET_PATH,
    index=False
)


print(
    f"✓ Master Data Dictionary created with "
    f"{len(DATA_MANIFEST)} series."
)

print(
    "\nBy dataset:"
)

display(
    DATA_MANIFEST
    .groupby("dataset")
    .size()
    .rename("Series")
    .to_frame()
)

print(
    "\nBy category:"
)

display(
    DATA_MANIFEST
    .groupby("category")
    .size()
    .sort_values(ascending=False)
    .rename("Series")
    .to_frame()
)


# ===== ORIGINAL NOTEBOOK CELL 13 =====
# ============================================================
# CELL B3 — STORAGE HELPERS
# ============================================================


def safe_filename(series_id: str) -> str:
    """
    Convert ticker / series identifiers into safe filenames.
    """

    return (
        series_id
        .replace("^", "")
        .replace("=", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(".", "_")
    )


def get_raw_path(
    dataset: str,
    series_id: str
) -> Path:
    """
    Return persistent raw-data path for a series.
    """

    filename = (
        f"{safe_filename(series_id)}.parquet"
    )

    if dataset == "fred":

        return (
            FRED_RAW_DIR / filename
        )

    elif dataset == "market":

        return (
            MARKET_RAW_DIR / filename
        )

    else:

        raise ValueError(
            f"Unsupported dataset: {dataset}"
        )


def load_existing_series(
    dataset: str,
    series_id: str
) -> pd.DataFrame:
    """
    Load an existing raw Parquet file.
    Return an empty DataFrame if it does not exist.
    """

    path = get_raw_path(
        dataset,
        series_id
    )

    if not path.exists():

        return pd.DataFrame()

    df = pd.read_parquet(
        path
    )

    return df


def save_series(
    df: pd.DataFrame,
    dataset: str,
    series_id: str
) -> None:
    """
    Save a series to persistent Parquet storage.
    """

    path = get_raw_path(
        dataset,
        series_id
    )

    df.to_parquet(
        path,
        index=False
    )


def merge_incremental_data(
    existing: pd.DataFrame,
    new: pd.DataFrame,
    subset: List[str]
) -> pd.DataFrame:
    """
    Append new observations, remove duplicates,
    and return chronologically sorted data.
    """

    if existing.empty:

        combined = new.copy()

    elif new.empty:

        combined = existing.copy()

    else:

        combined = pd.concat(
            [
                existing,
                new,
            ],
            ignore_index=True
        )


    combined = (
        combined
        .drop_duplicates(
            subset=subset,
            keep="last"
        )
        .sort_values(
            subset
        )
        .reset_index(
            drop=True
        )
    )

    return combined


print("✓ Storage helper functions initialized.")

# ===== ORIGINAL NOTEBOOK CELL 14 =====
# ============================================================
# CELL B4 — DATA UPDATE REGISTRY
# ============================================================


def get_registry_record(
    dataset: str,
    series_id: str
):
    """
    Retrieve update metadata for a specific series.
    """

    result = conn.execute(
        """
        SELECT
            dataset,
            series_id,
            first_observation_date,
            last_observation_date,
            last_update_timestamp,
            source,
            row_count
        FROM data_update_registry
        WHERE dataset = ?
          AND series_id = ?
        """,
        [
            dataset,
            series_id,
        ]
    ).fetchdf()

    if result.empty:

        return None

    return result.iloc[0]


def update_registry(
    dataset: str,
    series_id: str,
    source: str,
    df: pd.DataFrame,
    date_column: str = "date"
):
    """
    Update persistent metadata after successfully
    saving a dataset.
    """

    if df.empty:

        return


    first_date = pd.to_datetime(
        df[date_column]
    ).min().date()

    last_date = pd.to_datetime(
        df[date_column]
    ).max().date()

    row_count = len(df)


    conn.execute(
        """
        INSERT OR REPLACE INTO data_update_registry
        (
            dataset,
            series_id,
            first_observation_date,
            last_observation_date,
            last_update_timestamp,
            source,
            row_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            dataset,
            series_id,
            first_date,
            last_date,
            datetime.now(),
            source,
            row_count,
        ]
    )


def determine_update_start(
    dataset: str,
    series_id: str,
    default_start: str
) -> pd.Timestamp:
    """
    Determine incremental download start date.

    If no history exists:
        return full historical start.

    Otherwise:
        return last stored date minus overlap period.
    """

    record = get_registry_record(
        dataset,
        series_id
    )

    if record is None:

        return pd.Timestamp(
            default_start
        )


    last_date = pd.Timestamp(
        record["last_observation_date"]
    )


    overlap = timedelta(
        days=CONFIG["data"]["update_overlap_days"]
    )


    return (
        last_date - overlap
    )


print("✓ Data update registry functions initialized.")

# ===== ORIGINAL NOTEBOOK CELL 15 =====
# ============================================================
# CELL B5 — FRED INCREMENTAL UPDATE ENGINE
# ============================================================


def validate_fred_data(
    df: pd.DataFrame,
    series_id: str
) -> pd.DataFrame:
    """
    Basic validation for FRED observations.
    """

    if df.empty:

        return df


    df = df.copy()

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df["value"] = pd.to_numeric(
        df["value"],
        errors="coerce"
    )


    # Remove rows without usable dates
    df = df.dropna(
        subset=["date"]
    )


    # FRED can contain missing values.
    # We retain only actual observations.
    df = df.dropna(
        subset=["value"]
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


    if df.empty:

        logger.warning(
            f"{series_id}: FRED data empty after validation."
        )


    return df


def update_fred_series_group(
    manifest_group: pd.DataFrame
):
    """
    Download a group of FRED series in one request.
    """

    manifest_group = manifest_group[
        manifest_group["enabled"]
    ].copy()


    if manifest_group.empty:

        return


    series_ids = (
        manifest_group["series_id"]
        .tolist()
    )


    # --------------------------------------------------------
    # Determine earliest required update date
    # --------------------------------------------------------

    starts = []

    for _, row in manifest_group.iterrows():

        starts.append(
            determine_update_start(
                dataset="fred",
                series_id=row["series_id"],
                default_start=row["historical_start"]
            )
        )


    download_start = min(
        starts
    )


    logger.info(
        f"FRED downloading {len(series_ids)} series "
        f"from {download_start.date()}."
    )


    # --------------------------------------------------------
    # Batch download
    # --------------------------------------------------------

    try:

        fred_api_key = os.getenv("FRED_API_KEY", "").strip()

        if fred_api_key:
            fred_client = Fred(api_key=fred_api_key)
            fred_frames = {}
            for _series_id in series_ids:
                _series = fred_client.get_series(
                    _series_id,
                    observation_start=download_start,
                    observation_end=datetime.now(),
                )
                fred_frames[_series_id] = pd.to_numeric(
                    _series, errors="coerce"
                )
            raw = pd.DataFrame(fred_frames)
            raw.index = pd.to_datetime(raw.index)
            logger.info("FRED source: official API via FRED_API_KEY.")
        else:
            raw = pdr.DataReader(
                series_ids,
                "fred",
                download_start,
                datetime.now()
            )
            logger.info("FRED source: pandas_datareader fallback (no API key set).")

    except Exception as exc:

        logger.error(
            f"FRED batch download failed: {exc}"
        )

        return


    # DataReader returns a Series for one item
    if isinstance(
        raw,
        pd.Series
    ):

        raw = raw.to_frame(
            name=series_ids[0]
        )


    # --------------------------------------------------------
    # Process each series separately
    # --------------------------------------------------------

    for series_id in series_ids:

        try:

            if series_id not in raw.columns:

                logger.warning(
                    f"{series_id}: missing from FRED response."
                )

                continue


            new = pd.DataFrame(
                {
                    "date":
                        raw.index,

                    "value":
                        raw[series_id].values,

                    "series_id":
                        series_id,

                    "source":
                        "FRED",

                    "ingested_at":
                        datetime.now(),
                }
            )


            new = validate_fred_data(
                new,
                series_id
            )


            existing = load_existing_series(
                "fred",
                series_id
            )


            combined = merge_incremental_data(
                existing,
                new,
                subset=["date"]
            )


            save_series(
                combined,
                "fred",
                series_id
            )


            update_registry(
                dataset="fred",
                series_id=series_id,
                source="FRED",
                df=combined
            )


            logger.info(
                f"FRED {series_id}: "
                f"{len(combined):,} observations | "
                f"latest "
                f"{combined['date'].max().date()}"
            )


        except Exception as exc:

            logger.error(
                f"FRED {series_id} processing failed: "
                f"{exc}"
            )


def update_all_fred():
    """
    Update enabled FRED series grouped by frequency.
    """

    fred_df = DATA_MANIFEST[
        (DATA_MANIFEST["dataset"] == "fred")
        &
        (DATA_MANIFEST["enabled"])
    ].copy()


    frequencies = (
        fred_df["frequency"]
        .dropna()
        .unique()
    )


    for frequency in frequencies:

        group = fred_df[
            fred_df["frequency"] == frequency
        ]


        logger.info(
            f"Updating FRED frequency group: "
            f"{frequency}"
        )


        update_fred_series_group(
            group
        )


print("✓ FRED incremental update engine initialized.")

# ===== ORIGINAL NOTEBOOK CELL 16 =====
# ============================================================
# CELL B6 — MARKET DATA INCREMENTAL UPDATE ENGINE
# ============================================================


def validate_market_data(
    df: pd.DataFrame,
    ticker: str
) -> pd.DataFrame:
    """
    Validate downloaded daily OHLCV data.
    """

    if df.empty:

        return df


    df = df.copy()


    df["date"] = pd.to_datetime(
        df["date"]
    )


    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    ]


    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )


    # Must have a valid date and close
    df = df.dropna(
        subset=[
            "date",
            "close",
        ]
    )


    # Invalid market prices
    df = df[
        df["close"] > 0
    ]


    df = (
        df
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )


    return df


def update_all_market_data():
    """
    Batch-download enabled market series and
    merge them into persistent Parquet storage.
    """

    market_df = DATA_MANIFEST[
        (DATA_MANIFEST["dataset"] == "market")
        &
        (DATA_MANIFEST["enabled"])
    ].copy()


    tickers = (
        market_df["series_id"]
        .tolist()
    )


    # --------------------------------------------------------
    # Determine earliest required start date
    # --------------------------------------------------------

    starts = []

    for _, row in market_df.iterrows():

        starts.append(
            determine_update_start(
                dataset="market",
                series_id=row["series_id"],
                default_start=row["historical_start"]
            )
        )


    download_start = min(
        starts
    )


    # Yahoo end date is exclusive.
    download_end = (
        pd.Timestamp.today().normalize()
        +
        pd.Timedelta(days=1)
    )


    logger.info(
        f"Market data downloading "
        f"{len(tickers)} tickers "
        f"from {download_start.date()}."
    )


    # --------------------------------------------------------
    # Batch download
    # --------------------------------------------------------

    try:

        raw = yf.download(

            tickers=tickers,

            start=download_start.strftime(
                "%Y-%m-%d"
            ),

            end=download_end.strftime(
                "%Y-%m-%d"
            ),

            group_by="ticker",

            auto_adjust=False,

            actions=False,

            threads=True,

            progress=False,
        )


    except Exception as exc:

        logger.error(
            f"Market batch download failed: {exc}"
        )

        return


    # --------------------------------------------------------
    # Process ticker by ticker
    # --------------------------------------------------------

    for ticker in tickers:

        try:

            # Multi-ticker yfinance download
            if isinstance(
                raw.columns,
                pd.MultiIndex
            ):

                if ticker not in raw.columns.get_level_values(0):

                    logger.warning(
                        f"{ticker}: not returned by Yahoo."
                    )

                    continue


                ticker_df = (
                    raw[ticker]
                    .copy()
                )


            else:

                # Fallback if only one ticker exists
                ticker_df = raw.copy()


            ticker_df = (
                ticker_df
                .reset_index()
            )


            # Normalize field names
            ticker_df.columns = [

                str(column)
                .strip()
                .lower()
                .replace(" ", "_")

                for column in ticker_df.columns

            ]


            # Yahoo calls the adjusted close:
            # Adj Close -> adj_close
            expected_columns = [
                "date",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
            ]


            # Keep fields that exist
            keep_columns = [
                col
                for col in expected_columns
                if col in ticker_df.columns
            ]


            ticker_df = ticker_df[
                keep_columns
            ]


            ticker_df["series_id"] = ticker

            ticker_df["source"] = (
                "Yahoo Finance"
            )

            ticker_df["ingested_at"] = (
                datetime.now()
            )


            ticker_df = validate_market_data(
                ticker_df,
                ticker
            )


            existing = load_existing_series(
                "market",
                ticker
            )


            combined = merge_incremental_data(
                existing,
                ticker_df,
                subset=["date"]
            )


            save_series(
                combined,
                "market",
                ticker
            )


            update_registry(
                dataset="market",
                series_id=ticker,
                source="Yahoo Finance",
                df=combined
            )


            logger.info(
                f"Market {ticker}: "
                f"{len(combined):,} observations | "
                f"latest "
                f"{combined['date'].max().date()}"
            )


        except Exception as exc:

            logger.error(
                f"Market {ticker} processing failed: "
                f"{exc}"
            )


print("✓ Market incremental update engine initialized.")

# ===== ORIGINAL NOTEBOOK CELL 17 =====
# ============================================================
# CELL B7 — RUN CORE DATA UPDATE
# ============================================================

update_start_time = time.time()


logger.info(
    "=" * 60
)

logger.info(
    "CORE DATA UPDATE STARTED"
)

logger.info(
    "=" * 60
)


# ------------------------------------------------------------
# Update FRED
# ------------------------------------------------------------

update_all_fred()


# ------------------------------------------------------------
# Update market / cross-asset data
# ------------------------------------------------------------

update_all_market_data()


# ------------------------------------------------------------
# Timing
# ------------------------------------------------------------

elapsed_seconds = (
    time.time()
    -
    update_start_time
)


logger.info(
    f"Core data update completed "
    f"in {elapsed_seconds:,.1f} seconds."
)


print(
    "\n✓ Core data update completed."
)

print(
    f"Elapsed time: "
    f"{elapsed_seconds:,.1f} seconds"
)

# ===== ORIGINAL NOTEBOOK CELL 18 =====
# ============================================================
# SECTION B.1 — DATA QA & GOVERNANCE
# CELL B9 — DATA QUALITY REQUIREMENTS
# ============================================================

# ------------------------------------------------------------
# Minimum history requirements
# ------------------------------------------------------------
# These are not model lookback windows.
# They are QA requirements: "does this dataset contain enough
# history to be useful?"
# ------------------------------------------------------------

MIN_HISTORY_YEARS = {
    "daily": 5,
    "weekly": 5,
    "monthly": 10,
    "quarterly": 10,
}


# ------------------------------------------------------------
# Maximum acceptable observation lag
# ------------------------------------------------------------
# IMPORTANT:
# Observation dates are NOT release dates.
#
# Example:
# Q2 GDP is usually stored as 1-Apr even though released later.
# Therefore a simple "days since observation" rule creates
# false alarms.
# ------------------------------------------------------------

MAX_OBSERVATION_LAG_DAYS = {
    "daily": 7,
    "weekly": 21,
    "monthly": 90,
    "quarterly": 300,
}


print("✓ Frequency-aware QA rules initialized.")


# ===== ORIGINAL NOTEBOOK CELL 19 =====
# ============================================================
# CELL B10 — DATA QUALITY AUDIT ENGINE
# ============================================================


def audit_series(
    dataset: str,
    series_id: str,
    frequency: str,
    expected_start: str,
) -> dict:
    """
    Run data-quality tests for one stored series.

    Tests:
        1. File exists
        2. Row count
        3. Date coverage
        4. Minimum historical coverage
        5. Freshness
        6. Duplicate dates
        7. Missing critical values
    """

    df = load_existing_series(
        dataset,
        series_id
    )

    result = {
        "dataset": dataset,
        "series_id": series_id,
        "frequency": frequency,
        "exists": False,
        "row_count": 0,
        "first_date": pd.NaT,
        "last_date": pd.NaT,
        "history_years": np.nan,
        "days_since_latest": np.nan,
        "duplicate_dates": np.nan,
        "missing_values": np.nan,
        "history_status": "FAIL",
        "freshness_status": "FAIL",
        "overall_status": "FAIL",
    }


    if df.empty:
        return result


    result["exists"] = True
    result["row_count"] = len(df)


    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    dates = pd.to_datetime(
        df["date"]
    )

    first_date = dates.min()
    last_date = dates.max()

    result["first_date"] = first_date
    result["last_date"] = last_date


    # --------------------------------------------------------
    # Historical coverage
    # --------------------------------------------------------

    history_years = (
        last_date - first_date
    ).days / 365.25

    result["history_years"] = (
        history_years
    )


    min_years = MIN_HISTORY_YEARS.get(
        frequency,
        5
    )


    if history_years >= min_years:

        result["history_status"] = "PASS"

    else:

        result["history_status"] = "CHECK"


    # --------------------------------------------------------
    # Freshness
    # --------------------------------------------------------

    today = pd.Timestamp.today().normalize()

    days_since_latest = (
        today - last_date.normalize()
    ).days

    result["days_since_latest"] = (
        days_since_latest
    )


    max_lag = MAX_OBSERVATION_LAG_DAYS.get(
        frequency,
        90
    )


    if days_since_latest <= max_lag:

        result["freshness_status"] = "PASS"

    else:

        result["freshness_status"] = "CHECK"


    # --------------------------------------------------------
    # Duplicate dates
    # --------------------------------------------------------

    result["duplicate_dates"] = int(
        dates.duplicated().sum()
    )


    # --------------------------------------------------------
    # Missing observations
    # --------------------------------------------------------

    if dataset == "fred":

        critical_column = "value"

    else:

        critical_column = "close"


    if critical_column in df.columns:

        result["missing_values"] = int(
            df[critical_column]
            .isna()
            .sum()
        )

    else:

        result["missing_values"] = np.nan


    # --------------------------------------------------------
    # Overall status
    # --------------------------------------------------------

    if (
        result["history_status"] == "PASS"
        and
        result["freshness_status"] == "PASS"
        and
        result["duplicate_dates"] == 0
        and
        (
            pd.isna(result["missing_values"])
            or
            result["missing_values"] == 0
        )
    ):

        result["overall_status"] = "PASS"

    else:

        result["overall_status"] = "CHECK"


    return result


# ============================================================
# Run audit across entire manifest
# ============================================================

audit_results = []


for _, row in DATA_MANIFEST[
    DATA_MANIFEST["enabled"]
].iterrows():

    audit_results.append(

        audit_series(

            dataset=row["dataset"],

            series_id=row["series_id"],

            frequency=row["frequency"],

            expected_start=row["historical_start"],

        )

    )


DATA_AUDIT = pd.DataFrame(
    audit_results
)


# Add descriptive names
DATA_AUDIT = DATA_AUDIT.merge(

    DATA_MANIFEST[
        [
            "dataset",
            "series_id",
            "category",
            "name",
            "priority",
        ]
    ],

    on=[
        "dataset",
        "series_id",
    ],

    how="left",
)


# Reorder
DATA_AUDIT = DATA_AUDIT[
    [
        "dataset",
        "category",
        "series_id",
        "name",
        "priority",
        "frequency",
        "row_count",
        "first_date",
        "last_date",
        "history_years",
        "days_since_latest",
        "duplicate_dates",
        "missing_values",
        "history_status",
        "freshness_status",
        "overall_status",
    ]
]


display(
    DATA_AUDIT
)


print(
    "\nQA Summary:"
)

display(

    DATA_AUDIT[
        "overall_status"
    ]
    .value_counts()
    .rename("Series")
    .to_frame()

)

# ===== ORIGINAL NOTEBOOK CELL 20 =====
# ============================================================
# CELL B11 — FINAL SECTION B DATA AUDIT
# ============================================================
#
# Purpose:
#   Convert the raw QA output from B10 into a production gate.
#
# Important:
#   - LIVE_ONLY series may fail long-history requirements but
#     can still be usable for current monitoring.
#   - backtest_ready remains a separate governance flag and is
#     intentionally False until the PIT / availability layer.
# ============================================================


# ------------------------------------------------------------
# 1. START FROM B10 QA RESULTS — DO NOT RE-RUN DOWNLOAD/QA
# ------------------------------------------------------------

if "DATA_AUDIT" not in globals():
    raise RuntimeError(
        "DATA_AUDIT is unavailable. Run B10 before B11."
    )


FINAL_DATA_AUDIT = DATA_AUDIT.copy()


# Defensive metadata check: B10 should retain priority, but
# recover it from the manifest if an older B10 output is in memory.
if "priority" not in FINAL_DATA_AUDIT.columns:
    FINAL_DATA_AUDIT = FINAL_DATA_AUDIT.merge(
        DATA_MANIFEST[["dataset", "series_id", "priority"]],
        on=["dataset", "series_id"],
        how="left",
        validate="one_to_one",
    )


# ------------------------------------------------------------
# 2. MERGE GOVERNANCE METADATA
# ------------------------------------------------------------

governance_columns = [
    "dataset",
    "series_id",
    "pit_required",
    "pit_ready",
    "backtest_ready",
    "usage_scope",
    "data_note",
]


FINAL_DATA_AUDIT = FINAL_DATA_AUDIT.merge(
    DATA_MANIFEST[governance_columns],
    on=["dataset", "series_id"],
    how="left",
    validate="one_to_one",
)


# ------------------------------------------------------------
# 3. CLASSIFY FINAL LIVE-DATA STATUS
# ------------------------------------------------------------

def classify_final_status(row: pd.Series) -> str:
    """Classify whether a series is usable in the live engine."""

    clean_values = (
        row["duplicate_dates"] == 0
        and (
            pd.isna(row["missing_values"])
            or row["missing_values"] == 0
        )
    )

    if row["usage_scope"] == "LIVE_ONLY":
        if row["freshness_status"] == "PASS" and clean_values:
            return "◉ LIVE ONLY"
        return "⚠ REVIEW"

    if row["overall_status"] == "PASS":
        return "✓ PASS"

    return "⚠ REVIEW"


FINAL_DATA_AUDIT["final_status"] = FINAL_DATA_AUDIT.apply(
    classify_final_status,
    axis=1,
)


# ------------------------------------------------------------
# 4. VALIDATE MANIFEST COVERAGE
# ------------------------------------------------------------

enabled_manifest = DATA_MANIFEST[
    DATA_MANIFEST["enabled"]
].copy()

expected_enabled = int(len(enabled_manifest))
actual_audited = int(len(FINAL_DATA_AUDIT))

if actual_audited != expected_enabled:
    raise RuntimeError(
        "Section B audit coverage mismatch: "
        f"expected {expected_enabled}, audited {actual_audited}."
    )


# ------------------------------------------------------------
# 5. EXCEPTIONS / CRITICAL FAILURES
# ------------------------------------------------------------

exceptions = FINAL_DATA_AUDIT[
    FINAL_DATA_AUDIT["final_status"] != "✓ PASS"
].copy()

critical_failures = FINAL_DATA_AUDIT[
    (FINAL_DATA_AUDIT["final_status"] == "⚠ REVIEW")
    & (FINAL_DATA_AUDIT["priority"] == "core")
].copy()


# ------------------------------------------------------------
# 6. SAVE AUDIT OUTPUT
# ------------------------------------------------------------

DATA_QA_OUTPUT_DIR = OUTPUTS_DIR / "data_quality"
DATA_QA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FINAL_DATA_AUDIT_PATH = (
    DATA_QA_OUTPUT_DIR / "final_data_audit.parquet"
)

FINAL_DATA_AUDIT.to_parquet(
    FINAL_DATA_AUDIT_PATH,
    index=False,
)


# ------------------------------------------------------------
# 7. DISPLAY
# ------------------------------------------------------------

print("=" * 72)
print("SECTION B — FINAL DATA QUALITY AUDIT")
print("=" * 72)

print(f"\nEnabled series:     {expected_enabled}")
print(f"Audited series:     {actual_audited}")
print(
    "Backtest-ready:   "
    f"{int(enabled_manifest['backtest_ready'].sum())} "
    "(intentionally gated until PIT layer)"
)

print("\nStatus summary:")
display(
    FINAL_DATA_AUDIT["final_status"]
    .value_counts()
    .rename("Series")
    .to_frame()
)


if exceptions.empty:
    print("\n✓ No live-data exceptions detected.")
else:
    print("\nData exceptions / live-only series:")
    display(
        exceptions[
            [
                "dataset",
                "category",
                "series_id",
                "name",
                "frequency",
                "row_count",
                "first_date",
                "last_date",
                "history_years",
                "history_status",
                "freshness_status",
                "pit_required",
                "pit_ready",
                "backtest_ready",
                "usage_scope",
                "final_status",
            ]
        ]
    )


# ------------------------------------------------------------
# 8. PRODUCTION GATE
# ------------------------------------------------------------

if critical_failures.empty:
    logger.info(
        "SECTION B PASSED — no unresolved core live-data failures."
    )
    print(
        "\n✓ SECTION B COMPLETE — "
        "No unresolved core live-data failures."
    )
else:
    logger.error(
        "SECTION B FAILED — "
        f"{len(critical_failures)} core series require review."
    )
    display(critical_failures)
    raise RuntimeError(
        "SECTION B NOT READY — core data issues remain."
    )

