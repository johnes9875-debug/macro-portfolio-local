# Claude dashboard artifact

Source of the hosted "Macro Portfolio Cockpit" page on claude.ai.

- Reads runs from its own store (one document per run, the same JSON as `ledger/snapshots/*.json`).
- **Load new run**: pick one or more `ledger/snapshots/*.json` files after a run to add them.
- **Model / My actual** toggle: model target portfolio vs the positions you record on the page.
- **My actual positions**: add, remove, import `ledger/actual_holdings.csv`, or copy back out as CSV.
- Track record is recomputed in the page with the same method as `ledger/track_record.csv`.

Only the page owner can add runs or change positions.
