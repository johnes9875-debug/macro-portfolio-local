import pandas as pd

from macro_portfolio.cockpit import render_cockpit
from macro_portfolio.ledger import _not_traded


def _snap():
    return {
        "run_id": "R2", "market_session": "2026-11-11",
        "state": {"portfolio_state_mode": "MODEL", "portfolio_state_is_actual": False, "real_money_execution_ready": False},
        "kpis": {"invested": 0.47, "cash": 0.53, "positions": 1, "expected_return": 0.087, "expected_volatility": 0.079,
                 "expected_sharpe": 0.49, "prob_loss_1y": 0.146, "var_99_1y": 0.098, "turnover": 0.63,
                 "transaction_cost": 634.0, "trades": 1},
        "regime": {"label": "Mixed", "top_candidate": "Reflation", "top_probability": 0.33, "growth": "Neutral",
                   "inflation": "Inflationary", "financial_conditions": "Restrictive",
                   "probabilities": [{"regime": "Reflation", "probability": 0.33}]},
        "sectors": [{"ticker": "XLV", "sector": "Healthcare", "combined_rank": 1, "combined_signal": "Strong positive",
                     "macro_market_alignment": "Positive confirmation", "hard_conflict": False, "relative_3m": 0.147,
                     "model_weight": 0.03}],
        "holdings": [{"ticker": "MO", "sector_ticker": "XLP", "target_weight": 0.1, "expected_total_return_annual": 0.12,
                      "risk_contribution_share": 0.12, "valuation_review_severity": "REVIEW"}],
        "trades": [{"ticker": "MO", "company_name": "Altria", "side": "BUY", "previous_weight": 0.0, "target_weight": 0.1,
                    "trade_notional": 100000.0, "trade_shares_est": 1292.0, "current_price": 77.39,
                    "below_buy_price_pct": 0.21, "valuation_review_severity": "REVIEW"}],
        "not_traded": [{"ticker": "BF.B", "target_weight": 0.0, "reason": "optimizer residue"}],
        "flags": [], "blocked": [], "watchlist": [], "prices": {"MO": 77.39}, "benchmark": {"ticker": "SPY", "price": 760.0},
    }


def test_cockpit_is_self_contained_and_shows_trade_and_model_banner():
    html = render_cockpit(_snap())
    assert "cdn." not in html and "<script src" not in html
    assert "Model portfolio, not your actual holdings" in html
    assert "MO" in html and "Valuation review" in html
    assert "+14.7%" in html  # relative_3m stored as a fraction


def test_not_traded_dedupes_and_labels_residue():
    nt = pd.DataFrame([{"ticker": "BF.B", "target_weight": 3.8e-8}, {"ticker": "DLTR", "target_weight": 0.0042}])
    res = pd.DataFrame([{"ticker": "BF.B", "target_weight": 3.8e-8}])
    out = _not_traded(nt, res, 0.005)
    assert list(out["ticker"]).count("BF.B") == 1
    assert out.set_index("ticker").loc["BF.B", "reason"] == "optimizer residue"
