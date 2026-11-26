# GraphRAG

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Microsoft GraphRAG](https://microsoft.github.io/graphrag/), [From Local to Global (GraphRAG paper)](https://arxiv.org/abs/2404.16130)

## Why this matters

Vector RAG retrieves similar chunks. It cannot answer "What are the main themes in this corpus?" or "How do these entities relate?" — those need *structure*, not similarity. GraphRAG extracts an entity-relationship graph from your corpus and uses it for retrieval. The expert framing: similarity is a *local* signal (this chunk ≈ that query); themes, relationships, and summaries-of-the-whole are *global* signals that no per-chunk similarity can produce, because the answer isn't *in* any chunk — it's distributed across all of them.

## Core concepts

### The pipeline

1. **Chunk** the corpus as usual.
2. **Extract entities and relationships** from each chunk with an LLM ("Alice works at Acme; Acme is in the analytics industry").
3. **Cluster entities** into communities (Leiden algorithm).
4. **Summarize each community** with an LLM.
5. **At query time:** either (a) map the query to entities and traverse, or (b) find the relevant community summaries.

Steps 3–4 are the paper's core contribution ("From Local to Global", arXiv 2404.16130): community detection (Leiden) partitions the entity graph into hierarchical, interpretable clusters, and community summaries pre-compute the "global view" once at index time so query-time global questions are answered from a handful of summaries instead of a million chunks. Map-reduce over community summaries = the "global search" method.

### Local vs global queries (the routing decision)

| Query type | Example | Method |
|------------|---------|--------|
| **Local (specific entity)** | "What did Acme announce in Q3?" | Entity-anchored traversal: find the Acme node, expand to its relationships and nearby text units |
| **Global (corpus-wide)** | "What are the main themes?" | Community summaries — map-reduce over pre-computed summaries |
| **Relational** | "How is Alice connected to Globex?" | Shortest-path / multi-hop traversal the vector index has no representation for |

The misrouting failure: running *local* queries through *global* search produces vague, summary-flavored non-answers ("Acme is involved in several strategic initiatives..."); running global queries through vector RAG produces cherry-picked chunks that miss the distribution. GraphRAG's own CLI exposes `--method local|global` because the routing is intrinsic.

### Why vector RAG structurally can't do this

A "themes" question requires *aggregating* the corpus; vector retrieval can only *select* from it. Even if you retrieved the 50 most theme-adjacent chunks, the model sees a sample, not a census — prevalence information ("how much of the corpus is about X vs Y") is unrecoverable from top-K similarity. Community summaries are a census. This is the same effective-context lesson as `02-context-engineering/01-context-budgeting.md` (RULER's aggregation tasks fail long before retrieval tasks), applied at the corpus scale.

### The cost structure (decide with numbers)

Indexing is 10–100x more expensive than vector RAG, and it's per-*corpus-version*: every meaningful corpus update re-runs extraction over changed chunks plus community re-clustering. The paper's own accounting: entity extraction touches *every* chunk with an LLM call, then community summarization adds another pass over each community. On a 1M-token corpus at cheap-model pricing (~$0.10/1M in, $0.50/1M out, ~5-10x token amplification from extraction prompts), expect roughly $10-100 in LLM spend — plus hours of wall-clock. That's the *minimum* viable scale; the pattern only pays when the corpus is stable enough to amortize indexing over many queries.

### When GraphRAG wins

- Whole-corpus questions ("What are the main themes?").
- Multi-entity relationship questions ("connect A to B").
- Questions where the answer is spread across many non-adjacent chunks.
- Corpora where entities are the natural unit (intelligence analysis, legal discovery, biomedical literature, financial filings).

### When GraphRAG loses

- Single-fact lookup (vector RAG is 10–100x cheaper).
- Cost-sensitive or frequently-updated corpuses (re-indexing burns the budget).
- Small corpuses (<1K chunks) — a long-context model reading everything beats building an index (`08-long-context-vs-rag.md`).
- Chatty corpora with few entities (chat logs, tickets) — the graph is sparse and noisy.

### The lighter-weight alternatives

- **LightRAG / nano-graphrag** — smaller extraction footprint, simpler pipelines, trade away some global-query fidelity.
- **Entity-store + vector RAG** — extract entities into a structured store (or just a table) and let a normal agent join them at query time; you lose pre-computed community summaries but keep update flexibility. This is often the right first step: it's incremental and debuggable, and it tells you whether the corpus actually has graph-shaped questions before you pay for full GraphRAG.

## Code: minimal GraphRAG with Microsoft's lib (CLI-driven)

The `graphrag` package is CLI-first — there is no stable `run_pipeline`/`GlobalSearch` Python API:

```bash
pip install graphrag
graphrag init --root ./ragtest          # scaffolds settings.yaml + prompts
# put your .txt corpus in ./ragtest/input/
graphrag index --root ./ragtest         # one-time, expensive: entities + communities
graphrag query --root ./ragtest --method global "What are the main themes in this corpus?"
graphrag query --root ./ragtest --method local "What did Acme announce in Q3?"
```

Global queries answer across the whole corpus via community summaries; local queries start from entities near your question.

## Production concerns

- **Latency:** Indexing a 1M-token corpus takes 1–4 hours and $10–100+ of LLM calls (scale with corpus size and extraction prompt design). Query-time: local queries are one traversal (fast); global queries map-reduce over community summaries (one summarization call per community tier — budget seconds, not milliseconds).
- **Cost:** Don't run GraphRAG on corpuses that don't need it. Vector RAG is 10–100x cheaper. Model the indexing cost *including re-indexing cadence* before committing: with weekly corpus updates, indexing dominates total cost fast.
- **Failure modes:** (1) Entity extraction is noisy — normalization matters ("Acme Corp", "ACME", "Acme Inc." are three nodes unless you dedupe); (2) hallucinated relationships — the extractor invents plausible-but-false edges, which then surface in community summaries as if established; (3) community drift — Leiden partitions shift on re-index, so community IDs aren't stable references across versions.
- **Security:** The graph *aggregates* — it can reveal relationships that individual chunks don't ("employee X is named in the same community as 'fraud investigation'"). Aggregate inference is a disclosure channel vector RAG doesn't have. Audit access controls at the community-summary level for sensitive corpora.
- **Eval:** Global queries resist gold-label evals (themes are judgment calls); use LLM-judge comparisons of summary comprehensiveness against a human baseline, and eval local queries like normal RAG (recall@k against entity-anchored golds). `../07-evals/02-llm-as-judge.md`.

## Anti-patterns

- ❌ **GraphRAG for everything.** It's a scalpel for global/relational questions, not a better hammer.
- ❌ **Re-indexing the full corpus on every update.** Use incremental indexing; budget re-index cadence into the cost model.
- ❌ **Skipping community summaries.** They're what makes global queries work — without them you've built an entity database, not GraphRAG.
- ❌ **Skipping entity normalization.** One entity, three spellings = a fragmented, useless graph.
- ❌ **Answering "what is X" (local) queries via global search.** Route local vs global deliberately.

## References

- [Microsoft GraphRAG](https://microsoft.github.io/graphrag/) — verified 2026-10-20
- [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130) — verified 2026-10-20
