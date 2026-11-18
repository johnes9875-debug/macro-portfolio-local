import json
import sys
from pathlib import Path

from macro_portfolio import run_control as rc


def test_start_status_finish(tmp_path, monkeypatch):
    (tmp_path / "outputs/state").mkdir(parents=True)
    (tmp_path / "outputs/state/latest_run.json").write_text(json.dumps({"run_id": "OLD"}))
    snaps = tmp_path / "ledger/snapshots"; snaps.mkdir(parents=True)
    # fake pipeline: writes a new pointer and snapshot, then exits
    fake = tmp_path / "fake.py"
    fake.write_text(
        "import json,pathlib,sys\n"
        f"r=pathlib.Path(r'{tmp_path}')\n"
        "(r/'ledger/snapshots/2026-11-18_NEW.json').write_text('{\"run_id\":\"NEW\"}')\n"
        "(r/'outputs/state/latest_run.json').write_text(json.dumps({'run_id':'NEW'}))\n")
    real_popen = rc.subprocess.Popen
    monkeypatch.setattr(rc.subprocess, "Popen", lambda cmd, **kw: real_popen([sys.executable, str(fake)], **kw))
    st = rc.start(tmp_path)
    assert st["state"] == "running" and st["previous_run_id"] == "OLD"
    assert rc.start(tmp_path)["pid"] == st["pid"] or rc.status(tmp_path)["state"] != "running"  # no double start
    import time
    for _ in range(50):
        if rc.status(tmp_path)["state"] != "running":
            break
        time.sleep(0.1)
    assert rc.status(tmp_path)["state"] == "finished"
    assert json.loads((tmp_path / "ledger/latest_snapshot.json").read_text())["run_id"] == "NEW"


def test_failed_when_no_new_pointer(tmp_path, monkeypatch):
    (tmp_path / "outputs/state").mkdir(parents=True)
    (tmp_path / "outputs/state/latest_run.json").write_text(json.dumps({"run_id": "OLD"}))
    real_popen = rc.subprocess.Popen
    monkeypatch.setattr(rc.subprocess, "Popen", lambda cmd, **kw: real_popen([sys.executable, "-c", "raise SystemExit(1)"], **kw))
    rc.start(tmp_path)
    import time
    for _ in range(50):
        if rc.status(tmp_path)["state"] != "running":
            break
        time.sleep(0.1)
    assert rc.status(tmp_path)["state"] == "failed"
