import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import Finding, Supervisor, Worker


def good(q):
    return [{"source": "s", "fact": "f1", "confidence": 0.9}]


def insufficient(q):
    return None  # typed failure


def low_conf(q):
    return [{"source": "s", "fact": "f", "confidence": 0.2}]


def test_composition_and_goal_predicate():
    sup = Supervisor(workers=[Worker("a", good), Worker("b", good)])
    out = sup.research("q")
    assert out["done"] and len(out["findings"]) == 2


def test_typed_failure_recorded_not_raised():
    sup = Supervisor(workers=[Worker("bad", insufficient), Worker("ok", good)])
    out = sup.research("q")
    assert any(not e["ok"] for e in out["events"])
    assert out["done"]  # the good worker's evidence suffices


def test_low_confidence_fails_goal_predicate():
    assert not Supervisor(workers=[Worker("x", low_conf)]).research("q")["done"]


def test_synthesizer_sees_findings():
    sup = Supervisor(workers=[Worker("a", good)])
    out = sup.research("q", synthesizer=lambda q, fs: f"answer from {len(fs)}")
    assert out["answer"] == "answer from 1"
