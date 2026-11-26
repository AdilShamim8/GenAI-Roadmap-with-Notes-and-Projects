# Re-Ranking for Precision

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Cohere Rerank](https://docs.cohere.com/docs/reranking), [ColBERT](https://arxiv.org/abs/2004.12832)

## Why this matters

Vector search returns top-K candidates ranked by embedding similarity — fast but coarse. Re-ranking re-scores those K candidates with a more expensive model, giving you top-N with much higher precision. RAG answer quality is often more sensitive to re-ranker quality than to LLM choice. The expert framing: retrieval and ranking are *different problems* — recall-oriented retrieval must be cheap over millions of chunks; precision-oriented ranking must be smart over dozens. Conflating them (one-stage, single-vector search) is the original sin of naive RAG.

## Core concepts

### Two-stage retrieval

1. **Retrieve** — fast, recall-oriented. Get top-50 from vector + BM25.
2. **Re-rank** — slow, precision-oriented. Score each of the 50 with a cross-encoder, keep top-5.

The recall/precision split is quantifiable: if retrieval recall@50 is 90%, no re-ranker can recover the missing 10% — the ceiling is set at stage 1. If retrieval recall@50 is 90% but precision@5 is 40%, the re-ranker's job is picking the right 5 of the 45 retrievable ones. Diagnose which stage is failing before buying either bigger embedders or bigger re-rankers.

### Why cross-encoders beat bi-encoders

Bi-encoders (your embedding model) encode query and doc separately; similarity is a single dot product at the end — query and document *never interact during encoding*. This is what makes them fast (docs pre-embeddable offline) and what makes them coarse (all matching must compress into one fixed-size vector).

Cross-encoders encode `(query, doc)` jointly through the full transformer; every attention layer can compare query tokens against doc tokens directly. That interaction is the precision. The cost: no pre-embedding possible — every (query, doc) pair is a forward pass *at query time*.

### The middle term: late interaction (ColBERT lineage)

ColBERT (arXiv 2004.12832) keeps per-token embeddings for docs (pre-computable) and does cheap MaxSim operations between query tokens and doc token vectors at query time — interaction *without* the full cross-encode cost. It's the precision-cost middle point: notably better than pure bi-encoders, much cheaper than cross-encoders at scale, at the price of 100x-larger indexes (one vector per token, not per chunk). In 2026 the practical late-interaction option ships inside BGE-M3 (`return_colbert_vecs=True`). Most systems still land on: bi-encoder retrieval + cross-encoder re-rank, because it's the best precision-per-engineering-hour.

### Re-ranker options (2026)

| Model | Type | Open-weight? | Latency (per pair) |
|-------|------|--------------|---------------------|
| Cohere Rerank v3.5 | API | No | ~50ms |
| Voyage rerank-2.5 | API | No | ~50ms |
| BGE-reranker-v2-m3 | Open | Yes | ~20ms on GPU |
| Jina reranker v2 / Qwen3-Reranker | Open | Yes | ~20-25ms on GPU |
| LLM-as-reranker (GPT-6 Luna / Haiku 5.5) | API | No | ~200ms per pair (use batch) |

LLM-as-reranker deserves its row: one batched call scoring all 50 candidates ("rate relevance 0-10 of each doc to this query, JSON out") can beat dedicated re-rankers on weird domains (the LLM reads instructions and domain nuance a fine-tuned re-ranker never saw) at ~$0.001-0.005/call with Luna-class pricing. It's the right choice when off-the-shelf re-rankers score poorly on your bake-off.

### The K/N geometry

Latency and cost scale with K (candidates re-ranked), quality saturates fast. The pattern: retrieval recall@50 ≈ recall@100 for most corpora (diminishing returns past ~64), while re-ranking 50 vs 10 candidates doubles cost for the last 1% of recall. Reasonable defaults: K=50 retrieved → N=5 re-ranked for chat; K=100 → N=10 for legal/medical where missing evidence is expensive. Tune by measuring recall@N of the re-ranker against gold labels — not by vibes about "more is safer."

## Code: BGE reranker (self-hosted)

```python
from FlagEmbedding import FlagReranker
reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

pairs = [(query, doc) for doc in candidate_docs]
scores = reranker.compute_score(pairs, normalize=True)
ranked = sorted(zip(candidate_docs, scores), key=lambda x: -x[1])[:5]
```

## Code: Cohere rerank (API)

```python
import cohere
co = cohere.Client()

results = co.rerank(
    model="rerank-v3.5",
    query=query,
    documents=candidate_docs,
    top_n=5,
)
top_docs = [candidate_docs[r.index] for r in results.results]
```

## Code: LLM-as-reranker (batched, one call)

```python
from openai import OpenAI
import json
client = OpenAI()

def llm_rerank(query: str, docs: list[str], top_n: int = 5) -> list[int]:
    numbered = "\n".join(f"[{i}] {d[:500]}" for i, d in enumerate(docs))
    resp = client.chat.completions.create(
        model="gpt-6-luna",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Rate each document's relevance to the query, 0-10. "
                "Respond as JSON: {\"scores\": [s0, s1, ...]} in document order."
            )},
            {"role": "user", "content": f"Query: {query}\n\nDocuments:\n{numbered}"},
        ],
    )
    scores = json.loads(resp.choices[0].message.content)["scores"]
    return sorted(range(len(docs)), key=lambda i: -scores[i])[:top_n]
```

## Production concerns

- **Latency:** Re-ranking 50 candidates adds 200–500ms (cross-encoders batch well on GPU — the per-pair figure ÷ batch size is your real budget). The re-ranker is usually the largest *query-time* component in a RAG stack; put it on the latency budget line next to the LLM call.
- **Cost:** Cohere rerank is ~$2/1K searches. Self-hosted is free at scale. LLM-as-rerank at Luna pricing is ~$0.001-0.005/search. All three beat "stuff 50 chunks into a frontier model" by an order of magnitude.
- **Failure modes:** (1) Re-rankers biased toward longer documents — cross-encoders accumulate relevance evidence over length; if your corpus has heterogeneous chunk sizes, normalize or re-chunk first (`01-chunking-strategies.md`). (2) Domain mismatch — general re-rankers trained on web-search pairs misjudge legal/code/medical relevance; run the bake-off (`02-embedding-model-selection.md` pattern, applied to re-rankers). (3) Score thresholding — re-ranker scores are *relative*, not calibrated probabilities; a fixed "score > 0.5 means relevant" cutoff drifts across models and corpora. Threshold on *rank* or on downstream answer quality.
- **Security:** Re-rankers see query + doc together — no new exfiltration risk, but in multi-tenant deployments a shared re-ranker service processes cross-tenant pairs; ensure logging doesn't persist query-doc joins across tenants.

## Anti-patterns

- ❌ **Skipping re-ranking for production RAG.** Top-K from vector search alone is rarely good enough.
- ❌ **Re-ranking the entire corpus.** Only re-rank the top-K candidates from retrieval.
- ❌ **Treating re-ranker scores as probabilities.** They're relative rankings, not calibrated.
- ❌ **Raising K without measuring recall@K.** Past ~64 candidates you pay latency for nothing.
- ❌ **Fixing a stage-1 recall problem with a better re-ranker.** It can't recover what retrieval never found.

## References

- [Cohere rerank](https://docs.cohere.com/docs/reranking) — verified 2026-10-20
- [BGE reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3) — verified 2026-10-20
- [Voyage rerank](https://docs.voyageai.com/docs/reranker) — verified 2026-10-20
- [ColBERT: Efficient and Effective Passage Search](https://arxiv.org/abs/2004.12832) — verified 2026-10-20
