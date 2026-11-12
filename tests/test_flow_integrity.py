import re
from pathlib import Path


def _cell(section_text: str, cell_no: int) -> str:
    pattern = re.compile(r"^# ===== ORIGINAL NOTEBOOK CELL (\d+) =====\n", re.MULTILINE)
    matches = list(pattern.finditer(section_text))
    for i, match in enumerate(matches):
        if int(match.group(1)) == cell_no:
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
            return section_text[start:end]
    raise AssertionError(f"cell {cell_no} not found")


def test_runtime_injects_shared_helpers_once():
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "src/macro_portfolio/runtime.py").read_text(encoding="utf-8")
    assert "from .numeric_safety import safe_isfinite, safe_bool_series" in runtime
    assert '"safe_isfinite": safe_isfinite' in runtime
    assert '"safe_bool_series": safe_bool_series' in runtime
    assert '"require_objects": require_objects' in runtime


def test_c24_has_explicit_upstream_dependency_gate():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/macro_portfolio/engine/sections/section_c.py").read_text(encoding="utf-8")
    c24 = _cell(text, 39)
    assert "require_objects(" in c24
    for name in ["PM_MACRO_STATE", "MACRO_CONFIDENCE", "INFLATION_IMPULSE_LABEL", "HISTORICAL_RATE_TIGHTNESS"]:
        assert name in c24


def test_f5_has_explicit_upstream_dependency_gate():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/macro_portfolio/engine/sections/section_f.py").read_text(encoding="utf-8")
    f5 = _cell(text, 72)
    assert "require_objects(" in f5
    for name in ["F4F_PASSED", "F4C_MANIFEST", "F3_FORECAST_ASSUMPTIONS", "F4_FINAL_EXIT_MULTIPLE_ANCHORS"]:
        assert name in f5


def test_section_c_order_guarantees_c21_before_c24():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/macro_portfolio/engine/sections/section_c.py").read_text(encoding="utf-8")
    assert text.index("ORIGINAL NOTEBOOK CELL 36") < text.index("ORIGINAL NOTEBOOK CELL 39")
