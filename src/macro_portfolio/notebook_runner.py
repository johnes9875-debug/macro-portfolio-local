from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import run_latest_pipeline
from .runtime import repository_root


def validate_notebook_environment() -> Path:
    """Validate the local Jupyter runtime without creating model state."""
    if not ((3, 11) <= sys.version_info[:2] < (3, 13)):
        raise RuntimeError(
            "MacroPortfolioLocal requires Python 3.11 or 3.12. "
            f"Current interpreter: {sys.version.split()[0]}."
        )

    root = repository_root()
    required = [
        root / "config" / "settings.yaml",
        root / "src" / "macro_portfolio" / "engine" / "sections",
        root / "data",
        root / "models",
        root / "logs",
        root / "outputs",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Incomplete local package. Missing: " + ", ".join(missing))

    load_dotenv(root / ".env", override=True)
    if not os.getenv("FRED_API_KEY", "").strip():
        raise RuntimeError(
            "FRED_API_KEY is not configured. The supplied local package should contain "
            "a private .env file; do not share that file publicly."
        )
    return root


def run_everything(include_diagnostic_l: bool | None = None):
    """Run the entire dynamic production flow from a fresh runtime.

    Flow: fresh runtime -> B data refresh -> C features -> D regime/sector ->
    E stock selection -> F valuation -> G portfolio -> H monitoring -> I daily
    actions -> J attribution -> K governance -> optional non-blocking L diagnostic.
    """
    validate_notebook_environment()
    return run_latest_pipeline(include_diagnostic_l=include_diagnostic_l)
