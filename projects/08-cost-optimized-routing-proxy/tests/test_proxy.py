import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import RoutingProxy


def test_task_type_routing_zero_misroute():
    p = RoutingProxy()
    assert p.route("extract") == "cheap"
    assert p.route("analyze") == "balanced"
    assert p.route("verify") == "flagship"
    assert p.route("unknown") == "balanced"  # safe default


def test_budget_guard_blocks():
    p = RoutingProxy(budget_usd=0.001)
    r = p.call("verify", est_in=1_000_000, est_out=10_000)  # ~$10.5
    assert not r["ok"] and r["error"] == "budget exceeded"


def test_attribution_by_tier():
    p = RoutingProxy(budget_usd=10)
    p.call("extract", 100_000, 1_000)
    p.call("analyze", 10_000, 1_000)
    by = p.cost_by_tier()
    assert set(by) == {"cheap", "balanced"} and by["balanced"] > by["cheap"] * 10
