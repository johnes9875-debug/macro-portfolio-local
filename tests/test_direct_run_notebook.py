import json
from pathlib import Path


def _nb():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "RUN_ME.ipynb").read_text(encoding="utf-8"))


def test_notebook_is_thin_orchestrator_using_bundled_src():
    nb = _nb()
    joined = "\n".join("".join(c.get("source", [])) for c in nb["cells"])
    assert "src" in joined
    assert "sys.path.insert" in joined
    assert "macro_portfolio.notebook_runner" in joined
    assert "run_everything" in joined
    # Production section code must not be copied into the notebook anymore.
    assert "CELL C17 — MONETARY POLICY STANCE" not in joined
    assert "CELL F5 — SCENARIO INTRINSIC VALUATION ENGINE" not in joined


def test_notebook_runs_full_system_once():
    nb = _nb()
    joined = "\n".join("".join(c.get("source", [])) for c in nb["cells"])
    assert "RESULT = run_everything(include_diagnostic_l=True)" in joined


def test_requirements_include_fredapi_and_runtime_dependencies():
    root = Path(__file__).resolve().parents[1]
    req = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    for package in ["fredapi", "python-dotenv", "pandas-market-calendars", "filelock"]:
        assert package in req
