"""Multi-agent research pipeline — supervisor + context-isolated workers.

Encodes 06-multi-agent/01 + 05: workers get one job each with typed failure
modes; the supervisor composes results and stays in control (agent-as-tool,
not handoff). LLM calls are injected fns so tests run offline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    source: str
    fact: str
    confidence: float


class Worker:
    """One job, typed failures, own context (findings never leak between
    workers — isolation is the point)."""

    def __init__(self, name: str, run_fn):
        self.name, self.run_fn = name, run_fn

    def run(self, task: str) -> list[Finding] | None:
        out = self.run_fn(task)
        if out is None:  # typed failure: insufficient evidence
            return None
        return [Finding(**f) if isinstance(f, dict) else f for f in out]


@dataclass
class Supervisor:
    workers: list[Worker] = field(default_factory=list)
    correlation_id: str = "run-0"

    def research(self, question: str, synthesizer=None) -> dict:
        events = []
        findings: list[Finding] = []
        for w in self.workers:
            result = w.run(question)
            events.append({"agent": w.name, "correlation_id": self.correlation_id, "ok": result is not None})
            if result:
                findings.extend(result)
        # goal predicate: enough verified findings = done (checkable, not felt)
        done = len(findings) >= 1 and all(f.confidence >= 0.5 for f in findings)
        answer = synthesizer(question, findings) if (synthesizer and done) else None
        return {"done": done, "findings": [f.__dict__ for f in findings], "answer": answer, "events": events}


def main() -> None:
    def fake_search(q):
        return [{"source": "web", "fact": f"about {q}", "confidence": 0.8}]
    sup = Supervisor(workers=[Worker("searcher", fake_search)])
    out = sup.research("MoE routing")
    print(out["done"], len(out["findings"]))


if __name__ == "__main__":
    main()
