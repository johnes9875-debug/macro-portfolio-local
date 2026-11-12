# Run ledger

Permanent, git-tracked record of every successful production run. Written
automatically after each run (`local.record_ledger` in `config/settings.yaml`)
and pushed to GitHub when `local.auto_push_ledger: true`.

| File | One row per | Use |
|---|---|---|
| `runs.csv` | run | KPIs, regime, readiness, SPY price |
| `holdings_history.csv` | run × ticker | model target weights and prices (≥ 0.5% positions) |
| `trades_history.csv` | run × trade | proposed buys / sells / trims |
| `track_record.csv` | consecutive run pair | forward (paper) return of the model vs SPY and vs what the model expected |
| `snapshots/<date>_<run>.json` | run | compact payload the cockpit, Streamlit app and Claude dashboard read |
| `actual_holdings.csv` | your position | **edit by hand** (or in the Streamlit "My actual holdings" tab) |

## Track record method

Holdings at run *t* are marked to market at run *t+1* with adjusted closes
from the local price cache; cash earns 0. It is a paper record of the model,
not of your account. It is the honest test for this system: the pipeline is
not point-in-time backtest-ready (`pit_backtest_ready = False`), so a
historical backtest would use statements that did not exist on past dates.

## Commands

```
scripts\backfill_ledger.bat              # record all archived runs, then push
scripts\push_ledger.bat                  # push ledger/ only
python -m macro_portfolio.ledger record <run_dir>
```
