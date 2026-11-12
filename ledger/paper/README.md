# Paper account

Simulated account that follows the model with monthly rebalancing. You review
and edit every order before anything fills. Started 2026-11-11 with $1,000,000.

## Monthly cycle

1. **Propose (automatic).** After the first successful run of a month, orders appear in
   `orders/<date>_proposed.csv`, sized from the account's actual positions and cash.
   Orders below 0.25% of NAV are pre-set to SKIP; exits are always kept.
2. **Amend (you).** Edit that file, or use the Streamlit **Paper trading** tab:
   change `shares`, set `action` to `SKIP`, add `limit_price`, set `fill_price` to force a
   price, add or delete rows.
3. **Approve (you).** `scripts\paper_approve.bat` or the **Approve orders** button.
   This writes `orders/<date>_approved.csv` with the approval time (UTC) and pushes it to GitHub.
4. **Fill (automatic).** The next pipeline run fills approved orders at the first US open
   (09:30 New York) after your approval: sells first, then buys, whole shares, cost
   `execution.transaction_cost_rate` (10 bps). A limit order fills only if that day's range
   reaches it. Buys are cut to the cash available. Unfilled orders expire after
   `paper.order_expiry_sessions` sessions (5).
5. **Mark (automatic).** Every run values positions at the close and appends `nav.csv` with
   SPY's close. The optimizer then starts from these positions
   (`execution.portfolio_state_mode: PAPER`), so next month's orders reflect what you
   actually approved.

Out-of-cycle changes: `scripts\paper_propose.bat` proposes from the latest run immediately.

## Files

| File | What |
|---|---|
| `account.json` | cash, initial cash, last valuation date |
| `positions.csv` | shares and average cost (cost includes fees) |
| `orders/*_proposed.csv` / `*_approved.csv` | proposed orders and the approved, filled, expired result |
| `fills.csv` | every simulated fill with price, fee and realized P&L |
| `nav.csv` | daily NAV, cash, invested share and SPY close |
| `optimizer_state.csv` | current weights handed to the optimizer |

## Limits of the simulation

- Fills at the open price (or your limit) with a flat 10 bps cost; no market impact modelling.
- Values use unadjusted closes. Dividends are not credited to the account or to SPY, so the
  comparison is price return against price return.
- Idle cash earns `paper.cash_annual_rate` (0 by default).
- Corporate actions such as splits are not handled automatically; adjust `positions.csv` by hand.
