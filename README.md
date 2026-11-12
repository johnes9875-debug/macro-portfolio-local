# MacroPortfolioLocal v1.0.15 — Industry Betas, Valuation Fixes, Risk Panel, Paper Trading

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

## Paper trading (monthly)

The system runs a $1,000,000 paper account (`execution.portfolio_state_mode: PAPER`).
After the first run of each month it proposes orders in `ledger/paper/orders/`; you edit
and approve them (Streamlit **Paper trading** tab or `scripts\paper_approve.bat`), and the
next run fills them at the US open after your approval. See `ledger/paper/README.md`.

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

## v1.0.15 bottom-up industry betas (config: `valuation.industry_beta`)

The discount rate's beta now comes from the company's industry, not its own 2-year regression.
Why: in 2023-2026 technology dominated SPY and every defensive sector's recent beta collapsed
(staples ETF: 0.19 over 3 years vs 0.56 over 10; energy 0.29 vs 0.90; healthcare 0.38 vs 0.72),
which put most defensives on the old beta floor.

1. **Level**: the sector ETF's 10-year weekly beta vs SPY.
2. **Industry tilt**: beta of an equal-weighted portfolio of the GICS sub-industry's universe stocks
   minus that of the sector's, over 3 years, shrunk by n/(n+4) and capped at +/-0.35
   (sector level alone when fewer than 4 peers).
3. **Leverage**: unlevered at the peers' median debt/equity, relevered at the company's own.
   Financial models (banks, insurers) use the levered industry beta.
4. Cost of equity, WACC and discount rate are recomputed with the engine's own identities.

Audit files: `outputs/stocks/f4_industry_beta_audit.csv`, `f4_industry_beta_sector_levels.csv`.
`enabled: false` restores v1.0.14. Before/after: `docs/industry_beta_before_after_v1015.csv`.
Known limit: sub-industries with fewer than 4 universe peers (e.g. gold miners, tobacco) use the
sector level.

## v1.0.14 valuation fixes (config: `valuation.fixes`)

Each fix can be switched off to reproduce v1.0.13.

1. **Working capital on incremental revenue** (`nwc_on_incremental_revenue`). v1.0.13 charged
   (3-year median cash-flow change in working capital / revenue) x forecast revenue every year and
   into the terminal value. One-off items became permanent: KO lost ~$5bn of free cash flow a year;
   CPAY, EL and DLTR got impossible perpetual working-capital releases. Now:
   intensity per $ of revenue change (5-year aggregate, clipped to [-10%, 30%], default 10%) x
   change in revenue. Audit: `outputs/stocks/f5_nwc_intensity_audit.csv`.
2. **Exit multiple keeps part of the company's own premium** (`exit_multiple_own_weight: 0.5`).
   Year-5 multiple = current^0.5 x peer-anchor^0.5. The existing low-quality-anchor guardrail and
   its checks are unchanged (they validate `peer_guardrail_base_exit_multiple`).
3. **Configurable beta floor** (`min_valuation_beta: 0.70`, was a hard-coded 0.50 in F4, F4A, F4B).
   Note: at 0.70 the floor binds for most names; industry (bottom-up) betas are the proper next step.

Also: Section K no longer fails a run when an existing holding becomes valuation-blocked and is held
(not added to). Before/after valuations for all 60 stocks: `docs/valuation_before_after_v1014.csv`.

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
