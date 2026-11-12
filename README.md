# MacroPortfolioLocal v1.0.13 — Valuation Guardrails

## Setup from GitHub

1. `git clone https://github.com/johnes9875-debug/macro-portfolio-local.git`
2. Copy `.env.example` to `.env` and put your FRED key in it. `.env` is git-ignored and never pushed.
3. Run `RUN_ME.ipynb` as below. The first run downloads all market data into `data/` (also git-ignored).

## After every successful run

- `outputs/runs/<date>/<run>/execution_cockpit.html` is a one-page, offline cockpit:
  status, key numbers, trade ticket, what needs attention, macro context, holdings, watchlist, track record.
- `ledger/` records the run (holdings, trades, KPIs, forward track record) and is pushed to GitHub
  automatically (`local.auto_push_ledger` in `config/settings.yaml`). See `ledger/README.md`.
- Record what you actually bought in `ledger/actual_holdings.csv` or in the Streamlit app
  (`scripts\start_dashboard.bat` → "My actual holdings").

## One supported workflow

1. Extract the ZIP into its own folder.
2. Open `RUN_ME.ipynb` in the existing Python 3.11 Jupyter environment.
3. `Kernel -> Restart Kernel and Clear All Outputs`.
4. `Run -> Run All Cells`.

`RUN_ME.ipynb` is only the orchestrator. Production logic lives once under
`src/macro_portfolio/engine/sections/`.

## Dynamic production flow

Every Run All creates a fresh runtime and executes:

`B data refresh -> C macro features -> D regime/sectors -> E stocks -> F valuation -> G portfolio -> H monitoring -> I actions -> J attribution -> K governance -> L diagnostic`.

Live inputs, universe membership, rankings, valuations, portfolio weights and
trades are recalculated on every run. Stable methodology parameters remain in
`config/settings.yaml`.

## Dynamic investable universe

The deduplicated master universe is:

- S&P 500 — core universe
- Nasdaq-100 — growth / innovation overlay
- SOXX — semiconductor specialist overlay

All investable names must be mapped to one of the 11 canonical GICS sectors
before Section E is allowed to continue.

## v1.0.13 valuation / execution corrections

### 1. Cross-currency and ADR-safe intrinsic value

Section F now explicitly separates:

- `financial_currency` — currency of the financial statements / DCF cash flows
- `price_currency` — currency of the traded security
- `financial_to_price_fx` — dynamic FX translation used by valuation
- `valuation_share_units` — units of the actually traded listed security

For cross-currency listings, total equity value is translated to the listed
security's price currency **before** per-share / per-ADR intrinsic value is
computed.

The reverse-DCF / implied-exit-multiple layer uses the same lineage in reverse:
quoted market equity value is translated back into the financial-statement
currency before it is compared with DCF cash flows or terminal values.

`market_cap / current_price` is preferred as the listed-unit reconciliation for
cross-currency securities because both values refer to the quoted listed
security. Explicit depositary-receipt ratios are retained as audit/fallback
metadata.

TSM is explicitly documented as an ADR with 5 ordinary shares per ADR. The
system still fetches FX dynamically; no TSM fair value or FX level is hard-coded.

### 2. Valuation model-risk gate

Section F now classifies valuation anomalies as:

- `NORMAL`
- `REVIEW`
- `CRITICAL_REVIEW`

A critical review is triggered by configurable conditions such as:

- unresolved currency / listed-unit reconciliation
- extreme intrinsic-value / market-price ratio
- extreme model / analyst-consensus divergence

Critical names remain visible for research diagnosis but are **blocked from new
portfolio entries**. Ordinary review flags remain non-blocking.

### 3. Optimizer numerical-residue cleanup

Weights smaller than `portfolio.optimizer_weight_epsilon` are set to zero after
the QP solve. Small non-executable trades are labeled `DEFER_SMALL` rather than
`BUY` / `SELL`.

This prevents outputs such as a near-zero position being displayed as an active
purchase.

## MOS policy

The existing confidence-aware MOS policy is unchanged. MOS remains a necessary
entry condition, but it is now combined with valuation model-risk governance:

`new entry = ranking eligible AND MOS satisfied AND not critical valuation block`.

## FRED credential

This private build includes the user's FRED credential in the local `.env` file
so Jupyter does not prompt on every run. Do not share the ZIP or `.env` file.
The credential is never printed by the notebook or logs.

## Key audit outputs

In addition to the existing research outputs, inspect:

- `f2_currency_reconciliation_audit_v1_0_0.csv`
- `f_final_valuation_handoff.csv`
- `g1_entry_candidates.csv`
- `g_final_portfolio.csv`
- `g_final_trade_plan.csv`

The final valuation handoff now includes currency lineage, listed-unit lineage,
`iv_price_ratio`, consensus divergence, review severity, critical-block status,
and entry eligibility.
