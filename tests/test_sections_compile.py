from pathlib import Path


def test_all_engine_sections_compile():
    root = Path(__file__).resolve().parents[1]
    section_dir = root / "src" / "macro_portfolio" / "engine" / "sections"
    files = sorted(section_dir.glob("section_*.py"))
    assert files
    for p in files:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
