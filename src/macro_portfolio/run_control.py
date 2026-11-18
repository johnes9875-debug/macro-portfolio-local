"""Start the full pipeline from the dashboard and follow it.

The run happens in a separate background process (the same thing
scripts\\run_once.bat does), so closing or refreshing the browser does not
stop it. Progress goes to outputs/state/manual_run.log; a status file stops
two runs at once. When the run finishes, the pipeline itself records the
ledger, writes the cockpit, pushes ledger/ to GitHub (if enabled) and moves
the "latest run" pointer, so the dashboard shows the new entry on its next
refresh. It also copies the snapshot to ledger/latest_snapshot.json for the
Claude page's "Load new run" button.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _paths(root: Path):
    d = Path(root) / "outputs" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d / "manual_run.json", d / "manual_run.log"


_PROCS: dict[int, subprocess.Popen] = {}   # handles for runs started by this server process


def _alive(pid: int) -> bool:
    if not pid:
        return False
    if pid in _PROCS:                       # reaps the child, so no zombie
        return _PROCS[pid].poll() is None
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pointer(root: Path) -> dict:
    p = Path(root) / "outputs" / "state" / "latest_run.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def status(root: Path) -> dict:
    sp, lp = _paths(root)
    st = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    if st.get("state") == "running" and not _alive(int(st.get("pid") or 0)):
        ptr = _pointer(root)
        ok = bool(ptr) and ptr.get("run_id") != st.get("previous_run_id")   # a new successful run was recorded
        st.update(state="finished" if ok else "failed", finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        sp.write_text(json.dumps(st), encoding="utf-8")
        if ok:
            export_latest_snapshot(root)
    return st


def start(root: Path, force: bool = True) -> dict:
    root = Path(root)
    cur = status(root)
    if cur.get("state") == "running":
        return cur
    sp, lp = _paths(root)
    cmd = [sys.executable, "-u", "-m", "macro_portfolio.scheduler"] + (["--force"] if force else [])
    env = dict(os.environ, PYTHONPATH=str(root / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""), PYTHONIOENCODING="utf-8")
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    log = open(lp, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, **kw)
    _PROCS[proc.pid] = proc
    st = {"state": "running", "pid": proc.pid, "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "command": " ".join(cmd), "previous_run_id": _pointer(root).get("run_id")}
    sp.write_text(json.dumps(st), encoding="utf-8")
    return st


def log_tail(root: Path, lines: int = 25) -> str:
    _, lp = _paths(root)
    if not lp.exists():
        return ""
    return "\n".join(lp.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def export_latest_snapshot(root: Path) -> Path | None:
    """Copy the newest ledger snapshot to ledger/latest_snapshot.json (git-ignored)."""
    snaps = sorted((Path(root) / "ledger" / "snapshots").glob("*.json"))
    if not snaps:
        return None
    out = Path(root) / "ledger" / "latest_snapshot.json"
    out.write_bytes(snaps[-1].read_bytes())
    return out
