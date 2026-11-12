import json

import pandas as pd
import pytest

from macro_portfolio import paper


def _bars(path, rows):
    pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"]).to_parquet(path, index=False)


@pytest.fixture()
def root(tmp_path):
    paper._PX_CACHE.clear()
    (tmp_path / "data/raw/stocks/prices").mkdir(parents=True)
    (tmp_path / "data/raw/market").mkdir(parents=True)
    days = ["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04"]
    _bars(tmp_path / "data/raw/market/SPY.parquet", [(d, 700, 701, 699, 700 + i) for i, d in enumerate(days)])
    _bars(tmp_path / "data/raw/stocks/prices/AAA.parquet", [(d, 100, 101, 99, 100) for d in days])
    # BF.B is stored with a dash, like the real cache
    _bars(tmp_path / "data/raw/stocks/prices/BF-B.parquet",
          [("2026-10-30", 50, 50, 50, 50), ("2026-11-02", 52, 53, 47, 51), ("2026-11-03", 51, 51, 50, 50),
           ("2026-11-04", 50, 50, 50, 50)])
    run = tmp_path / "outputs/runs/2026-10-30/R1"
    run.mkdir(parents=True)
    pd.DataFrame({"ticker": ["AAA", "BF.B", "CASH"], "target_weight": [0.5, 0.3, 0.2]}).to_parquet(
        run / "G_FINAL_PORTFOLIO_WEIGHTS.parquet", index=False)
    (run / "manifest.json").write_text(json.dumps({"market_session": "2026-10-30", "run_id": "R1"}))
    return tmp_path


CFG = {"paper": {"enabled": True, "initial_cash": 10000}, "portfolio": {"optimizer_weight_epsilon": 0.005},
       "execution": {"transaction_cost_rate": 0.001}}


def test_full_cycle_respects_edits_limits_cash_and_timezone(root):
    p = paper.propose_orders(root, root / "outputs/runs/2026-10-30/R1", config=CFG)
    od = paper.read_orders(p)
    assert set(od["ticker"]) == {"AAA", "BF.B"}
    assert od.set_index("ticker").loc["AAA", "shares"] == 50          # floor(0.5*10000/100)
    # user edit: limit BF.B at 48 (day-1 low is 47, so it fills at the limit)
    od.loc[od["ticker"] == "BF.B", "limit_price"] = 48
    p.write_text(od.to_csv(index=False))
    # approved 01:00 UTC on 2 Nov = 20:00 New York 1 Nov -> fills at the 2 Nov open
    paper.approve_orders(root, p, approved_at=pd.Timestamp("2026-11-02 01:00", tz="UTC"))
    res = paper.process(root, CFG, upto="2026-11-04")
    assert res["filled"] == 2
    fills = pd.read_csv(root / "ledger/paper/fills.csv").set_index("ticker")
    assert fills.loc["AAA", "session"] == "2026-11-02" and fills.loc["AAA", "price"] == 100
    assert fills.loc["BF.B", "price"] == 48 and fills.loc["BF.B", "how"] == "limit"
    acct = json.loads((root / "ledger/paper/account.json").read_text())
    assert acct["cash"] == pytest.approx(10000 - 50 * 100 * 1.001 - 60 * 48 * 1.001)
    st = pd.read_csv(root / "ledger/paper/optimizer_state.csv").set_index("ticker")["current_weight"]
    assert st.sum() == pytest.approx(1.0)
    assert not paper.rebalance_due(root, "2026-10-31", paper.paper_cfg(CFG))


def test_no_fill_before_approval_and_expiry(root):
    p = paper.propose_orders(root, root / "outputs/runs/2026-10-30/R1", config=CFG)
    od = paper.read_orders(p)
    od.loc[od["ticker"] == "AAA", "limit_price"] = 90                # never reached
    od.loc[od["ticker"] == "BF.B", "action"] = "SKIP"
    p.write_text(od.to_csv(index=False))
    # approved after the 3 Nov open (15:00 UTC = 10:00 NY) -> only 4 Nov is eligible
    a = paper.approve_orders(root, p, approved_at=pd.Timestamp("2026-11-03 15:00", tz="UTC"))
    cfg = {**CFG, "paper": {**CFG["paper"], "order_expiry_sessions": 1}}
    assert paper.process(root, cfg, upto="2026-11-04")["filled"] == 0
    st = pd.read_csv(a).set_index("ticker")["status"]
    assert st["AAA"] == "EXPIRED" and st["BF.B"] == "SKIPPED"


def test_bad_edits_are_rejected(root):
    p = paper.propose_orders(root, root / "outputs/runs/2026-10-30/R1", config=CFG)
    od = paper.read_orders(p)
    od.loc[0, "shares"] = -5
    p.write_text(od.to_csv(index=False))
    with pytest.raises(RuntimeError):
        paper.approve_orders(root, p)
