import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import LongHorizonAgent, Run


def ok_step(task):
    return 1.0, f"artifact:{task}"


def test_happy_completion_with_critic():
    agent = LongHorizonAgent(budget=10)
    run = Run(plan=["research", "write"])
    out = agent.run(run, ok_step, critic=lambda plan, arts: len(arts) == len(plan))
    assert out["status"] == "done" and out["completed"] == 2


def test_budget_breach_escalates():
    agent = LongHorizonAgent(budget=2.0)
    run = Run(plan=["a", "b", "c"])
    out = agent.run(run, ok_step)  # 1.0 each -> breaches at 3rd
    assert out["status"] == "escalated" and run.escalated


def test_expensive_single_step_escalates():
    agent = LongHorizonAgent(budget=100, max_step_cost=2.0)
    run = Run(plan=["one"])
    assert agent.run(run, lambda t: (5.0, "x"))["status"] == "escalated"


def test_critic_rejection_reported():
    agent = LongHorizonAgent()
    run = Run(plan=["a"])
    out = agent.run(run, ok_step, critic=lambda p, a: False)
    assert out["status"] == "critic_rejected"


def test_resume_from_partial_state():
    agent = LongHorizonAgent()
    run = Run(plan=["a", "b"], completed=["a"], artifacts={"a": "x"})
    out = agent.run(run, ok_step)
    assert out["status"] == "done" and out["completed"] == 2  # checkpoint resume
