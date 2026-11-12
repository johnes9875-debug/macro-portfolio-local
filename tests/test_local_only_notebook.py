import json
from pathlib import Path


def test_notebook_is_local_only_clean_and_single_source():
    root = Path(__file__).resolve().parents[1]
    path = root / "RUN_ME.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(notebook, ensure_ascii=False).lower()

    hosted_runtime_name = "co" + "lab"
    banned = [
        "google." + hosted_runtime_name,
        "drive." + "mount",
        "/content/" + "drive",
        "google " + "drive",
        hosted_runtime_name,
    ]
    for token in banned:
        assert token not in serialized

    code_cells = [c for c in notebook["cells"] if c.get("cell_type") == "code"]
    assert code_cells
    assert all(c.get("execution_count") is None for c in code_cells)
    assert all(not c.get("outputs") for c in code_cells)

    joined = "\n".join("".join(c.get("source", [])) for c in notebook["cells"])
    assert "macro_portfolio.notebook_runner" in joined
    assert "Production logic lives only" in joined


def test_project_text_has_no_cloud_notebook_runtime_dependencies():
    root = Path(__file__).resolve().parents[1]
    hosted_runtime_name = "co" + "lab"
    banned = (
        "google." + hosted_runtime_name,
        "drive." + "mount",
        "/content/" + "drive",
    )
    suffixes = {".py", ".ps1", ".bat", ".md", ".txt", ".yaml", ".toml", ".ipynb"}

    paths = [p for p in [root / "README.md", root / "START_HERE.txt", root / "RUN_ME.ipynb", root / "pyproject.toml"] if p.exists()]
    for scan_root in [root / "src", root / "scripts", root / "config"]:
        paths.extend(p for p in scan_root.rglob("*") if p.is_file())

    for path in paths:
        if path.suffix.lower() not in suffixes and path.name not in {"README.md", "START_HERE.txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for token in banned:
            assert token not in text, f"{token} found in {path.relative_to(root)}"
