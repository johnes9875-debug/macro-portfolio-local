import json
from pathlib import Path


def test_private_env_contains_autoloaded_fred_credential_without_notebook_prompt():
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    if not env_path.exists():
        import pytest
        pytest.skip(".env is private and not committed to git; create it from .env.example")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    fred_line = next((x for x in lines if x.startswith("FRED_API_KEY=")), None)
    assert fred_line is not None
    value = fred_line.split("=", 1)[1].strip()
    assert len(value) >= 20

    nb = json.loads((root / "RUN_ME.ipynb").read_text(encoding="utf-8"))
    joined = "\n".join("".join(c.get("source", [])) for c in nb["cells"])
    assert "getpass" not in joined
    assert "Enter your FRED API key" not in joined
    assert value not in joined


def test_runtime_loads_private_env_and_requires_key():
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "src/macro_portfolio/runtime.py").read_text(encoding="utf-8")
    assert 'load_dotenv(root / ".env", override=True)' in runtime
    assert 'os.getenv("FRED_API_KEY", "").strip()' in runtime
    assert "FRED_API_KEY is missing" in runtime


def test_sections_use_official_fred_api_when_key_present():
    root = Path(__file__).resolve().parents[1]
    b = (root / "src/macro_portfolio/engine/sections/section_b.py").read_text(encoding="utf-8")
    f = (root / "src/macro_portfolio/engine/sections/section_f.py").read_text(encoding="utf-8")
    for text in (b, f):
        assert 'os.getenv("FRED_API_KEY"' in text
        assert "Fred(api_key=fred_api_key)" in text
