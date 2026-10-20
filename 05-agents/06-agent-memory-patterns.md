# Agent Memory Patterns

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Letta](https://github.com/letta-ai/letta), [Mem0](https://github.com/mem0ai/mem0)

## Why this matters

An agent without memory repeats itself, forgets decisions, and can't learn from its own history. Memory is what turns a stateless call into a persistent, improving assistant. But memory done wrong is a privacy and cost nightmare.

## Core concepts

### Four types of memory

| Type | What | Example | Storage |
|------|------|---------|---------|
| **Working** | Current turn + recent turns | Last 5 messages | In-context |
| **Episodic** | Past conversations | "User asked about refunds last week" | Vector DB |
| **Semantic** | Facts about the user/world | "User is on the Pro plan" | KV / graph |
| **Procedural** | How to do things | "Always cite sources" | System prompt |

### Memory operations

- **Write** — after a turn, extract salient facts and persist (an LLM extraction step, not raw transcript storage).
- **Read** — before a turn, retrieve relevant memories.
- **Consolidate** — merge duplicates, resolve conflicts, promote recurring facts.
- **Decay** — old or low-relevance memories fade.

### Memory layers (don't build from scratch first)

- **Mem0** — extract/update memory operations over your existing vector/graph store; the lightest integration path.
- **Letta (formerly MemGPT)** — full agent OS with core/archival memory blocks and sleep-time compute.
- **Zep / Graphiti** — temporal knowledge graphs: facts with validity intervals, good for "what was true when."
- **Provider-native** — Anthropic's memory tool (see `../02-context-engineering/03-context-distillation.md`) covers the simple end.

### The retrieval problem

Don't dump all memories into context. Retrieve the top-K most relevant to the current turn, similar to RAG.

## Code: simple episodic memory

```python
import time
import faiss, numpy as np
from openai import OpenAI

client = OpenAI()
DIM = 1536  # text-embedding-3-small; use 3072 for -large
index = faiss.IndexFlatL2(DIM)
memories = []  # list of {text, ts}

def embed(text: str) -> np.ndarray:
    return np.array(client.embeddings.create(
        model="text-embedding-3-small", input=text).data[0].embedding, dtype="float32")

def remember(text: str):
    index.add(embed(text).reshape(1, -1))
    memories.append({"text": text, "ts": time.time()})

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
        {"role": "system", "content": f"You are a helpful assistant.\n\nRelevant past context:\n{memory_block}"},
        {"role": "user", "content": user_input},
    ]
```

## Production concerns

- **Latency:** Memory retrieval adds 20–100ms.
- **Cost:** Embedding memory writes + retrieval queries add up. Cache aggressively.
- **Failure modes:** Stale memories cause confusion. Implement TTLs and forgetting.
- **Security:** Memories can contain PII. Encrypt at rest; respect deletion requests.

## Anti-patterns

- ❌ **Stuffing all memories into context.** Top-K retrieval only.
- ❌ **Never forgetting.** Implement decay.
- ❌ **Shared memory across users.** Strict per-user isolation.
- ❌ **Storing raw transcripts as "memory."** Extract facts (write pipeline) — raw text retrieval is RAG, not memory.

## Decision framework

| Need | Use |
|------|-----|
| Simple cross-session facts | Provider memory tool / hand-rolled KV |
| Conversational memory at scale | Mem0 over your existing store |
| Long-running autonomous agents | Letta (core/archival blocks, sleep-time compute) |
| Time-aware facts ("what was true when") | Zep/Graphiti temporal graph |
| Measuring any of this | Memory recall evals — golden Q&A over past sessions (`../07-evals/01-golden-datasets.md`) |

## References

- [Letta (formerly MemGPT)](https://github.com/letta-ai/letta) — verified 2026-10-20
- [Mem0](https://github.com/mem0ai/mem0) — verified 2026-10-20
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — verified 2026-10-20
