"""One-page, offline execution cockpit.

Replaces the 8-panel Plotly figure with a single readable page ordered by what
you need to decide: status -> key numbers -> trade ticket -> what needs your
attention -> context -> holdings -> watchlist -> track record.

Self-contained HTML (inline CSS + SVG, no CDN), so it opens offline.
Input is the ledger snapshot dict (see ledger.build_snapshot).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

CSS = """
:root{--bg:#fff;--card:#f6f6f4;--ink:#1d1d1b;--mut:#6b6a65;--line:#e4e2dc;
--good:#2f6b12;--goodbg:#eaf3de;--bad:#a32d2d;--badbg:#fcebeb;--warn:#7a4a06;--warnbg:#faeeda;--acc:#185fa5;--accbg:#e6f1fb}
@media (prefers-color-scheme:dark){:root{--bg:#1b1b1a;--card:#262624;--ink:#ecebe6;--mut:#a3a19a;--line:#3a3936;
--good:#97c459;--goodbg:#27360f;--bad:#f09595;--badbg:#4a1b1b;--warn:#fac775;--warnbg:#412402;--acc:#85b7eb;--accbg:#0c2c4f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
h1{font-size:20px;font-weight:600;margin:0}h2{font-size:15px;font-weight:600;margin:28px 0 10px}
.sub{color:var(--mut);font-size:13px}
.banner{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 14px;border-radius:8px;margin:14px 0;font-size:13px}
.warn{background:var(--warnbg);color:var(--warn)}.ok{background:var(--goodbg);color:var(--good)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.k{background:var(--card);border-radius:8px;padding:12px 14px}.k .l{font-size:12px;color:var(--mut)}.k .v{font-size:24px;font-weight:600}.k .s{font-size:12px;color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:13px}th{font-weight:500;color:var(--mut);text-align:left;padding:7px 6px;border-bottom:1px solid var(--line)}
td{padding:7px 6px;border-bottom:1px solid var(--line)}td.r,th.r{text-align:right}tr:hover td{background:var(--card)}
.pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:6px}
.p-buy{background:var(--goodbg);color:var(--good)}.p-sell{background:var(--badbg);color:var(--bad)}.p-rev{background:var(--warnbg);color:var(--warn)}.p-n{background:var(--accbg);color:var(--acc)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}
.list div{padding:6px 0;border-bottom:1px solid var(--line);font-size:13px}
.bar{height:8px;border-radius:4px;background:var(--acc)}.bart{background:var(--line);border-radius:4px;width:100%}
.mut{color:var(--mut)}.pos{color:var(--good)}.neg{color:var(--bad)}
details summary{cursor:pointer;color:var(--mut);font-size:13px;margin-top:6px}
"""


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _pct(x, d=1, sign=False) -> str:
    if x is None:
        return "—"
    try:
        v = float(x) * 100
    except (TypeError, ValueError):
        return "—"
    return f"{v:+.{d}f}%" if sign else f"{v:.{d}f}%"


def _money(x) -> str:
    if x is None:
        return "—"
    v = float(x)
    return f"−${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


def _cls(x) -> str:
    try:
        return "pos" if float(x) > 0 else ("neg" if float(x) < 0 else "")
    except (TypeError, ValueError):
        return ""


SIDE_PILL = {"BUY": "p-buy", "ADD": "p-buy", "SELL": "p-sell", "TRIM": "p-sell"}
SIDE_LABEL = {"BUY": "Buy", "ADD": "Add", "SELL": "Sell", "TRIM": "Trim"}


def _sparkline(values: list[float], w=320, h=70) -> str:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals + [0]), max(vals + [0])
    rng = (hi - lo) or 1e-9
    pts = []
    for i, v in enumerate(values):
        x = 4 + i * (w - 8) / (len(values) - 1)
        y = h - 4 - (v - lo) / rng * (h - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    zero = h - 4 - (0 - lo) / rng * (h - 8)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="cumulative return">'
            f'<line x1="0" x2="{w}" y1="{zero:.1f}" y2="{zero:.1f}" stroke="currentColor" stroke-opacity=".2"/>'
            f'<polyline fill="none" stroke="var(--acc)" stroke-width="2" points="{" ".join(pts)}"/></svg>')


def render_cockpit(snap: dict, track: pd.DataFrame | None = None, runs: pd.DataFrame | None = None) -> str:
    s, k, r = snap["state"], snap["kpis"], snap["regime"]
    model = str(s.get("portfolio_state_mode", "")).upper() == "MODEL" or not s.get("portfolio_state_is_actual")
    real = bool(s.get("real_money_execution_ready"))
    prev = None
    if runs is not None and not runs.empty:
        earlier = runs[runs["market_session"] < snap["market_session"]]
        if not earlier.empty:
            prev = earlier.iloc[-1]

    out = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Cockpit {snap['market_session']}</title><style>{CSS}</style></head><body><div class='wrap'>"]
    out.append(f"<h1>Portfolio cockpit</h1><div class='sub'>Market data as of {snap['market_session']} · run {_e(snap['run_id'])}"
               + (f" · compared with {prev['market_session']}" if prev is not None else "") + "</div>")

    if model or not real:
        out.append("<div class='banner warn'><span>Model portfolio, not your actual holdings."
                   + (" Real-money execution is not marked ready." if not real else "")
                   + "</span><span>Record real positions in ledger/actual_holdings.csv</span></div>")
    else:
        out.append("<div class='banner ok'><span>Actual portfolio state. Execution ready.</span></div>")

    def was(field, fmt=_pct):
        if prev is None or field not in prev or pd.isna(prev[field]):
            return ""
        return f"was {fmt(prev[field])}"

    out.append("<div class='kpis'>")
    for label, val, sub in [
        ("Invested", _pct(k["invested"]), was("invested")),
        ("Expected return (1y)", _pct(k["expected_return"]), f"vol {_pct(k['expected_volatility'])} · Sharpe {k['expected_sharpe']:.2f}" if k.get("expected_sharpe") is not None else ""),
        ("Chance of a loss (1y)", _pct(k["prob_loss_1y"]), f"1-in-100 loss {_pct(-abs(k['var_99_1y'] or 0))}" if k.get("var_99_1y") is not None else ""),
        ("Trades today", str(k["trades"]), f"turnover {_pct(k['turnover'], 0)} · cost {_money(k['transaction_cost'])}"),
    ]:
        out.append(f"<div class='k'><div class='l'>{label}</div><div class='v'>{val}</div><div class='s'>{_e(sub)}</div></div>")
    out.append("</div>")

    # ---- trade ticket
    out.append("<h2>Trade ticket</h2>")
    if snap["trades"]:
        out.append("<table><tr><th>Ticker</th><th>Company</th><th>Side</th><th class='r'>Weight</th><th class='r'>Amount</th>"
                   "<th class='r'>Est. shares</th><th class='r'>Price</th><th class='r'>Below buy price</th><th>Flag</th></tr>")
        for t in snap["trades"]:
            sev = t.get("valuation_review_severity")
            flag = "<span class='pill p-rev'>Valuation review</span>" if sev in ("REVIEW", "CRITICAL_REVIEW") else ""
            if t["side"] == "SELL" and (t.get("target_weight") or 0) == 0:
                flag = flag or "<span class='mut'>Exit</span>"
            sh = t.get("trade_shares_est")
            out.append(
                f"<tr><td><b>{_e(t['ticker'])}</b></td><td class='mut'>{_e(t.get('company_name') or '')}</td>"
                f"<td><span class='pill {SIDE_PILL.get(t['side'], 'p-n')}'>{SIDE_LABEL.get(t['side'], t['side'])}</span></td>"
                f"<td class='r'>{_pct(t.get('previous_weight'))} → {_pct(t.get('target_weight'))}</td>"
                f"<td class='r'>{_money(t.get('trade_notional'))}</td>"
                f"<td class='r'>{'' if sh is None else f'{abs(sh):,.0f}'}</td>"
                f"<td class='r'>{'' if t.get('current_price') is None else f'{t['current_price']:,.2f}'}</td>"
                f"<td class='r'>{_pct(t.get('below_buy_price_pct')) if t.get('below_buy_price_pct') is not None else '—'}</td>"
                f"<td>{flag}</td></tr>")
        out.append("</table>")
    else:
        out.append("<p class='mut'>No trades. The model portfolio is unchanged.</p>")
    if snap.get("not_traded"):
        nt = ", ".join(f"{_e(x['ticker'])} {_pct(x.get('target_weight'), 2)} ({_e(x.get('reason'))})" for x in snap["not_traded"])
        out.append(f"<p class='sub'>Not traded: {nt}.</p>")
    out.append("<p class='sub'>“Below buy price” = how far the price sits under the margin-of-safety entry price. Higher is cheaper.</p>")

    # ---- paper account
    pa = snap.get("paper")
    if pa:
        out.append("<h2>Paper account</h2>")
        perf = pa.get("performance") or {}
        out.append("<div class='kpis'>")
        for label, val, sub in [
            ("Paper NAV", _money(pa.get("nav")), f"started with {_money(pa.get('initial_cash'))}"),
            ("Return since start", _pct(perf.get("nav_return"), 2, True), f"SPY {_pct(perf.get('spy_return'), 2, True)} since {perf.get('since') or '—'}"),
            ("Cash", _money(pa.get("cash")), f"valued at {pa.get('last_marked_session') or '—'}"),
            ("Open orders", str(len(pa.get("pending_orders") or [])), "fill at the next US open"),
        ]:
            out.append(f"<div class='k'><div class='l'>{label}</div><div class='v'>{_e(val)}</div><div class='s'>{_e(sub)}</div></div>")
        out.append("</div>")
        aw = pa.get("awaiting_approval")
        if aw:
            out.append(f"<div class='banner warn'><span>Orders waiting for your approval: ledger/paper/orders/{_e(aw['file'])}. "
                       "Edit it if you want, then run scripts\\paper_approve.bat (or use the Streamlit Paper trading tab).</span></div>")
        if pa.get("positions"):
            out.append("<table><tr><th>Ticker</th><th class='r'>Shares</th><th class='r'>Avg cost</th><th class='r'>Price</th>"
                       "<th class='r'>Value</th><th class='r'>Weight</th><th class='r'>Unrealized P&amp;L</th></tr>")
            for p in pa["positions"]:
                out.append(f"<tr><td><b>{_e(p['ticker'])}</b></td><td class='r'>{p['shares']:,.0f}</td><td class='r'>{p['avg_cost']:,.2f}</td>"
                           f"<td class='r'>{p['price']:,.2f}</td><td class='r'>{_money(p['market_value'])}</td><td class='r'>{_pct(p.get('weight'))}</td>"
                           f"<td class='r {_cls(p['unrealized_pl'])}'>{_money(p['unrealized_pl'])}</td></tr>")
            out.append("</table>")
        else:
            out.append("<p class='sub'>No paper positions yet.</p>")

    # ---- attention + context
    out.append("<div class='grid2'><div><h2>Needs your attention</h2><div class='list'>")
    warn = [f for f in snap["flags"] if f.get("severity") in ("CRITICAL", "WARNING")]
    info = [f for f in snap["flags"] if f.get("severity") not in ("CRITICAL", "WARNING")]
    if not warn and not info and not snap.get("blocked"):
        out.append("<div class='mut'>Nothing flagged.</div>")
    for f in warn:
        out.append(f"<div><span class='pill p-rev'>{_e(f['severity'].title())}</span> {_e(f['message'])}</div>")
    if snap.get("blocked"):
        names = ", ".join(_e(b["ticker"]) for b in snap["blocked"])
        out.append(f"<div><span class='pill p-sell'>Blocked</span> {names}: critical valuation anomaly, new entries not allowed</div>")
    for f in info:
        out.append(f"<div class='mut'>{_e(f['message'])}</div>")
    out.append("</div></div>")

    out.append("<div><h2>Macro context</h2>")
    out.append(f"<div class='sub'>Regime: <b>{_e(r['label'])}</b>, leaning {_e(r['top_candidate'])} "
               f"({_pct(r['top_probability'], 0)}) · growth {_e(r['growth']).lower()} · inflation {_e(r['inflation']).lower()} · "
               f"financial conditions {_e(r['financial_conditions']).lower()}</div><table style='margin-top:8px'>")
    for p in sorted(r["probabilities"], key=lambda x: -(x["probability"] or 0)):
        w = max(2, (p["probability"] or 0) * 100)
        out.append(f"<tr><td style='width:42%'>{_e(p['regime'])}</td><td><div class='bart'><div class='bar' style='width:{w:.0f}%'></div></div></td>"
                   f"<td class='r' style='width:15%'>{_pct(p['probability'], 0)}</td></tr>")
    out.append("</table></div></div>")

    # ---- sectors
    out.append("<h2>Sector ranking</h2><table><tr><th>#</th><th>Sector</th><th>Signal</th><th>Macro vs market</th><th class='r'>3m vs SPY</th><th class='r'>Model weight</th></tr>")
    for x in snap["sectors"]:
        sig = str(x.get("combined_signal") or "")
        pill = "p-buy" if "positive" in sig.lower() else ("p-sell" if "negative" in sig.lower() else "p-n")
        conflict = " <span class='pill p-rev'>Conflict</span>" if x.get("hard_conflict") else ""
        out.append(f"<tr><td>{_e(x.get('combined_rank'))}</td><td>{_e(x.get('sector'))} <span class='mut'>{_e(x['ticker'])}</span></td>"
                   f"<td><span class='pill {pill}'>{_e(sig)}</span></td><td class='mut'>{_e(x.get('macro_market_alignment'))}{conflict}</td>"
                   f"<td class='r {_cls(x.get('relative_3m'))}'>{_pct(x.get('relative_3m'), 1, True)}</td>"
                   f"<td class='r'>{_pct(x.get('model_weight')) if x.get('model_weight') else '—'}</td></tr>")
    out.append("</table>")

    # ---- holdings + watchlist
    out.append("<div class='grid2'><div><h2>Target holdings</h2><table><tr><th>Ticker</th><th class='r'>Weight</th><th class='r'>Exp. return</th><th class='r'>Risk share</th></tr>")
    for h in snap["holdings"]:
        rev = " <span class='pill p-rev'>Review</span>" if h.get("valuation_review_severity") in ("REVIEW", "CRITICAL_REVIEW") else ""
        out.append(f"<tr><td><b>{_e(h['ticker'])}</b> <span class='mut'>{_e(h.get('sector_ticker'))}</span>{rev}</td>"
                   f"<td class='r'>{_pct(h['target_weight'])}</td><td class='r'>{_pct(h.get('expected_total_return_annual'))}</td>"
                   f"<td class='r'>{_pct(h.get('risk_contribution_share'), 0)}</td></tr>")
    out.append(f"<tr><td class='mut'>Cash</td><td class='r'>{_pct(k['cash'])}</td><td></td><td></td></tr></table></div>")
    out.append("<div><h2>Closest to a buy</h2><table><tr><th>Ticker</th><th class='r'>Price</th><th class='r'>Buy price</th><th class='r'>Needs to fall</th></tr>")
    for w in snap["watchlist"][:8]:
        out.append(f"<tr><td><b>{_e(w['ticker'])}</b> <span class='mut'>{_e(w.get('sector_ticker'))}</span></td>"
                   f"<td class='r'>{w['current_price']:,.2f}</td><td class='r'>{w['mos_price_threshold']:,.2f}</td>"
                   f"<td class='r'>{_pct(w['distance_to_mos_pct'])}</td></tr>")
    out.append("</table></div></div>")

    # ---- track record
    out.append("<h2>Track record (model, forward)</h2>")
    if track is not None and not track.empty:
        out.append(_sparkline([0.0] + list(track["cumulative_model"])))
        out.append("<table><tr><th>Period</th><th class='r'>Days</th><th class='r'>Invested</th><th class='r'>Model</th>"
                   "<th class='r'>Expected</th><th class='r'>SPY</th><th class='r'>vs SPY</th></tr>")
        for _, t in track.iterrows():
            out.append(f"<tr><td>{t['from_session']} → {t['to_session']}</td><td class='r'>{t['days']}</td><td class='r'>{_pct(t['invested'], 0)}</td>"
                       f"<td class='r {_cls(t['model_return'])}'>{_pct(t['model_return'], 2, True)}</td>"
                       f"<td class='r mut'>{_pct(t['expected_return_for_period'], 2, True)}</td>"
                       f"<td class='r {_cls(t['spy_return'])}'>{_pct(t['spy_return'], 2, True)}</td>"
                       f"<td class='r {_cls(t['excess_vs_spy'])}'>{_pct(t['excess_vs_spy'], 2, True)}</td></tr>")
        last = track.iloc[-1]
        out.append(f"</table><p class='sub'>Cumulative: model {_pct(last['cumulative_model'], 2, True)} vs SPY {_pct(last['cumulative_spy'], 2, True)}. "
                   "Holdings at each run marked to the next run's close; cash earns 0. This is a paper record of the model, not your account.</p>")
    else:
        out.append("<p class='mut'>Starts after the second recorded run.</p>")

    out.append("<details><summary>Raw snapshot (JSON)</summary><pre style='font-size:11px;white-space:pre-wrap'>"
               + _e(json.dumps(snap, indent=1)[:20000]) + "</pre></details>")
    out.append("</div></body></html>")
    return "".join(out)


def write_cockpit(project_root: Path, run_dir: Path, snap: dict) -> Path:
    led = Path(project_root) / "ledger"
    track = pd.read_csv(led / "track_record.csv") if (led / "track_record.csv").exists() and (led / "track_record.csv").stat().st_size > 5 else None
    runs = pd.read_csv(led / "runs.csv") if (led / "runs.csv").exists() else None
    if track is not None:
        track = track[track["to_session"] <= snap["market_session"]]
    page = render_cockpit(snap, track, runs)
    out = Path(run_dir) / "execution_cockpit.html"
    out.write_text(page, encoding="utf-8")
    return out
