"""Per-order thesis + red-team memos.  A reviewer, never a decider.

For every proposed order the pipeline assembles an EVIDENCE PACK from the
run (valuation sheet, cost of capital, scenarios, consensus, flags, risk
contribution, sector signal, price history).  Each fact has an id such as
``V.base_value`` or ``R.risk_share`` so a memo can cite it.

A memo (JSON, one per order) has:
  verdict            SUPPORT | SUPPORT_WITH_CONCERNS | CHALLENGE
                     (an opinion for you; the order is unchanged until you
                      edit/approve it yourself)
  thesis             why the model wants the trade
  red_team           why the model might be wrong
  what_would_change  observable things that would flip the view
  news               dated external sources, ids N1, N2 ...
Every claim carries ``cites``: evidence ids and/or news ids.  ``validate``
rejects a memo if any claim is uncited, cites something that does not exist,
a news item has no URL or date, or a flagged order has a thin red team.

Memos can be written three ways:
  * by hand / by Claude in chat, saved as  ledger/paper/memos/<session>/<TICKER>.json
  * by ``python -m macro_portfolio.memo generate`` using the Anthropic API with
    web search (needs ANTHROPIC_API_KEY in .env and memos.api_enabled: true)
  * not at all - the cockpit then shows the evidence pack only.

CLI:  python -m macro_portfolio.memo status|validate|generate [--session YYYY-MM-DD] [--force]
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

VERDICTS = ("SUPPORT", "SUPPORT_WITH_CONCERNS", "CHALLENGE")
MEMO_SCHEMA_VERSION = 1
DEFAULT_MODEL = "claude-opus-5-5"
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 6}


def memo_dir(root: Path, session: str) -> Path:
    return Path(root) / "ledger" / "paper" / "memos" / str(session)[:10]


def _num(x):
    try:
        x = float(x)
        return None if (math.isnan(x) or math.isinf(x)) else x
    except (TypeError, ValueError):
        return None


def _add(ev: dict, key: str, label: str, value, unit: str = ""):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return
    if isinstance(value, float):
        value = round(value, 6)
    ev[key] = {"label": label, "value": value, "unit": unit}


# ---------------------------------------------------------------------------
# evidence packs
# ---------------------------------------------------------------------------

def memo_session(snap: dict) -> str:
    """Memos belong to the paper proposal they review (its file date), else to the run."""
    aw = (snap.get("paper") or {}).get("awaiting_approval") or {}
    return str(aw.get("file") or snap["market_session"])[:10]


def orders_for(snap: dict) -> list[dict]:
    """Orders that need a memo: the open paper proposal; with no paper account, the model's trades.
    Once a proposal is approved there is nothing to review until next month's proposal."""
    pa = snap.get("paper")
    aw = (pa or {}).get("awaiting_approval") or {}
    if aw.get("orders"):
        return [{"ticker": o["ticker"], "side": o["side"], "shares": o.get("shares"),
                 "est_value": o.get("est_value"), "flag": o.get("flag") or ""} for o in aw["orders"]]
    if pa:
        return []
    return [{"ticker": t["ticker"], "side": t["side"], "shares": t.get("trade_shares_est"),
             "est_value": t.get("trade_notional"), "flag": t.get("valuation_review_severity") or ""}
            for t in snap.get("trades", []) if t.get("executable", True)]


def evidence_pack(snap: dict, order: dict) -> dict:
    t = order["ticker"]
    ev: dict = {}
    hold = next((h for h in snap.get("holdings", []) if h["ticker"] == t), {})
    trade = next((x for x in snap.get("trades", []) if x["ticker"] == t), {})
    sheet = (snap.get("valuation_sheets") or {}).get(t, {})
    price = _num(sheet.get("price")) or _num(hold.get("current_price")) or _num(trade.get("current_price"))

    _add(ev, "O.side", "Order side", order["side"])
    _add(ev, "O.shares", "Order shares", _num(order.get("shares")))
    _add(ev, "O.value", "Order value", _num(order.get("est_value")), "USD")
    _add(ev, "O.target_weight", "Target weight", _num(hold.get("target_weight") or trade.get("target_weight")), "fraction")
    _add(ev, "P.price", "Price at run", price, "USD")

    sc = sheet.get("scenarios") or {}
    for k in ("bear", "base", "bull", "expected"):
        _add(ev, f"V.{k}_value", f"Model {k} intrinsic value per share", _num(sc.get(k)), "USD")
    if price and _num(sc.get("expected")):
        _add(ev, "V.expected_upside", "Model expected upside", _num(sc["expected"]) / price - 1, "fraction")
    if price and _num(sc.get("bear")):
        _add(ev, "V.bear_upside", "Upside even in model bear case", _num(sc["bear"]) / price - 1, "fraction")
    _add(ev, "V.mos_price", "Margin-of-safety buy price", _num(sheet.get("mos_price")), "USD")
    _add(ev, "V.mos_met", "Price below margin-of-safety price", sheet.get("mos_met"))
    _add(ev, "V.model", "Valuation model", sheet.get("model"))
    _add(ev, "V.confidence", "Valuation confidence", _num(sheet.get("confidence")))
    ct = _num(sheet.get("consensus_target"))
    _add(ev, "C.target", "Analyst consensus target", ct, "USD")
    if ct and price:
        _add(ev, "C.upside", "Consensus upside", ct / price - 1, "fraction")
    if ct and _num(sc.get("expected")):
        _add(ev, "C.model_vs_consensus", "Model expected value / consensus target", _num(sc["expected"]) / ct)
    _add(ev, "F.review", "Valuation review flag", sheet.get("review") or hold.get("valuation_review_severity") or "NONE")
    _add(ev, "F.review_reason", "Review reason", sheet.get("review_reason"))
    b = sheet.get("bridge") or {}
    _add(ev, "V.terminal_share", "Share of value from terminal value", _num(b.get("terminal_value_share")), "fraction")
    _add(ev, "V.discount_rate", "Discount rate", _num(b.get("discount_rate")), "fraction")
    _add(ev, "V.terminal_growth", "Terminal growth", _num(b.get("terminal_growth")), "fraction")
    cc = sheet.get("cost_of_capital") or {}
    _add(ev, "K.raw_beta", "Company regression beta", _num(cc.get("raw_beta")))
    _add(ev, "K.valuation_beta", "Beta used in valuation", _num(cc.get("valuation_beta")))
    _add(ev, "K.beta_source", "Beta source", cc.get("beta_source"))
    im = sheet.get("implied") or {}
    if im.get("driver"):
        _add(ev, "I.driver", "Reverse-DCF driver", im.get("driver"))
        _add(ev, "I.market_implied", "Market-implied value of driver", _num(im.get("market_implied")))
        _add(ev, "I.model_base", "Model base-case value of driver", _num(im.get("model_base")))
    mu = sheet.get("multiples") or {}
    _add(ev, "M.metric", "Multiple", mu.get("metric"))
    _add(ev, "M.current", "Current multiple", _num(mu.get("current")))
    _add(ev, "M.exit_base", "Exit multiple in base case", _num(mu.get("exit_base")))
    fc = sheet.get("forecast") or []
    if fc:
        _add(ev, "V.yr1_growth", "Forecast revenue growth year 1", _num(fc[0].get("revenue_growth")), "fraction")
        _add(ev, "V.yr5_growth", "Forecast revenue growth year 5", _num(fc[-1].get("revenue_growth")), "fraction")
        _add(ev, "V.yr1_margin", "Forecast EBIT margin year 1", _num(fc[0].get("ebit_margin")), "fraction")
        _add(ev, "V.yr5_margin", "Forecast EBIT margin year 5", _num(fc[-1].get("ebit_margin")), "fraction")
    rg = sheet.get("range_52w") or {}
    _add(ev, "P.low_52w", "52-week low", _num(rg.get("low")), "USD")
    _add(ev, "P.high_52w", "52-week high", _num(rg.get("high")), "USD")
    if price and _num(rg.get("low")):
        _add(ev, "P.vs_low_52w", "Price vs 52-week low", price / _num(rg["low"]) - 1, "fraction")

    risk = snap.get("risk") or {}
    rc = next((r for r in risk.get("risk_contributions", []) if r["ticker"] == t), {})
    _add(ev, "R.risk_share", "Share of portfolio volatility", _num(rc.get("risk_share")), "fraction")
    _add(ev, "R.standalone_vol", "Standalone annual volatility", _num(rc.get("standalone_vol")), "fraction")
    _add(ev, "R.expected_return", "Optimizer expected annual return", _num(hold.get("expected_total_return_annual")), "fraction")

    sec_t = hold.get("sector_ticker") or trade.get("sector_ticker")
    sec = next((s for s in snap.get("sectors", []) if s["ticker"] == sec_t), {})
    _add(ev, "S.sector", "Sector ETF", sec_t)
    _add(ev, "S.rank", "Sector combined rank (1 = best of 11)", sec.get("combined_rank"))
    _add(ev, "S.signal", "Sector combined signal", sec.get("combined_signal"))
    _add(ev, "S.alignment", "Macro vs market alignment", sec.get("macro_market_alignment"))
    _add(ev, "S.relative_3m", "Sector 3-month return vs SPY", _num(sec.get("relative_3m")), "fraction")
    reg = snap.get("regime") or {}
    _add(ev, "G.regime", "Economic regime", reg.get("label"))
    _add(ev, "G.top_probability", "Top regime probability", _num(reg.get("top_probability")), "fraction")

    flags = [f for f in snap.get("flags", []) if f.get("ticker") == t]
    for i, f in enumerate(flags, 1):
        _add(ev, f"F.flag{i}", f"{f.get('severity')} {f.get('type')}", f.get("message"))

    sq = snap.get("signal_quality") or {}
    mb = next((m for m in sq.get("model_buys", []) if m["horizon"] == 63), None) or next(iter(sq.get("model_buys", [])), None)
    if mb:
        _add(ev, "Q.buy_hit_rate", f"Past model buys beating SPY (vol-adj, {mb['horizon']} sessions)", mb["hit_rate"], "fraction")
        _add(ev, "Q.runs_scored", "Runs scored so far", mb["runs_scored"])

    return {"ticker": t, "company_name": sheet.get("company_name") or hold.get("company_name") or trade.get("company_name"),
            "session": memo_session(snap), "run_id": snap["run_id"], "side": order["side"],
            "flagged": bool(order.get("flag")) or ev.get("F.review", {}).get("value") in ("REVIEW", "CRITICAL_REVIEW"),
            "evidence": ev}


def build_evidence_packs(root: Path, snap: dict) -> list[Path]:
    out = []
    d = memo_dir(root, memo_session(snap))
    orders = orders_for(snap)
    if not orders:
        return out
    d.mkdir(parents=True, exist_ok=True)
    for o in orders:
        p = d / f"{o['ticker']}.evidence.json"
        if p.exists():  # frozen at proposal time so memos and the order prices stay consistent
            continue
        p.write_text(json.dumps(evidence_pack(snap, o), indent=1, default=str), encoding="utf-8")
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate(memo: dict, pack: dict | None) -> list[str]:
    errs = []
    if memo.get("verdict") not in VERDICTS:
        errs.append(f"verdict must be one of {VERDICTS}")
    news = {n.get("id"): n for n in memo.get("news", [])}
    for nid, n in news.items():
        if not str(nid or "").startswith("N"):
            errs.append(f"news id {nid!r} must start with N")
        if not str(n.get("url", "")).startswith("http"):
            errs.append(f"news {nid} has no URL")
        if not _DATE.match(str(n.get("date", ""))):
            errs.append(f"news {nid} date must be YYYY-MM-DD")
        elif pack and n["date"] > str(memo.get("written_at", "9999"))[:10]:
            errs.append(f"news {nid} is dated after the memo was written")
    keys = set((pack or {}).get("evidence", {}))
    for section in ("thesis", "red_team", "what_would_change"):
        items = memo.get(section) or []
        if not items:
            errs.append(f"{section} is empty")
        for i, c in enumerate(items, 1):
            cites = c.get("cites") or []
            if not str(c.get("text", "")).strip():
                errs.append(f"{section}[{i}] has no text")
            if section != "what_would_change" and not cites:
                errs.append(f"{section}[{i}] cites nothing")
            for k in cites:
                if k in news:
                    continue
                if pack is not None and k not in keys:
                    errs.append(f"{section}[{i}] cites unknown evidence {k!r}")
    if pack and pack.get("flagged") and len(memo.get("red_team") or []) < 3:
        errs.append("flagged order needs at least 3 red-team points")
    if pack and memo.get("ticker") != pack.get("ticker"):
        errs.append("ticker does not match evidence pack")
    return errs


def load_memos(root: Path, snap: dict) -> dict:
    d = memo_dir(root, memo_session(snap))
    out = {}
    if not d.exists():
        return out
    for o in orders_for(snap):
        t = o["ticker"]
        pp, mp = d / f"{t}.evidence.json", d / f"{t}.json"
        pack = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
        memo = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else None
        out[t] = {"memo": memo, "errors": validate(memo, pack) if memo else ["no memo written"],
                  "evidence": (pack or {}).get("evidence", {}), "flagged": (pack or {}).get("flagged", False)}
    return out


# ---------------------------------------------------------------------------
# optional writer: Anthropic API + web search
# ---------------------------------------------------------------------------

PROMPT = """You are the red-team reviewer for a systematic portfolio. You do NOT decide trades; a human approves them.
Write a memo on this proposed order. Today is {today}.

Evidence pack from the model (cite these ids exactly):
{evidence}

Use web search for news from the last 90 days that bears on the thesis (earnings, guidance, regulation, litigation,
commodity prices, analyst actions). Cite each source as a news item with id N1, N2, ...; include its URL and its
publication date (YYYY-MM-DD). Do not cite anything you did not retrieve.

Rules: every thesis and red_team point must cite at least one evidence id or news id. Be specific and quantitative.
The red team must argue in good faith why the model might be wrong (model risk, data risk, what the market knows).
{flag_rule}
Return ONLY a JSON object:
{{"ticker": "{ticker}", "side": "{side}", "verdict": "SUPPORT|SUPPORT_WITH_CONCERNS|CHALLENGE",
  "summary": "two sentences",
  "thesis": [{{"text": "...", "cites": ["V.base_value"]}}],
  "red_team": [{{"text": "...", "cites": ["C.upside", "N1"]}}],
  "what_would_change": [{{"text": "...", "cites": []}}],
  "news": [{{"id": "N1", "title": "...", "publisher": "...", "date": "YYYY-MM-DD", "url": "https://..."}}]}}"""


def generate(root: Path, session: str, cfg: dict, force: bool = False, log=print) -> list[str]:
    mcfg = (cfg.get("memos") or {})
    if not mcfg.get("api_enabled", False):
        raise RuntimeError("memos.api_enabled is false in config/settings.yaml")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set (.env)")
    import anthropic  # optional dependency
    client = anthropic.Anthropic()
    model = mcfg.get("model", DEFAULT_MODEL)
    done = []
    for pp in sorted(memo_dir(root, session).glob("*.evidence.json")):
        pack = json.loads(pp.read_text(encoding="utf-8"))
        mp = pp.with_name(f"{pack['ticker']}.json")
        if mp.exists() and not force:
            continue
        today = datetime.now(timezone.utc).date().isoformat()
        prompt = PROMPT.format(today=today, evidence=json.dumps(pack["evidence"], indent=1), ticker=pack["ticker"],
                               side=pack["side"], flag_rule=("This order is FLAGGED for valuation review: give at least "
                                                             "3 red-team points and explain the model-vs-consensus gap.")
                               if pack["flagged"] else "")
        messages = [{"role": "user", "content": prompt}]
        tool = dict(WEB_SEARCH_TOOL, max_uses=int(mcfg.get("max_searches", 6)))
        for _ in range(4):  # server-side loop may pause
            resp = client.messages.create(model=model, max_tokens=int(mcfg.get("max_tokens", 4000)),
                                          messages=messages, tools=[tool])
            if resp.stop_reason != "pause_turn":
                break
            messages = [messages[0], {"role": "assistant", "content": resp.content}]
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            log(f"{pack['ticker']}: no JSON in response")
            continue
        memo = json.loads(m.group(0))
        memo.update({"schema": MEMO_SCHEMA_VERSION, "session": pack["session"], "run_id": pack["run_id"],
                     "author": f"{model} via API", "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        errs = validate(memo, pack)
        memo["validation_errors"] = errs
        target = mp if not errs else mp.with_suffix(".rejected.json")
        target.write_text(json.dumps(memo, indent=1), encoding="utf-8")
        log(f"{pack['ticker']}: {'OK' if not errs else 'REJECTED ' + '; '.join(errs)} -> {target.name}")
        done.append(pack["ticker"])
    return done


def _main(argv):
    from .paper import load_config
    from .runtime import repository_root
    root = repository_root()
    cmd = argv[1] if len(argv) > 1 else "status"
    sess = argv[argv.index("--session") + 1] if "--session" in argv else None
    if sess is None:
        days = sorted(p.name for p in (root / "ledger/paper/memos").glob("*") if p.is_dir())
        sess = days[-1] if days else None
    if not sess:
        print("No evidence packs yet. They are written after each pipeline run.")
        return
    if cmd == "generate":
        try:
            from dotenv import load_dotenv
            load_dotenv(root / ".env")
        except Exception:
            pass
        generate(root, sess, load_config(root), force="--force" in argv)
        return
    for pp in sorted(memo_dir(root, sess).glob("*.evidence.json")):
        pack = json.loads(pp.read_text(encoding="utf-8"))
        mp = pp.with_name(f"{pack['ticker']}.json")
        if not mp.exists():
            print(f"{pack['ticker']:6s} no memo")
            continue
        memo = json.loads(mp.read_text(encoding="utf-8"))
        errs = validate(memo, pack)
        print(f"{pack['ticker']:6s} {memo.get('verdict'):22s} {'valid' if not errs else 'INVALID: ' + '; '.join(errs)}")


if __name__ == "__main__":
    _main(sys.argv)
