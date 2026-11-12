from pathlib import Path
import pandas as pd

from macro_portfolio.universe import load_live_or_cache, _load_bundled_soxx_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_bundled_soxx_snapshot_has_20_plus_names():
    path = ROOT / "data" / "reference" / "constituents" / "soxx_last_known_good.csv"
    out = _load_bundled_soxx_snapshot(path)
    assert len(out) >= 20
    assert set(out["membership_source_detail"]) == {"BUNDLED_SOXX_LAST_KNOWN_GOOD"}


def test_live_failure_without_cache_falls_back_to_bundled(tmp_path):
    bundled = ROOT / "data" / "reference" / "constituents" / "soxx_last_known_good.csv"
    def broken():
        raise RuntimeError("vendor markup changed")
    out, mode, detail = load_live_or_cache(
        "soxx",
        pd.Timestamp("2026-10-01"),
        tmp_path / "raw",
        tmp_path / "curated",
        broken,
        bundled_fallback=bundled,
        bundled_loader=_load_bundled_soxx_snapshot,
    )
    assert mode == "FALLBACK_BUNDLED_SNAPSHOT"
    assert len(out) >= 20
    assert "vendor markup changed" in detail
    assert (tmp_path / "curated" / "soxx_latest.parquet").exists() or (tmp_path / "curated" / "soxx_latest.csv").exists()


def test_sox_is_not_used_as_soxx_membership_proxy():
    text = (ROOT / "src" / "macro_portfolio" / "universe.py").read_text(encoding="utf-8")
    assert "NasdaqSOXProxy" not in text
    assert "NASDAQ_SOX_INDEX_PROXY" not in text
    assert "stockanalysis.com/etf/soxx/holdings/" in text
