import re
from pathlib import Path


def _section_f_text():
    root = Path(__file__).resolve().parents[1]
    return (root / "src" / "macro_portfolio" / "engine" / "sections" / "section_f.py").read_text(encoding="utf-8")


def _cell_source(text: str, cell_no: int) -> str:
    pattern = re.compile(r"^# ===== ORIGINAL NOTEBOOK CELL (\d+) =====\n", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, match in enumerate(matches):
        if int(match.group(1)) != cell_no:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        return text[start:end]
    raise AssertionError(f"cell {cell_no} not found")


def test_f4f_extreme_multiple_guardrail_regression():
    text = _section_f_text()
    f4f = _cell_source(text, 71)
    assert "relative_guardrail_applicable" in f4f
    assert "F4F_RELATIVE_GUARDRAIL_NOT_APPLICABLE" in f4f
    assert '& F4F_ANCHORS["relative_guardrail_applicable"]' in f4f


def test_f5_dimension_counts_follow_frozen_lineage():
    text = _section_f_text()
    f5 = _cell_source(text, 72)
    assert "F5_EXPECTED_SCENARIO_COUNT = len(expected_scenarios)" in f5
    assert "F5_EXPECTED_YEAR_COUNT = len(expected_years)" in f5
    assert "F5_EXPECTED_ROWS_PER_COMPANY" in f5
    assert "F5_COMPANY_COUNT\n    * F5_EXPECTED_SCENARIO_COUNT\n    * F5_EXPECTED_YEAR_COUNT" in f5
    assert "F5_COMPANY_COUNT\n    * F5_EXPECTED_SCENARIO_COUNT" in f5
    assert "!=\n        15" not in f5


def test_f5a_dimension_counts_follow_frozen_lineage():
    text = _section_f_text()
    f5a = _cell_source(text, 73)
    assert "F5A_FORECAST_YEAR_COUNT = len(F5A_FORECAST_YEARS)" in f5a
    assert "F5A_SCENARIO_COUNT = len(F5A_SCENARIO_ORDER)" in f5a
    assert "range(F5A_FORECAST_YEAR_COUNT)" in f5a
    assert "range(5)" not in f5a
    assert "* F5A_SCENARIO_COUNT" in f5a
    assert "* F5A_FORECAST_YEAR_COUNT" in f5a
