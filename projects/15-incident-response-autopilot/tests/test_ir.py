import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import IncidentAutopilot


def setup():
    ap = IncidentAutopilot()
    ap.register_run("r1", ["email", "db"])
    ap.register_run("r2", ["search"])
    ap.recall.record("r1", "sent_email", "user_42", "wrong price quoted")
    ap.recall.record("r2", "posted_reply", "user_7")
    return ap


def test_kill_plus_quarantine():
    ap = setup()
    out = ap.handle_incident()
    assert out["kill_switch"] and set(out["quarantined_runs"]) == {"r1", "r2"}


def test_quarantine_revokes_tools_not_just_flag():
    ap = setup()
    ap.handle_incident()
    assert ap.runs["r1"].tools == []  # can't act even if loop lives


def test_recall_index_measures_delivered_harm():
    ap = setup()
    ap.handle_incident()
    affected = ap.recall.affected("user_42")
    assert len(affected) == 1 and "wrong price" in affected[0]["detail"]


def test_new_requests_blocked_after_kill():
    ap = setup()
    ap.kill()
    assert ap.kill_switch is True  # gateway consults this before accepting work
