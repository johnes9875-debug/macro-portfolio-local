from pathlib import Path


def test_notebook_does_not_duplicate_production_sections():
    root = Path(__file__).resolve().parents[1]
    notebook = (root / "RUN_ME.ipynb").read_text(encoding="utf-8")
    for marker in [
        "CELL C17 — MONETARY POLICY STANCE",
        "CELL C24 — FINAL PM MACRO DASHBOARD V2",
        "CELL F5 — SCENARIO INTRINSIC VALUATION ENGINE",
        "CELL G1 — REGIME",
    ]:
        assert marker not in notebook


def test_pipeline_is_single_source_and_strictly_ordered():
    root = Path(__file__).resolve().parents[1]
    p = (root / "src/macro_portfolio/pipeline.py").read_text(encoding="utf-8")
    assert 'SECTION_ORDER = ["b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]' in p
    assert "for letter in SECTION_ORDER" in p
    assert "execute_section(ns, letter)" in p
    assert "run_latest_pipeline" in p
