# Embedding Model Selection

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard)

## Why this matters

Your embedding model is the lens through which retrieval sees your corpus. A weak embedding model caps RAG quality no matter how good your chunker, re-ranker, or LLM is.

## Core concepts

### The 2026 landscape

| Model | Dim | Open-weight? | Strengths | Notes |
|-------|-----|--------------|-----------|-------|
| OpenAI `text-embedding-3-large` / `-small` | 3072 / 1536 | No | Strong baseline; Matryoshka truncation supported | API only |
| Cohere `embed-v5.0-pro` / `-fast` | 256–2048 (default 2048) | No | Multilingual, multimodal (image+text+PDF), 128k context | API only; `embed-v4.0` still served |
| Voyage AI `voyage-3-large` | 2048 | No | Top-tier retrieval quality | API only; supports int8/binary |
| Qwen3-Embedding series | up to 4096 | Yes | Top of the open MTEB boards (2025-26) | Self-host |
| BGE-M3 | 1024 | Yes | Multi-lingual, multi-function (dense+sparse+colbert) | Self-host |
| gte-Qwen2.5 / NV-Embed | 1536+ | Yes | Strong open-weight alternatives | Self-host |
| Nomic Embed v1.5 | 768 | Yes | Open data, reproducible | Self-host |
| Jina v3/v4 | 1024 | Yes | Long-context | Self-host |

Google also serves embeddings through the Gemini API (`text-embedding-004`-class models) — check current pricing before committing; and remember MTEB leaderboard positions churn monthly: pick from the top cluster, not the single #1.

### Selection criteria

1. **Language coverage** — English-only models underperform on non-English.
2. **Modality** — text-only vs text+image.
3. **Dimension** — higher dim = better recall, more storage.
4. **Matryoshka support** — can you truncate dim for cost? (Yes for OpenAI v3, Nomic.)
5. **Max input length** — short models (512 tokens) force pre-truncation.

## Code: OpenAI

```python
from openai import OpenAI
client = OpenAI()

resp = client.embeddings.create(
    model="text-embedding-3-large",
    input=["text one", "text two"],
    dimensions=1536,  # matryoshka truncation
)
v1 = resp.data[0].embedding
```

## Code: self-hosted BGE-M3

```python
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

embeddings = model.encode(
    ["text one", "text two"],
    batch_size=12,
    max_length=8192,
    return_dense=True,
    return_sparse=True,
    return_colbert_vecs=False,
)
```

## Production concerns

- **Latency:** Self-hosted embeddings add 5–20ms per call on a GPU.
- **Cost:** OpenAI v3-large is ~$0.13/1M tokens. Self-hosted is essentially free at scale.
- **Failure modes:** Switching embedding models requires re-indexing everything. Pick carefully.
- **Security:** Embeddings can leak training data via inversion attacks. Don't expose raw embeddings of sensitive text.

## Anti-patterns

- ❌ **Using `ada-002` in 2026.** Superseded.
- ❌ **Mixing embedding models.** A query embedded with model A cannot match docs embedded with model B.
- ❌ **Defaulting to the highest-dim model.** Dim 3072 costs 4× storage vs 768, often with marginal recall gain.

## References

- [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard) — verified 2026-10-20
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings) — verified 2026-10-20
- [BGE-M3](https://huggingface.co/BAAI/bge-m3) — verified 2026-10-20
