"""Hybrid RAG — chunking, hybrid retrieval (dense + BM25), RRF fusion, reranking,
and citation-grounded generation.

The engine is provider-agnostic and runs fully offline for tests: embeddings
are hash-based by default (deterministic, no network), the BM25 index is pure
Python, and the LLM call is injected. Swap ``embed_fn`` for a real embedder and
``llm_fn`` for a real model in production — the retrieval math and tests are
identical either way.

Design notes (matching 03-rag/):
- Hybrid works because dense and sparse failure sets are orthogonal (03/03).
- RRF (k=60) fuses on ranks, not scores — robust to incomparable distributions.
- Retrieval wants small chunks; generation wants context — parent expansion
  (03/01) resolves both: match children, return parent sections.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    id: str
    doc_id: str
    text: str
    parent_id: str | None = None

    def tokens(self) -> list[str]:
        return re.findall(r"[a-z0-9]+", self.text.lower())


@dataclass
class RetrievedDoc:
    chunk: Chunk
    score: float


# ---------------------------------------------------------------------------
# Chunking — structure-aware with parent expansion
# ---------------------------------------------------------------------------


def chunk_document(
    doc_id: str,
    text: str,
    max_children_per_parent: int = 6,
    child_sentences: int = 2,
) -> list[Chunk]:
    """Split on paragraphs (parents); each parent yields rolling 2-sentence
    children. Children are what we match; parents are what we return."""
    parents = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    for pi, para in enumerate(parents):
        parent_id = f"{doc_id}::p{pi}"
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        if not sentences:
            continue
        window = max(1, child_sentences)
        for ci in range(0, len(sentences), window):
            child_text = " ".join(sentences[ci : ci + window])
            chunks.append(Chunk(id=f"{parent_id}::c{ci}", doc_id=doc_id, text=child_text, parent_id=parent_id))
        # keep the parent itself retrievable for exact-paragraph matches
        chunks.append(Chunk(id=parent_id, doc_id=doc_id, text=para, parent_id=parent_id))
        if len(chunks) > 10_000:  # safety valve for absurd inputs
            break
    _ = max_children_per_parent  # reserved for future length-capping
    return chunks


# ---------------------------------------------------------------------------
# BM25 (pure Python, 03/03 mechanics: k1=1.2, b=0.75)
# ---------------------------------------------------------------------------


class BM25Index:
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs: list[Chunk] = []
        self.tf: list[dict[str, int]] = []
        self.df: dict[str, int] = {}
        self.avg_len = 0.0

    def add(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self.docs.append(c)
            counts: dict[str, int] = {}
            for t in c.tokens():
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                self.df[t] = self.df.get(t, 0) + 1
        self.avg_len = sum(len(d.tokens()) for d in self.docs) / max(1, len(self.docs))

    def search(self, query: str, k: int = 10) -> list[RetrievedDoc]:
        q_tokens = re.findall(r"[a-z0-9]+", query.lower())
        n = len(self.docs)
        if n == 0:
            return []
        scores: list[float] = []
        for i, counts in enumerate(self.tf):
            dl = sum(counts.values())
            s = 0.0
            for t in q_tokens:
                if t not in counts:
                    continue
                idf = math.log(1 + (n - self.df.get(t, 0) + 0.5) / (self.df.get(t, 0) + 0.5))
                tf = counts[t]
                s += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avg_len))
            scores.append(s)
        ranked = sorted(range(n), key=lambda i: -scores[i])[:k]
        return [RetrievedDoc(self.docs[i], scores[i]) for i in ranked if scores[i] > 0]


# ---------------------------------------------------------------------------
# Dense index (embeddings injected; hash default for offline determinism)
# ---------------------------------------------------------------------------


def hash_embed(text: str, dim: int = 256) -> list[float]:
    """Deterministic pseudo-embeddings: same text -> same vector. NOT semantic —
    a stand-in so the pipeline is testable offline. Production swaps in a real
    embedder (e.g. text-embedding-3-small) via ``embed_fn``."""
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = hash(tok) % dim  # noqa: S324 — determinism within a process is fine here
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class DenseIndex:
    def __init__(self, embed_fn: Callable[[str], list[float]] = hash_embed):
        self.embed_fn = embed_fn
        self.docs: list[Chunk] = []
        self.vecs: list[list[float]] = []

    def add(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self.docs.append(c)
            self.vecs.append(self.embed_fn(c.text))

    def search(self, query: str, k: int = 10) -> list[RetrievedDoc]:
        if not self.docs:
            return []
        q = self.embed_fn(query)
        scored = sorted(
            ((cosine(q, v), d) for d, v in zip(self.docs, self.vecs)),
            key=lambda x: -x[0],
        )[:k]
        return [RetrievedDoc(d, s) for s, d in scored if s > 0]


# ---------------------------------------------------------------------------
# RRF fusion + reranking + parent expansion
# ---------------------------------------------------------------------------


def rrf_fuse(result_lists: list[list[RetrievedDoc]], k: int = 60) -> list[RetrievedDoc]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)). Rank-based, so it
    tolerates incomparable score scales across retrievers."""
    scores: dict[str, float] = {}
    by_id: dict[str, Chunk] = {}
    for results in result_lists:
        for rank, r in enumerate(results):
            scores[r.chunk.id] = scores.get(r.chunk.id, 0.0) + 1.0 / (k + rank)
            by_id[r.chunk.id] = r.chunk
    ordered = sorted(scores.items(), key=lambda x: -x[1])
    return [RetrievedDoc(by_id[cid], s) for cid, s in ordered]


class Reranker:
    """Cross-encoder stand-in: scores (query, doc) jointly. The default scorer
    is lexical overlap (deterministic, offline); production injects a real
    cross-encoder (BGE-reranker) — the interface is the point."""

    def __init__(self, score_fn: Callable[[str, str], float] | None = None):
        self.score_fn = score_fn or self._overlap

    @staticmethod
    def _overlap(query: str, doc: str) -> float:
        q = set(re.findall(r"[a-z0-9]+", query.lower()))
        d = set(re.findall(r"[a-z0-9]+", doc.lower()))
        return len(q & d) / len(q) if q else 0.0

    def rerank(self, query: str, docs: list[RetrievedDoc], top_n: int = 5) -> list[RetrievedDoc]:
        scored = [(self.score_fn(query, d.chunk.text), d) for d in docs]
        scored.sort(key=lambda x: -x[0])
        return [d for s, d in scored[:top_n]]


def expand_to_parents(hits: list[RetrievedDoc], chunk_by_id: dict[str, Chunk]) -> list[Chunk]:
    """Small-to-big: dedupe child hits into their parent sections."""
    seen: set[str] = set()
    out: list[Chunk] = []
    for h in hits:
        pid = h.chunk.parent_id or h.chunk.id
        if pid not in seen:
            seen.add(pid)
            parent = chunk_by_id.get(pid, h.chunk)
            out.append(parent)
    return out


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------


@dataclass
class HybridRAG:
    chunks: list[Chunk] = field(default_factory=list)
    bm25: BM25Index = field(default_factory=BM25Index)
    dense: DenseIndex = field(default_factory=DenseIndex)
    reranker: Reranker = field(default_factory=Reranker)
    chunk_by_id: dict[str, Chunk] = field(default_factory=dict)

    def index(self, docs: dict[str, str]) -> None:
        for doc_id, text in docs.items():
            cs = chunk_document(doc_id, text)
            self.chunks.extend(cs)
            self.bm25.add(cs)
            self.dense.add(cs)
            for c in cs:
                self.chunk_by_id[c.id] = c

    def retrieve(self, query: str, k: int = 20, top_n: int = 5) -> list[Chunk]:
        dense_hits = self.dense.search(query, k=k)
        sparse_hits = self.bm25.search(query, k=k)
        fused = rrf_fuse([dense_hits, sparse_hits])
        reranked = self.reranker.rerank(query, fused, top_n=top_n)
        return expand_to_parents(reranked, self.chunk_by_id)

    def answer(self, query: str, llm_fn: Callable[[str, list[Chunk]], str] | None = None) -> dict:
        """Retrieve then generate. llm_fn(query, contexts) -> answer text.
        Returns answer + citations; without llm_fn, returns contexts only
        (retrieval-only mode, used by tests and evals)."""
        contexts = self.retrieve(query)
        if llm_fn is None:
            return {"answer": None, "citations": [c.id for c in contexts], "contexts": contexts}
        answer = llm_fn(query, contexts)
        return {"answer": answer, "citations": [c.id for c in contexts], "contexts": contexts}


def default_llm(query: str, contexts: list[Chunk]) -> str:
    """Production LLM call (OpenAI, env-configured). Kept separate so the
    pipeline core stays dependency-free."""
    import os

    from openai import OpenAI

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=key)
    ctx_text = "\n\n".join(f"[{c.id}]\n{c.text}" for c in contexts)
    resp = client.chat.completions.create(
        model="gpt-6.1-sol",
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer using ONLY the provided context chunks. Cite the chunk id "
                    "for every claim like [doc::p0]. If the context is insufficient, "
                    "say exactly what is missing."
                ),
            },
            {"role": "user", "content": f"Context:\n{ctx_text}\n\nQuestion: {query}"},
        ],
    )
    return resp.choices[0].message.content or ""


def main() -> None:
    import json
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m src.main '<query>'   (index a demo corpus first)")
        return
    rag = HybridRAG()
    rag.index(
        {
            "pricing": "Pricing\n\nThe Pro plan costs $49 per seat per month. Enterprise "
            "pricing is custom and starts at $10,000 annually.\n\nThe Free tier supports "
            "up to 3 projects and community support only.",
            "security": "Security\n\nData is encrypted at rest with AES-256 and in transit "
            "with TLS 1.3. SOC 2 Type II certification was obtained in 2025.\n\nSingle "
            "sign-on via SAML is available on Enterprise plans only.",
        }
    )
    result = rag.answer(sys.argv[1], llm_fn=default_llm if os_env_key() else None)
    print(json.dumps({"answer": result["answer"], "citations": result["citations"]}, indent=2))


def os_env_key() -> bool:
    import os

    return bool(os.environ.get("OPENAI_API_KEY"))


if __name__ == "__main__":
    main()
