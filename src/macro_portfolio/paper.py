"""Paper-trading account with monthly rebalancing and editable orders.

Cycle (one calendar month):

  1. PROPOSE   After the first successful run of a month, the model's target
               weights are turned into whole-share orders against the PAPER
               account's real positions and cash (not the model's assumption
               that last month's targets were filled).
               -> ledger/paper/orders/<session>_proposed.csv

  2. AMEND     Edit that CSV by hand (or in the Streamlit "Paper trading" tab):
               change `shares`, set `action` to SKIP, add a `limit_price`,
               add your own rows, or set `fill_price` to force a price.

  3. APPROVE   scripts\\paper_approve.bat  (or the Approve button)
               -> ledger/paper/orders/<session>_approved.csv, stamped with
               approved_on. Nothing is filled until you approve.

  4. FILL      Every later run fills approved orders at the first session open
               AFTER the approval date (sells before buys). A limit order
               fills only if the day's range reaches the limit. Buys are cut
               to whole shares that fit the cash. Unfilled orders expire
               after `order_expiry_sessions`. Cost = transaction_cost_rate.

  5. MARK      Every run values positions at the session close and appends
               ledger/paper/nav.csv (with SPY close for comparison). Prices
               are unadjusted closes for both the account and SPY, so the
               comparison is price-return vs price-return; dividends are not
               credited (see README).

The account's weights are written to ledger/paper/optimizer_state.csv so that
with execution.portfolio_state_mode: PAPER the optimizer starts from what the
paper account actually holds.

CLI (also wrapped by scripts\\paper_*.bat):
    python -m macro_portfolio.paper status
    python -m macro_portfolio.paper propose [--force] [run_dir]
    python -m macro_portfolio.paper approve [orders_csv]
    python -m macro_portfolio.paper process          # fill + mark now
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PAPER_VERSION = "1.0.0"

ORDER_COLUMNS = [
    "order_id", "ticker", "side", "shares", "action", "limit_price", "fill_price",
    "ref_price", "est_value", "current_shares", "target_shares", "target_weight",
    "reason", "flag", "note",
]

DEFAULTS = {
    "initial_cash": 1_000_000.0,
    "rebalance_frequency": "monthly",
    "whole_shares": True,
    "order_expiry_sessions": 5,
    "cash_annual_rate": 0.0,
    "min_order_value_pct": 0.0025,
    "transaction_cost_rate": 0.001,
}


# ---------------------------------------------------------------------------
# config / paths / io
# ---------------------------------------------------------------------------

def paper_cfg(config: dict | None) -> dict:
    config = config or {}
    out = dict(DEFAULTS)
    out.update((config.get("paper") or {}))
    out["transaction_cost_rate"] = float((config.get("execution") or {}).get(
        "transaction_cost_rate", out["transaction_cost_rate"]))
    return out


def load_config(root: Path) -> dict:
    p = Path(root) / "config" / "settings.yaml"
    if not p.exists():
        return {}
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def pdir(root: Path) -> Path:
    d = Path(root) / "ledger" / "paper"
    (d / "orders").mkdir(parents=True, exist_ok=True)
    return d


def _read(path: Path, cols=None) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 2:
        return pd.read_csv(path, comment="#")
    return pd.DataFrame(columns=cols or [])


def load_account(root: Path, cfg: dict) -> dict:
    p = pdir(root) / "account.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    acct = {"version": PAPER_VERSION, "created_at": datetime.now().isoformat(timespec="seconds"),
            "initial_cash": float(cfg["initial_cash"]), "cash": float(cfg["initial_cash"]),
            "last_marked_session": None, "last_cash_accrual_session": None}
    save_account(root, acct)
    return acct


def save_account(root: Path, acct: dict) -> None:
    (pdir(root) / "account.json").write_text(json.dumps(acct, indent=1), encoding="utf-8")


def load_positions(root: Path) -> pd.DataFrame:
    df = _read(pdir(root) / "positions.csv", ["ticker", "shares", "avg_cost"])
    if df.empty:
        return pd.DataFrame(columns=["ticker", "shares", "avg_cost"])
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0.0)
    df["avg_cost"] = pd.to_numeric(df["avg_cost"], errors="coerce").fillna(0.0)
    return df[df["shares"].abs() > 1e-9][["ticker", "shares", "avg_cost"]].reset_index(drop=True)


def save_positions(root: Path, pos: pd.DataFrame) -> None:
    pos = pos[pos["shares"].abs() > 1e-9].sort_values("ticker")
    pos[["ticker", "shares", "avg_cost"]].to_csv(pdir(root) / "positions.csv", index=False)


# ---------------------------------------------------------------------------
# prices (local cache written by Section B / E3)
# ---------------------------------------------------------------------------

def _price_path(root: Path, ticker: str) -> Path:
    sym = str(ticker).upper().replace(".", "-")
    p = Path(root) / "data" / "raw" / "stocks" / "prices" / f"{sym}.parquet"
    return p if p.exists() else Path(root) / "data" / "raw" / "market" / f"{sym}.parquet"


_PX_CACHE: dict = {}


def price_frame(root: Path, ticker: str) -> pd.DataFrame:
    key = (str(root), ticker)
    if key in _PX_CACHE:
        return _PX_CACHE[key]
    p = _price_path(root, ticker)
    if not p.exists():
        df = pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    else:
        df = pd.read_parquet(p)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        df = df.sort_values("date").drop_duplicates("date", keep="last")
        df = df[[c for c in ["date", "open", "high", "low", "close"] if c in df.columns]].dropna(subset=["close"])
    _PX_CACHE[key] = df
    return df


def close_on(root: Path, ticker: str, session) -> float | None:
    df = price_frame(root, ticker)
    df = df[df["date"] <= pd.Timestamp(session)]
    return None if df.empty else float(df.iloc[-1]["close"])


def latest_session(root: Path) -> pd.Timestamp | None:
    spy = price_frame(root, "SPY")
    return None if spy.empty else spy["date"].iloc[-1]


def sessions_after(root: Path, after) -> list[pd.Timestamp]:
    spy = price_frame(root, "SPY")
    return list(spy.loc[spy["date"] > pd.Timestamp(after), "date"])


# ---------------------------------------------------------------------------
# valuation of the account
# ---------------------------------------------------------------------------

def valuation(root: Path, session, acct: dict | None = None, pos: pd.DataFrame | None = None) -> dict:
    acct = acct or load_account(root, paper_cfg(load_config(root)))
    pos = load_positions(root) if pos is None else pos
    rows, missing = [], []
    for r in pos.itertuples():
        px = close_on(root, r.ticker, session)
        if px is None:
            missing.append(r.ticker)
            px = float(r.avg_cost)
        rows.append({"ticker": r.ticker, "shares": r.shares, "avg_cost": r.avg_cost, "price": px,
                     "market_value": r.shares * px, "unrealized_pl": r.shares * (px - r.avg_cost)})
    detail = pd.DataFrame(rows, columns=["ticker", "shares", "avg_cost", "price", "market_value", "unrealized_pl"])
    mv = float(detail["market_value"].sum()) if not detail.empty else 0.0
    nav = float(acct["cash"]) + mv
    if not detail.empty:
        detail["weight"] = detail["market_value"] / nav if nav else 0.0
    return {"session": str(pd.Timestamp(session).date()), "cash": float(acct["cash"]), "positions_value": mv,
            "nav": nav, "detail": detail, "missing_prices": missing}


def write_optimizer_state(root: Path, session) -> Path:
    """Weights the optimizer should treat as current (PAPER mode)."""
    v = valuation(root, session)
    rows = [{"ticker": r.ticker, "current_weight": r.weight} for r in v["detail"].itertuples()] if not v["detail"].empty else []
    rows.append({"ticker": "CASH", "current_weight": max(0.0, v["cash"] / v["nav"]) if v["nav"] else 1.0})
    out = pd.DataFrame(rows)
    total = out["current_weight"].sum()
    if total > 0:
        out["current_weight"] = out["current_weight"] / total
    path = pdir(root) / "optimizer_state.csv"
    out.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# 1. propose
# ---------------------------------------------------------------------------

def _orders_files(root: Path, kind: str) -> list[Path]:
    return sorted((pdir(root) / "orders").glob(f"*_{kind}.csv"))


def rebalance_due(root: Path, session, cfg: dict) -> bool:
    if str(cfg.get("rebalance_frequency", "monthly")).lower() != "monthly":
        return True
    month = str(pd.Timestamp(session))[:7]
    for p in _orders_files(root, "proposed"):
        if p.name[:7] == month:
            return False
    return True


def propose_orders(root: Path, run_dir: Path, force: bool = False, config: dict | None = None) -> Path | None:
    config = config if config is not None else load_config(root)
    cfg = paper_cfg(config)
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")) if (run_dir / "manifest.json").exists() else {}
    session = manifest.get("market_session") or run_dir.parent.name
    run_id = manifest.get("run_id") or run_dir.name
    if not force and not rebalance_due(root, session, cfg):
        return None

    weights = pd.read_parquet(run_dir / "G_FINAL_PORTFOLIO_WEIGHTS.parquet")
    weights["target_weight"] = pd.to_numeric(weights["target_weight"], errors="coerce").fillna(0.0)
    min_w = float((config.get("portfolio") or {}).get("optimizer_weight_epsilon", 0.005))
    targets = weights[(weights["ticker"].astype(str).str.upper() != "CASH") & (weights["target_weight"] >= max(min_w, 1e-6))]
    tw = dict(zip(targets["ticker"], targets["target_weight"]))

    flags = {}
    vpath = run_dir / "F_FINAL_VALUATION_HANDOFF.parquet"
    if vpath.exists():
        v = pd.read_parquet(vpath)
        if "valuation_review_severity" in v.columns:
            flags = {t: s for t, s in zip(v["ticker"], v["valuation_review_severity"]) if s in ("REVIEW", "CRITICAL_REVIEW")}

    acct = load_account(root, cfg)
    pos = load_positions(root)
    val = valuation(root, session, acct, pos)
    nav = val["nav"]
    nav_path = pdir(root) / "nav.csv"
    if not nav_path.exists():
        # opening row: both the account and SPY are measured from this date
        pd.DataFrame([{"session": str(pd.Timestamp(session).date()), "nav": round(nav, 2), "cash": round(acct["cash"], 2),
                       "positions_value": 0.0, "positions": 0, "invested": 0.0,
                       "spy_close": close_on(root, "SPY", session), "missing_prices": ""}]).to_csv(nav_path, index=False)
    cur = dict(zip(pos["ticker"], pos["shares"]))
    rows = []
    for tk in sorted(set(tw) | set(cur)):
        ref = close_on(root, tk, session)
        if ref is None or ref <= 0:
            rows.append({"ticker": tk, "side": "", "shares": 0, "action": "SKIP", "reason": "no price in local cache",
                         "current_shares": cur.get(tk, 0), "target_weight": tw.get(tk, 0.0)})
            continue
        target_sh = tw.get(tk, 0.0) * nav / ref
        if cfg["whole_shares"]:
            target_sh = math.floor(target_sh)
        delta = target_sh - cur.get(tk, 0.0)
        if abs(delta) < 1e-9:
            continue
        value = delta * ref
        is_exit = tk not in tw and cur.get(tk, 0) > 0
        small = abs(value) < cfg["min_order_value_pct"] * nav and not is_exit
        reason = ("exit: no longer in model" if is_exit else
                  "new position" if cur.get(tk, 0) == 0 else
                  "increase to target" if delta > 0 else "reduce to target")
        rows.append({
            "ticker": tk, "side": "BUY" if delta > 0 else "SELL", "shares": abs(delta),
            "action": "SKIP" if small else "EXECUTE", "limit_price": "", "fill_price": "",
            "ref_price": round(ref, 4), "est_value": round(value, 2),
            "current_shares": cur.get(tk, 0), "target_shares": target_sh,
            "target_weight": round(tw.get(tk, 0.0), 6),
            "reason": reason + (" (below minimum order size)" if small else ""),
            "flag": {"REVIEW": "valuation review", "CRITICAL_REVIEW": "critical valuation review"}.get(flags.get(tk), ""),
            "note": "",
        })
    df = pd.DataFrame(rows, columns=[c for c in ORDER_COLUMNS if c != "order_id"])
    if not df.empty:
        df["_abs"] = df["est_value"].abs()
        df["_side"] = df["side"].map({"SELL": 0, "BUY": 1}).fillna(2)
        df = df.sort_values(["_side", "_abs"], ascending=[True, False]).drop(columns=["_abs", "_side"])
    df.insert(0, "order_id", [f"{session}-{i+1:02d}" for i in range(len(df))])
    path = pdir(root) / "orders" / f"{session}_proposed.csv"
    header = (f"# Paper orders proposed from run {run_id} (market data {session}). NAV {nav:,.2f}, cash {val['cash']:,.2f}.\n"
              "# Edit freely: shares, action (EXECUTE/SKIP), limit_price, fill_price, note; add or delete rows.\n"
              "# Then run scripts\\paper_approve.bat. Nothing fills until approved.\n")
    path.write_text(header + df.to_csv(index=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 2-3. approve
# ---------------------------------------------------------------------------

def read_orders(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, comment="#", dtype={"order_id": str, "ticker": str})
    for c in ORDER_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["side"] = df["side"].astype(str).str.strip().str.upper()
    df["action"] = df["action"].fillna("EXECUTE").astype(str).str.strip().str.upper()
    for c in ["shares", "limit_price", "fill_price", "ref_price"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def validate_orders(df: pd.DataFrame) -> list[str]:
    errs = []
    live = df[df["action"] == "EXECUTE"]
    for r in live.itertuples():
        if r.side not in ("BUY", "SELL"):
            errs.append(f"{r.ticker}: side must be BUY or SELL (got {r.side!r})")
        if not (isinstance(r.shares, float) and r.shares > 0):
            errs.append(f"{r.ticker}: shares must be a positive number")
    bad = set(df["action"]) - {"EXECUTE", "SKIP"}
    if bad:
        errs.append(f"action must be EXECUTE or SKIP (found {sorted(bad)})")
    return errs


def _session_open_utc(sess) -> pd.Timestamp:
    """09:30 New York on that session date, in UTC (handles daylight saving)."""
    return pd.Timestamp(f"{pd.Timestamp(sess).date()} 09:30", tz="America/New_York").tz_convert("UTC")


def approve_orders(root: Path, path: Path | None = None, approved_at: pd.Timestamp | None = None) -> Path:
    if path is None:
        props = _orders_files(root, "proposed")
        if not props:
            raise RuntimeError("No proposed orders to approve.")
        path = props[-1]
    path = Path(path)
    df = read_orders(path)
    errs = validate_orders(df)
    if errs:
        raise RuntimeError("Orders not approved:\n  " + "\n  ".join(errs))
    approved_at = pd.Timestamp(approved_at) if approved_at is not None else pd.Timestamp.now(tz="UTC")
    if approved_at.tzinfo is None:
        approved_at = approved_at.tz_localize("UTC")
    df["approved_at_utc"] = approved_at.tz_convert("UTC").isoformat(timespec="seconds")
    df["status"] = np.where(df["action"] == "EXECUTE", "OPEN", "SKIPPED")
    df["filled_shares"] = 0.0
    df["filled_price"] = np.nan
    df["filled_session"] = ""
    out = path.with_name(path.name.replace("_proposed", "_approved"))
    df.to_csv(out, index=False)
    return out


# ---------------------------------------------------------------------------
# 4-5. fill + mark
# ---------------------------------------------------------------------------

def _fill_price(root: Path, r, session: pd.Timestamp):
    if pd.notna(r.fill_price) and r.fill_price > 0:
        return float(r.fill_price), "manual price"
    bar = price_frame(root, r.ticker)
    bar = bar[bar["date"] == session]
    if bar.empty:
        return None, "no bar"
    b = bar.iloc[0]
    o = float(b.get("open", np.nan)) if pd.notna(b.get("open", np.nan)) else float(b["close"])
    lo = float(b.get("low", o)) if pd.notna(b.get("low", np.nan)) else o
    hi = float(b.get("high", o)) if pd.notna(b.get("high", np.nan)) else o
    lim = r.limit_price
    if pd.isna(lim) or lim <= 0:
        return o, "open"
    if r.side == "BUY":
        return (o, "open (below limit)") if o <= lim else ((float(lim), "limit") if lo <= lim else (None, "limit not reached"))
    return (o, "open (above limit)") if o >= lim else ((float(lim), "limit") if hi >= lim else (None, "limit not reached"))


def process(root: Path, config: dict | None = None, upto=None) -> dict:
    """Fill approved open orders for every session not yet processed, then mark NAV."""
    config = config if config is not None else load_config(root)
    cfg = paper_cfg(config)
    root = Path(root)
    acct = load_account(root, cfg)
    pos = load_positions(root)
    fills_path = pdir(root) / "fills.csv"
    fills = _read(fills_path)
    new_fills = []
    last = latest_session(root)
    if last is None:
        return {"filled": 0, "nav": None}
    upto = pd.Timestamp(upto) if upto is not None else last

    for path in _orders_files(root, "approved"):
        od = pd.read_csv(path, dtype={"order_id": str, "ticker": str})
        for c in ("note", "filled_session", "status", "flag", "reason", "side"):
            if c in od.columns:
                od[c] = od[c].astype(object).where(od[c].notna(), "")
        for c in ("shares", "limit_price", "fill_price", "filled_shares", "filled_price"):
            if c in od.columns:
                od[c] = pd.to_numeric(od[c], errors="coerce")
        if not (od["status"] == "OPEN").any():
            continue
        approved_at = pd.Timestamp(str(od["approved_at_utc"].iloc[0]))
        proposed_session = pd.Timestamp(path.name[:10])
        # Eligible sessions: after the data date the orders were sized on, and
        # whose 09:30 New York open is after the moment you approved.
        sessions = [s for s in sessions_after(root, proposed_session)
                    if s <= upto and _session_open_utc(s) > approved_at]
        changed = False
        for k, sess in enumerate(sessions):
            open_mask = od["status"] == "OPEN"
            if not open_mask.any():
                break
            # sells first, then buys (so sale proceeds fund purchases)
            for side in ("SELL", "BUY"):
                for i in od.index[open_mask & (od["side"] == side)]:
                    r = od.loc[i]
                    px, how = _fill_price(root, r, sess)
                    if px is None:
                        continue
                    shares = float(r["shares"])
                    held = float(pos.loc[pos["ticker"] == r["ticker"], "shares"].sum())
                    if side == "SELL":
                        shares = min(shares, held)
                        if shares <= 0:
                            od.loc[i, "status"] = "REJECTED"
                            od.loc[i, "note"] = f"{r.get('note') or ''} no shares to sell".strip()
                            changed = True
                            continue
                    cost_rate = cfg["transaction_cost_rate"]
                    if side == "BUY":
                        affordable = acct["cash"] / (px * (1 + cost_rate))
                        if cfg["whole_shares"]:
                            affordable = math.floor(affordable)
                        if affordable < shares:
                            shares = max(0.0, affordable)
                            od.loc[i, "note"] = f"{r.get('note') or ''} cut to cash available".strip()
                        if shares <= 0:
                            od.loc[i, "status"] = "REJECTED"
                            changed = True
                            continue
                    gross = shares * px
                    fee = gross * cost_rate
                    if side == "BUY":
                        acct["cash"] -= gross + fee
                        if (pos["ticker"] == r["ticker"]).any():
                            j = pos.index[pos["ticker"] == r["ticker"]][0]
                            tot = pos.at[j, "shares"] + shares
                            pos.at[j, "avg_cost"] = (pos.at[j, "shares"] * pos.at[j, "avg_cost"] + gross + fee) / tot
                            pos.at[j, "shares"] = tot
                        else:
                            pos = pd.concat([pos, pd.DataFrame([{"ticker": r["ticker"], "shares": shares,
                                                                 "avg_cost": (gross + fee) / shares}])], ignore_index=True)
                        realized = 0.0
                    else:
                        j = pos.index[pos["ticker"] == r["ticker"]][0]
                        realized = shares * (px - pos.at[j, "avg_cost"]) - fee
                        acct["cash"] += gross - fee
                        pos.at[j, "shares"] -= shares
                    od.loc[i, "status"] = "FILLED" if shares >= float(r["shares"]) - 1e-9 else "PARTIAL"
                    od.loc[i, "filled_shares"] = shares
                    od.loc[i, "filled_price"] = round(px, 4)
                    od.loc[i, "filled_session"] = str(sess.date())
                    new_fills.append({"session": str(sess.date()), "order_id": r["order_id"], "ticker": r["ticker"],
                                      "side": side, "shares": shares, "price": round(px, 4), "how": how,
                                      "gross": round(gross, 2), "fee": round(fee, 2), "realized_pl": round(realized, 2),
                                      "cash_after": round(acct["cash"], 2), "orders_file": path.name})
                    changed = True
            if k + 1 >= int(cfg["order_expiry_sessions"]):
                exp = od["status"] == "OPEN"
                if exp.any():
                    od.loc[exp, "status"] = "EXPIRED"
                    changed = True
                break
        if changed:
            od.to_csv(path, index=False)

    if new_fills:
        fills = pd.concat([fills, pd.DataFrame(new_fills)], ignore_index=True)
        fills.to_csv(fills_path, index=False)
    pos = pos[pos["shares"].abs() > 1e-9]
    save_positions(root, pos)

    # cash interest (simple daily accrual over calendar days), then mark NAV
    rate = float(cfg["cash_annual_rate"] or 0.0)
    prev = acct.get("last_cash_accrual_session")
    if rate and prev:
        days = (upto - pd.Timestamp(prev)).days
        if days > 0:
            acct["cash"] *= (1 + rate) ** (days / 365.0)
    acct["last_cash_accrual_session"] = str(upto.date())

    v = valuation(root, upto, acct, pos)
    nav_path = pdir(root) / "nav.csv"
    nav = _read(nav_path)
    spy = close_on(root, "SPY", upto)
    row = {"session": v["session"], "nav": round(v["nav"], 2), "cash": round(v["cash"], 2),
           "positions_value": round(v["positions_value"], 2), "positions": int(len(v["detail"])),
           "invested": round(v["positions_value"] / v["nav"], 6) if v["nav"] else 0.0,
           "spy_close": spy, "missing_prices": "|".join(v["missing_prices"])}
    if not nav.empty:
        nav = nav[nav["session"].astype(str) != row["session"]]
    nav = pd.concat([nav, pd.DataFrame([row])], ignore_index=True).sort_values("session")
    nav.to_csv(nav_path, index=False)
    acct["last_marked_session"] = row["session"]
    save_account(root, acct)
    write_optimizer_state(root, upto)
    return {"filled": len(new_fills), "nav": row["nav"], "session": row["session"]}


# ---------------------------------------------------------------------------
# summary for dashboards
# ---------------------------------------------------------------------------

def summary(root: Path, max_nav_rows: int = 400) -> dict:
    root = Path(root)
    d = pdir(root)
    if not (d / "account.json").exists():
        return {}
    acct = json.loads((d / "account.json").read_text(encoding="utf-8"))
    nav = _read(d / "nav.csv")
    last = acct.get("last_marked_session")
    v = valuation(root, last) if last else None
    pending = []
    for p in _orders_files(root, "approved")[-2:]:
        od = pd.read_csv(p, dtype={"order_id": str})
        pending += od[od["status"] == "OPEN"][["order_id", "ticker", "side", "shares", "limit_price"]].to_dict("records")
    proposals = _orders_files(root, "proposed")
    awaiting = None
    if proposals and not proposals[-1].with_name(proposals[-1].name.replace("_proposed", "_approved")).exists():
        od = read_orders(proposals[-1])
        awaiting = {"file": proposals[-1].name,
                    "orders": od[["ticker", "side", "shares", "action", "ref_price", "est_value", "flag"]].to_dict("records")}
    fills = _read(d / "fills.csv")

    def clean(o):
        if isinstance(o, float):
            return None if (math.isnan(o) or math.isinf(o)) else round(o, 6)
        if isinstance(o, dict):
            return {k: clean(x) for k, x in o.items()}
        if isinstance(o, list):
            return [clean(x) for x in o]
        if isinstance(o, (np.floating,)):
            return clean(float(o))
        if isinstance(o, (np.integer,)):
            return int(o)
        return o

    first = nav.iloc[0] if not nav.empty else None
    lastrow = nav.iloc[-1] if not nav.empty else None
    perf = None
    if first is not None:
        perf = {"since": first["session"], "nav_return": float(lastrow["nav"]) / float(acct["initial_cash"]) - 1,
                "spy_return": (float(lastrow["spy_close"]) / float(first["spy_close"]) - 1)
                if pd.notna(first["spy_close"]) and pd.notna(lastrow["spy_close"]) else None}
    return clean({
        "initial_cash": acct["initial_cash"], "cash": acct["cash"], "last_marked_session": last,
        "nav": acct["cash"] if v is None else v["nav"], "performance": perf,
        "positions": [] if v is None or v["detail"].empty else v["detail"].round(6).to_dict("records"),
        "nav_history": nav.tail(max_nav_rows)[["session", "nav", "invested", "spy_close"]].to_dict("records") if not nav.empty else [],
        "pending_orders": pending, "awaiting_approval": awaiting,
        "recent_fills": fills.tail(30).to_dict("records") if not fills.empty else [],
    })


# ---------------------------------------------------------------------------
# pipeline hook + CLI
# ---------------------------------------------------------------------------

def after_run(root: Path, run_dir: Path, config: dict, log=print) -> dict:
    """Called after every successful production run (non-blocking)."""
    if not bool((config.get("paper") or {}).get("enabled", False)):
        return {}
    res = process(root, config)
    log(f"Paper account: filled {res['filled']} order(s); NAV {res['nav']:,.2f} at {res['session']}")
    path = propose_orders(root, run_dir, config=config)
    if path:
        log(f"Paper account: monthly rebalance orders proposed -> {path} (edit, then approve)")
    return {**res, "proposed": str(path) if path else None}


def _latest_run_dir(root: Path) -> Path:
    p = Path(root) / "outputs" / "state" / "latest_run.json"
    return Path(json.loads(p.read_text(encoding="utf-8"))["run_dir"])


def _main(argv):
    from .runtime import repository_root
    root = repository_root()
    cmd = argv[1] if len(argv) > 1 else "status"
    rest = [a for a in argv[2:] if not a.startswith("--")]
    if cmd == "propose":
        path = propose_orders(root, Path(rest[0]) if rest else _latest_run_dir(root), force="--force" in argv)
        print(path or "Not due: orders were already proposed this month (use --force).")
    elif cmd == "approve":
        print("Approved ->", approve_orders(root, Path(rest[0]) if rest else None))
    elif cmd == "process":
        print(process(root))
    else:
        s = summary(root)
        print(json.dumps({k: s.get(k) for k in ["nav", "cash", "last_marked_session", "performance", "pending_orders"]}, indent=1, default=str))
        if s.get("awaiting_approval"):
            print("Awaiting approval:", s["awaiting_approval"]["file"])


if __name__ == "__main__":
    _main(sys.argv)
