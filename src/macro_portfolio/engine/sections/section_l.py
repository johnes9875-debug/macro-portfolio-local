# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 96 =====
# ==================================================================================================
# SECTION L — REGIME -> SECTOR ROTATION VALIDATION BACKTEST
#             (IMPROVEMENT #2: DIAGNOSTIC WORKSTREAM, NON-BLOCKING,
#              APPROXIMATE PIT ONLY) V1.0.0
# ==================================================================================================
#
# WHAT THIS IS
# ------------
#
#   Section 18 of the blueprint correctly blocks any historical
#   ALPHA backtest of the live A-K stock-selection engine until a
#   full point-in-time (PIT) infrastructure exists: historical
#   constituent membership, PIT financial statements, vintage-aware
#   macro data, survivorship-bias control, and so on. That gate is
#   NOT changed or weakened by this cell.
#
#   This cell answers a narrower, cheaper question that does NOT
#   need any of that stock-level infrastructure: does the REGIME
#   layer alone (Sections C/D's growth-inflation classification)
#   have any historical relationship with SECTOR-level returns?
#   Sector-ETF prices are never revised (unlike macro data), so the
#   price side of this question is genuinely point-in-time clean
#   today, using data Section B already has cached -- no new
#   network calls are made by this cell.
#
# WHAT THIS IS NOT
# -----------------
#
#   - This is NOT the Section-18 PIT historical backtesting engine.
#     It is a smaller, standalone, SIMPLIFIED replica of D2's
#     growth/inflation-axis and regime-probability logic, built
#     directly from two representative FRED series per axis rather
#     than Section C's full multi-series weighted feature engine.
#     A full replication using the exact production feature engine
#     is a natural follow-on, not attempted here.
#   - The underlying FRED series used here are the standard
#     (latest-revised) series Section B already caches, NOT ALFRED
#     vintage/real-time data. DATA_MANIFEST already flags this
#     limitation for the live system (pit_required / pit_ready /
#     backtest_ready). To partially mitigate it, every macro
#     observation is only made "usable" a conservative number of
#     days after its calendar date (L_PUBLICATION_LAG_DAYS) --
#     this prevents the most obvious look-ahead (using a value
#     before it could have existed at all) but does NOT remove
#     revision risk (using a value that was later restated).
#   - This cell NEVER sets DATA_MANIFEST["backtest_ready"] or any
#     HISTORICAL_ALPHA_BACKTEST_ELIGIBLE flag to True. Its output
#     is for regime-signal screening only, not a certified alpha
#     claim, and must not be quoted as a backtested Sharpe for the
#     live system.
#
# METHOD
# ------
#
#   1. Load cached sector-ETF price history (Section B) and two
#      representative FRED growth series + one inflation series
#      (also Section B) -- no new downloads.
#   2. Build a growth axis (expanding/point-in-time z-score of YoY
#      Industrial Production and Nonfarm Payrolls, averaged) and an
#      inflation axis (expanding z-score of YoY CPI minus the 2%
#      target), each lagged by L_PUBLICATION_LAG_DAYS before being
#      considered usable on any given date.
#   3. Reuse D2's exact RBF-kernel regime-probability formula
#      (same prototypes / distance scale, or the same defaults if
#      D2 has not run in this session) and D2B's EWMA smoothing, so
#      this backtest is methodologically consistent with the live
#      engine, not a different model.
#   4. Map the smoothed regime-probability vector to a sector
#      target-weight vector each month, using a transparent,
#      economically-motivated (not fitted) regime -> sector tilt
#      table.
#   5. Compare monthly-rebalanced realized returns against an
#      equal-weight-all-sectors benchmark and SPY buy-and-hold.
# ==================================================================================================


# ==================================================================================================
# 1. VALIDATE UPSTREAM
# ==================================================================================================

required_l_objects = [

    "load_existing_series",
    "N_REGIMES",
    "DATA_MANIFEST",
    "MACRO_COMPONENT_SPECS",
    "ECONOMIC_REGIME_PROTOTYPES",
    "REGIME_PROTOTYPE_LEVEL",
    "REGIME_DISTANCE_SCALE",
    "REGIME_SMOOTHING_HALF_LIFE_DAYS",

]

missing_l_objects = [
    obj
    for obj in required_l_objects
    if obj not in globals()
]

if missing_l_objects:
    raise RuntimeError(
        "Section L requires Section B's storage helpers. Missing: "
        f"{missing_l_objects}"
    )

L_VERSION = "1.1.0"


# ==================================================================================================
# 2. CONFIGURATION
# ==================================================================================================

L_PUBLICATION_LAG_DAYS = int(
    cfg(["diagnostics", "regime_backtest", "publication_lag_days"], 45)
)
L_MIN_HISTORY_MONTHS = int(
    cfg(["diagnostics", "regime_backtest", "min_history_months"], 36)
)
L_REBALANCE = str(
    cfg(["diagnostics", "regime_backtest", "rebalance"], "M")
)

# Reuse the CURRENT live regime methodology; no duplicate frozen state.
L_PROTOTYPE_LEVEL = float(REGIME_PROTOTYPE_LEVEL)
L_DISTANCE_SCALE = float(REGIME_DISTANCE_SCALE)
L_SMOOTHING_HALF_LIFE_DAYS = float(REGIME_SMOOTHING_HALF_LIFE_DAYS)
L_SMOOTHING_DECAY_DAILY = float(
    np.exp(np.log(0.5) / L_SMOOTHING_HALF_LIFE_DAYS)
)

# Dynamically select representative MONTHLY FRED series from the live
# C13 component specification rather than hard-coding specific tickers.
_l_manifest = DATA_MANIFEST[["dataset", "series_id", "frequency", "enabled"]].copy()
_l_specs = MACRO_COMPONENT_SPECS.merge(
    _l_manifest,
    on="series_id",
    how="left",
)
_l_specs = _l_specs[
    (_l_specs["dataset"] == "fred")
    & (_l_specs["enabled"] == True)
    & (_l_specs["frequency"].astype(str).str.lower() == "monthly")
].copy()

def _l_pick_series(factor, count):
    subset = (
        _l_specs[_l_specs["factor"] == factor]
        .sort_values(["weight", "series_id"], ascending=[False, True])
    )
    values = subset["series_id"].astype(str).drop_duplicates().head(int(count)).tolist()
    if not values:
        raise RuntimeError(f"Section L found no enabled monthly FRED series for factor={factor}.")
    return values

L_GROWTH_SERIES = _l_pick_series(
    "growth",
    cfg(["diagnostics", "regime_backtest", "growth_series_count"], 2),
)
L_INFLATION_SERIES = _l_pick_series(
    "inflation",
    cfg(["diagnostics", "regime_backtest", "inflation_series_count"], 2),
)

L_SECTOR_TICKERS = (
    DATA_MANIFEST.loc[
        (DATA_MANIFEST["dataset"] == "market")
        & (DATA_MANIFEST["category"] == "sector")
        & (DATA_MANIFEST["enabled"] == True),
        "series_id",
    ]
    .astype(str)
    .drop_duplicates()
    .tolist()
)
L_BENCHMARK_TICKER = str(cfg(["portfolio", "benchmark"], "SPY"))

L_REGIME_PROTOTYPES = dict(ECONOMIC_REGIME_PROTOTYPES)

# Reuse the SAME centralized regime-sector economic priors as D3.
# Convert each signed prior to a strictly-positive long-only tilt.
_l_priors = cfg(["regime", "sector_prior_matrix"], {})
L_REGIME_SECTOR_TILTS = {
    regime: {
        ticker: max(0.05, 1.0 + float(prior))
        for ticker, prior in mapping.items()
        if ticker in set(L_SECTOR_TICKERS)
    }
    for regime, mapping in _l_priors.items()
}

for _l_regime_name in L_REGIME_PROTOTYPES:
    if _l_regime_name not in L_REGIME_SECTOR_TILTS:
        raise RuntimeError(
            f"Section L: no sector-tilt row defined for regime "
            f"'{_l_regime_name}'."
        )


# ==================================================================================================
# 3. LOAD CACHED SERIES (no new network calls -- reuses Section B's
#    already-persisted raw data via the same helper it uses)
# ==================================================================================================

def l_load_fred(series_id):
    df = load_existing_series("fred", series_id)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)


def l_load_market(ticker):
    df = load_existing_series("market", ticker)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "adj_close"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    price_col = "adj_close" if "adj_close" in df.columns else "close"
    df["adj_close"] = pd.to_numeric(df[price_col], errors="coerce")
    return df.dropna(subset=["date", "adj_close"]).sort_values("date").reset_index(drop=True)


L_FRED_RAW = {sid: l_load_fred(sid) for sid in L_GROWTH_SERIES + L_INFLATION_SERIES}
L_SECTOR_RAW = {t: l_load_market(t) for t in L_SECTOR_TICKERS}
L_BENCHMARK_RAW = l_load_market(L_BENCHMARK_TICKER)

L_MISSING_FRED = [sid for sid, df in L_FRED_RAW.items() if df.empty]
L_MISSING_SECTORS = [t for t, df in L_SECTOR_RAW.items() if df.empty]

if L_MISSING_FRED:
    raise RuntimeError(
        "Section L: no cached history for required FRED series "
        f"{L_MISSING_FRED}. Run Section B first."
    )

if len(L_MISSING_SECTORS) > len(L_SECTOR_TICKERS) // 2:
    raise RuntimeError(
        "Section L: too many sector ETFs missing cached history "
        f"({L_MISSING_SECTORS}). Run Section B/E market updates first."
    )

if L_BENCHMARK_RAW.empty:
    raise RuntimeError(
        "Section L: no cached SPY history. Run Section B/E first."
    )

L_AVAILABLE_SECTORS = [t for t in L_SECTOR_TICKERS if t not in L_MISSING_SECTORS]


# ==================================================================================================
# 4. POINT-IN-TIME-SAFE FEATURE CONSTRUCTION
# ==================================================================================================

def l_yoy_pct_change(df):
    out = df.set_index("date")["value"].sort_index()
    return out.pct_change(periods=12).dropna() if out.index.freqstr is None else out


def l_yoy_from_monthly(df):
    """
    YoY %% change computed against the observation ~12 months
    prior, regardless of exact calendar spacing (monthly FRED
    series occasionally have irregular gaps).
    """
    s = df.set_index("date")["value"].sort_index()
    s_monthly = s.resample("MS").last().ffill(limit=2)
    yoy = s_monthly.pct_change(periods=12) * 100.0
    return yoy.dropna().rename("yoy")


def l_expanding_zscore(series, min_periods):
    mean = series.expanding(min_periods=min_periods).mean()
    std = series.expanding(min_periods=min_periods).std()
    z = (series - mean) / std.replace(0.0, np.nan)
    return z.clip(-3.0, 3.0)


def l_apply_publication_lag(series, lag_days):
    out = series.reset_index()
    out.columns = ["obs_date", "value"]
    out["usable_date"] = out["obs_date"] + pd.Timedelta(days=lag_days)
    return out[["usable_date", "value"]].sort_values("usable_date").reset_index(drop=True)


def l_asof_daily(lagged_df, daily_dates):
    """
    PIT-safe reindex: for each date in daily_dates, use the most
    recent lagged_df value whose usable_date <= that date.
    """
    daily_frame = pd.DataFrame({"date": daily_dates}).sort_values("date")
    merged = pd.merge_asof(
        daily_frame,
        lagged_df.rename(columns={"usable_date": "date"}),
        on="date",
        direction="backward",
    )
    return merged.set_index("date")["value"]


L_GROWTH_YOY = {sid: l_yoy_from_monthly(L_FRED_RAW[sid]) for sid in L_GROWTH_SERIES}
L_INFLATION_YOY = {sid: l_yoy_from_monthly(L_FRED_RAW[sid]) for sid in L_INFLATION_SERIES}

L_GROWTH_Z = {
    sid: l_expanding_zscore(series, min_periods=L_MIN_HISTORY_MONTHS)
    for sid, series in L_GROWTH_YOY.items()
}

L_INFLATION_LEVEL = {
    sid: (series - 2.0) for sid, series in L_INFLATION_YOY.items()
}

L_INFLATION_Z = {
    sid: l_expanding_zscore(series, min_periods=L_MIN_HISTORY_MONTHS)
    for sid, series in L_INFLATION_LEVEL.items()
}

L_GROWTH_COMPOSITE = pd.concat(L_GROWTH_Z.values(), axis=1).mean(axis=1).dropna()
L_INFLATION_COMPOSITE = pd.concat(L_INFLATION_Z.values(), axis=1).mean(axis=1).dropna()

L_GROWTH_COMPOSITE.index.name = "date"
L_INFLATION_COMPOSITE.index.name = "date"

L_GROWTH_LAGGED = l_apply_publication_lag(L_GROWTH_COMPOSITE, L_PUBLICATION_LAG_DAYS)
L_INFLATION_LAGGED = l_apply_publication_lag(L_INFLATION_COMPOSITE, L_PUBLICATION_LAG_DAYS)


# ==================================================================================================
# 5. BUILD A MONTHLY REBALANCE CALENDAR FROM SECTOR-ETF PRICE HISTORY
# ==================================================================================================

L_PRICE_PANEL = pd.DataFrame(
    {t: L_SECTOR_RAW[t].set_index("date")["adj_close"] for t in L_AVAILABLE_SECTORS}
)
L_PRICE_PANEL[L_BENCHMARK_TICKER] = (
    L_BENCHMARK_RAW.set_index("date")["adj_close"]
)
L_PRICE_PANEL = L_PRICE_PANEL.sort_index().ffill(limit=5).dropna(how="any")

if len(L_PRICE_PANEL) < 252:
    raise RuntimeError(
        "Section L: insufficient common sector-ETF price history "
        f"({len(L_PRICE_PANEL)} trading days) to run a meaningful "
        "backtest."
    )

L_MONTH_ENDS = (
    L_PRICE_PANEL.resample("ME").last().index
)
L_MONTH_ENDS = L_MONTH_ENDS[L_MONTH_ENDS.isin(
    L_PRICE_PANEL.index.to_period("M").to_timestamp("M")
) | True]  # keep all month-end anchors; price lookup below is as-of

L_GROWTH_ASOF = l_asof_daily(L_GROWTH_LAGGED, L_MONTH_ENDS)
L_INFLATION_ASOF = l_asof_daily(L_INFLATION_LAGGED, L_MONTH_ENDS)

L_FIRST_VALID_DATE = max(
    L_GROWTH_ASOF.first_valid_index(),
    L_INFLATION_ASOF.first_valid_index(),
    L_PRICE_PANEL.index.min(),
)

L_REBALANCE_DATES = [
    d for d in L_MONTH_ENDS
    if d >= L_FIRST_VALID_DATE and not pd.isna(L_GROWTH_ASOF.get(d, np.nan))
    and not pd.isna(L_INFLATION_ASOF.get(d, np.nan))
]

if len(L_REBALANCE_DATES) < 24:
    raise RuntimeError(
        "Section L: fewer than 24 valid monthly rebalance dates "
        f"({len(L_REBALANCE_DATES)}) after lag-buffering and "
        "warm-up -- cannot run a meaningful backtest yet."
    )


# ==================================================================================================
# 6. REGIME PROBABILITY (same RBF kernel as D2) + EWMA SMOOTHING (same as D2B)
# ==================================================================================================

def l_regime_probabilities(growth_axis, inflation_axis):
    rows = []
    for regime_name, prototype in L_REGIME_PROTOTYPES.items():
        growth_distance = growth_axis - prototype["growth"]
        inflation_distance = inflation_axis - prototype["inflation"]
        squared_distance = growth_distance ** 2 + inflation_distance ** 2
        similarity = float(
            np.exp(-squared_distance / (2.0 * L_DISTANCE_SCALE ** 2))
        )
        rows.append((regime_name, similarity))
    total = sum(s for _, s in rows)
    return {name: sim / total for name, sim in rows}


L_RAW_REGIME_PROB_HISTORY = {}
for d in L_REBALANCE_DATES:
    L_RAW_REGIME_PROB_HISTORY[d] = l_regime_probabilities(
        float(L_GROWTH_ASOF[d]), float(L_INFLATION_ASOF[d])
    )

L_RAW_REGIME_PROB_DF = pd.DataFrame(L_RAW_REGIME_PROB_HISTORY).T
L_RAW_REGIME_PROB_DF.index.name = "date"

L_SMOOTHED_REGIME_PROB_DF = L_RAW_REGIME_PROB_DF.copy()
for i in range(1, len(L_SMOOTHED_REGIME_PROB_DF)):
    prior = L_SMOOTHED_REGIME_PROB_DF.iloc[i - 1]
    raw = L_RAW_REGIME_PROB_DF.iloc[i]
    blended = L_SMOOTHING_DECAY_DAILY * prior + (1.0 - L_SMOOTHING_DECAY_DAILY) * raw
    L_SMOOTHED_REGIME_PROB_DF.iloc[i] = blended / blended.sum()


# ==================================================================================================
# 7. REGIME-WEIGHTED SECTOR TARGET WEIGHTS + MONTHLY FORWARD RETURNS
# ==================================================================================================

L_NORMALIZED_TILTS = {}
for regime_name, tilts in L_REGIME_SECTOR_TILTS.items():
    available_tilts = {t: tilts[t] for t in L_AVAILABLE_SECTORS if t in tilts}
    total_tilt = sum(available_tilts.values())
    L_NORMALIZED_TILTS[regime_name] = {
        t: v / total_tilt for t, v in available_tilts.items()
    }

L_TARGET_WEIGHTS_ROWS = []
for d in L_REBALANCE_DATES:
    probs = L_SMOOTHED_REGIME_PROB_DF.loc[d]
    blended = {t: 0.0 for t in L_AVAILABLE_SECTORS}
    for regime_name, prob in probs.items():
        for t, w in L_NORMALIZED_TILTS[regime_name].items():
            blended[t] += float(prob) * w
    row = {"date": d}
    row.update(blended)
    L_TARGET_WEIGHTS_ROWS.append(row)

L_TARGET_WEIGHTS = pd.DataFrame(L_TARGET_WEIGHTS_ROWS).set_index("date")
L_TARGET_WEIGHTS = L_TARGET_WEIGHTS.div(L_TARGET_WEIGHTS.sum(axis=1), axis=0)

L_MONTHLY_PRICES = L_PRICE_PANEL.reindex(
    L_PRICE_PANEL.index.union(L_REBALANCE_DATES)
).ffill().loc[L_REBALANCE_DATES]

L_SECTOR_FWD_RETURNS = (
    L_MONTHLY_PRICES[L_AVAILABLE_SECTORS].pct_change().shift(-1)
)
L_BENCHMARK_FWD_RETURNS = (
    L_MONTHLY_PRICES[L_BENCHMARK_TICKER].pct_change().shift(-1)
)

# The last rebalance date has no forward return yet -- drop it.
L_USABLE_DATES = L_REBALANCE_DATES[:-1]

L_REGIME_STRATEGY_RETURNS = (
    (L_TARGET_WEIGHTS.loc[L_USABLE_DATES, L_AVAILABLE_SECTORS]
     * L_SECTOR_FWD_RETURNS.loc[L_USABLE_DATES])
    .sum(axis=1)
)

L_EQUAL_WEIGHT_RETURNS = (
    L_SECTOR_FWD_RETURNS.loc[L_USABLE_DATES].mean(axis=1)
)

L_BENCHMARK_RETURNS = L_BENCHMARK_FWD_RETURNS.loc[L_USABLE_DATES]


# ==================================================================================================
# 8. PERFORMANCE STATISTICS
# ==================================================================================================

def l_performance_stats(monthly_returns):
    monthly_returns = monthly_returns.dropna()
    if len(monthly_returns) < 12:
        return {
            "n_months": len(monthly_returns), "cagr": np.nan, "annual_vol": np.nan,
            "sharpe": np.nan, "max_drawdown": np.nan,
        }
    n_months = len(monthly_returns)
    cumulative = (1.0 + monthly_returns).cumprod()
    years = n_months / 12.0
    cagr = float(cumulative.iloc[-1] ** (1.0 / years) - 1.0)
    annual_vol = float(monthly_returns.std() * np.sqrt(12))
    sharpe = float(cagr / annual_vol) if annual_vol > 1e-10 else np.nan
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1.0
    max_drawdown = float(drawdown.min())
    return {
        "n_months": n_months, "cagr": round(cagr, 4),
        "annual_vol": round(annual_vol, 4), "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_drawdown, 4),
    }


L_BACKTEST_SUMMARY = pd.DataFrame(
    {
        "regime_weighted_sectors": l_performance_stats(L_REGIME_STRATEGY_RETURNS),
        "equal_weight_sectors": l_performance_stats(L_EQUAL_WEIGHT_RETURNS),
        "spy_buy_and_hold": l_performance_stats(L_BENCHMARK_RETURNS),
    }
).T

L_HIT_RATE_VS_EQUAL_WEIGHT = float(
    (L_REGIME_STRATEGY_RETURNS > L_EQUAL_WEIGHT_RETURNS).mean()
)
L_HIT_RATE_VS_SPY = float(
    (L_REGIME_STRATEGY_RETURNS > L_BENCHMARK_RETURNS).mean()
)


# ==================================================================================================
# 9. SAVE + DISPLAY
# ==================================================================================================

L_OUTPUT_DIR = globals().get("REGIME_MODEL_DIR", Path("."))

L_BACKTEST_SUMMARY.to_parquet(
    L_OUTPUT_DIR / "l_regime_sector_backtest_summary.parquet"
)
L_TARGET_WEIGHTS.to_parquet(
    L_OUTPUT_DIR / "l_regime_sector_backtest_target_weights.parquet"
)

print("=" * 82)
print("SECTION L — REGIME -> SECTOR ROTATION VALIDATION BACKTEST")
print("=" * 82)

print(
    "\n⚠ DIAGNOSTIC ONLY -- approximate PIT (standard revised FRED "
    "data, not ALFRED vintage-aware; publication-lag-buffered only). "
    "This is NOT the Section-18 PIT historical backtesting engine "
    "and does NOT certify the live A-K stock-selection system. "
    "HISTORICAL_ALPHA_BACKTEST_ELIGIBLE / DATA_MANIFEST['backtest_ready'] "
    "are untouched by this cell and remain False."
)

print(
    f"\nSector ETFs available: {len(L_AVAILABLE_SECTORS)}/{len(L_SECTOR_TICKERS)} "
    f"(missing: {L_MISSING_SECTORS or 'none'})"
)
print(f"Publication lag applied: {L_PUBLICATION_LAG_DAYS} days")
print(f"Rebalance months tested: {len(L_USABLE_DATES)}")
print(
    f"Period: {L_USABLE_DATES[0].date()} to {L_USABLE_DATES[-1].date()}"
    if L_USABLE_DATES else "Period: n/a"
)
print(
    "  (start date is gated by the NEWEST sector ETF's inception -- "
    "e.g. XLC listed in 2018, XLRE in 2015 -- since the panel "
    "requires all sectors present simultaneously; this is "
    "conservative but means older regimes such as the dot-com bust "
    "or 2008 are excluded whenever a younger sector is in the mix.)"
)

print("\nPerformance summary (monthly rebalance):")
display(L_BACKTEST_SUMMARY)

print(
    f"\nHit rate vs equal-weight sectors: {L_HIT_RATE_VS_EQUAL_WEIGHT:.1%}"
)
print(
    f"Hit rate vs SPY buy-and-hold:     {L_HIT_RATE_VS_SPY:.1%}"
)

print(
    "\n✓ SECTION L COMPLETE — regime-signal screening diagnostic "
    "only; no production or governance flag was changed."
)

