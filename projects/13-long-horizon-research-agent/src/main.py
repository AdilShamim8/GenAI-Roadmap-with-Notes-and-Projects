"""Long-horizon agent — checkpoints, budget guard, critic loop, escalation.

Encodes 06-multi-agent/04: durable steps (resume from last checkpoint),
cost caps with mechanical escalation triggers, critic with fresh context."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Run:
    plan: list[str]
    completed: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    cost_spent: float = 0.0
    escalated: bool = False


class LongHorizonAgent:
    def __init__(self, budget: float = 10.0, max_step_cost: float = 3.0, max_steps: int = 20):
        self.budget, self.max_step_cost, self.max_steps = budget, max_step_cost, max_steps

    def step(self, run: Run, step_fn) -> str:
        """Execute one plan step; returns verdict: continue | done | escalate."""
        if run.completed and len(run.completed) >= len(run.plan):
            return "done"
        next_task = run.plan[len(run.completed)]
        cost, artifact = step_fn(next_task)  # injected; may raise
        if cost > self.max_step_cost:
            return "escalate"  # mechanical trigger: expensive step
        run.cost_spent += cost
        if run.cost_spent > self.budget:
            return "escalate"  # mechanical trigger: budget breach
        run.completed.append(next_task)
        run.artifacts[next_task] = artifact
        if len(run.completed) >= len(run.plan):
            return "done"
        return "continue"

    def run(self, run: Run, step_fn, critic=None) -> dict:
        """Loop with periodic critic review (fresh context: plan + summaries,
        never the worker's full history — drift detection without inherited frames)."""
        steps = 0
        while steps < self.max_steps:
            steps += 1
            verdict = self.step(run, step_fn)
            if verdict == "escalate":
                run.escalated = True
                return {"status": "escalated", "completed": len(run.completed), "cost": run.cost_spent}
            if verdict == "done":
                if critic and not critic(run.plan, run.artifacts):
                    return {"status": "critic_rejected", "completed": len(run.completed), "cost": run.cost_spent}
                return {"status": "done", "completed": len(run.completed), "cost": run.cost_spent}
        return {"status": "max_steps", "completed": len(run.completed), "cost": run.cost_spent}
