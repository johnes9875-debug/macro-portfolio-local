from __future__ import annotations

from pathlib import Path
import pandas as pd

from .snapshot import load_object, load_pointer


def _first_col(df, candidates):
    if not isinstance(df, pd.DataFrame):
        return None
    return next((c for c in candidates if c in df.columns), None)


def _compare_frame(prev, cur, object_name, key_candidates, fields, min_abs_delta=0.0, both_only=False):
    rows = []
    if not isinstance(prev, pd.DataFrame) or not isinstance(cur, pd.DataFrame):
        return rows
    key = _first_col(cur, key_candidates)
    if key is None or key not in prev.columns:
        return rows
    p = prev.drop_duplicates(key).set_index(key)
    c = cur.drop_duplicates(key).set_index(key)
    idents = set(p.index) & set(c.index) if both_only else set(p.index) | set(c.index)
    for ident in sorted(idents, key=str):
        for field in fields:
            if field not in p.columns or field not in c.columns:
                continue
            old = p[field].get(ident) if ident in p.index else None
            new = c[field].get(ident) if ident in c.index else None
            if pd.isna(old) and pd.isna(new):
                continue
            changed = str(old) != str(new)
            delta = None
            try:
                delta = float(new) - float(old)
                if abs(delta) <= min_abs_delta:
                    changed = False
            except Exception:
                pass
            if changed:
                rows.append({
                    "object": object_name,
                    "id": str(ident),
                    "field": field,
                    "previous": old,
                    "current": new,
                    "delta": delta,
                })
    return rows


def build_daily_changes(project_root: Path, current_run_dir: Path) -> pd.DataFrame:
    # build_daily_changes runs BEFORE publish_latest(), so the prior successful
    # run is still the "latest" pointer here (previous_run.json lags one run).
    previous = None
    for which in ("latest", "previous"):
        ptr = load_pointer(project_root, which)
        if ptr and Path(ptr["run_dir"]).resolve() != Path(current_run_dir).resolve() and Path(ptr["run_dir"]).exists():
            previous = ptr
            break
    if not previous:
        out = pd.DataFrame(columns=["object", "id", "field", "previous", "current", "delta"])
        out.to_parquet(current_run_dir / "daily_changes.parquet", index=False)
        (current_run_dir / "daily_brief.md").write_text(
            "# Daily model brief\n\nFirst local production snapshot. No prior run is available for comparison.\n",
            encoding="utf-8",
        )
        return out

    prev_dir = Path(previous["run_dir"])
    rows = []
    # Ordered by importance; only decision-relevant fields (prices change every run).
    specs = [
        ("G_FINAL_PORTFOLIO_WEIGHTS", ["ticker"], ["target_weight"], 0.0025),
        ("FINAL_SECTOR_SIGNAL_DASHBOARD", ["ticker", "sector_ticker", "sector"],
         ["combined_signal", "macro_market_alignment"], 0.0),
        ("F_FINAL_VALUATION_HANDOFF", ["ticker"],
         ["mos_threshold_met", "valuation_review_severity", "valuation_entry_eligible"], 0.0),
        ("I_FINAL_ACTION_BOOK", ["ticker"], ["decision_category"], 0.0),
    ]
    for obj, keys, fields, threshold in specs:
        prev_df = load_object(prev_dir, obj)
        cur_df = load_object(current_run_dir, obj)
        both_only = obj != "G_FINAL_PORTFOLIO_WEIGHTS"  # universe churn is summarised separately
        rows.extend(_compare_frame(prev_df, cur_df, obj, keys, fields, threshold, both_only))
        if obj == "F_FINAL_VALUATION_HANDOFF" and isinstance(prev_df, pd.DataFrame) and isinstance(cur_df, pd.DataFrame) \
                and "ticker" in prev_df.columns and "ticker" in cur_df.columns:
            entered = sorted(set(cur_df["ticker"]) - set(prev_df["ticker"]))
            left = sorted(set(prev_df["ticker"]) - set(cur_df["ticker"]))

    changes = pd.DataFrame(rows, columns=["object", "id", "field", "previous", "current", "delta"])
    # previous/current mix numbers, bools and text across fields; parquet needs one type.
    for col in ("previous", "current"):
        changes[col] = changes[col].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    changes["delta"] = pd.to_numeric(changes["delta"], errors="coerce")
    changes.to_parquet(current_run_dir / "daily_changes.parquet", index=False)

    entered = locals().get("entered", [])
    left = locals().get("left", [])
    lines = ["# Daily model brief", "", f"Compared with run `{previous.get('run_id')}` ({previous.get('market_session')}).", ""]
    if changes.empty:
        lines.append("No material tracked changes versus the previous successful run.")
    else:
        lines.append(f"Material tracked changes: **{len(changes)}**")
        lines.append("")
        for _, r in changes.head(30).iterrows():
            if r["field"] == "target_weight":
                fmt = lambda v: "0%" if v is None or pd.isna(v) or str(v) == "nan" else f"{float(v):.1%}"
                lines.append(f"- **{r['id']}** — weight {fmt(r['previous'])} → {fmt(r['current'])}")
                continue
            delta = "" if pd.isna(r["delta"]) else f" (Δ {r['delta']:+.4f})"
            lines.append(f"- **{r['id']}** — {r['field']}: `{r['previous']}` → `{r['current']}`{delta}")
        if len(changes) > 30:
            lines.append(f"- …and {len(changes)-30} additional changes in `daily_changes.parquet`.")
    if entered or left:
        lines += ["", f"Research universe: {len(entered)} names entered, {len(left)} left."]
    (current_run_dir / "daily_brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changes
