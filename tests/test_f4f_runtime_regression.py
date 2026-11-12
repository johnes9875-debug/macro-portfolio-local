import re
from pathlib import Path

import pandas as pd
import yaml


def _cell_source(section_text: str, cell_no: int) -> str:
    pattern = re.compile(r"^# ===== ORIGINAL NOTEBOOK CELL (\d+) =====\n", re.MULTILINE)
    matches = list(pattern.finditer(section_text))
    for i, match in enumerate(matches):
        if int(match.group(1)) == cell_no:
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
            return section_text[start:end]
    raise AssertionError(f"cell {cell_no} not found")


def test_f4f_extreme_current_multiple_does_not_create_impossible_gate(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    section_text = (
        root / "src" / "macro_portfolio" / "engine" / "sections" / "section_f.py"
    ).read_text(encoding="utf-8")
    f4f = _cell_source(section_text, 71)

    config = yaml.safe_load((root / "config" / "settings.yaml").read_text(encoding="utf-8"))
    # This regression test checks the v1.0.13 low-quality guardrail mechanics, so the
    # v1.0.14 own-multiple blend (a separate, later step) is switched off here.
    config.setdefault("valuation", {}).setdefault("fixes", {})["exit_multiple_own_weight"] = 0.0

    def cfg(keys, default=None):
        current = config
        try:
            for key in keys:
                current = current[key]
            return current
        except Exception:
            return default

    anchors = pd.DataFrame([
        {
            "ticker": "FOXA_TEST",
            "company_name": "Normal low-quality",
            "gics_sub_industry": "Media",
            "terminal_multiple_metric": "EV_EBITDA",
            "current_trading_multiple": 4.3,
            "peer_anchor_source": "BROAD_SIMILARITY",
            "peer_count": 5,
            "peer_tickers": "A|B|C|D|E",
            "bear_exit_multiple": 19.8,
            "base_exit_multiple": 22.0,
            "bull_exit_multiple": 24.2,
            "terminal_anchor_confidence": 0.60,
            "ranking_eligible_after_f5": True,
            "specialist_completion_status": "COMPLETE",
        },
        {
            "ticker": "EXTREME_TEST",
            "company_name": "Extreme current multiple",
            "gics_sub_industry": "Test",
            "terminal_multiple_metric": "PRICE_EARNINGS",
            "current_trading_multiple": 100.0,
            "peer_anchor_source": "BROAD_SIMILARITY",
            "peer_count": 5,
            "peer_tickers": "F|G|H|I|J",
            "bear_exit_multiple": 36.0,
            "base_exit_multiple": 40.0,
            "bull_exit_multiple": 40.0,
            "terminal_anchor_confidence": 0.60,
            "ranking_eligible_after_f5": True,
            "specialist_completion_status": "COMPLETE",
        },
    ])
    manifest = anchors[["ticker", "ranking_eligible_after_f5"]].copy()

    # Keep the regression in-memory; F4F's artifact writes are not under test here.
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, *a, **k: None)
    monkeypatch.setattr(pd.DataFrame, "to_csv", lambda self, *a, **k: None)

    ns = {
        "F4E_PASSED": True,
        "VALUATION_PRE_F5_PASSED": True,
        "F4E_EXIT_MULTIPLE_ANCHORS": anchors,
        "F4C_MANIFEST": manifest,
        "VALUATION_UNIVERSE_FREEZE_ID": "TEST",
        "VALUATION_UNIVERSE_SHA256": "0" * 64,
        "STOCK_MODEL_DIR": tmp_path,
        "STOCK_OUTPUT_DIR": tmp_path,
        "F4C_PASSED": True,
        "VALUATION_F4D_NARROW_STAGE_PASSED": True,
        "cfg": cfg,
        "display": lambda *args, **kwargs: None,
    }

    exec(compile(f4f, "F4F_CELL", "exec"), ns, ns)

    assert ns["F4F_PASSED"] is True
    out = ns["F4F_ANCHORS"].set_index("ticker")
    assert bool(out.loc["FOXA_TEST", "relative_guardrail_applicable"]) is True
    assert bool(out.loc["FOXA_TEST", "guardrail_applied"]) is True
    assert abs(float(out.loc["FOXA_TEST", "final_anchor_to_current_ratio"]) - 2.0) < 1e-10

    assert bool(out.loc["EXTREME_TEST", "relative_guardrail_applicable"]) is False
    assert bool(out.loc["EXTREME_TEST", "guardrail_applied"]) is False
    assert "EXTREME_TEST" in ns["F4F_RELATIVE_GUARDRAIL_NOT_APPLICABLE"]["ticker"].tolist()
