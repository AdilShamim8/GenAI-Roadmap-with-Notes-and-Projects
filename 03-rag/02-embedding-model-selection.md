# Embedding Model Selection

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard), [M3-Embedding](https://arxiv.org/abs/2402.03216)

## Why this matters

Your embedding model is the lens through which retrieval sees your corpus. A weak embedding model caps RAG quality no matter how good your chunker, re-ranker, or LLM is. The expert catch: embedding model choice is **the most expensive component to change later** — swap it and you re-embed the entire corpus, invalidate every cached vector, and re-validate every retrieval eval. Pick like you're marrying it.

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

Google also serves embeddings through the Gemini API (`text-embedding-004`-class models) — check current pricing before committing.

### How to read the MTEB leaderboard like an expert

Leaderboard positions churn monthly. The failure mode is chasing the #1 slot; the expert heuristics:

- **Pick from the top cluster, not the top row.** Differences within the top ~5 on MTEB averages are usually within noise for your corpus — and MTEB averages across 50+ tasks say little about *your* domain (legal, code, support tickets).
- **MTEB is retrieval-shaped but not your-retrieval-shaped.** It uses public corpora (Wikipedia, StackExchange, scientific abstracts). Your corpus has its own vocabulary and density. A model 2 points lower on MTEB can win on your data by 5.
- **Run a local bake-off.** Sample ~500 representative (query, gold-chunk) pairs from *your* production traffic, and measure recall@k for 3-4 finalists. This is a one-day exercise that beats a month of leaderboard-watching, and it's the only selection method that survives contact with your domain.

### Selection criteria

1. **Language coverage** — English-only models underperform on non-English; multilingual models pay a small English-quality tax (check per-language scores, not averages).
2. **Domain fit** — code corpora need code-trained embedders (Qwen3-Embedding code variants); generic models miss identifier-level matches.
3. **Modality** — text-only vs text+image (Cohere embed-v5 family does text+image+PDF natively).
4. **Dimension** — higher dim = better recall *marginally*, more storage + slower search. Dim 3072 costs 4x storage vs 768 for often single-digit recall gains.
5. **Matryoshka support** — can you truncate dim for cost? (Yes for OpenAI v3, Cohere v5, Nomic.) This is your escape hatch when storage outgrows budget: truncate *at query time* to build a two-tier index (coarse short-dim first pass, full-dim verification).
6. **Max input length** — short models (512 tokens) force pre-truncation and interact badly with long-chunk strategies; 8K+ (BGE-M3, Cohere v5, Jina) enables late chunking (`01-chunking-strategies.md`).
7. **Symmetric vs asymmetric** — some models distinguish query/doc prefixes (BGE uses `Represent this sentence...` instructions); using the model's intended prefix pattern is worth several MTEB points.

### The bi-encoder contract (what you're really buying)

An embedding model is trained with a specific objective — contrastive query-doc pairs (asymmetric retrieval) vs sentence-pair similarity (symmetric STS). Retrieval tasks want asymmetric training. This is why sentence-similarity models (trained on NLI/STS data) disappoint in RAG: they encode "are these two texts about the same thing," not "does this doc answer this question." M3-Embedding (arXiv 2402.03216) documents the multi-function design — dense + sparse + multi-vector from one model — which is why BGE-M3 shows up in so many hybrid-search stacks: one embed pass yields all three signals.

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

## Code: self-hosted BGE-M3 (dense + sparse in one pass)

```python
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

embeddings = model.encode(
    ["text one", "text two"],
    batch_size=12,
    max_length=8192,
    return_dense=True,
    return_sparse=True,   # sparse weights power the BM25-ish half of hybrid search
    return_colbert_vecs=False,
)
```

## Code: local bake-off harness

```python
import random

def bakeoff(model_embed, gold_pairs, k=10):
    '''gold_pairs: list of (query, gold_chunk_text) from YOUR traffic.'''
    random.shuffle(gold_pairs)
    corpus = [c for _, c in gold_pairs]
    doc_embs = model_embed(corpus)
    hits = 0
    for i, (q, gold) in enumerate(gold_pairs):
        scores = [dot(model_embed([q])[0], d) for d in doc_embs]
        top = sorted(range(len(scores)), key=lambda j: -scores[j])[:k]
        if i in top:  # gold's own index must appear in top-k
            hits += 1
    return hits / len(gold_pairs)

# Compare finalists on identical samples; the winner on YOUR data is the winner.
```

## Production concerns

- **Latency:** Self-hosted embeddings add 5–20ms per call on a GPU (batch heavily at index time). API embedders add network RTT — batch queries to 1 request where possible.
- **Cost:** OpenAI v3-large is ~$0.13/1M tokens — a 100M-token corpus is ~$13 one-time; query-side is negligible. Self-hosted is essentially free at scale but carries the serving burden (GPU, versioning, batch sizing).
- **Failure modes:** (1) **Silent model swaps** — providers update embedding models behind stable names; vectors drift out of distribution with your stored ones. Pin versions and monitor a recall canary (a fixed set of query→gold pairs scored daily). (2) Mixing models — a query embedded with model A cannot match docs embedded with model B (different vector spaces, even at identical dims). (3) Prefix mismatch — missing the model's expected query/doc instruction prefixes quietly costs recall.
- **Security:** Embeddings can leak training data via inversion attacks. Don't expose raw embeddings of sensitive text through public APIs; treat vector stores as sensitive data stores, not metadata.

## Anti-patterns

- ❌ **Using `ada-002` in 2026.** Superseded.
- ❌ **Mixing embedding models across query/doc sides.** Different spaces — retrieval silently degrades to noise.
- ❌ **Defaulting to the highest-dim model.** Dim 3072 costs 4x storage vs 768, often with marginal recall gain.
- ❌ **Picking by leaderboard #1 without a local bake-off.** MTEB averages ≠ your domain.
- ❌ **Assuming stable model names mean stable vectors.** Monitor a recall canary; plan re-index runs.

## References

- [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard) — verified 2026-10-20
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings) — verified 2026-10-20
- [M3-Embedding (BGE-M3)](https://arxiv.org/abs/2402.03216) — verified 2026-10-20
- [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3) — verified 2026-10-20
