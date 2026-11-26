"""Cost-optimized routing proxy — task-type routing + per-request budget guard.

Encodes 08-production/01: route by task TYPE from the call site (never a
difficulty guess), track spend per route, hard budget per request."""
from __future__ import annotations

from dataclasses import dataclass, field

PRICE = {"cheap": (0.10, 0.50), "balanced": (2.0, 10.0), "flagship": (10.0, 50.0)}
ROUTE = {"summarize": "cheap", "extract": "cheap", "analyze": "balanced", "verify": "flagship"}


@dataclass
class RoutingProxy:
    budget_usd: float = 0.50
    spend: list[dict] = field(default_factory=list)

    def route(self, task_type: str) -> str:
        return ROUTE.get(task_type, "balanced")

    def call(self, task_type: str, est_in: int, est_out: int, tier: str | None = None) -> dict:
        tier = tier or self.route(task_type)
        pin, pout = PRICE[tier]
        cost = est_in / 1e6 * pin + est_out / 1e6 * pout
        if cost > self.budget_usd:
            return {"ok": False, "error": "budget exceeded", "est_cost": cost, "tier": tier}
        rec = {"ok": True, "tier": tier, "est_cost": cost, "task_type": task_type}
        self.spend.append(rec)
        return rec

    def cost_by_tier(self) -> dict:
        out: dict[str, float] = {}
        for s in self.spend:
            out[s["tier"]] = out.get(s["tier"], 0.0) + s["est_cost"]
        return out
