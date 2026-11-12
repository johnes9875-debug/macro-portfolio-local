from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from filelock import FileLock

from .runtime import build_runtime, repository_root
from .snapshot import archive_outputs, publish_latest
from .changes import build_daily_changes
from .state import finish_run, start_run
from .notify import send_telegram

SECTION_ORDER = ["b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
CODE_VERSION = "local-1.0.13-valuation-guardrails"


def _section_path(letter: str) -> Path:
    return Path(__file__).resolve().parent / "engine" / "sections" / f"section_{letter}.py"


def execute_section(ns: dict, letter: str) -> None:
    path = _section_path(letter)
    code = path.read_text(encoding="utf-8")
    ns["logger"].info("Starting Section %s", letter.upper())
    exec(compile(code, str(path), "exec"), ns, ns)
    ns["logger"].info("Completed Section %s", letter.upper())


def run_pipeline(market_session, include_diagnostic_l: bool = False):
    root = repository_root()
    lock_path = root / "data" / ".pipeline.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = f"LOCAL_{market_session:%Y%m%d}_{datetime.now():%H%M%S}"

    with FileLock(str(lock_path), timeout=1):
        ns = build_runtime(run_id=run_id)
        conn = ns["conn"]
        config = ns["CONFIG"]
        start_run(
            root, run_id, market_session,
            config["system"]["version"], CODE_VERSION,
        )
        try:
            for letter in SECTION_ORDER:
                execute_section(ns, letter)

            if not bool(ns.get("SYSTEM_PRODUCTION_READY", False)):
                raise RuntimeError("K did not declare SYSTEM_PRODUCTION_READY=True")

            ns["SECTION_L_STATUS"] = "NOT_REQUESTED"
            if include_diagnostic_l:
                try:
                    execute_section(ns, "l")
                    ns["SECTION_L_STATUS"] = "PASSED"
                except Exception as diagnostic_exc:
                    ns["SECTION_L_STATUS"] = "FAILED_NON_BLOCKING"
                    ns["SECTION_L_ERROR"] = str(diagnostic_exc)
                    ns["logger"].warning(
                        "Section L diagnostic failed but production B-K remains valid: %s",
                        diagnostic_exc,
                    )

            run_dir = archive_outputs(ns, market_session)
            build_daily_changes(root, run_dir)
            publish_latest(root, run_dir, run_id, market_session)
            finish_run(root, run_id, "SUCCESS", None)
            try:
                brief_path = run_dir / "daily_brief.md"
                brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
                send_telegram(f"Macro Portfolio {market_session}\nSUCCESS {run_id}\n\n{brief_text[:3200]}")
            except Exception as notify_exc:
                ns["logger"].warning("Optional notification failed: %s", notify_exc)
            ns["logger"].info("Production run SUCCESS: %s", run_id)
            return {"run_id": run_id, "run_dir": str(run_dir), "namespace": ns}
        except Exception as exc:
            err = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            try:
                finish_run(root, run_id, "FAILED", err[-12000:])
            finally:
                ns["logger"].exception("Production run FAILED")
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass


def run_latest_pipeline(include_diagnostic_l: bool | None = None):
    """Run a fresh production cycle using the latest fully closed NYSE session.

    Every invocation creates a new runtime namespace, refreshes upstream data in
    Section B, and recomputes all downstream state. No prior in-memory notebook
    variables are reused.
    """
    from .market_clock import latest_closed_session
    from .runtime import load_config

    root = repository_root()
    config = load_config(root)
    local_cfg = config.get("local", {})
    due = latest_closed_session(
        minutes_after_close=int(local_cfg.get("minutes_after_close", 30)),
        calendar_name=str(local_cfg.get("market_calendar", "NYSE")),
    )
    if due is None:
        raise RuntimeError("No fully closed NYSE session is available yet.")

    if include_diagnostic_l is None:
        include_diagnostic_l = bool(local_cfg.get("run_section_l", True))

    return run_pipeline(
        due["session_date"],
        include_diagnostic_l=bool(include_diagnostic_l),
    )
