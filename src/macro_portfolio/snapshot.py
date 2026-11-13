from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

KEY_OBJECTS = [
    "ECONOMIC_REGIME_PROBABILITIES",
    "LIVE_REGIME_SUMMARY",
    "FINAL_SECTOR_SIGNAL_DASHBOARD",
    "F_FINAL_VALUATION_HANDOFF",
    "G1_FINAL_ALPHA_HANDOFF",
    "G_FINAL_PORTFOLIO_WEIGHTS",
    "G_FINAL_TRADE_PLAN",
    "G_FINAL_PORTFOLIO_SUMMARY",
    "G9_PATH_MC_SUMMARY",
    "H_FINAL_MONITORING_SNAPSHOT",
    "H_FINAL_BUY_WATCHLIST",
    "H_FINAL_ALERTS",
    "I_FINAL_ACTION_BOOK",
    "I_FINAL_TRIGGERS",
    "I_FINAL_REBALANCE_TRIGGERS",
    "I_FINAL_OPERATING_SNAPSHOT",
    "I_FINAL_DAILY_SUMMARY",
    "J_FINAL_RUN_MANIFEST",
    "K2_READINESS",
    "K3_DYNAMIC_STATE_AUDIT",
    "SECTION_L_STATUS",
    "L_BACKTEST_SUMMARY",
    "L_TARGET_WEIGHTS",
    # v1.0.14: valuation detail for per-holding valuation sheets
    "F4_COST_OF_CAPITAL",
    "F4_INDUSTRY_BETA_AUDIT",
    "F5_FINAL_SCENARIO_VALUATIONS",
    "F5_FINAL_FORECAST_CASHFLOWS",
    "F5_SCENARIO_VALUATIONS",
    "F5_FORECAST_CASHFLOWS",
    "F5A_FINAL_COMPANY_VALUATION_SUMMARY",
]


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _write_obj(obj, path_base: Path):
    if isinstance(obj, pd.DataFrame):
        path = path_base.with_suffix(".parquet")
        if not isinstance(obj.index, pd.RangeIndex):
            obj = obj.reset_index()
        obj.to_parquet(path, index=False)
        return path
    if isinstance(obj, pd.Series):
        path = path_base.with_suffix(".parquet")
        obj.rename("value").reset_index().to_parquet(path, index=False)
        return path
    path = path_base.with_suffix(".json")
    path.write_text(json.dumps(obj, indent=2, default=_json_default), encoding="utf-8")
    return path


def archive_outputs(ns: dict, market_session) -> Path:
    root = Path(ns["PROJECT_ROOT"])
    run_id = ns["RUN_ID"]
    run_dir = root / "outputs" / "runs" / str(market_session) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "market_session": str(market_session),
        "created_at": datetime.now().isoformat(),
        "system_version": ns["CONFIG"]["system"]["version"],
        "objects": {},
    }
    for name in KEY_OBJECTS:
        if name not in ns:
            continue
        try:
            path = _write_obj(ns[name], run_dir / name)
            manifest["objects"][name] = path.name
        except Exception as exc:
            manifest["objects"][name] = {"error": str(exc)}

    # Preserve generated production HTML if present.
    dashboard = ns.get("H_FINAL_EXECUTION_DASHBOARD")
    if dashboard and Path(dashboard).exists():
        dst = run_dir / "execution_cockpit.html"
        shutil.copy2(Path(dashboard), dst)
        manifest["execution_cockpit"] = dst.name

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=_json_default), encoding="utf-8"
    )

    return run_dir


def publish_latest(root: Path, run_dir: Path, run_id: str, market_session) -> None:
    """Atomically advance the dashboard pointer only after the run is fully complete."""
    state_dir = Path(root) / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    latest_path = state_dir / "latest_run.json"
    previous_path = state_dir / "previous_run.json"
    if latest_path.exists():
        previous_path.write_text(latest_path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = state_dir / "latest_run.json.tmp"
    tmp.write_text(
        json.dumps({"run_dir": str(run_dir), "run_id": run_id, "market_session": str(market_session)}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(latest_path)


def load_pointer(root: Path, which: str = "latest"):
    p = root / "outputs" / "state" / f"{which}_run.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_object(run_dir: Path, name: str):
    pq = run_dir / f"{name}.parquet"
    js = run_dir / f"{name}.json"
    if pq.exists():
        return pd.read_parquet(pq)
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    return None
