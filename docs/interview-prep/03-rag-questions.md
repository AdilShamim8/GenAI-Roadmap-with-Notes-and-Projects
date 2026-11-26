# RAG — Interview Questions

> **Rung:** [03-rag](../../03-rag/01-chunking-strategies.md) · **Last verified:** 2026-10-20

## Q1 — Your RAG system retrieves the right chunk but generates wrong answers. Where do you look?

**Model answer:** If retrieval is verified correct (gold chunk in top-K), the problem is generation-side, and the usual suspects in order:

1. **Decontextualized chunks** — the chunk that matched the query doesn't carry enough context for the *model* to use it (a table row without headers, a pronoun whose referent was in the previous paragraph). Fix: parent-expansion (retrieve small, return the section) or contextual prefixes on chunks.
2. **Distractor overload** — 20 chunks stuffed in insertion order; irrelevant retrieved chunks actively absorb attention and degrade reasoning (NoLiMa's core finding). Fix: rerank and *shrink* the context to the top 5, ordered best-first.
3. **No citation discipline** — the model synthesizes across chunks instead of grounding in one. Fix: instructions + structured outputs requiring source IDs per claim, and evals that check citation accuracy.
4. **Position effects** — the gold chunk sits mid-context where recall is weakest. Fix: place the best chunk last or first.

The diagnostic that distinguishes them: run the same generation with *only* the gold chunk. If it's still wrong, it's chunk decontextualization (or the model); if it's right, it's context interference — rerankers and smaller K fix it.

**Senior note:** the discipline is measuring the two stages separately — retrieval metrics (recall@k vs gold) and answer metrics (faithfulness, correctness) — because "RAG is bad" collapses three different bugs into one vibe. DeepEval/Ragas's triad exists precisely for this: low faithfulness with high context-recall indicts generation; low recall indicts retrieval.

## Q2 — Design chunking for a corpus of technical PDFs with tables and code

**Model answer:** Structure-first: split on document structure before any character-based fallback — headings, then code fences, then paragraphs. Tables never split (a row without its header is meaningless to embedder and generator alike); code blocks stay intact. Then apply **small-to-big**: embed 1-3 sentence child windows for retrieval precision, return the parent section for generation context — this decouples the retrieval-granularity/generation-context tradeoff that fixed-size chunking is stuck in.

Add contextual prefixes (Anthropic's contextual retrieval: a one-sentence "this chunk is from X section discussing Y" prefix, ~49% fewer retrieval failures; ~$0.08-0.30 per 1K chunks on a cheap model, index-time only) and dedupe parent expansions so three child hits return one parent, not three copies.

**Senior note:** what you *don't* do matters — no overlap needed once parent-expansion handles continuity; no fixed 1000-char splitting anywhere near tables; and eval end-to-end answers, not recall@10 alone, because a chunking change that improves retrieval metrics can *degrade* answers (smaller, decontextualized chunks retrieve better and generate worse).

## Q3 — When does hybrid search actually beat pure vector search, and why?

**Model answer:** Hybrid wins when queries contain **exact-match signals** the embedder can't represent: product codes, error strings, rare named entities, version numbers, negations. Dense embeddings fail on out-of-vocabulary identifiers and exact strings because their training never contrasted those; BM25 fails on paraphrase and synonyms. The failure sets are *orthogonal* — which is why fusion is reliably positive and why hybrid recall approaches the union of both retrievers.

Fusion mechanics: RRF (`Σ 1/(k+rank)`, k=60) beats score fusion because it uses ranks, not incomparable score distributions. And the modern shortcut: BGE-M3 emits dense + sparse vectors in one encode pass, so the BM25 half of hybrid comes free with the embedding step.

**Senior note:** know *why* k=60 — it flattens the head of the reciprocal curve so rank-1 vs rank-2 barely differ, letting strong signals from either retriever win without dominating. And track per-retriever recall separately — when hybrid regresses, the decomposition tells you which half broke.

## Q4 — Explain the two-stage retrieve-then-rerank pattern and its economics

**Model answer:** Stage 1 (recall-oriented): cheap bi-encoder retrieval over the whole corpus, top-50. Stage 2 (precision-oriented): a cross-encoder scores each (query, doc) *jointly* — attention models fine-grained relevance that a fixed-size embedding can't — and you keep the top 5. The bi-encoder can pre-compute doc embeddings offline (that's why it scales); the cross-encoder can't pre-compute anything (every pair is a forward pass), which is why it only sees the top-K.

Economics: cross-encoder latency dominates query-time cost — 50 pairs at ~20ms on GPU batches to ~200-500ms added; LLM-as-reranker (one batched cheap-model call scoring all 50) is ~$0.001-0.005 and wins on weird domains where fine-tuned rerankers underperform. K/N geometry: recall saturates past ~64 candidates; re-ranking 100 vs 10 doubles cost for the last 1%.

**Senior note:** the ceiling argument — if retrieval recall@50 is 90%, the reranker can't recover the missing 10%; diagnose *which* stage fails before buying a bigger anything. And cross-encoders bias toward longer docs (evidence accumulates over length); normalize or re-chunk on heterogeneous corpora.

## Q5 — When is GraphRAG worth it over vector RAG?

**Model answer:** GraphRAG answers *global and relational* questions that similarity can't: "what are the main themes," "how is X connected to Y." The structural reason: vector retrieval *selects* from the corpus while themes require *aggregating* it — no top-K sample recovers prevalence. GraphRAG's pipeline (entity extraction → Leiden communities → community summaries) pre-computes the aggregate view at index time; global queries map-reduce over summaries, local queries traverse from entities.

The cost is the catch: indexing is 10-100x vector RAG's cost — every chunk passes through LLM extraction, plus community summarization — and *re-indexing cadence* multiplies it on living corpora. It earns its keep on stable, entity-dense corpora (legal discovery, intelligence, biomedical literature) queried for structure, not lookup.

**Senior note:** the routing discipline — local/entity questions through vector or entity lookup, global through community summaries; misrouting produces the classic vague-summary non-answer. And the failure modes interviewers probe: entity normalization ("Acme Corp"/"ACME" = three nodes), hallucinated edges surfacing in summaries as established fact, and community IDs unstable across re-indexes.

## Q6 — "We'll just use the model's 1M context instead of retrieval." Push back with numbers

**Model answer:** Take GPT-6.1 Sol at $2/1M input: stuffing a 1M-token corpus is $2/request fresh (~$0.10 cached — *if* the prefix is stable and the cache survives your traffic pattern; caches are prefix-exact and evicted in minutes). Retrieval with 10K reranked tokens: $0.02. At 1,000 queries/day that's $2,000/day vs $20/day — two orders of magnitude, before latency: 1M-token prefill is 10-60s TTFT vs sub-second retrieval.

The capability side is just as damning: the advertised window is a capacity envelope, not an attention guarantee — RULER showed aggregation/multi-hop degrade far inside 1M; NoLiMa showed associative reasoning degrading by 32K. And the governance side: per-tenant access control belongs in the index; a stuffed context must be filtered before assembly or it leaks.

Where long-context *does* win: single-doc tasks, ad-hoc exploration, low-frequency queries, small cache-friendly corpora. The production pattern is hybrid — retrieve top-10, give the long-context model 10-50K tokens of *selected* evidence to reason across.

**Senior note:** do the break-even aloud for *their* numbers: `corpus_tokens × queries × price` vs `index_cost + queries × (k × price + retrieval_cost)`, and name the three regimes (tiny corpus + few users → long-context; tiny + many users → long-context-with-caching can win until eviction breaks it; anything bigger or multi-tenant → RAG, no contest). Interviewers remember candidates who turn opinions into arithmetic.
