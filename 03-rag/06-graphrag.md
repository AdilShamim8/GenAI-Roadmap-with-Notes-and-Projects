# GraphRAG

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Microsoft GraphRAG](https://microsoft.github.io/graphrag/)

## Why this matters

Vector RAG retrieves similar chunks. It cannot answer "What are the main themes in this corpus?" or "How do these entities relate?" — those need structure, not similarity. GraphRAG extracts an entity-relationship graph from your corpus and uses it for retrieval.

## Core concepts

### The pipeline

1. **Chunk** the corpus as usual.
2. **Extract entities and relationships** from each chunk with an LLM ("Alice works at Acme; Acme is in the analytics industry").
3. **Cluster entities** into communities (Leiden algorithm).
4. **Summarize each community** with an LLM.
5. **At query time:** either (a) map the query to entities and traverse, or (b) find the relevant community summaries.

### When GraphRAG wins

- Whole-corpus questions ("What are the main themes?").
- Multi-entity relationship questions.
- Questions where the answer is spread across many non-adjacent chunks.

### When GraphRAG loses

- Single-fact lookup.
- Cost-sensitive workloads (indexing is 10–100× more expensive than vector RAG).
- Small corpuses (<1K chunks).

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

Global queries answer across the whole corpus via community summaries; local queries start from entities near your question. For a cheaper/simpler graph, consider LightRAG or nano-graphrag.

## Production concerns

- **Latency:** Indexing a 1M-token corpus takes 1–4 hours and $50–$200 of LLM calls.
- **Cost:** Don't run GraphRAG on corpuses that don't need it. Vector RAG is 10–100× cheaper.
- **Failure modes:** Entity extraction is noisy. Bad entities = bad graph.
- **Security:** The graph can reveal relationships that individual chunks don't. Audit access controls.

## Anti-patterns

- ❌ **GraphRAG for everything.** It's a scalpel, not a hammer.
- ❌ **Re-indexing on every update.** Use incremental indexing.
- ❌ **Skipping community summaries.** They're what makes global queries work.

## References

- [Microsoft GraphRAG](https://microsoft.github.io/graphrag/) — verified 2026-10-20
- [GraphRAG paper](https://arxiv.org/abs/2404.16130) — verified 2026-10-20
