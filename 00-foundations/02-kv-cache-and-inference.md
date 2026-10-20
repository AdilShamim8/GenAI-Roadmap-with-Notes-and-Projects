# KV-Cache and Inference Economics

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [vLLM PagedAttention paper](https://arxiv.org/abs/2309.06180), [FlashAttention-2](https://arxiv.org/abs/2307.08691)

## Why this matters

The KV-cache is the single biggest determinant of inference cost at scale. Understanding it unlocks why vLLM is faster than naive HuggingFace, why prompt caching saves money, and why your 128K-context request is OOMing the GPU.

## Core concepts

### What is the KV-cache?

For every token in the prompt, the model computes Key and Value tensors that downstream tokens attend to. Instead of recomputing these on every decode step, we cache them. The cache grows linearly with sequence length × layers × heads × head_dim.

### The size math — and why modern models broke the naive formula

The textbook formula (MHA, all heads cached): a 70B-class model with 80 layers, 64 heads, 128 head_dim in fp16 caches `80 × 64 × 128 × 2 (K+V) × 2 bytes ≈ 2.6 MB/token` → ~83 GB for a 32K context — more than an 80GB H100. **No production model actually pays this**, because attention variants (see `00-transformers-deep-dive.md`) shrink it:

- **GQA** (Llama 3/4, Qwen): 8 KV heads instead of 64 → ~10x smaller cache (~260 KB/token in the example).
- **MLA** (DeepSeek V3/V4): KV compressed into a latent vector → order-of-magnitude smaller again.

When you size serving memory, read the model card's attention type first — the naive MHA math overshoots by 10–100x on modern architectures.

### Why vLLM is fast

vLLM's **PagedAttention** treats the KV-cache like virtual memory — pages, not contiguous blocks. This eliminates fragmentation and lets you batch 3–5× more requests per GPU.

## Code: see the cache in action

```python
# Naive generation — cache is internal but you can see its effect
from transformers import AutoModelForCausalLM, AutoTokenizer
import time

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.2-1B", device_map="auto")
tok = AutoTokenizer.from_pretrained("meta-llama/Llama-3.2-1B")

prompt = "Explain attention. " * 200  # ~1K tokens

# With KV-cache (default)
t = time.time()
out = model.generate(tok(prompt, return_tensors="pt").to("cuda").input_ids, max_new_tokens=100)
print(f"With cache: {time.time()-t:.2f}s")

# Without KV-cache (use_cache=False) — much slower
t = time.time()
out = model.generate(tok(prompt, return_tensors="pt").to("cuda").input_ids, max_new_tokens=100, use_cache=False)
print(f"Without cache: {time.time()-t:.2f}s")
```

## Production concerns

- **Latency:** Decode is sequential; cache size drives memory bandwidth, which drives per-token latency. Prefill-decode disaggregation (separate pools) is the 2026 answer at scale.
- **Cost:** KV-cache is often the binding GPU-memory constraint, not weights — it caps your batch size and therefore $/token. Anthropic/OpenAI prompt caching saves 50–90% on cache hits at the API layer.
- **Failure modes:** Long-context requests can OOM mid-decode and silently retry. FP8/INT8 KV-cache quantization halves memory for a small quality cost; speculative decoding (vLLM, SGLang) multiplies effective decode speed.
- **Security:** Cached prefixes are shared state — never cache user-specific data across tenants (see `01-llm-calling/06-prompt-caching.md`).

## Anti-patterns

- ❌ **Re-sending the same system prompt every request without prompt caching.** 5–10x cost penalty.
- ❌ **Using HuggingFace `generate` in production.** Use vLLM or SGLang (continuous batching is table stakes).
- ❌ **Assuming batch size = parallelism.** Continuous batching decouples them.
- ❌ **Sizing GPU memory with MHA math.** GQA/MLA models need 10–100x less cache — you'll massively overprovision.

## Decision framework

| Need | Use |
|------|-----|
| Self-serve, high throughput | vLLM (v0.30.x) with PagedAttention + prefix caching on by default |
| Structured outputs at speed | SGLang (RadixAttention reuses KV across similar prefixes) |
| Multi-model on one GPU | vLLM with LoRA adapters |
| API, no infra | OpenAI/Anthropic with prompt caching enabled |

## References

- [Efficient Memory Management for LLMs (PagedAttention)](https://arxiv.org/abs/2309.06180) — verified 2026-10-20
- [FlashAttention-2](https://arxiv.org/abs/2307.08691) — verified 2026-10-20
- [vLLM docs](https://docs.vllm.ai/) — verified 2026-10-20
