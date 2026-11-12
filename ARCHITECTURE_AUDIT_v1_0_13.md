# Architecture Audit — v1.0.13 Valuation Guardrails

## Production principle

`RUN_ME.ipynb` remains a thin orchestrator. Production code lives once under `src/macro_portfolio/engine/sections/`.

## Valuation currency/unit lineage

The canonical valuation chain is now:

`financial statements -> financial-currency enterprise/equity value -> as-of FX translation -> listed-security units -> intrinsic value per traded share/ADR`.

The reverse valuation chain uses the exact inverse reconciliation:

`quoted price x listed units -> price-currency market equity value -> inverse FX -> financial-currency market equity value -> implied growth / implied exit multiple`.

Forward and reverse valuation therefore no longer mix USD security prices with TWD/EUR/etc. financial-statement values.

## Entry governance

Research ranking and entry eligibility are deliberately separate:

`research ranking -> MOS -> valuation model-risk gate -> optimizer eligibility`.

A critical model-risk anomaly does not disappear from research output. It remains visible but cannot create a new holding.

## Portfolio execution

Post-solver weights are cleaned for numerical residue before cash is computed. The cleaned weights, not raw QP noise, feed the final portfolio and trade plan.

## Unchanged policy

v1.0.13 does **not** change:

- base MOS policy or confidence adjustment;
- macro regime model;
- sector-ranking methodology;
- stock-selection weights;
- DCF Bear/Base/Bull probabilities;
- stock/sector concentration limits;
- risk-aversion policy.

This release repairs model/data lineage and governance rather than changing the investment thesis.
