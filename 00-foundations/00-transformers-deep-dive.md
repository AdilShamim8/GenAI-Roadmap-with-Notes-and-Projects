# Transformers Deep Dive

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [Illustrated Transformer](http://jalammar.github.io/illustrated-transformer/), [Attention Is All You Need](https://arxiv.org/abs/1706.03762)

## Why this matters

Every frontier model you'll touch in 2026 — GPT-6, Claude 5.5, Gemini 3.x, Llama 4, DeepSeek V4 — is a transformer. You don't need to implement one from scratch, but you need enough mental model to reason about context windows, KV-cache, MoE, and why inference is expensive.

## Core concepts

### The transformer block

```mermaid
graph TD
    Input[Token embeddings + position] --> MHA[Multi-head self-attention]
    MHA --> Add1[Add & LayerNorm]
    Add1 --> FFN[Feed-forward network]
    FFN --> Add2[Add & LayerNorm]
    Add2 --> Out[Output]
```

Three operations dominate:
1. **Attention** — every token looks at every other token. O(n²) in sequence length.
2. **Feed-forward** — per-token MLP. The "knowledge" lives here.
3. **Residual + LayerNorm** — keeps gradients flowing.

### Attention variants you'll actually meet (2026)

The textbook multi-head attention (MHA) above is no longer what production models run. Three variants matter because they shrink the KV-cache (see `02-kv-cache-and-inference.md`):

- **GQA (grouped-query attention)** — many query heads share a few KV heads (Llama 3/4, Qwen). ~8x smaller KV-cache than MHA.
- **MLA (multi-head latent attention)** — DeepSeek's latent compression of KV (V3/V4 lines). An order of magnitude smaller cache; the reason DeepSeek serves so cheaply.
- **Sliding-window / hybrid attention** — attention restricted to a local window for long contexts (Gemma, some open models).

Positional encoding is RoPE (rotary) in essentially every current model — the detail that matters when serving stacks extend context (YaRN-style scaling).

### Attention in one line

```text
attention(Q, K, V) = softmax(Q·Kᵀ / sqrt(d_k)) · V
```

### The two-phase inference cost

This is the part most tutorials skip:

| Phase | What happens | Cost |
|-------|--------------|------|
| **Prefill** | Process the prompt; fill KV-cache | Compute-bound; parallel over tokens |
| **Decode** | Generate one token at a time; read KV-cache | Memory-bound; sequential |

Decode is why token generation is slow. The KV-cache is what makes it bearable.

## Code: minimal attention

```python
import torch
import torch.nn.functional as F

def attention(Q, K, V, mask=None):
    # Q, K, V: (batch, heads, seq, d_head)
    d_k = Q.size(-1)
    scores = Q @ K.transpose(-2, -1) / d_k ** 0.5
    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))
    weights = F.softmax(scores, dim=-1)
    return weights @ V
```

## Production concerns

- **Latency:** Prefill is parallel; decode is sequential. A 1M-token prompt takes seconds to prefill even on H100s.
- **Cost:** APIs bill separately for input (prefill) and output (decode) tokens. Output is usually 3–5× more expensive per token.
- **Failure modes:** "Lost in the middle" — models attend less well to tokens in the middle of long contexts.
- **Security:** Prompt injection works because attention has no concept of "trusted" vs "untrusted" tokens.

## Anti-patterns

- ❌ **Treating context window as free.** Doubling context does not double latency; it can 4× it (attention is O(n²)).
- ❌ **Assuming bigger context = better recall.** Empirically false past ~64K without retrieval.
- ❌ **Ignoring KV-cache economics.** A 128K context can blow your GPU memory budget on the cache alone.

## Decision framework

If you're picking a model for a task:
- Long input + short output → favor cheap-input models (Gemini Flash-Lite, DeepSeek).
- Short input + long output → favor cheap-output models (GPT-6 Luna, Claude Haiku 5.5).
- Both long → use prompt caching aggressively.

## References

- [The Illustrated Transformer — Jay Alammar](http://jalammar.github.io/illustrated-transformer/) — verified 2026-10-20
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — verified 2026-10-20
- [The Illustrated GPT-2 — Jay Alammar](https://jalammar.github.io/illustrated-gpt-2/) — verified 2026-10-20
