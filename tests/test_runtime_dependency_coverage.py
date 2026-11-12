from pathlib import Path
import ast
import builtins
import symtable


def _runtime_keys(runtime_text: str):
    tree = ast.parse(runtime_text)
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _defs_and_global_refs(text: str, filename: str):
    table = symtable.symtable(text, filename, "exec")
    definitions = {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }
    references = set()

    def visit(scope):
        for symbol in scope.get_symbols():
            if symbol.is_referenced() and symbol.is_global():
                references.add(symbol.get_name())
        for child in scope.get_children():
            visit(child)

    visit(table)
    return definitions, references


def test_shared_runtime_covers_all_section_global_dependencies_in_execution_order():
    root = Path(__file__).resolve().parents[1]
    runtime_path = root / "src/macro_portfolio/runtime.py"
    available = set(dir(builtins)) | _runtime_keys(runtime_path.read_text(encoding="utf-8")) | {"__name__"}

    for letter in "bcdefghijkl":
        path = root / "src/macro_portfolio/engine/sections" / f"section_{letter}.py"
        text = path.read_text(encoding="utf-8")
        definitions, references = _defs_and_global_refs(text, str(path))
        missing = references - available - definitions
        assert not missing, f"section {letter.upper()} has unresolved global dependencies: {sorted(missing)}"
        available |= definitions


def test_each_pipeline_run_builds_a_fresh_runtime_namespace():
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / "src/macro_portfolio/pipeline.py").read_text(encoding="utf-8")
    assert "ns = build_runtime(run_id=run_id)" in pipeline
    assert "for letter in SECTION_ORDER" in pipeline
    assert "exec(compile(code" in pipeline
