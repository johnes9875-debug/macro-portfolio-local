from __future__ import annotations

import argparse
from pathlib import Path
import yaml

from .market_clock import latest_closed_session
from .state import session_already_succeeded


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_local_config(root: Path) -> dict:
    with (root / "config" / "settings.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run_if_due(force: bool = False, include_diagnostic_l: bool = False):
    root = repository_root()
    config = load_local_config(root)
    local = config.get("local", {})
    due = latest_closed_session(
        minutes_after_close=int(local.get("minutes_after_close", 30)),
        calendar_name=str(local.get("market_calendar", "NYSE")),
    )
    if not due:
        print("No closed NYSE session is currently due.")
        return None

    session = due["session_date"]
    if not force and session_already_succeeded(root, session):
        print(f"Session {session} already completed successfully. Nothing to do.")
        return None

    # Heavy research libraries are imported only when a run is genuinely due.
    from .pipeline import run_pipeline

    print(f"Running production close for NYSE session {session}...")
    result = run_pipeline(session, include_diagnostic_l=include_diagnostic_l)
    print(f"SUCCESS: {result['run_id']}")
    print(f"Snapshot: {result['run_dir']}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Local Macro Portfolio daily-close scheduler")
    parser.add_argument("--force", action="store_true", help="Rerun the latest closed session even if already successful")
    parser.add_argument("--with-section-l", action="store_true", help="Also run the non-blocking Section L diagnostic")
    args = parser.parse_args()
    run_if_due(force=args.force, include_diagnostic_l=args.with_section_l)


if __name__ == "__main__":
    main()
