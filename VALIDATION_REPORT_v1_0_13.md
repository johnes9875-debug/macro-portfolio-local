# Validation Report — MacroPortfolioLocal v1.0.13

## Scope

This release corrects the valuation/execution issues exposed by the successful v1.0.12 live run:

1. Cross-currency / ADR per-listed-unit valuation (especially TSM-like listings).
2. Critical valuation anomaly governance before new portfolio entry.
3. Numerical optimizer residue / tiny-trade cleanup.
4. Forward and reverse valuation unit-lineage consistency.

## Validation results

- Pytest: **45 passed, 1 skipped**.
- Skip reason: build environment lacks `pandas_market_calendars`; it remains listed in `requirements.txt` and the Jupyter runner installs missing dependencies.
- Python source compile: **PASS**.
- `RUN_ME.ipynb` code-cell compile: **PASS**.
- No stale v1.0.12 identifiers in the v1.0.13 package: **PASS**.

## Cross-currency / ADR controls

- Financial-statement currency and traded-security price currency are separated.
- FX translation is dynamic and as-of `MARKET_AS_OF_DATE`; future FX observations are excluded.
- Cross-currency listings prefer `market_cap / current_price` for listed-security unit reconciliation.
- Explicit ADR/GDR ratios are retained as audit/fallback metadata.
- TSM override documents `1 ADR = 5 ordinary shares`, TWD financial currency, USD price currency.
- Missing live currency metadata may be filled by a security-specific override; conflicting live metadata is **not** silently overwritten.
- Forward FCFF/residual-income valuation translates total equity value to price currency before computing per-listed-unit intrinsic value.
- Reverse DCF / market-implied-exit-multiple logic converts quoted market equity value back to financial-statement currency before comparison with forecast cash flows.

## Model-risk gate

`F_FINAL_VALUATION_HANDOFF` now includes:

- `iv_price_ratio`
- `consensus_divergence_abs`
- `valuation_review_severity`
- `valuation_anomaly_reason`
- `valuation_critical_block`
- `valuation_entry_eligible`

Default policy:

- IV/Price outside 0.20x–3.00x -> critical review.
- Model/consensus divergence above 40% -> review.
- Model/consensus divergence above 75% -> critical review.
- Currency/listed-unit reconciliation failure -> critical review.
- `CRITICAL_REVIEW` remains visible for research but cannot open a new position when `block_critical_new_entries: true`.
- Ordinary `REVIEW` remains non-blocking.

Section G now explicitly validates that no critical valuation anomaly is entry-eligible.

## Execution residue control

- `portfolio.optimizer_weight_epsilon` defaults to `1e-8`.
- Optimizer target weights below the epsilon are set to zero.
- Non-executable small deltas are labeled `DEFER_SMALL`, not `BUY`/`SELL`.
- This prevents numerical residues such as an approximately zero BKR weight from appearing as a real trade.

## Synthetic regression checks

- A TSM-like old output of ~NT$10,491 per ADR-equivalent unit translated at ~NT$31.6/USD produces roughly US$332, not US$10,491.
- The pre-fix TSM-like 23x IV/Price output is classified `CRITICAL_REVIEW`.
- A normal RMD-like valuation is not classified critical.
- Currency-reconciliation failure blocks new entry.
- A 5.7e-9 optimizer residue is zeroed.

## Live-run limitation of this build validation

The build container does not execute the full live market-data pipeline. Therefore the package is unit/static validated, but the user should confirm the corrected live TSM row after `Restart Kernel + Clear Outputs -> Run All`.

Expected live audit fields for a cross-currency ADR include:

- `price_currency`
- `valuation_financial_currency`
- `financial_to_price_fx`
- `valuation_share_units`
- `valuation_share_unit_source`
- `currency_unit_reconciliation_ready`

The notebook now surfaces `F2_CURRENCY_RECONCILIATION_AUDIT` and a `CRITICAL_VALUATION_REVIEW_QUEUE` after a successful run.
