"""Agent with episodic memory — extraction-based writes, recency-weighted
recall, decay. Encodes 05-agents/06: write path is an update-decision (not
transcript storage); memory is hints, never ground truth."""
from __future__ import annotations

import time


class EpisodicMemory:
    def __init__(self, ttl_s: float = 3600.0):
        self.store: list[dict] = []  # {fact, ts}
        self.ttl_s = ttl_s

    def write_from_turn(self, facts: list[str], now: float | None = None) -> list[str]:
        """Write path: caller passes EXTRACTED facts (the extraction step is
        upstream); dedupe against existing, update timestamps on re-mention."""
        now = now if now is not None else time.time()
        added = []
        existing = {m["fact"] for m in self.store}
        for f in facts:
            if f in existing:
                for m in self.store:
                    if m["fact"] == f:
                        m["ts"] = now  # re-mention refreshes recency
            else:
                self.store.append({"fact": f, "ts": now})
                added.append(f)
        return added

    def recall(self, query_terms: list[str], k: int = 3, now: float | None = None) -> list[str]:
        """Recall ranked by overlap x recency; stale entries decay out."""
        now = now if now is not None else time.time()
        scored = []
        for m in self.store:
            age = now - m["ts"]
            if age > self.ttl_s:
                continue  # decayed
            overlap = sum(1 for t in query_terms if t.lower() in m["fact"].lower())
            if overlap:
                scored.append((overlap / max(1, len(query_terms)) * (1.0 / (1.0 + age / 600)), m["fact"]))
        scored.sort(key=lambda x: -x[0])
        return [f for _, f in scored[:k]]

    def purge_expired(self, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        before = len(self.store)
        self.store = [m for m in self.store if now - m["ts"] <= self.ttl_s]
        return before - len(self.store)
