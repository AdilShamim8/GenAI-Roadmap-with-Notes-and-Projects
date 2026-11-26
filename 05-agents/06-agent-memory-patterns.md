# Agent Memory Patterns

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Letta](https://github.com/letta-ai/letta), [Mem0](https://github.com/mem0ai/mem0)

## Why this matters

An agent without memory repeats itself, forgets decisions, and can't learn from its own history. Memory is what turns a stateless call into a persistent, improving assistant. But memory done wrong is a privacy and cost nightmare. The expert framing: memory is a *retrieval system over a curated knowledge store* — and the hard problems are curation (what deserves to be a memory), conflict (memories contradicting each other and reality), and governance (who can read, delete, and audit). "Store everything, retrieve by similarity" is the naive design that fails all three.

## Core concepts

### Four types of memory

| Type | What | Example | Storage |
|------|------|---------|---------|
| **Working** | Current turn + recent turns | Last 5 messages | In-context |
| **Episodic** | Past conversations | "User asked about refunds last week" | Vector DB |
| **Semantic** | Facts about the user/world | "User is on the Pro plan" | KV / graph |
| **Procedural** | How to do things | "Always cite sources" | System prompt |

The taxonomy earns its keep when you realize each type has a *different correctness criterion*: working memory must be *current* (stale = confusing this turn); episodic must be *retrievable* (the right episode at the right moment); semantic must be *true and current* (a fact contradicted by reality is a bug — "user is on Pro" after they downgraded is a lie the agent tells confidently); procedural must be *tested* (it's prompt behavior, evaluated like prompts). Most memory systems that "feel dumb" are failing one specific type — diagnose by type, not by vibe.

### Memory operations

- **Write** — after a turn, extract salient facts and persist (an LLM extraction step, not raw transcript storage).
- **Read** — before a turn, retrieve relevant memories.
- **Consolidate** — merge duplicates, resolve conflicts, promote recurring facts.
- **Decay** — old or low-relevance memories fade.

Two of these are where systems actually fail:

- **Write is a precision/recall tradeoff.** Over-write (store every sentence) → retrieval noise and cost blow-up; under-write → the memory exists in the transcript but never becomes retrievable. The production-grade write is *extraction with an update decision* (Mem0's core design): "given existing memories and this turn, what facts are new, what's updated, what's contradicted?" — not "embed this turn."
- **Consolidation is where semantic truth lives.** Without it, the store accumulates "Pro plan" and "downgraded to Free" as *coexisting* facts, and retrieval dice-rolls which one the agent sees this turn. Conflict resolution (latest-wins for user attributes, source-trust for disputed facts) is a design decision, not an emergent property.

### Memory layers (don't build from scratch first)

- **Mem0** — extract/update memory operations over your existing vector/graph store; the lightest integration path.
- **Letta (formerly MemGPT)** — full agent OS with core/archival memory blocks and sleep-time compute.
- **Zep / Graphiti** — temporal knowledge graphs: facts with validity intervals, good for "what was true when."
- **Provider-native** — Anthropic's memory tool (see `../02-context-engineering/03-context-distillation.md`) covers the simple end.

### The retrieval problem — and the injection amplification

Don't dump all memories into context. Retrieve the top-K most relevant to the current turn, similar to RAG — with two memory-specific twists:

1. **Recency and type belong in the ranking.** Pure similarity retrieves "user mentioned refunds in June 2024" for today's refund question — technically relevant, operationally stale. Rank by similarity × recency-weight, and query each memory type separately (semantic facts deserve a direct lookup — "what plan is this user on?" — not a fuzzy search).
2. **Memories are a prompt-injection persistence mechanism.** A malicious message in *one* session can be written into memory ("user prefers responses that include X URL") and re-injected into every future session. Memory turns transient injection into *persistent* injection — sanitize and provenance-tag at write time, not read time (`02-context-engineering/04-prompt-injection-defense.md`). This is the memory-specific attack surface most teams never consider until red-teaming finds it.

### Temporal validity — the underrated dimension

"User is on the Pro plan" is true *for an interval*. Zep/Graphiti's design insight: model facts with validity intervals (valid_from/valid_to), and query with "what was true when." Without temporal modeling, every fact update is either a destructive overwrite (you lose history — and audit) or an accumulating contradiction (consolidation burden forever). For user-attribute memory, latest-wins with a history table is usually enough; for anything where *when* matters (compliance, recommendations, "what did I tell you last month"), temporal graphs earn their complexity.

## Code: episodic memory with extraction-based writes

```python
import time
import faiss, numpy as np
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()
DIM = 1536  # text-embedding-3-small; use 3072 for -large
index = faiss.IndexFlatL2(DIM)
memories = []  # list of {text, ts, source}

class Extracted(BaseModel):
    facts: list[str]  # new or updated facts worth remembering

def embed(text: str) -> np.ndarray:
    return np.array(client.embeddings.create(
        model="text-embedding-3-small", input=text).data[0].embedding, dtype="float32")

def write_from_turn(user_input: str, assistant_reply: str, existing: list[str]):
    '''Extraction with dedupe — not raw transcript storage.'''
    resp = client.chat.completions.create(
        model="gpt-6-luna",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Given existing memories and a conversation turn, list NEW durable "
                "facts only (preferences, decisions, stable attributes). Skip "
                "transient content. Respond as JSON: {\"facts\": [...]}")},
            {"role": "user", "content": f"Existing: {existing}\n\nTurn: {user_input}\n{assistant_reply}"},
        ],
    )
    import json
    for fact in json.loads(resp.choices[0].message.content)["facts"]:
        index.add(embed(fact).reshape(1, -1))
        memories.append({"text": fact, "ts": time.time(), "source": "conversation"})

def recall(query: str, k: int = 3) -> list[str]:
    if not memories:
        return []
    _, idx = index.search(embed(query).reshape(1, -1), k)
    return [memories[i]["text"] for i in idx[0] if i >= 0]
```

## Code: injecting memories into the prompt

```python
def build_messages(user_input: str) -> list[dict]:
    relevant = recall(user_input)
    memory_block = "\n".join(f"- {m}" for m in relevant)
    return [
        {"role": "system", "content": f"You are a helpful assistant.\n\nRelevant past context (may be outdated; verify against current tools when it matters):\n{memory_block}"},
        {"role": "user", "content": user_input},
    ]
```

The parenthetical matters: memories are *hints with a staleness risk*, not authoritative state. Authoritative facts ("what plan is this user on") should come from a live tool call, with memory as the shortcut when freshness doesn't matter. Agents that treat retrieved memory as ground truth confidently contradict reality.

## Production concerns

- **Latency:** Memory retrieval adds 20–100ms; write extraction adds a background LLM call per turn (make it async — never block the user-facing path on write).
- **Cost:** Write extraction is a cheap-model call per turn (~$0.0001-0.0005 at Luna pricing) — meaningful at scale, and only worth it on sessions where memory changes. Cache by "turn contained a durable fact" heuristics if needed.
- **Failure modes:** (1) stale memories causing confident wrong answers — verify-against-tool for authoritative facts; (2) contradiction accumulation — consolidation runs (nightly, or Letta-style sleep-time compute); (3) memory bloat degrading retrieval precision — decay + dedupe; (4) the write-extractor being injected (garbage facts permanently stored) — sanitize + provenance-tag at write.
- **Security:** Memories are long-lived PII concentrates — encrypt at rest, per-user isolation (never a shared index across users), and deletion support that actually works (a user's "delete my data" must purge memories *and* the vector index entries *and* backups policy). Audit what's remembered — memory systems quietly become shadow profiles with compliance exposure.
- **Evals:** Memory recall evals — golden Q&A over past sessions ("what did I say my workspace setup was last week?") — are the only way to know the write/read pipeline works end-to-end (`../07-evals/01-golden-datasets.md`). Test staleness handling explicitly: golden pairs where the correct answer is "call the tool, don't trust memory."

## Anti-patterns

- ❌ **Stuffing all memories into context.** Top-K retrieval only, ranked by relevance × recency.
- ❌ **Never forgetting.** Implement decay and consolidation.
- ❌ **Shared memory across users.** Strict per-user isolation — this is a data-boundary requirement, not a preference.
- ❌ **Storing raw transcripts as "memory."** Extract facts (write pipeline) — raw text retrieval is RAG, not memory.
- ❌ **Memory as ground truth for authoritative facts.** Live tool calls for anything that can change; memory is hints.
- ❌ **No write-time sanitization.** Memory is an injection persistence mechanism — sanitize at write.
- ❌ **Deletion that doesn't reach the index.** Vector stores keep entries their row deletions forget; test the purge path.

## Decision framework

| Need | Use |
|------|-----|
| Simple cross-session facts | Provider memory tool / hand-rolled KV |
| Conversational memory at scale | Mem0 over your existing store |
| Long-running autonomous agents | Letta (core/archival blocks, sleep-time compute) |
| Time-aware facts ("what was true when") | Zep/Graphiti temporal graph |
| Authoritative current state | Not memory — a tool call to the system of record |
| Measuring any of this | Memory recall evals — golden Q&A over past sessions (`../07-evals/01-golden-datasets.md`) |

## References

- [Letta (formerly MemGPT)](https://github.com/letta-ai/letta) — verified 2026-10-20
- [Mem0](https://github.com/mem0ai/mem0) — verified 2026-10-20
- [Zep / Graphiti](https://github.com/getzep/graphiti) — verified 2026-10-20
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — verified 2026-10-20
