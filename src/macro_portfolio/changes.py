from __future__ import annotations

from pathlib import Path
import pandas as pd

from .snapshot import load_object, load_pointer


def _first_col(df, candidates):
    if not isinstance(df, pd.DataFrame):
        return None
    return next((c for c in candidates if c in df.columns), None)


def _compare_frame(prev, cur, object_name, key_candidates, fields, min_abs_delta=0.0):
    rows = []
    if not isinstance(prev, pd.DataFrame) or not isinstance(cur, pd.DataFrame):
        return rows
    key = _first_col(cur, key_candidates)
    if key is None or key not in prev.columns:
        return rows
    p = prev.drop_duplicates(key).set_index(key)
    c = cur.drop_duplicates(key).set_index(key)
    for ident in sorted(set(p.index).union(c.index), key=str):
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
    previous = load_pointer(project_root, "previous")
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
    specs = [
        ("FINAL_SECTOR_SIGNAL_DASHBOARD", ["ticker", "sector_ticker", "sector"],
         ["stock_research_scope", "final_signal", "decision", "status"], 0.0),
        ("F_FINAL_VALUATION_HANDOFF", ["ticker"],
         ["mos_threshold_met", "expected_upside_pct", "current_price", "mos_price_threshold"], 0.005),
        ("G_FINAL_PORTFOLIO_WEIGHTS", ["ticker"],
         ["target_weight", "portfolio_weight", "weight"], 0.0025),
        ("I_FINAL_ACTION_BOOK", ["ticker"],
         ["action", "research_status", "decision", "target_weight"], 0.0025),
    ]
    for obj, keys, fields, threshold in specs:
        prev_df = load_object(prev_dir, obj)
        cur_df = load_object(current_run_dir, obj)
        rows.extend(_compare_frame(prev_df, cur_df, obj, keys, fields, threshold))

    changes = pd.DataFrame(rows, columns=["object", "id", "field", "previous", "current", "delta"])
    changes.to_parquet(current_run_dir / "daily_changes.parquet", index=False)

    lines = ["# Daily model brief", ""]
    if changes.empty:
        lines.append("No material tracked changes versus the previous successful run.")
    else:
        lines.append(f"Material tracked changes: **{len(changes)}**")
        lines.append("")
        for _, r in changes.head(30).iterrows():
            delta = "" if pd.isna(r["delta"]) else f" (Δ {r['delta']:+.4f})"
            lines.append(f"- **{r['id']}** — {r['field']}: `{r['previous']}` → `{r['current']}`{delta}")
        if len(changes) > 30:
            lines.append(f"- …and {len(changes)-30} additional changes in `daily_changes.parquet`.")
    (current_run_dir / "daily_brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changes
