from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cvxpy as cp
import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pyarrow as pa
import pyarrow.parquet as pq
import scipy
from scipy import stats as scipy_stats
import statsmodels.api as sm
import yfinance as yf
import yaml
from arch import arch_model
from fredapi import Fred
from dotenv import load_dotenv
from hmmlearn.hmm import GaussianHMM
from pandas_datareader import data as pdr
from sklearn.covariance import LedoitWolf
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from plotly.subplots import make_subplots

from .numeric_safety import safe_isfinite, safe_bool_series
from .dependencies import require_objects

try:
    from IPython.display import display
except Exception:
    def display(obj):
        print(obj)



def repository_root() -> Path:
    # src/macro_portfolio/runtime.py -> project root
    return Path(__file__).resolve().parents[2]


def load_config(root: Path) -> dict:
    path = root / "config" / "settings.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing configuration: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_runtime(run_id: str | None = None) -> dict:
    root = repository_root()
    config = load_config(root)
    load_dotenv(root / ".env", override=True)

    fred_api_key = os.getenv("FRED_API_KEY", "").strip()
    if not fred_api_key:
        raise RuntimeError(
            "FRED_API_KEY is missing. This local build expects it in the bundled .env file "
            "or in the process environment before runtime initialization."
        )

    # Local project paths shared by CLI and notebook execution.
    project_root = root
    data_dir = project_root / "data"
    models_dir = project_root / "models"
    config_dir = project_root / "config"
    logs_dir = project_root / "logs"
    outputs_dir = project_root / "outputs"

    raw_data_dir = data_dir / "raw"
    curated_data_dir = data_dir / "curated"
    feature_data_dir = data_dir / "features"

    regime_model_dir = models_dir / "regime"
    sector_model_dir = models_dir / "sector"
    stock_model_dir = models_dir / "stock"
    risk_model_dir = models_dir / "risk"

    dashboard_output_dir = outputs_dir / "dashboard"
    trade_output_dir = outputs_dir / "trades"
    portfolio_output_dir = outputs_dir / "portfolio"
    backtest_output_dir = outputs_dir / "backtests"

    for d in [
        data_dir, models_dir, config_dir, logs_dir, outputs_dir,
        raw_data_dir, curated_data_dir, feature_data_dir,
        regime_model_dir, sector_model_dir, stock_model_dir, risk_model_dir,
        dashboard_output_dir, trade_output_dir, portfolio_output_dir,
        backtest_output_dir, outputs_dir / "runs", outputs_dir / "state",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "portfolio.duckdb"
    now = datetime.now()
    run_id = run_id or f"RUN_{now:%Y%m%d_%H%M%S}"
    log_file = logs_dir / f"{run_id}.log"

    logger = logging.getLogger("MacroPortfolioEngine")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(sh)

    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_metadata (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            updated_at TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_update_registry (
            dataset VARCHAR,
            series_id VARCHAR,
            first_observation_date DATE,
            last_observation_date DATE,
            last_update_timestamp TIMESTAMP,
            source VARCHAR,
            row_count BIGINT,
            PRIMARY KEY (dataset, series_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_run_registry (
            run_id VARCHAR PRIMARY KEY,
            run_timestamp TIMESTAMP,
            model_version VARCHAR,
            status VARCHAR,
            notes VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS local_pipeline_runs (
            run_id VARCHAR PRIMARY KEY,
            market_session DATE,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            status VARCHAR,
            error_message VARCHAR,
            model_version VARCHAR,
            code_version VARCHAR
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO system_metadata VALUES (?, ?, ?)",
        ["system_version", config["system"]["version"], now],
    )

    def cfg(path, default=None):
        obj = config
        try:
            for key in path:
                obj = obj[key]
            return obj
        except Exception:
            return default

    pd.set_option("display.max_columns", 100)
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.float_format", lambda x: f"{x:,.4f}")

    ns = {
        "__name__": "__macro_portfolio_pipeline__",
        "os": os, "sys": sys, "json": json, "math": math, "time": time,
        "logging": logging, "warnings": warnings,
        "Path": Path, "datetime": datetime, "date": date, "timedelta": timedelta,
        "Dict": Dict, "List": List, "Optional": Optional, "Tuple": Tuple, "Union": Union,
        "np": np, "pd": pd, "pa": pa, "pq": pq, "duckdb": duckdb,
        "yf": yf, "pdr": pdr, "Fred": Fred, "scipy": scipy, "scipy_stats": scipy_stats,
        "sm": sm, "arch_model": arch_model, "GaussianHMM": GaussianHMM,
        "StandardScaler": StandardScaler, "LedoitWolf": LedoitWolf,
        "GaussianMixture": GaussianMixture, "cp": cp,
        "px": px, "go": go, "make_subplots": make_subplots, "display": display,
        "CONFIG": config, "cfg": cfg, "safe_isfinite": safe_isfinite, "safe_bool_series": safe_bool_series, "require_objects": require_objects,
        "PROJECT_ROOT": project_root,
        "DATA_DIR": data_dir, "MODELS_DIR": models_dir, "CONFIG_DIR": config_dir,
        "LOGS_DIR": logs_dir, "OUTPUTS_DIR": outputs_dir,
        "RAW_DATA_DIR": raw_data_dir, "CURATED_DATA_DIR": curated_data_dir,
        "FEATURE_DATA_DIR": feature_data_dir,
        "REGIME_MODEL_DIR": regime_model_dir, "SECTOR_MODEL_DIR": sector_model_dir,
        "STOCK_MODEL_DIR": stock_model_dir, "RISK_MODEL_DIR": risk_model_dir,
        "DASHBOARD_OUTPUT_DIR": dashboard_output_dir, "TRADE_OUTPUT_DIR": trade_output_dir,
        "PORTFOLIO_OUTPUT_DIR": portfolio_output_dir, "BACKTEST_OUTPUT_DIR": backtest_output_dir,
        "DB_PATH": db_path, "conn": conn,
        "RUN_TIMESTAMP": now.strftime("%Y%m%d_%H%M%S"), "RUN_ID": run_id,
        "LOG_FILE": log_file, "logger": logger,
        "FRED_API_CONFIGURED": True,
        "RUNTIME_INITIALIZED_AT": now,
    }
    logger.info("Local runtime initialized: %s", project_root)
    return ns
