# System-Design Walkthroughs

> **All rungs** · **Last verified:** 2026-10-20

Four full walkthroughs of the prompts interviewers actually use. The structure is the skill: **requirements → assumptions with numbers → architecture → the three cross-cutting concerns (evals, observability, failure modes) → trade-offs stated aloud**. Practice delivering each in ~10 minutes spoken.

## Walkthrough 1 — "Design a customer-support agent for an e-commerce company"

**Clarify requirements first (2 min):** What channels (chat only? email? voice)? What's in scope — order status, returns, refunds, product questions? What's the escalation policy (when does a human take over)? Volume? Let's assume: chat first, 50K conversations/day, order status + returns + product Q&A, humans handle refunds > $500 and anything irate.

**Architecture (the loops):**

1. **Triage** — cheap model classifies: order-status (deterministic path — it's a lookup, not a generation), returns/policy (RAG over policy docs), product Q&A (RAG over catalog), or escalate. Task-type routing from a classifier, not "difficulty" guessing.
2. **Order status** — no LLM needed for the fetch; a tool call to the order service with the response *templated*. LLM only wraps tone. (Point this out — knowing where *not* to use the model is a hire signal.)
3. **RAG path** — hybrid search (BM25 for order numbers/SKUs + dense for paraphrase) → rerank top-50→5 → generation with citation-required structured output. Contextual chunk prefixes on the policy corpus (it changes weekly; re-indexing is incremental).
4. **Refund action** — the agent can *issue* refunds ≤ $500 via tool with idempotency keys; > $500 routes to a human queue with the conversation summary attached. This is privilege separation by dollar threshold — and the approval queue carries decision context, not raw JSON.

**Cross-cutting (say these unprompted):**

- **Evals:** golden set from sampled real tickets (refund thresholds, policy edge cases, "insufficient evidence" cases); online eval 2% sampled with judges; every escalated ticket reviewed and fed back as cases.
- **Observability:** OTel traces per conversation (triage decision, retrieved chunk ids, tool calls, costs); the trace id is the correlation key when a customer complains.
- **Failure modes:** injection via *customer messages* (direct — moderate risk) and via *product reviews* in the catalog (indirect — the reader path gets no issue-refund tool); tool-call loops (caps + dedup); hallucinated policy (citations required, faithfulness eval).
- **Latency/cost:** cheap-tier routing for the 70% simple traffic; prompt caching on the shared system prompt + policy prefix; batch the nightly email backlog at 50% off.

**The trade-off to state aloud:** "I'm choosing a router-supervisor with single agents per domain over one big multi-agent graph because support traffic decomposes cleanly by intent — the multi-agent complexity buys nothing here and costs handoff latency. If we add voice or cross-domain tasks ('I want to return the item from my missing order'), the topology revisits."

## Walkthrough 2 — "Design a RAG system over 1M internal documents, 10K queries/day"

**Requirements & numbers:** 1M docs ≈ 1-2B tokens; 10K queries/day ≈ 0.12 QPS average, peak maybe 10x — *tiny* load. This immediately kills over-engineering: no sharded vector cluster needed; a single pgvector instance with the right index handles it. Saying "the QPS is low, so simplicity wins" out loud is the senior move.

**Pipeline:** ingestion (structure-aware chunking — docs are PDFs/HTML with tables; parent-expansion small-to-big; contextual prefixes at index time ~$30 one-time on a cheap model) → hybrid search (BM25 + dense in Postgres; error codes and doc IDs need exact match) → cross-encoder rerank top-50→10 (self-hosted BGE-reranker — at 0.12 QPS, GPU rerank is free) → generation with citations.

**Embedding choice:** local bake-off of 3-4 finalists on ~500 (query, gold-chunk) pairs from *our* traffic — MTEB clusters, not leaderboard #1. Matryoshka-capable model for a future storage escape hatch. Recall canary (fixed query set scored daily) against silent model swaps.

**The hard parts to raise unprompted:**

- **Access control at the index** — 1M internal docs means per-team permissions; filter *at retrieval* (metadata prefilter), never post-retrieval (leaks) and never context-stuffing (slow + leaks).
- **Freshness** — docs update; incremental indexing with delete-and-replace by doc ID; a nightly diff job; versioned chunks so "which version of the policy did the answer cite" is answerable.
- **Eval** — golden set ~200 questions with gold doc ids (recall@k) + gold answers (faithfulness/correctness); the offline/online loop: sampled production queries judged, failures become cases.
- **Long-context pressure** — the "why not stuff 1M docs" question: at 10K queries/day, stuffing even 1M-token contexts (if they fit) is ~$20K/day vs ~$200/day for RAG at 10K tokens/query — and effective-context limits break multi-hop anyway. Hybrid pattern: retrieve top-10, give the model 10-50K tokens to reason across.

## Walkthrough 3 — "Design an agent that reads a code repository and answers architecture questions"

**The twist vs. plain RAG:** code has *structure* (ASTs, imports, call graphs) that plain chunking destroys. The architecture: (1) **index the graph** — parse the repo (tree-sitter per language), extract symbols, definitions, references, import edges; embed *symbol-level* chunks (function/class with signature and docstring) not arbitrary text windows. (2) **Retrieval is graph + vector hybrid** — vector search finds semantically related symbols; the call/import graph expands context (a question about "how does auth work" needs the middleware chain, which similarity won't assemble but the import graph will). (3) **Generation** with code-grounded citations (file:line), and answers quote code — verbatim quotability is the checkability story.

**Cross-cutting:** eval on real questions with the answer's *file:line* verifiable automatically (deterministic checks — no judge needed for citation correctness); token discipline is the cost story (repos are big; the agent retrieves symbol windows, never whole files); freshness is *cheap* here (re-index on git diff — only changed symbols re-embed); and security is interesting: the agent reads a repo, so secrets scanning on the index path, and the *agent's answers* inherit repo access — per-repo isolation.

**State the trade-off:** "This is a specialized agent, not a general one — I'm trading generality for structure-awareness. The same design fails on prose corpora; the vector-only design fails here on multi-hop ('who calls this deprecated function?'). Matching retrieval structure to corpus structure is the core decision."

## Walkthrough 4 — "Design a multi-agent research assistant that produces daily competitive-intelligence briefs"

**Requirements:** autonomous (runs nightly), long-horizon (hours of work), reads the open web (untrusted), writes a brief (the deliverable). The three constraints that shape everything: untrusted inputs, long runtime, asynchronous delivery.

**Architecture:** a **graph skeleton** (LangGraph-class durable execution) with **agent-loop nodes** — plan → search/fetch (parallel researchers, context-isolated) → extract & grade (CRAG-style: retrieval-grading before generation) → synthesize → critic review → deliver. Checkpoints at every semantic boundary; the run is resumable (crash at hour 3 ≠ restart from zero). Cost budget hard-capped with 50/80/100% alerts; per-stage attribution.

**The security design (this walkthrough's differentiator):** researchers that fetch untrusted web content get **read-only tools and no exfiltration channels** (egress allowlist: they fetch and write to the artifact store; nothing else). The synthesizer reads only *extracted structured findings* — never raw pages. Prompt-injection via a competitor's poisoned page is the *expected* attack; the architecture contains it by construction.

**The quality loop:** the critic reviews with fresh context (goal + plan + summaries — not researcher history, so it can catch drift without inheriting frames); a weekly human reviews a brief sample and adjusts the rubric; evals score briefs on factuality (citations resolvable), coverage (did it catch the events a human analyst found?), and calibration ("no significant developments" days must say so).

**State the trade-off:** "Fully autonomous vs. human-on-the-loop: I'm shipping autonomous-with-checkpoints because the daily cadence and low per-brief stakes tolerate a wrong day, and the human review samples rather than gates. If a brief drove trading decisions, the critic gate becomes a human gate and the whole cost model changes — the autonomy budget is set by consequence, not by capability."

---

## The general script (works for any prompt)

1. **Requirements & numbers** — volume, latency tolerance, channels, stakes, who's the adversary. Two minutes; state assumptions explicitly.
2. **Architecture** — boxes and arrows *with the loops* (agentic loop, eval loop, failure loop), naming which model tier goes where and why.
3. **Cross-cutting three** — evals (golden set + online sampling + the feedback loop), observability (traces with correlation ids, cost per span), failure modes (the taxonomy rows relevant here + what detection looks like).
4. **Trade-offs aloud** — the one you chose, what it cost, when you'd revisit.
5. **Numbers where possible** — rough cost/query, latency budget, corpus size. Arithmetic separates senior from mid instantly.

The most common failure at all levels: jumping to boxes without requirements. The second most common: no evals or observability until prompted — mentioning them *unprompted* is the strongest single signal in this round.
