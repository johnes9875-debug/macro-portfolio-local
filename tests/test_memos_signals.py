import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_portfolio import memo as M
from macro_portfolio import signal_eval as S

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# signal tracking
# ---------------------------------------------------------------------------

def test_labels():
    assert S.label(1.2) == "strong buy"
    assert S.label(0.5) == "buy"
    assert S.label(0.0) == "hold"
    assert S.label(-0.5) == "sell"
    assert S.label(-3) == "strong sell"


@pytest.fixture()
def sigroot(tmp_path):
    """60 stocks; a 'good' signal equal to the realised 21-day excess return, a 'bad' one its negative."""
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2026-01-02", "2026-12-31")
    run_day = pd.Timestamp("2026-06-30")
    (tmp_path / "data/raw/market").mkdir(parents=True)
    (tmp_path / "data/raw/stocks/prices").mkdir(parents=True)
    run_dir = tmp_path / "outputs/runs/2026-06-30/R1"
    run_dir.mkdir(parents=True)
    spy = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(dates)))
    pd.DataFrame({"date": dates, "adj_close": spy}).to_parquet(tmp_path / "data/raw/market/SPY.parquet", index=False)
    rows, fut = [], {}
    for i in range(60):
        r = rng.normal(0, 0.015, len(dates))
        drift = rng.normal(0, 0.004)
        r[dates > run_day] += drift
        px = 100 * np.cumprod(1 + r)
        pd.DataFrame({"date": dates, "adj_close": px}).to_parquet(tmp_path / f"data/raw/stocks/prices/S{i}.parquet", index=False)
        fut[f"S{i}"] = drift
        rows.append({"ticker": f"S{i}", "sector_ticker": "XLB", "master_alpha_score": drift, "master_alpha_rank": 0,
                     "sector_signal": 0.0, "company_selection_signal": -drift, "valuation_signal_normalized": rng.normal(),
                     "expected_upside_pct": drift, "mos_threshold_met": True, "entry_eligible_now": True,
                     "valuation_review_severity": "NORMAL", "current_price": float(px[dates <= run_day][-1])})
    g = pd.DataFrame(rows)
    g.to_parquet(run_dir / "G1_FINAL_ALPHA_HANDOFF.parquet", index=False)
    pd.DataFrame({"ticker": g["ticker"], "consensus_upside_pct": 0.0}).to_parquet(run_dir / "F_FINAL_VALUATION_HANDOFF.parquet", index=False)
    top = g.sort_values("master_alpha_score").tail(5)["ticker"]
    pd.DataFrame({"ticker": top, "target_weight": 0.1}).to_parquet(run_dir / "G_FINAL_PORTFOLIO_WEIGHTS.parquet", index=False)
    return tmp_path, run_dir


def test_record_and_evaluate(sigroot):
    root, run_dir = sigroot
    S.record_signals(root, run_dir, "2026-06-30", "R1")
    S.record_signals(root, run_dir, "2026-06-30", "R1")  # idempotent per run_id
    hist = pd.read_csv(root / "ledger/signals_history.csv")
    assert len(hist) == 60
    out = S.evaluate(root)
    sig = {(x["signal"], x["horizon"]): x for x in out["signals"]}
    assert sig[("master_alpha_score", 21)]["mean_ic"] > 0.5
    assert sig[("company_selection_signal", 21)]["mean_ic"] < -0.5
    assert sig[("master_alpha_score", 63)]["runs_scored"] == 1
    buys = {b["horizon"]: b for b in out["model_buys"]}
    assert buys[63]["positions_scored"] == 5
    assert buys[63]["hit_rate"] >= 0.6
    assert -1.5 <= buys[63]["asymmetric_score"] <= 1.0
    assert "anecdotal" in out["note"]
    assert (root / "ledger/signal_quality_summary.json").exists()


def test_outcome_needs_future_and_history(sigroot):
    root, _ = sigroot
    spy = S._px(root, "SPY")
    assert S.outcome(root, "S1", "2026-12-28", 21, spy, {}) is None   # no future yet
    assert S.outcome(root, "S1", "2026-01-15", 21, spy, {}) is None   # not enough history for vol
    o = S.outcome(root, "S1", "2026-06-30", 21, spy, {})
    assert set(o) >= {"z", "label", "excess"}


def test_asymmetric_penalty(sigroot, monkeypatch):
    root, run_dir = sigroot
    S.record_signals(root, run_dir, "2026-06-30", "R1")
    real = S.outcome
    monkeypatch.setattr(S, "outcome", lambda *a, **k: {**real(*a, **k), "z": -2.0, "label": "strong sell"} if real(*a, **k) else None)
    out = S.evaluate(root)
    assert all(b["asymmetric_score"] == -1.5 for b in out["model_buys"])


def test_snapshot_keeps_dated_index(tmp_path):
    from macro_portfolio.snapshot import _write_obj
    df = pd.DataFrame({"XLB": [0.1, 0.2]}, index=pd.DatetimeIndex(["2026-01-31", "2026-02-28"], name="date"))
    p = _write_obj(df, tmp_path / "L_TARGET_WEIGHTS")
    assert "date" in pd.read_parquet(p).columns


# ---------------------------------------------------------------------------
# memos
# ---------------------------------------------------------------------------

def _snap(paper=True, awaiting=True):
    snap = {"market_session": "2026-12-01", "run_id": "R9",
            "holdings": [{"ticker": "AAA", "company_name": "Aaa", "sector_ticker": "XLB", "target_weight": 0.1,
                          "current_price": 10.0, "valuation_review_severity": "REVIEW"}],
            "trades": [{"ticker": "AAA", "side": "BUY", "trade_shares_est": 100, "trade_notional": 1000, "current_price": 10.0,
                        "valuation_review_severity": "REVIEW", "executable": True}],
            "valuation_sheets": {"AAA": {"price": 10.0, "scenarios": {"bear": 9, "base": 14, "bull": 18, "expected": 14},
                                         "consensus_target": 11, "review": "REVIEW", "mos_price": 12, "mos_met": True}},
            "risk": {"risk_contributions": [{"ticker": "AAA", "risk_share": 0.3, "standalone_vol": 0.3}]},
            "sectors": [{"ticker": "XLB", "combined_rank": 2, "combined_signal": "Positive"}], "flags": [], "regime": {}}
    if paper:
        snap["paper"] = {"awaiting_approval": {"file": "2026-12-01_proposed.csv", "orders": [
            {"ticker": "AAA", "side": "BUY", "shares": 100, "est_value": 1000, "flag": "valuation review"}]} if awaiting else None}
    return snap


def _good_memo():
    return {"ticker": "AAA", "side": "BUY", "verdict": "CHALLENGE", "written_at": "2026-12-02T00:00:00+00:00",
            "thesis": [{"text": "cheap", "cites": ["V.expected_upside"]}],
            "red_team": [{"text": "consensus disagrees", "cites": ["C.upside"]},
                         {"text": "risk", "cites": ["R.risk_share"]},
                         {"text": "news", "cites": ["N1"]}],
            "what_would_change": [{"text": "x", "cites": []}],
            "news": [{"id": "N1", "title": "t", "date": "2026-11-30", "url": "https://example.com/a"}]}


def test_orders_for_modes():
    assert [o["ticker"] for o in M.orders_for(_snap())] == ["AAA"]
    assert M.orders_for(_snap(awaiting=False)) == []          # approved: nothing to review
    assert [o["ticker"] for o in M.orders_for(_snap(paper=False))] == ["AAA"]   # no paper account: model trades


def test_evidence_pack_and_validation(tmp_path):
    snap = _snap()
    paths = M.build_evidence_packs(tmp_path, snap)
    pack = json.loads(paths[0].read_text())
    assert pack["flagged"] and pack["session"] == "2026-12-01"
    assert pack["evidence"]["V.expected_upside"]["value"] == pytest.approx(0.4)
    assert pack["evidence"]["C.upside"]["value"] == pytest.approx(0.1)
    m = _good_memo()
    assert M.validate(m, pack) == []

    bad = copy.deepcopy(m); bad["thesis"][0]["cites"] = []
    assert any("cites nothing" in e for e in M.validate(bad, pack))
    bad = copy.deepcopy(m); bad["thesis"][0]["cites"] = ["V.made_up"]
    assert any("unknown evidence" in e for e in M.validate(bad, pack))
    bad = copy.deepcopy(m); bad["news"][0]["date"] = "last week"
    assert any("YYYY-MM-DD" in e for e in M.validate(bad, pack))
    bad = copy.deepcopy(m); bad["news"][0]["date"] = "2027-01-01"
    assert any("after the memo" in e for e in M.validate(bad, pack))
    bad = copy.deepcopy(m); bad["red_team"] = bad["red_team"][:2]
    assert any("at least 3" in e for e in M.validate(bad, pack))
    bad = copy.deepcopy(m); bad["verdict"] = "BUY"
    assert any("verdict" in e for e in M.validate(bad, pack))


def test_pack_frozen_and_loaded(tmp_path):
    snap = _snap()
    p = M.build_evidence_packs(tmp_path, snap)[0]
    snap2 = _snap(); snap2["valuation_sheets"]["AAA"]["price"] = 12.0; snap2["market_session"] = "2026-12-02"
    M.build_evidence_packs(tmp_path, snap2)        # later daily run: same proposal, pack unchanged
    assert json.loads(p.read_text())["evidence"]["P.price"]["value"] == 10.0
    (p.parent / "AAA.json").write_text(json.dumps(_good_memo()))
    loaded = M.load_memos(tmp_path, snap2)
    assert loaded["AAA"]["errors"] == [] and loaded["AAA"]["memo"]["verdict"] == "CHALLENGE"


def test_committed_memos_are_valid():
    d = REPO / "ledger/paper/memos"
    memos = [p for p in d.glob("*/*.json") if not p.name.endswith((".evidence.json", ".rejected.json"))] if d.exists() else []
    if not memos:
        pytest.skip("no committed memos")
    for mp in memos:
        pack = json.loads(mp.with_name(mp.stem + ".evidence.json").read_text())
        assert M.validate(json.loads(mp.read_text()), pack) == [], mp.name


def test_cockpit_renders_memos_and_signal_quality():
    from macro_portfolio.cockpit import render_memos, render_signal_quality
    memos = {"AAA": {"memo": _good_memo(), "errors": [], "evidence": {"C.upside": {"label": "c", "value": 0.1, "unit": "fraction"}}}}
    html = render_memos(memos)
    assert "Challenge" in html and "https://example.com/a" in html
    html = render_signal_quality({"sessions_recorded": 2, "signals": [{"signal": "master_alpha_score", "name": "Master", "horizon": 21,
                                                                      "runs_scored": 1, "mean_ic": 0.1, "mean_quintile_spread_z": 0.2}],
                                  "model_buys": [], "note": "anecdotal"})
    assert "Do the signals work" in html
