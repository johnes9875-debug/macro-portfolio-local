from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

import yaml

REQUIRED_IMPORTS = [
    "numpy", "pandas", "scipy", "duckdb", "pyarrow", "yaml", "yfinance",
    "statsmodels", "sklearn", "plotly", "streamlit", "pandas_market_calendars",
    "filelock", "requests", "IPython", "arch", "hmmlearn", "pandas_datareader", "fredapi", "dotenv", "cvxpy",
]


def main():
    root = Path(__file__).resolve().parents[2]
    failures = []
    print("=" * 88)
    print("MACRO PORTFOLIO LOCAL — SELF CHECK")
    print("=" * 88)

    for mod in REQUIRED_IMPORTS:
        try:
            importlib.import_module(mod)
            print(f"[PASS] import {mod}")
        except Exception as exc:
            failures.append(f"import {mod}: {exc}")
            print(f"[FAIL] import {mod}: {exc}")

    try:
        from importlib.metadata import version as pkg_version
        for pkg in ["numpy", "pandas", "scipy", "duckdb", "pyarrow", "yfinance", "cvxpy"]:
            print(f"[INFO] {pkg} version {pkg_version(pkg)}")
    except Exception as exc:
        print(f"[INFO] package-version reporting unavailable: {exc}")

    cfg = root / "config" / "settings.yaml"
    try:
        config = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        assert isinstance(config, dict) and "system" in config and "portfolio" in config
        print(f"[PASS] config {cfg}")
    except Exception as exc:
        failures.append(f"config: {exc}")
        print(f"[FAIL] config: {exc}")

    # Runtime numeric-safety regression. This reproduces the F5/F5A failure
    # class where optional/empty pandas branches yield object-dtype numerics.
    try:
        import numpy as np
        import pandas as pd
        from .numeric_safety import safe_isfinite, safe_bool_series
        obj_series = pd.Series(["1.25", 2.5, None, "bad"], dtype=object)
        finite = safe_isfinite(obj_series)
        assert finite.tolist() == [True, True, False, False]
        obj_frame = pd.DataFrame({"x": pd.Series(["1.0", None], dtype=object)})
        assert safe_isfinite(obj_frame)["x"].tolist() == [True, False]
        bools = safe_bool_series(pd.Series([True, "False", "1", None], dtype=object))
        assert bools.tolist() == [True, False, True, False]
        # Exact mixed/empty-branch concat pattern used by F5A.
        operating = pd.DataFrame({
            "ticker": ["TEST"],
            "scenario": ["BASE"],
            "intrinsic_value_per_share": [123.4],
            "ranking_eligible_after_f5": [True],
        })
        financial = pd.DataFrame(columns=list(operating.columns) + ["raw_equity_value"])
        union = list(dict.fromkeys(list(operating.columns) + list(financial.columns)))
        for c in union:
            if c not in operating.columns: operating[c] = np.nan
            if c not in financial.columns: financial[c] = np.nan
        mixed = pd.concat([operating[union], financial[union]], ignore_index=True)
        assert safe_isfinite(mixed["intrinsic_value_per_share"]).all()
        print("[PASS] runtime numeric/dtype safety regression (F5/F5A pattern)")
    except Exception as exc:
        failures.append(f"numeric safety regression: {exc}")
        print(f"[FAIL] runtime numeric/dtype safety regression: {exc}")

    section_dir = root / "src" / "macro_portfolio" / "engine" / "sections"
    for p in sorted(section_dir.glob("section_*.py")):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
            print(f"[PASS] compile {p.name}")
        except Exception as exc:
            failures.append(f"compile {p.name}: {exc}")
            print(f"[FAIL] compile {p.name}: {exc}")

    try:
        raw_np_isfinite = []
        stats_collisions = []
        for p in sorted(section_dir.glob("section_*.py")):
            text = p.read_text(encoding="utf-8")
            if "np.isfinite(" in text:
                raw_np_isfinite.append(p.name)
            if re.search(r"(?m)^\s*stats\s*=", text):
                stats_collisions.append(p.name)
        assert not raw_np_isfinite, f"raw np.isfinite remains in {raw_np_isfinite}"
        assert not stats_collisions, f"top-level stats name collisions remain in {stats_collisions}"
        print("[PASS] static dtype/collision safety scan")
    except Exception as exc:
        failures.append(f"static dtype/collision safety: {exc}")
        print(f"[FAIL] static dtype/collision safety: {exc}")

    # Dynamic-state / F5 integrity scan. Stable model coefficients may be
    # configured constants, but live universe/count gates must remain data-derived.
    try:
        hardcoded_live_count_hits = []
        live_count_pattern = re.compile(
            r"(company_count|provisional_count|ranking_count|eligible_count|ticker_count|sector_count)"
            r"\s*(==|!=)\s*\d+"
        )
        for p in sorted(section_dir.glob("section_*.py")):
            text = p.read_text(encoding="utf-8")
            if live_count_pattern.search(text):
                hardcoded_live_count_hits.append(p.name)
        assert not hardcoded_live_count_hits, (
            f"hard-coded live-state count gates remain in {hardcoded_live_count_hits}"
        )

        section_f = (section_dir / "section_f.py").read_text(encoding="utf-8")
        assert "relative_guardrail_applicable" in section_f
        assert "F4F_RELATIVE_GUARDRAIL_NOT_APPLICABLE" in section_f
        for forbidden in ["range(5)", "expected 5 BASE forecast rows", "expected five forecast years"]:
            assert forbidden not in section_f, f"stale F5/F6 dimension assumption remains: {forbidden}"
        print("[PASS] dynamic-state and F4F/F5 integrity scan")
    except Exception as exc:
        failures.append(f"dynamic/F5 integrity: {exc}")
        print(f"[FAIL] dynamic-state and F4F/F5 integrity scan: {exc}")

    # The Jupyter notebook is intentionally a thin orchestrator. Production
    # section logic must exist only under src/macro_portfolio/engine/sections.
    try:
        notebook_path = root / "RUN_ME.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        joined = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
        )
        assert "macro_portfolio.notebook_runner" in joined
        assert "run_everything" in joined
        assert "CELL C17 — MONETARY POLICY STANCE" not in joined
        assert "CELL F5 — SCENARIO INTRINSIC VALUATION ENGINE" not in joined
        assert "getpass" not in joined
        assert "Enter your FRED API key" not in joined
        print("[PASS] thin-notebook / single-source production architecture")
    except Exception as exc:
        failures.append(f"thin notebook architecture: {exc}")
        print(f"[FAIL] thin-notebook architecture: {exc}")

    # Private local FRED credential must be auto-loadable, without printing it.
    try:
        from dotenv import dotenv_values
        secret_path = root / ".env"
        secret = str(dotenv_values(secret_path).get("FRED_API_KEY", "")).strip()
        assert len(secret) >= 20
        print("[PASS] private FRED credential is configured for automatic local loading")
    except Exception as exc:
        failures.append(f"FRED credential: {exc}")
        print(f"[FAIL] FRED credential configuration: {exc}")

    for d in [root / "data", root / "models", root / "logs", root / "outputs"]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            print(f"[PASS] writable {d.name}/")
        except Exception as exc:
            failures.append(f"writable {d}: {exc}")
            print(f"[FAIL] writable {d}: {exc}")

    try:
        from .market_clock import latest_closed_session
        due = latest_closed_session(minutes_after_close=30, calendar_name="NYSE")
        print(f"[PASS] NYSE calendar available; latest closed session={due}")
    except Exception as exc:
        failures.append(f"NYSE calendar: {exc}")
        print(f"[FAIL] NYSE calendar: {exc}")

    print("=" * 88)
    if failures:
        print(f"SELF CHECK FAILED: {len(failures)} issue(s)")
        for x in failures:
            print(" -", x)
        sys.exit(1)
    print("SELF CHECK PASSED")


if __name__ == "__main__":
    main()
