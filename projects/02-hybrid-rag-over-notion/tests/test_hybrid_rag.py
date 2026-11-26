"""Offline tests for the hybrid RAG pipeline — no network, no DB."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import (  # noqa: E402
    BM25Index,
    Chunk,
    DenseIndex,
    HybridRAG,
    Reranker,
    chunk_document,
    expand_to_parents,
    hash_embed,
    rrf_fuse,
)

DOCS = {
    "pricing": "Pricing\n\nThe Pro plan costs $49 per seat per month.\n\nEnterprise pricing is custom, starting at $10,000 annually.",
    "security": "Security\n\nAES-256 at rest, TLS 1.3 in transit.\n\nSOC 2 Type II since 2025. SAML SSO on Enterprise only.",
}


class TestChunking:
    def test_parents_and_children_created(self):
        chunks = chunk_document("d1", "First para here.\n\nSecond para also here.")
        parents = [c for c in chunks if c.parent_id == c.id]
        children = [c for c in chunks if c.parent_id != c.id]
        assert len(parents) == 2
        assert len(children) >= 2
        assert all(c.doc_id == "d1" for c in chunks)

    def test_child_ids_reference_parents(self):
        chunks = chunk_document("d1", "One sentence. Another sentence.")
        children = [c for c in chunks if c.parent_id != c.id]
        assert all(c.parent_id and c.parent_id.startswith("d1::") for c in children)


class TestBM25:
    def test_exact_token_match_ranks_first(self):
        idx = BM25Index()
        idx.add([Chunk("a", "a", "error code ERR_CONN_REFUSED appears in gateway logs")])
        idx.add([Chunk("b", "b", "connection settings for the web app")])
        hits = idx.search("ERR_CONN_REFUSED")
        assert hits[0].chunk.id == "a"

    def test_empty_index_returns_empty(self):
        assert BM25Index().search("anything") == []


class TestDense:
    def test_hash_embed_deterministic_and_normalized(self):
        v1, v2 = hash_embed("hello world"), hash_embed("hello world")
        assert v1 == v2
        assert abs(sum(x * x for x in v1) - 1.0) < 1e-6

    def test_identical_text_scores_highest(self):
        idx = DenseIndex()
        idx.add([Chunk("a", "a", "quantization reduces memory bandwidth"), Chunk("b", "b", "cats are pleasant")])
        hits = idx.search("quantization reduces memory bandwidth")
        assert hits[0].chunk.id == "a"


class TestFusion:
    def test_rrf_prefers_docs_found_by_both_retrievers(self):
        both = [RetrievedStub("x", 0).doc]
        from src.main import RetrievedDoc

        list_a = [RetrievedDoc(Chunk("x", "d", "x"), 1.0), RetrievedDoc(Chunk("y", "d", "y"), 0.9)]
        list_b = [RetrievedDoc(Chunk("x", "d", "x"), 0.1), RetrievedDoc(Chunk("z", "d", "z"), 0.05)]
        fused = rrf_fuse([list_a, list_b])
        assert fused[0].chunk.id == "x"  # found by both, ranks high in both
        _ = both

    def test_rrf_rank_not_score_based(self):
        # incomparable score scales (1.0 vs 100.0) — ranks fuse fine
        from src.main import RetrievedDoc

        a = [RetrievedDoc(Chunk("x", "d", "x"), 1.0)]
        b = [RetrievedDoc(Chunk("x", "d", "x"), 100.0), RetrievedDoc(Chunk("y", "d", "y"), 99.0)]
        fused = rrf_fuse([a, b])
        assert fused[0].chunk.id == "x"


class RetrievedStub:
    def __init__(self, id_, score):
        from src.main import RetrievedDoc

        self.doc = RetrievedDoc(Chunk(id_, "d", "text"), score)


class TestPipeline:
    def test_hybrid_retrieval_finds_right_doc(self):
        rag = HybridRAG()
        rag.index(DOCS)
        results = rag.retrieve("What does the Pro plan cost?")
        assert any("Pro plan" in c.text or "pricing" in c.doc_id for c in results)

    def test_bm25_side_catches_exact_codes(self):
        rag = HybridRAG()
        rag.index({"logs": "The gateway returns ERR_CONN_REFUSED under load."})
        results = rag.retrieve("ERR_CONN_REFUSED")
        assert results and "ERR_CONN_REFUSED" in results[0].text

    def test_parent_expansion_dedupes(self):
        rag = HybridRAG()
        rag.index(DOCS)
        hits = rag.dense.search("Pro plan", k=50)
        parents = expand_to_parents(hits, rag.chunk_by_id)
        ids = [p.id for p in parents]
        assert len(ids) == len(set(ids)), "duplicate parents returned"

    def test_answer_retrieval_only_mode(self):
        rag = HybridRAG()
        rag.index(DOCS)
        result = rag.answer("Is SSO available?")
        assert result["answer"] is None
        assert result["citations"]
        assert any("SAML" in c.text for c in result["contexts"])

    def test_answer_with_injected_llm(self):
        rag = HybridRAG()
        rag.index(DOCS)

        def fake_llm(query, contexts):
            return f"Answer based on {len(contexts)} chunks: SSO is Enterprise-only [security::p1]"

        result = rag.answer("Is SSO available?", llm_fn=fake_llm)
        assert "Enterprise-only" in result["answer"]
        assert "security" in " ".join(result["citations"])


class TestReranker:
    def test_overlap_reranker_orders_by_query_coverage(self):
        rr = Reranker()
        from src.main import RetrievedDoc

        docs = [
            RetrievedDoc(Chunk("a", "d", "pro plan pricing monthly cost"), 0.1),
            RetrievedDoc(Chunk("b", "d", "unrelated content here"), 0.2),
        ]
        out = rr.rerank("pro plan cost", docs, top_n=2)
        assert out[0].chunk.id == "a"

    def test_top_n_respected(self):
        rr = Reranker()
        from src.main import RetrievedDoc

        docs = [RetrievedDoc(Chunk(str(i), "d", f"doc number {i}"), 0.1) for i in range(10)]
        assert len(rr.rerank("doc", docs, top_n=3)) == 3
