"""Incident-response autopilot — kill switch, quarantine, recall index.

Encodes 08-production/05: kill stops NEW requests; quarantine revokes the
credentials of in-flight runs; the recall index makes delivered harm
measurable instead of archaeology."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunState:
    run_id: str
    tools: list[str]
    active: bool = True


@dataclass
class RecallIndex:
    """Every user-visible action logged as a retrievable artifact."""
    entries: list[dict] = field(default_factory=list)

    def record(self, run_id: str, action: str, audience: str, detail: str = "") -> None:
        self.entries.append({"run_id": run_id, "action": action, "audience": audience, "detail": detail})

    def affected(self, audience: str) -> list[dict]:
        return [e for e in self.entries if e["audience"] == audience]


class IncidentAutopilot:
    def __init__(self):
        self.kill_switch = False
        self.runs: dict[str, RunState] = {}
        self.recall = RecallIndex()

    def register_run(self, run_id: str, tools: list[str]) -> None:
        self.runs[run_id] = RunState(run_id, tools)

    def kill(self) -> None:
        self.kill_switch = True

    def quarantine(self) -> list[str]:
        """Kill is not enough: in-flight runs keep acting. Revoke tool access
        (a run whose tools are revoked cannot do harm even if the loop lives)."""
        quarantined = []
        for r in self.runs.values():
            if r.active:
                r.tools = []  # credential revocation
                r.active = False
                quarantined.append(r.run_id)
        return quarantined

    def handle_incident(self) -> dict:
        self.kill()
        q = self.quarantine()
        return {
            "kill_switch": True,
            "quarantined_runs": q,
            "recall_needed": len(self.recall.entries),
        }
