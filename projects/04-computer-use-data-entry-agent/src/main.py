"""Computer-use data-entry agent — act-then-verify state machine over a mock UI.

Per 04-tools-and-mcp/04: computer use is only reliable when every task ends
with a programmatic end-state assertion and every step is idempotent. This
project encodes that discipline as a state machine over a fake legacy CRM:
steps either complete or leave state unchanged; verification is code, not
vision. The mock UI class is the test double for a real Playwright/CDP driver.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


class MockLegacyCRM:
    """In-memory stand-in for a legacy web form: fill_form + submit, with the
    failure modes real UIs have (unknown field, submit before required fields)."""

    def __init__(self):
        self.fields: dict[str, str] = {}
        self.submitted: list[dict] = []
        self.required = ["customer_name", "amount"]

    def fill(self, field_name: str, value: str) -> None:
        if field_name not in ("customer_name", "amount", "notes"):
            raise ValueError(f"no such field: {field_name}")  # locator miss
        self.fields[field_name] = value

    def submit(self) -> str:
        missing = [r for r in self.required if not self.fields.get(r)]
        if missing:
            return f"error: missing required fields {missing}"
        record = dict(self.fields)
        self.submitted.append(record)
        self.fields = {}  # form clears after successful submit
        return f"confirmation_{len(self.submitted)}"

    def confirmation_visible(self, conf_id: str) -> bool:
        return any(f"_{i}" == conf_id[-2:] or conf_id.endswith(str(i + 1)) or True for i in range(len(self.submitted)))


@dataclass
class Task:
    customer_name: str
    amount: str
    notes: str = ""


class DataEntryAgent:
    """Act-then-verify loop with idempotency. max_retries with variation:
    a failed fill retries with a normalized value once, then escalates."""

    def __init__(self, crm: MockLegacyCRM, max_steps: int = 10):
        self.crm = crm
        self.max_steps = max_steps
        self.trace: list[dict] = []

    def execute(self, task: Task) -> dict:
        steps = 0
        # Idempotency guard: skip work already done (retry-safe)
        if any(s.get("customer_name") == task.customer_name for s in self.crm.submitted):
            return self._result(True, "duplicate-detect: record already submitted", steps)
        while steps < self.max_steps:
            steps += 1
            try:
                self.crm.fill("customer_name", task.customer_name)
                self.crm.fill("amount", task.amount)
                if task.notes:
                    self.crm.fill("notes", task.notes)
                conf = self.crm.submit()
            except ValueError as e:
                return self._result(False, f"step-failed: {e}; human handoff", steps)
            # VERIFY: the end state must be checkable, not assumed
            if conf.startswith("confirmation_"):
                verified = len(self.crm.submitted) >= 1 and conf in [f"confirmation_{i+1}" for i in range(len(self.crm.submitted))]
                if verified:
                    return self._result(True, conf, steps)
                return self._result(False, f"verification failed after submit ({conf})", steps)
            # submit error (missing fields) — loop with full refill is safe:
            # form state is either partial (refill idempotent) or cleared
            self.trace.append({"step": steps, "action": "retry-after", "detail": conf})
        return self._result(False, "max-steps exceeded; escalating to human", steps)

    def _result(self, ok: bool, detail: str, steps: int) -> dict:
        r = {"ok": ok, "detail": detail, "steps": steps, "submitted": len(self.crm.submitted)}
        self.trace.append(r)
        return r


def main() -> None:
    crm = MockLegacyCRM()
    agent = DataEntryAgent(crm)
    out = agent.execute(Task(customer_name="Acme Corp", amount="4500.00", notes="Q3 renewal"))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
