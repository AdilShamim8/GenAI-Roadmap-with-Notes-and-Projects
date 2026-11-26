"""GraphRAG over a codebase — symbol graph + traversal retrieval.

Encodes 06-multi-agent handoffs + 03-rag/06 applied to code (03-rag Q&A):
similarity finds entry points; the call/import GRAPH assembles multi-hop
context that similarity can't ("who calls this?")."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Symbol:
    name: str
    kind: str  # function | class | module
    doc: str = ""


@dataclass
class CodeGraph:
    symbols: dict[str, Symbol] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)  # caller -> callee

    def add_symbol(self, name: str, kind: str, doc: str = "") -> None:
        self.symbols[name] = Symbol(name, kind, doc)

    def add_call(self, caller: str, callee: str) -> None:
        if caller in self.symbols and callee in self.symbols:
            self.edges.append((caller, callee))

    def callers_of(self, target: str) -> list[str]:
        return [c for c, k in self.edges if k == target]

    def traverse(self, start: str, depth: int = 2) -> list[str]:
        """BFS over call edges — the multi-hop context assembly."""
        seen, frontier, out = {start}, [start], []
        for _ in range(depth):
            nxt = []
            for node in frontier:
                for c, k in self.edges:
                    if c == node and k not in seen:
                        seen.add(k); nxt.append(k); out.append(k)
                    if k == node and c not in seen:
                        seen.add(c); nxt.append(c); out.append(c)
            frontier = nxt
            if not frontier:
                break
        return out

    def answer_context(self, query: str, depth: int = 2) -> list[str]:
        """Vector-ish match (token overlap — inject a real embedder in prod),
        then graph-expand each hit."""
        q = set(re.findall(r"[a-z0-9_]+", query.lower()))
        hits = [s.name for s in self.symbols.values() if q & set(re.findall(r"[a-z0-9_]+", (s.name + " " + s.doc).lower()))]
        ctx: list[str] = []
        for h in hits[:3]:
            ctx.append(h)
            ctx.extend(self.traverse(h, depth))
        return list(dict.fromkeys(ctx))


def build_graph_from_source(source: str) -> CodeGraph:
    """Lightweight extractor: def/class lines + call sites by name."""
    g = CodeGraph()
    for m in re.finditer(r"^(?:async )?def (\w+)", source, re.M):
        g.add_symbol(m.group(1), "function")
    for m in re.finditer(r"^class (\w+)", source, re.M):
        g.add_symbol(m.group(1), "class")
    for caller_m in re.finditer(r"^(?:async )?def (\w+)", source, re.M):
        caller = caller_m.group(1)
        body = re.search(rf"def {caller}\b.*?(?=\ndef |\nclass |\Z)", source, re.S)
        if body:
            for callee in g.symbols:
                if callee != caller and re.search(rf"\b{callee}\(", body.group(0)):
                    g.add_call(caller, callee)
    return g
