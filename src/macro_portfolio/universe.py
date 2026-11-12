from __future__ import annotations

from io import StringIO
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd
import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json,text/csv,*/*;q=0.8",
}

GICS_TO_SECTOR_ETF = {
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}


CANONICAL_GICS_SECTORS = tuple(GICS_TO_SECTOR_ETF)

# Sector-level aliases emitted by common market-data vendors.  The master
# universe always stores the canonical 11-sector GICS naming convention.
SECTOR_ALIAS_TO_GICS = {
    # canonical spellings
    **{k.lower(): k for k in CANONICAL_GICS_SECTORS},
    # common vendor / legacy labels
    "technology": "Information Technology",
    "information tech": "Information Technology",
    "tech": "Information Technology",
    "healthcare": "Health Care",
    "health care": "Health Care",
    "financial services": "Financials",
    "finance": "Financials",
    "consumer cyclical": "Consumer Discretionary",
    "consumer discretionary": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "consumer staples": "Consumer Staples",
    "basic materials": "Materials",
    "materials": "Materials",
    "communication services": "Communication Services",
    "communications": "Communication Services",
    "telecommunication services": "Communication Services",
    "telecommunications": "Communication Services",
    "industrial": "Industrials",
    "industrials": "Industrials",
    "energy": "Energy",
    "utilities": "Utilities",
    "real estate": "Real Estate",
}


def canonicalize_gics_sector(value):
    """Return one of the 11 canonical GICS sectors, or NaN if unknown.

    Constituent vendors do not always use the exact GICS display spelling
    (e.g. Yahoo uses ``Technology`` and ``Consumer Cyclical``).  This function
    normalizes those labels without changing the economic sector assignment.
    """
    if pd.isna(value):
        return np.nan
    raw = re.sub(r"\s+", " ", str(value)).strip()
    if not raw or raw.lower() in {"nan", "none", "n/a", "na", "unknown"}:
        return np.nan
    key = raw.lower().replace("&", "and")
    key = re.sub(r"\s+", " ", key).strip()
    aliases = {k.replace("&", "and"): v for k, v in SECTOR_ALIAS_TO_GICS.items()}
    if key in aliases:
        return aliases[key]

    # Conservative keyword fallback for vendor labels that append industry
    # qualifiers.  Order matters for consumer categories.
    checks = [
        (("consumer cyclical", "consumer discretionary"), "Consumer Discretionary"),
        (("consumer defensive", "consumer staples"), "Consumer Staples"),
        (("communication", "telecom"), "Communication Services"),
        (("information technology", "technology", "software", "semiconductor"), "Information Technology"),
        (("health care", "healthcare", "pharma", "biotech"), "Health Care"),
        (("financial", "bank", "insurance"), "Financials"),
        (("real estate", "reit"), "Real Estate"),
        (("industrial",), "Industrials"),
        (("basic material", "materials"), "Materials"),
        (("utilities", "utility"), "Utilities"),
        (("energy", "oil", "gas"), "Energy"),
    ]
    for needles, sector in checks:
        if any(n in key for n in needles):
            return sector
    return np.nan


def _default_yahoo_sector_fetcher(ticker: str):
    """Fetch sector metadata for a single ticker via yfinance.

    Only used for names whose constituent sources and local sector cache did
    not already provide a canonical GICS sector.  This keeps network traffic
    bounded to the genuinely missing tail of the union universe.
    """
    import yfinance as yf
    info = yf.Ticker(normalize_yahoo_ticker(ticker)).get_info() or {}
    return {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "longName": info.get("longName") or info.get("shortName"),
    }


def enrich_gics_sector_coverage(
    master: pd.DataFrame,
    *,
    curated_dir: Path,
    snapshot_date,
    yahoo_fetcher=None,
) -> pd.DataFrame:
    """Guarantee canonical 11-sector GICS coverage for the master universe.

    Resolution order:
      1. Canonicalize sector supplied by constituent metadata.
      2. Force SOXX specialist members to Information Technology (semiconductors).
      3. Reuse persistent ticker->sector enrichment cache.
      4. Query company-level Yahoo sector metadata only for remaining tickers.
      5. Hard fail if *any* investable ticker still lacks a canonical sector.

    Unmapped normal companies are therefore never silently quarantined.
    """
    out = master.copy()
    curated_dir = Path(curated_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)
    cache_path = curated_dir / "company_gics_sector_latest.csv"

    out["gics_sector_raw"] = out.get("gics_sector", pd.Series(index=out.index, dtype="object"))
    out["gics_sector"] = out["gics_sector_raw"].map(canonicalize_gics_sector)
    out["gics_sector_source"] = np.where(
        out["gics_sector"].notna(), "CONSTITUENT_METADATA", "UNRESOLVED"
    )

    # SOXX is a semiconductor specialist overlay. Semiconductor companies map
    # to the Information Technology GICS sector at this sector-level taxonomy.
    soxx_mask = out.get("member_soxx", False).fillna(False).astype(bool)
    out.loc[soxx_mask, "gics_sector"] = "Information Technology"
    out.loc[soxx_mask, "gics_sector_source"] = "SOXX_SEMICONDUCTOR_OVERLAY"
    out.loc[soxx_mask & out["gics_sub_industry"].isna(), "gics_sub_industry"] = (
        "Semiconductors & Semiconductor Equipment"
    )

    # Persistent company-sector cache avoids repeated metadata calls across runs.
    if cache_path.exists():
        try:
            cache = pd.read_csv(cache_path)
            if {"ticker", "gics_sector"}.issubset(cache.columns):
                cache = cache[[c for c in ["ticker", "gics_sector", "gics_sub_industry", "company_name"] if c in cache.columns]].copy()
                cache["ticker"] = cache["ticker"].astype(str).str.strip().str.upper()
                cache["gics_sector"] = cache["gics_sector"].map(canonicalize_gics_sector)
                cmap = cache.dropna(subset=["gics_sector"]).drop_duplicates("ticker").set_index("ticker")["gics_sector"]
                missing = out["gics_sector"].isna()
                filled = out.loc[missing, "ticker"].map(cmap)
                use = filled.notna()
                idx = filled.index[use]
                out.loc[idx, "gics_sector"] = filled.loc[idx]
                out.loc[idx, "gics_sector_source"] = "PERSISTENT_SECTOR_CACHE"
        except Exception:
            # A corrupt cache must not override live constituent metadata.
            pass

    fetcher = yahoo_fetcher or _default_yahoo_sector_fetcher
    unresolved = out.loc[out["gics_sector"].isna(), "ticker"].astype(str).tolist()
    enrichment_rows = []
    for ticker in unresolved:
        try:
            meta = fetcher(ticker) or {}
            sector = canonicalize_gics_sector(meta.get("sector"))
            if pd.isna(sector):
                # Some vendors return a broad industry label but no sector.
                sector = canonicalize_gics_sector(meta.get("industry"))
            enrichment_rows.append({
                "ticker": ticker,
                "gics_sector": sector,
                "gics_sub_industry": meta.get("industry"),
                "company_name": meta.get("longName"),
                "sector_metadata_source": "YAHOO_COMPANY_METADATA",
            })
        except Exception as exc:
            enrichment_rows.append({
                "ticker": ticker,
                "gics_sector": np.nan,
                "gics_sub_industry": np.nan,
                "company_name": np.nan,
                "sector_metadata_source": f"YAHOO_ERROR:{type(exc).__name__}",
            })

    if enrichment_rows:
        enrich = pd.DataFrame(enrichment_rows).set_index("ticker")
        for idx, ticker in out["ticker"].items():
            if pd.notna(out.at[idx, "gics_sector"]):
                continue
            if ticker not in enrich.index:
                continue
            sector = enrich.at[ticker, "gics_sector"]
            if pd.notna(sector):
                out.at[idx, "gics_sector"] = sector
                out.at[idx, "gics_sector_source"] = "YAHOO_COMPANY_METADATA"
                if (pd.isna(out.at[idx, "gics_sub_industry"]) or not str(out.at[idx, "gics_sub_industry"]).strip()):
                    out.at[idx, "gics_sub_industry"] = enrich.at[ticker, "gics_sub_industry"]
                if (pd.isna(out.at[idx, "company_name"]) or not str(out.at[idx, "company_name"]).strip()):
                    out.at[idx, "company_name"] = enrich.at[ticker, "company_name"]

    out["gics_sector"] = out["gics_sector"].map(canonicalize_gics_sector)
    out["sector_ticker"] = out["gics_sector"].map(GICS_TO_SECTOR_ETF)
    out["sector_metadata_asof"] = pd.Timestamp(snapshot_date).normalize()

    unresolved_df = out.loc[
        out["gics_sector"].isna() | out["sector_ticker"].isna(),
        ["ticker", "company_name", "gics_sector_raw", "universe_memberships", "gics_sector_source"],
    ].copy()
    if not unresolved_df.empty:
        raise RuntimeError(
            "GICS sector enrichment failed: every master-universe stock must map "
            "to one of the 11 canonical GICS sectors. Unresolved tickers="
            + ",".join(unresolved_df["ticker"].astype(str).tolist())
        )

    if not out["gics_sector"].isin(CANONICAL_GICS_SECTORS).all():
        bad = sorted(out.loc[~out["gics_sector"].isin(CANONICAL_GICS_SECTORS), "gics_sector"].astype(str).unique())
        raise RuntimeError(f"Non-canonical GICS sector labels remain: {bad}")

    # Persist the fully resolved mapping for future constituent changes / outages.
    cache_cols = ["ticker", "company_name", "gics_sector", "gics_sub_industry"]
    resolved = out[cache_cols].drop_duplicates("ticker").sort_values("ticker")
    if cache_path.exists():
        try:
            old = pd.read_csv(cache_path)
            if "ticker" in old.columns:
                old["ticker"] = old["ticker"].astype(str).str.strip().str.upper()
                resolved = pd.concat([old[cache_cols], resolved], ignore_index=True, sort=False)
                resolved = resolved.drop_duplicates("ticker", keep="last").sort_values("ticker")
        except Exception:
            pass
    resolved.to_csv(cache_path, index=False)
    return out


def normalize_yahoo_ticker(symbol: str) -> str:
    if pd.isna(symbol):
        return np.nan
    return str(symbol).strip().replace(".", "-")


def _first_non_null(series):
    for value in series:
        if pd.notna(value) and str(value).strip() not in {"", "nan", "None"}:
            return value
    return np.nan


def _clean_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()
    for col in ["ticker", "company_name", "gics_sector", "gics_sub_industry"]:
        if col not in out.columns:
            out[col] = np.nan
    out["ticker"] = out["ticker"].astype("string").str.strip().str.upper()
    out["company_name"] = out["company_name"].astype("string").str.strip()
    out["gics_sector"] = out["gics_sector"].astype("string").str.strip()
    out["gics_sector"] = out["gics_sector"].map(canonicalize_gics_sector)
    out["gics_sub_industry"] = out["gics_sub_industry"].astype("string").str.strip()
    out = out[out["ticker"].notna() & ~out["ticker"].isin(["", "NAN", "NONE", "CASH", "USD"])].copy()
    out["source_name"] = source
    return out.drop_duplicates("ticker", keep="first").reset_index(drop=True)


def fetch_sp500(timeout: int = 30) -> pd.DataFrame:
    urls = [
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
    ]
    errors = []
    for url in urls:
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text)).rename(columns={
                "Symbol": "ticker", "Security": "company_name", "GICS Sector": "gics_sector",
                "GICS Sub-Industry": "gics_sub_industry", "Headquarters Location": "headquarters",
                "Date added": "date_added", "CIK": "cik", "Founded": "founded",
            })
            return _clean_frame(df, "S&P 500")
        except Exception as exc:
            errors.append(f"GitHub:{type(exc).__name__}:{exc}")
    # secondary live source
    try:
        r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        for table in tables:
            cols = {str(c) for c in table.columns}
            if {"Symbol", "Security", "GICS Sector"}.issubset(cols):
                df = table.rename(columns={
                    "Symbol": "ticker", "Security": "company_name", "GICS Sector": "gics_sector",
                    "GICS Sub-Industry": "gics_sub_industry", "Headquarters Location": "headquarters",
                    "Date added": "date_added", "CIK": "cik", "Founded": "founded",
                })
                return _clean_frame(df, "S&P 500")
        raise RuntimeError("Wikipedia S&P 500 constituent table not found")
    except Exception as exc:
        errors.append(f"Wikipedia:{type(exc).__name__}:{exc}")
    raise RuntimeError("Unable to fetch current S&P 500 constituents: " + " | ".join(errors))


def _nasdaq_wikipedia_metadata(timeout: int = 30) -> pd.DataFrame:
    r = requests.get("https://en.wikipedia.org/wiki/Nasdaq-100", headers=DEFAULT_HEADERS, timeout=timeout)
    r.raise_for_status()
    for table in pd.read_html(StringIO(r.text)):
        cols = {str(c) for c in table.columns}
        if "Ticker" in cols and ("Company" in cols or "Company name" in cols):
            rename = {"Ticker": "ticker", "Company": "company_name", "Company name": "company_name",
                      "GICS Sector": "gics_sector", "GICS Sub-Industry": "gics_sub_industry"}
            candidate = table.rename(columns=rename)
            if "ticker" in candidate and len(candidate) >= 80:
                return _clean_frame(candidate, "Nasdaq-100")
    raise RuntimeError("Nasdaq-100 constituent table not found on Wikipedia")


def fetch_nasdaq100(timeout: int = 30) -> pd.DataFrame:
    errors = []
    api = None
    try:
        r = requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        rows = (((r.json() or {}).get("data") or {}).get("data") or {}).get("rows") or []
        api = pd.DataFrame(rows)
        if api.empty or "symbol" not in api.columns:
            raise RuntimeError("Nasdaq API returned no constituent rows")
        api = api.rename(columns={"symbol": "ticker", "companyName": "company_name"})
        api = _clean_frame(api, "Nasdaq-100")
    except Exception as exc:
        errors.append(f"NasdaqAPI:{type(exc).__name__}:{exc}")
        api = None

    wiki = None
    try:
        wiki = _nasdaq_wikipedia_metadata(timeout=timeout)
    except Exception as exc:
        errors.append(f"Wikipedia:{type(exc).__name__}:{exc}")

    if api is None and wiki is None:
        raise RuntimeError("Unable to fetch Nasdaq-100 constituents: " + " | ".join(errors))
    if api is None:
        return wiki
    if wiki is None:
        return api

    meta = wiki[["ticker", "gics_sector", "gics_sub_industry"]].drop_duplicates("ticker")
    out = api.drop(columns=[c for c in ["gics_sector", "gics_sub_industry"] if c in api.columns]).merge(meta, on="ticker", how="left")
    # Official API defines membership; Wikipedia supplies GICS metadata.
    return _clean_frame(out, "Nasdaq-100")


def _flatten_columns(columns) -> list[str]:
    """Flatten pandas HTML/Excel style columns into simple strings."""
    out = []
    for col in columns:
        if isinstance(col, tuple):
            parts = [str(x).strip() for x in col if str(x).strip() and not str(x).startswith("Unnamed")]
            out.append(" ".join(parts).strip())
        else:
            out.append(str(col).strip())
    return out


def _find_column(columns, *candidates):
    """Case/whitespace/punctuation tolerant column lookup."""
    norm = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): c for c in columns}
    for candidate in candidates:
        key = re.sub(r"[^a-z0-9]+", "", str(candidate).lower())
        if key in norm:
            return norm[key]
    return None


def _finalize_soxx_frame(df: pd.DataFrame, source_detail: str) -> pd.DataFrame:
    """Normalize an official/proxy semiconductor holdings table."""
    out = df.copy()
    out.columns = _flatten_columns(out.columns)

    ticker_col = _find_column(out.columns, "Ticker", "Symbol")
    name_col = _find_column(out.columns, "Name", "Company", "Security")
    sector_col = _find_column(out.columns, "Sector", "GICS Sector")
    asset_col = _find_column(out.columns, "Asset Class", "AssetClass")
    weight_col = _find_column(out.columns, "Weight (%)", "Weight", "Weight Percent")

    if ticker_col is None:
        raise RuntimeError(f"SOXX/semiconductor source has no ticker column; columns={list(out.columns)}")

    rename = {ticker_col: "ticker"}
    if name_col is not None:
        rename[name_col] = "company_name"
    if sector_col is not None:
        rename[sector_col] = "gics_sector"
    if weight_col is not None:
        rename[weight_col] = "soxx_weight_pct"
    out = out.rename(columns=rename)

    if asset_col is not None:
        asset = out[asset_col].astype(str).str.strip().str.lower()
        # iShares CSV contains cash/derivatives rows after the equity holdings.
        if asset.eq("equity").any():
            out = out[asset.eq("equity")].copy()

    # Remove common cash / FX / total rows that can appear in downloaded holdings.
    bad = {"", "NAN", "NONE", "USD", "CASH", "-", "TOTAL"}
    out["ticker"] = out["ticker"].astype(str).str.strip().str.upper()
    out = out[~out["ticker"].isin(bad)].copy()

    if "company_name" not in out:
        out["company_name"] = out["ticker"]

    # SOXX is used only as a semiconductor specialist overlay.  If the
    # upstream source does not carry GICS, make the specialist mapping explicit.
    out["gics_sector"] = "Information Technology"
    out["gics_sub_industry"] = "Semiconductors & Semiconductor Equipment"
    out["membership_source_detail"] = source_detail

    cleaned = _clean_frame(out, "SOXX")
    if len(cleaned) < 20:
        raise RuntimeError(f"Unexpected semiconductor holding count: {len(cleaned)}")
    return cleaned


def _parse_ishares_csv(text: str) -> pd.DataFrame:
    """Parse iShares holdings CSV without assuming an exact header row format.

    BlackRock/iShares has changed preambles, quoting and product-page redirects
    over time.  We therefore detect the holdings header semantically instead of
    requiring ``line.startswith('Ticker,')``.
    """
    raw = text.replace("\ufeff", "")
    if re.search(r"<\s*html|<!doctype\s+html", raw[:2000], flags=re.I):
        raise RuntimeError("iShares CSV endpoint returned HTML")

    lines = raw.splitlines()
    header = None
    for i, line in enumerate(lines):
        normalized = re.sub(r"[\"']", "", line).strip().lower()
        # Accept commas, semicolons or tabs and extra columns/order changes.
        if "ticker" in normalized and "asset class" in normalized and "name" in normalized:
            header = i
            break
    if header is None:
        raise RuntimeError("iShares holdings CSV header not found")

    payload = "\n".join(lines[header:])
    # sep=None lets pandas infer comma/semicolon/tab delimiters.
    df = pd.read_csv(StringIO(payload), sep=None, engine="python")
    return _finalize_soxx_frame(df, "ISHARES_HOLDINGS_CSV")


def _parse_ishares_html(text: str) -> pd.DataFrame:
    """Parse a rendered iShares holdings table when CSV download redirects."""
    tables = pd.read_html(StringIO(text))
    errors = []
    for table in tables:
        try:
            cols = _flatten_columns(table.columns)
            table.columns = cols
            if _find_column(cols, "Ticker", "Symbol") is None:
                continue
            if _find_column(cols, "Name", "Company", "Security") is None:
                continue
            candidate = _finalize_soxx_frame(table, "ISHARES_HOLDINGS_HTML")
            if len(candidate) >= 20:
                return candidate
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}")
    raise RuntimeError("iShares holdings HTML table not found" + (" | " + " | ".join(errors) if errors else ""))




def _parse_stockanalysis_soxx_html(text: str) -> pd.DataFrame:
    """Parse the public SOXX holdings table from StockAnalysis.

    This is a secondary, non-issuer source. It is useful when the iShares
    download/rendering endpoints change markup. The result is tagged so the
    pipeline never represents it as issuer-exact membership.
    """
    tables = pd.read_html(StringIO(text))
    errors = []
    for table in tables:
        try:
            table = table.copy()
            table.columns = _flatten_columns(table.columns)
            sym = _find_column(table.columns, "Symbol", "Ticker")
            name = _find_column(table.columns, "Name", "Company")
            weight = _find_column(table.columns, "Weight", "Weight (%)")
            if sym is None or name is None:
                continue
            rename = {sym: "ticker", name: "company_name"}
            if weight is not None:
                rename[weight] = "soxx_weight_pct"
            candidate = table.rename(columns=rename)
            out = _finalize_soxx_frame(candidate, "STOCKANALYSIS_SOXX_HOLDINGS")
            if len(out) >= 20:
                return out
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}")
    raise RuntimeError(
        "StockAnalysis SOXX holdings table not found"
        + (" | " + " | ".join(errors) if errors else "")
    )


def _load_bundled_soxx_snapshot(path: Path) -> pd.DataFrame:
    """Load a packaged last-known-good SOXX research snapshot.

    This is deliberately a *continuity fallback*, not a claim of live
    membership.  It keeps the specialist research overlay available during
    first-run/vendor outages while preserving source/freshness metadata.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if "membership_source_detail" not in df.columns:
        df["membership_source_detail"] = "BUNDLED_SOXX_LAST_KNOWN_GOOD"
    return _finalize_soxx_frame(df, "BUNDLED_SOXX_LAST_KNOWN_GOOD")


def fetch_soxx(timeout: int = 30) -> pd.DataFrame:
    """Fetch the live SOXX specialist overlay with layered resilience.

    Source order:
      1. iShares issuer holdings CSV (preferred)
      2. iShares issuer rendered holdings page
      3. StockAnalysis public SOXX holdings table (secondary live source)

    The PHLX SOX index is intentionally *not* used as a substitute for SOXX
    membership because SOXX currently tracks the NYSE Semiconductor Index.
    A bundled last-known-good SOXX snapshot is handled by ``load_live_or_cache``
    if every live source is unavailable.
    """
    endpoints = [
        "https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf/1467271812596.ajax?fileType=csv&fileName=SOXX_holdings&dataType=fund",
        "https://www.ishares.com/us/products/239705/ishares-semiconductor-etf/1467271812596.ajax?fileType=csv&fileName=SOXX_holdings&dataType=fund",
        "https://www.ishares.com/us/products/239705/fund/1467271812596.ajax?fileType=csv&fileName=SOXX_holdings&dataType=fund",
    ]
    errors = []
    for url in endpoints:
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            r.raise_for_status()
            try:
                return _parse_ishares_csv(r.text)
            except Exception as csv_exc:
                try:
                    return _parse_ishares_html(r.text)
                except Exception as html_exc:
                    raise RuntimeError(f"CSV={csv_exc}; HTML={html_exc}")
        except Exception as exc:
            errors.append(f"iShares:{type(exc).__name__}:{exc}")

    product_pages = [
        "https://www.ishares.com/us/products/239705/ishares-semiconductor-etf",
        "https://www.ishares.com/us/products/239705/fund",
        "https://www.blackrock.com/us/individual/products/239705/ishares-semiconductor-etf",
    ]
    for url in product_pages:
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            r.raise_for_status()
            return _parse_ishares_html(r.text)
        except Exception as exc:
            errors.append(f"iSharesHTML:{type(exc).__name__}:{exc}")

    # Secondary LIVE holdings source. This is still SOXX-specific, unlike SOX.
    try:
        r = requests.get(
            "https://stockanalysis.com/etf/soxx/holdings/",
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        r.raise_for_status()
        return _parse_stockanalysis_soxx_html(r.text)
    except Exception as exc:
        errors.append(f"StockAnalysis:{type(exc).__name__}:{exc}")

    raise RuntimeError("Unable to fetch live SOXX holdings: " + " | ".join(errors))


def _read_cached_frame(parquet_path: Path, csv_path: Path):
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path), str(parquet_path)
        except Exception:
            pass
    if csv_path.exists():
        return pd.read_csv(csv_path), str(csv_path)
    return None, None


def _write_cached_frame(df: pd.DataFrame, parquet_path: Path, csv_path: Path) -> str:
    """Persist parquet when available and CSV as a universal fallback."""
    try:
        df.to_parquet(parquet_path, index=False)
        return str(parquet_path)
    except Exception:
        df.to_csv(csv_path, index=False)
        return str(csv_path)


def load_live_or_cache(
    name: str,
    snapshot_date: pd.Timestamp,
    raw_dir: Path,
    curated_dir: Path,
    fetcher,
    *,
    bundled_fallback: Path | None = None,
    bundled_loader=None,
):
    """Load dated snapshot -> live -> curated cache -> bundled snapshot.

    External constituent websites are not production single points of failure.
    Every degraded path is explicit in the returned source mode/detail.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp(snapshot_date).strftime("%Y-%m-%d")
    snap_parquet = raw_dir / f"{name}_{stamp}.parquet"
    snap_csv = raw_dir / f"{name}_{stamp}.csv"
    latest_parquet = curated_dir / f"{name}_latest.parquet"
    latest_csv = curated_dir / f"{name}_latest.csv"

    cached, cached_path = _read_cached_frame(snap_parquet, snap_csv)
    if cached is not None:
        return cached, "CACHED_DATED_SNAPSHOT", cached_path

    live_error = None
    try:
        df = fetcher()
        dated_path = _write_cached_frame(df, snap_parquet, snap_csv)
        latest_path = _write_cached_frame(df, latest_parquet, latest_csv)
        return df, "LIVE_FETCH", f"{name} | dated={dated_path} | latest={latest_path}"
    except Exception as exc:
        live_error = f"{type(exc).__name__}:{exc}"

    latest, latest_path = _read_cached_frame(latest_parquet, latest_csv)
    if latest is not None:
        return (
            latest,
            "FALLBACK_CURATED_CACHE",
            f"{latest_path} | live_error={live_error}",
        )

    if bundled_fallback is not None:
        bundled_fallback = Path(bundled_fallback)
        if bundled_fallback.exists():
            loader = bundled_loader or (lambda path: pd.read_csv(path))
            df = loader(bundled_fallback)
            seeded_path = _write_cached_frame(df, latest_parquet, latest_csv)
            return (
                df,
                "FALLBACK_BUNDLED_SNAPSHOT",
                f"{bundled_fallback} | seeded_cache={seeded_path} | live_error={live_error}",
            )

    raise RuntimeError(
        f"Unable to load {name}: live fetch failed ({live_error}); "
        "no dated, curated, or bundled fallback is available."
    )


def combine_current_universes(sp500: pd.DataFrame, nasdaq100: pd.DataFrame, soxx: pd.DataFrame, snapshot_date) -> pd.DataFrame:
    frames = []
    specs = [(sp500, "sp500"), (nasdaq100, "nasdaq100"), (soxx, "soxx")]
    for df, tag in specs:
        x = _clean_frame(df, {"sp500":"S&P 500","nasdaq100":"Nasdaq-100","soxx":"SOXX"}[tag])
        x[f"member_{tag}"] = True
        frames.append(x)
    stacked = pd.concat(frames, ignore_index=True, sort=False)
    for col in ["member_sp500", "member_nasdaq100", "member_soxx"]:
        if col not in stacked: stacked[col] = False
        stacked[col] = stacked[col].map(lambda x: bool(x) if pd.notna(x) else False).astype(bool)

    rows = []
    # precedence is core S&P metadata, then Nasdaq, then SOXX specialist metadata.
    source_order = {"S&P 500":0, "Nasdaq-100":1, "SOXX":2}
    stacked["_source_order"] = stacked["source_name"].map(source_order).fillna(9)
    for ticker, g in stacked.sort_values("_source_order").groupby("ticker", sort=True):
        _soxx_rows = g[g["member_soxx"]].copy()
        _soxx_source = (
            _first_non_null(_soxx_rows["membership_source_detail"])
            if (not _soxx_rows.empty and "membership_source_detail" in _soxx_rows.columns)
            else np.nan
        )
        rows.append({
            "symbol": ticker,
            "ticker": ticker,
            "company_name": _first_non_null(g["company_name"]),
            "gics_sector": _first_non_null(g["gics_sector"]),
            "gics_sub_industry": _first_non_null(g["gics_sub_industry"]),
            "member_sp500": bool(g["member_sp500"].any()),
            "member_nasdaq100": bool(g["member_nasdaq100"].any()),
            "member_soxx": bool(g["member_soxx"].any()),
            "soxx_membership_source": _soxx_source,
            "soxx_membership_exact": bool(
                (not _soxx_rows.empty)
                and pd.notna(_soxx_source)
                and "ISHARES" in str(_soxx_source).upper()
            ),
            "soxx_membership_quality": (
                "ISSUER_EXACT" if (pd.notna(_soxx_source) and "ISHARES" in str(_soxx_source).upper())
                else "SECONDARY_LIVE" if (pd.notna(_soxx_source) and "STOCKANALYSIS" in str(_soxx_source).upper())
                else "BUNDLED_LAST_KNOWN_GOOD" if (pd.notna(_soxx_source) and "BUNDLED" in str(_soxx_source).upper())
                else "UNKNOWN"
            ),
        })
    out = pd.DataFrame(rows)
    out["yahoo_ticker"] = out["ticker"].map(normalize_yahoo_ticker)
    out["gics_sector"] = out["gics_sector"].map(canonicalize_gics_sector)
    out["gics_sub_industry"] = out["gics_sub_industry"].astype("object")
    out["sector_ticker"] = out["gics_sector"].map(GICS_TO_SECTOR_ETF)
    # Specialist SOXX names are semiconductor/technology even if upstream metadata is absent.
    mask = out["member_soxx"] & out["sector_ticker"].isna()
    out.loc[mask, "gics_sector"] = "Information Technology"
    out.loc[mask, "gics_sub_industry"] = "Semiconductors & Semiconductor Equipment"
    out.loc[mask, "sector_ticker"] = "XLK"
    out["core_universe_member"] = out["member_sp500"]
    out["growth_overlay_member"] = out["member_nasdaq100"]
    out["semiconductor_overlay_member"] = out["member_soxx"]
    out["specialist_group"] = np.where(out["member_soxx"], "SEMICONDUCTORS", "GENERAL")
    out["universe_source_count"] = out[["member_sp500","member_nasdaq100","member_soxx"]].sum(axis=1).astype(int)
    out["universe_memberships"] = out.apply(lambda r: "+".join([
        n for flag,n in [(r.member_sp500,"SP500"),(r.member_nasdaq100,"NASDAQ100"),(r.member_soxx,"SOXX")] if flag
    ]), axis=1)
    out["universe_name"] = "S&P500 + Nasdaq100 + SOXX"
    out["membership_snapshot_date"] = pd.Timestamp(snapshot_date).normalize()
    out["historical_backtest_eligible"] = False
    return out.sort_values("ticker").reset_index(drop=True)
