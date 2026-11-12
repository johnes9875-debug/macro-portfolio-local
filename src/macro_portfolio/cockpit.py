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
.st-PASS{background:var(--goodbg);color:var(--good)}.st-WARN{background:var(--warnbg);color:var(--warn)}.st-FAIL{background:var(--badbg);color:var(--bad)}.st-NA{background:var(--card);color:var(--mut)}
.sheet{border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:12px 0}
.sheet h3{font-size:15px;margin:0 0 4px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px;margin-top:8px}
.kv td{padding:4px 6px}.kv td:first-child{color:var(--mut)}
.sens td,.sens th{text-align:right;padding:4px 6px;font-variant-numeric:tabular-nums}
.up{background:var(--goodbg)}.dn{background:var(--badbg)}.mid{outline:2px solid var(--acc)}
svg.ff text{font-size:11px;fill:var(--mut)}
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


def _num(v, d=2):
    try:
        return f"{float(v):,.{d}f}"
    except (TypeError, ValueError):
        return "—"


def _bn(v):
    try:
        f = float(v) / 1e9
    except (TypeError, ValueError):
        return "—"
    return f"−${abs(f):,.1f}bn" if f < 0 else f"${f:,.1f}bn"


def render_risk(risk: dict) -> str:
    if not risk or not risk.get("available"):
        return f"<h2>Risk and limits</h2><p class='mut'>Not available: {_e((risk or {}).get('reason', 'no data'))}</p>"
    o = ["<h2>Risk and limits</h2>"]
    ls = risk.get("limits_summary", {})
    worst = min((x for x in risk.get("stress", []) if x.get("portfolio_return") is not None),
                key=lambda x: x["portfolio_return"], default=None)
    o.append("<div class='kpis'>")
    for label, val, sub in [
        ("Limits", f"{ls.get('PASS', 0)} pass · {ls.get('WARN', 0)} warn · {ls.get('FAIL', 0)} fail", "every configured constraint"),
        ("Ex-ante volatility", _pct(risk.get("ex_ante_volatility")), f"beta {_num(risk.get('beta'))} to SPY (daily, 3y)"),
        ("Tracking error vs SPY", _pct(risk.get("tracking_error")), f"mostly the cash position ({_pct(1 - (risk.get('invested') or 0), 0)})"),
        ("1-day 99% VaR", _money(risk.get("var_99_1d_usd")), f"CVaR {_money(risk.get('cvar_99_1d_usd'))} (historical)"),
        ("Concentration", f"{_num(risk.get('effective_positions'), 1)} effective names", f"top 5 = {_pct(risk.get('top5_weight'))}, avg corr {_num(risk.get('average_correlation'))}"),
        ("Worst stress", _pct(worst["portfolio_return"]) if worst else "—", (worst or {}).get("scenario", "")),
    ]:
        o.append(f"<div class='k'><div class='l'>{_e(label)}</div><div class='v' style='font-size:19px'>{_e(val)}</div><div class='s'>{_e(sub)}</div></div>")
    o.append("</div>")
    o.append("<div class='grid2'><div><h2 style='font-size:14px'>Limits</h2><table><tr><th>Check</th><th class='r'>Value</th><th class='r'>Limit</th><th>Status</th></tr>")
    for l in risk.get("limits", []):
        fmt = (lambda x: _pct(x)) if l.get("unit") == "weight" else (lambda x: "—" if x is None else str(x))
        o.append(f"<tr><td>{_e(l['limit'])}<div class='sub'>{_e(l.get('detail') or '')}</div></td><td class='r'>{fmt(l.get('value'))}</td>"
                 f"<td class='r'>{fmt(l.get('limit_value'))}</td><td><span class='pill st-{_e(l['status'].replace('/', ''))}'>{_e(l['status'].title())}</span></td></tr>")
    o.append("</table></div><div><h2 style='font-size:14px'>Where the risk comes from</h2><table><tr><th>Ticker</th><th class='r'>Weight</th><th class='r'>Share of risk</th><th class='r'>Own vol</th><th style='width:35%'></th></tr>")
    for r in sorted(risk.get("risk_contributions", []), key=lambda r: -(r.get("risk_share") or 0)):
        o.append(f"<tr><td><b>{_e(r['ticker'])}</b></td><td class='r'>{_pct(r['weight'])}</td><td class='r'>{_pct(r['risk_share'], 0)}</td>"
                 f"<td class='r'>{_pct(r['standalone_vol'], 0)}</td><td><div class='bart'><div class='bar' style='width:{max(2, (r['risk_share'] or 0) * 100):.0f}%'></div></div></td></tr>")
    o.append("</table></div></div>")
    o.append("<h2 style='font-size:14px'>Stress tests</h2><table><tr><th>Scenario</th><th>Window</th><th class='r'>Portfolio</th><th class='r'>P&amp;L</th><th class='r'>SPY</th></tr>")
    for x in risk.get("stress", []):
        o.append(f"<tr><td>{_e(x['scenario'])}</td><td class='mut'>{_e(x['window'])}</td><td class='r {_cls(x['portfolio_return'])}'>{_pct(x['portfolio_return'], 1, True)}</td>"
                 f"<td class='r {_cls(x['portfolio_pnl'])}'>{_money(x['portfolio_pnl'])}</td><td class='r mut'>{_pct(x.get('spy_return'), 1, True) if x.get('spy_return') is not None else '—'}</td></tr>")
    o.append("</table><p class='sub'>Historical replays apply each holding's 3-year beta to its sector ETF to that ETF's move in the window "
             "(stock histories are too short to replay directly). Shocks use 3-year betas to SPY, long Treasuries (TLT) and oil. Cash is held at 0.</p>")
    return "".join(o)


def _football(sh: dict) -> str:
    rng = sh.get("range_52w") or {}
    sc = sh.get("scenarios") or {}
    rows = [("52-week range", rng.get("low"), rng.get("high"), 0.3),
            ("Model bear to bull", sc.get("bear"), sc.get("bull"), 0.55)]
    marks = [("Price", sh.get("price"), "var(--ink)", "3 0"), ("Buy price (MOS)", sh.get("mos_price"), "var(--good)", "3 0"),
             ("Consensus target", sh.get("consensus_target"), "var(--warn)", "5 3"), ("Model base", sc.get("base"), "var(--acc)", "3 0")]
    vals = [v for _, a, b, _ in rows for v in (a, b) if v] + [v for _, v, _, _ in marks if v]
    if not vals:
        return ""
    lo, hi = min(vals) * 0.97, max(vals) * 1.03
    W, L, R, H = 640, 130, 50, 70
    x = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    o = [f"<svg class='ff' viewBox='0 0 {W} {H}' style='width:100%;max-width:{W}px;display:block' role='img' aria-label='valuation range chart'>"]
    for i, (lab, a, b, op) in enumerate(rows):
        if a and b:
            y = 10 + i * 28
            o.append(f"<text x='0' y='{y + 12}'>{_e(lab)}</text>"
                     f"<rect x='{x(a):.1f}' y='{y}' width='{max(2, x(b) - x(a)):.1f}' height='16' rx='3' fill='var(--acc)' fill-opacity='{op}'/>"
                     f"<text x='{x(a) - 4:.1f}' y='{y + 12}' text-anchor='end'>{a:,.0f}</text><text x='{x(b) + 4:.1f}' y='{y + 12}'>{b:,.0f}</text>")
    for lab, v, col, dash in marks:
        if v:
            o.append(f"<line x1='{x(v):.1f}' x2='{x(v):.1f}' y1='4' y2='{H - 4}' stroke='{col}' stroke-width='2' stroke-dasharray='{dash}'><title>{_e(lab)} {v:,.2f}</title></line>")
    o.append("</svg><div class='sub' style='display:flex;flex-wrap:wrap;gap:14px'>")
    for lab, v, col, dash in marks:
        if v:
            o.append(f"<span><span style='display:inline-block;width:14px;height:0;border-top:2px {'dashed' if dash != '3 0' else 'solid'} {col};vertical-align:middle;margin-right:5px'></span>{_e(lab)} {v:,.2f}</span>")
    o.append("</div>")
    return "".join(o)


def render_sheets(sheets: dict, holdings: list) -> str:
    if not sheets:
        return ""
    order = [h["ticker"] for h in holdings] + [t for t in sheets if t not in {h["ticker"] for h in holdings}]
    o = ["<h2>Valuation sheets</h2><p class='sub'>One per target holding or new buy. The grid recomputes the base-case DCF at other discount rates and terminal growth rates; "
         "green cells are above today's price.</p>"]
    for t in order:
        sh = sheets.get(t)
        if not sh:
            continue
        sc, b, c, im, mu = sh.get("scenarios", {}), sh.get("bridge") or {}, sh.get("cost_of_capital") or {}, sh.get("implied") or {}, sh.get("multiples") or {}
        flag = f" <span class='pill p-rev'>{_e(str(sh.get('review')).replace('_', ' ').lower())}</span>" if sh.get("review") in ("REVIEW", "CRITICAL_REVIEW") else ""
        up = (sc.get("expected") / sh["price"] - 1) if sc.get("expected") and sh.get("price") else None
        o.append(f"<div class='sheet' id='sheet-{_e(t)}'><h3>{_e(t)} · {_e(sh.get('company_name'))}{flag}</h3>"
                 f"<div class='sub'>{_e(str(sh.get('model')).replace('_', ' ').lower())} · price {_num(sh.get('price'))} · expected value {_num(sc.get('expected'))} "
                 f"({_pct(up, 0, True)}) · consensus {_num(sh.get('consensus_target'))} · confidence {_pct(sh.get('confidence'), 0)}"
                 + (f" · {_e(sh.get('review_reason'))}" if sh.get("review_reason") else "") + "</div>")
        o.append(_football(sh))
        o.append("<div class='grid3'><div><b style='font-size:13px'>Bridge (base case)</b><table class='kv'>")
        for lab, v in [("PV of 5-year cash flows", _bn(b.get("pv_explicit_cash_flows"))), ("PV of terminal value", _bn(b.get("pv_terminal_value"))),
                       ("Enterprise value", _bn(b.get("enterprise_value"))), ("Less net debt", _bn(b.get("net_debt"))),
                       ("Equity value", _bn(b.get("equity_value"))), ("Shares", f"{(b.get('valuation_share_units') or 0) / 1e6:,.0f}m"),
                       ("Value per share", _num(b.get("intrinsic_value_per_share"))), ("Terminal value share", _pct(b.get("terminal_value_share"), 0))]:
            o.append(f"<tr><td>{lab}</td><td class='r'>{v}</td></tr>")
        o.append("</table></div><div><b style='font-size:13px'>Discount rate</b><table class='kv'>")
        for lab, v in [("Raw beta (2y weekly)", _num(c.get("raw_beta"))), ("Valuation beta" + (" (industry)" if c.get("beta_source") == "BOTTOM_UP_INDUSTRY" else ""), _num(c.get("valuation_beta"))),
                       ("Cost of equity", _pct(c.get("cost_of_equity"))), ("After-tax cost of debt", _pct(c.get("after_tax_cost_of_debt"))),
                       ("Debt weight", _pct(c.get("debt_weight"), 0)), ("Discount rate (WACC)", _pct(b.get("discount_rate") or c.get("discount_rate"))),
                       ("Terminal growth", _pct(b.get("terminal_growth") or c.get("terminal_growth")))]:
            o.append(f"<tr><td>{lab}</td><td class='r'>{v}</td></tr>")
        o.append("</table></div><div><b style='font-size:13px'>What the price implies</b><table class='kv'>")
        for lab, v in [(f"Market-implied {str(im.get('driver') or 'driver').replace('_', ' ').lower()}", _pct(im.get("market_implied"))),
                       ("Model base assumption", _pct(im.get("model_base"))),
                       (f"Current {mu.get('metric') or 'multiple'}", _num(mu.get("current"), 1) + "x"),
                       ("Exit multiple used (year 5)", _num(mu.get("exit_base"), 1) + "x"),
                       ("Scenario values bear / base / bull", f"{_num(sc.get('bear'), 0)} / {_num(sc.get('base'), 0)} / {_num(sc.get('bull'), 0)}")]:
            o.append(f"<tr><td>{lab}</td><td class='r'>{v}</td></tr>")
        o.append("</table></div></div>")
        sens = sh.get("sensitivity")
        if sens and sh.get("price"):
            o.append("<div style='overflow-x:auto;margin-top:8px'><table class='sens' style='width:auto'><tr><th style='text-align:left'>WACC \\ growth</th>"
                     + "".join(f"<th>{g * 100:.1f}%</th>" for g in sens["terminal_growth"]) + "</tr>")
            for i, (r, row) in enumerate(zip(sens["discount_rates"], sens["values"])):
                o.append(f"<tr><th style='text-align:left'>{r * 100:.1f}%</th>")
                for j, v in enumerate(row):
                    cls = ("up" if v and v > sh["price"] else "dn") if v else ""
                    cls += " mid" if i == 2 and j == 2 else ""
                    o.append(f"<td class='{cls}'>{_num(v, 0) if v else '—'}</td>")
                o.append("</tr>")
            o.append("</table>" + ("" if sh.get("reconciles") else "<div class='sub'>Note: grid does not exactly reproduce the engine's base value.</div>") + "</div>")
        o.append("</div>")
    return "".join(o)


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

    # ---- risk / limits and valuation sheets (v1.0.14)
    if snap.get("risk"):
        out.append(render_risk(snap["risk"]))
    if snap.get("valuation_sheets"):
        out.append(render_sheets(snap["valuation_sheets"], snap.get("holdings", [])))

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
