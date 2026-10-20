# KV-Cache and Inference Economics

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [vLLM PagedAttention paper](https://arxiv.org/abs/2309.06180), [Orca (continuous batching, OSDI'22)](https://www.usenix.org/conference/osdi22/presentation/yu), [SGLang RadixAttention](https://arxiv.org/abs/2312.07104)

## Why this matters

The KV-cache is the single biggest determinant of inference cost at scale. Understanding it unlocks why vLLM is faster than naive HuggingFace, why prompt caching saves money, and why your 128K-context request is OOMing the GPU. It is also the layer where the serving-stack vocabulary lives — continuous batching, prefix caching, chunked prefill, disaggregation — and you cannot capacity-plan or debug a production LLM service without that vocabulary.

## Core concepts

### What is the KV-cache?

For every token in the prompt, the model computes Key and Value tensors that downstream tokens attend to. Instead of recomputing these on every decode step, we cache them. The cache grows linearly with `sequence_length × layers × kv_heads × head_dim`. Two consequences follow immediately: the cache is *per sequence* (batch × context multiplies it), and every decode step must *read the whole cache* — so per-token decode latency creeps up as history grows, which is the TPOT-vs-context curve you see in every serving benchmark.

### The size math — and why modern models broke the naive formula

The textbook formula (MHA, all heads cached): a 70B-class model with 80 layers, 64 heads, 128 head_dim in fp16 caches `80 × 64 × 128 × 2 (K+V) × 2 bytes ≈ 2.6 MB/token` → ~84 GB for a 32K context — more than an 80 GB H100. **No production model actually pays this**, because attention variants (see `00-transformers-deep-dive.md`) shrink it:

- **GQA** (Llama 3/4, Qwen): 8 KV heads instead of 64 → exactly 8× smaller cache (~330 KB/token in the example); a 32K context now fits in ~10.5 GB.
- **MLA** (DeepSeek V3/V4): KV compressed into a latent vector → order-of-magnitude smaller again (93.3% cache reduction reported in the [DeepSeek-V2 paper](https://arxiv.org/abs/2405.04434)).

When you size serving memory, read the model card's attention type first — the naive MHA math overshoots by 10-100× on modern architectures. The full budget is `weights + Σ(batch × per-sequence cache) + activations`; the cache term is the only one that grows with traffic, which is why it — not weights — is usually the binding constraint and the thing that caps your batch size, and therefore $/token.

### Why vLLM is fast: two distinct tricks people conflate

1. **Continuous batching** (introduced by [Orca, Yu et al., OSDI'22](https://www.usenix.org/conference/osdi22/presentation/yu)): the scheduler operates at *token-iteration* granularity, not request granularity. Finished requests leave the batch immediately; queued requests join at the next iteration. With static batching, every short request waits for the longest one in its batch — the vLLM paper measured naive serving running at 4-36× below the hardware's capability, and continuous batching recovers most of it.
2. **PagedAttention** ([Kwon et al. 2023](https://arxiv.org/abs/2309.06180)): the KV-cache is stored in fixed-size blocks (16 tokens by default) with an indirection table, like OS virtual memory. This kills external fragmentation (reserve-the-max waste was 60-80% of cache in contiguous allocation) and enables block sharing: identical prefixes (system prompt, few-shot header) are stored once via copy-on-write. vLLM reports 2-4× throughput vs HuggingFace TGI at equal latency; the win comes from memory efficiency → bigger effective batches, not from faster kernels.

**Prefix caching** is the API-visible relative: SGLang's RadixAttention ([Zheng et al. 2023](https://arxiv.org/abs/2312.07104)) organizes cached prefixes in a radix tree so any request whose prompt extends a previously-seen prefix reuses its KV blocks outright; vLLM ships automatic prefix caching with the same effect. This is the self-hosted analogue of OpenAI/Anthropic prompt caching — and the reason multi-turn chat costs far less than 4 × single-turn.

## Code: see the cache in action

```python
# Naive generation — cache is internal but you can see its effect
from transformers import AutoModelForCausalLM, AutoTokenizer
import time

model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.2-1B", device_map="auto", torch_dtype="auto")  # gated: accept license first
tok = AutoTokenizer.from_pretrained("meta-llama/Llama-3.2-1B")

prompt = "Explain attention. " * 200  # ~1K tokens

# With KV-cache (default)
t = time.time()
out = model.generate(tok(prompt, return_tensors="pt").to("cuda").input_ids, max_new_tokens=100)
print(f"With cache: {time.time()-t:.2f}s")

# Without KV-cache (use_cache=False) — every step recomputes the whole prefix
t = time.time()
out = model.generate(tok(prompt, return_tensors="pt").to("cuda").input_ids,
                     max_new_tokens=100, use_cache=False)
print(f"Without cache: {time.time()-t:.2f}s")  # O(n^2) re-prefill per token: brutally slower
```

The gap you measure here *is* the KV-cache's value: without it, every decoded token re-runs the full prefix through every layer — quadratic total work instead of linear-plus-cache-reads.

## Production concerns

- **Latency:** Decode is sequential; cache size drives memory bandwidth, which drives per-token latency. The two SLO metrics that matter are **TTFT** (time to first token — prefill-dominated, what users feel as "it answered") and **TPOT/ITL** (time per output token — decode-dominated, what keeps the stream feeling live; users notice >100ms inter-token). Prefill-decode disaggregation (separate GPU pools) is the 2026 answer at scale precisely because the two phases want different hardware: prefill is compute-bound, decode is bandwidth-bound.
- **Cost:** KV-cache is often the binding GPU-memory constraint, not weights — it caps your batch size and therefore $/token. Anthropic/OpenAI prompt caching saves 50-90% on cache hits at the API layer.
- **Failure modes:** Long-context requests can OOM mid-decode and silently retry. FP8/INT8 KV-cache quantization halves cache memory for near-zero quality cost on most workloads (supported natively in vLLM via `kv_cache_dtype`); speculative decoding (vLLM, SGLang) multiplies effective decode speed on accept-heavy workloads.
- **Chunked prefill:** serving stacks slice long prompts into chunks interleaved with decode steps so one 1M-token prefill doesn't starve every other tenant's token stream — ask for it explicitly if you serve mixed long/short traffic.
- **Security:** Cached prefixes are shared state — never cache user-specific data across tenants (see `01-llm-calling/06-prompt-caching.md`). Prefix caches keyed only on content create a cross-tenant timing side-channel; key on tenant where the stack allows.

## Anti-patterns

- ❌ **Re-sending the same system prompt every request without prompt caching.** 5-10× cost penalty.
- ❌ **Using HuggingFace `generate` in production.** Use vLLM or SGLang (continuous batching is table stakes).
- ❌ **Assuming batch size = parallelism.** Continuous batching decouples them; your real lever is memory-bound batch capacity.
- ❌ **Sizing GPU memory with MHA math.** GQA/MLA models need 10-100× less cache — you'll massively overprovision.
- ❌ **Reporting only average latency.** TTFT and TPOT have different tails and different causes; a p50-only dashboard hides the exact pathology your users complain about.

## Decision framework

| Need | Use |
|------|-----|
| Self-serve, high throughput | vLLM (v0.30.x) with PagedAttention + prefix caching on by default |
| Structured outputs at speed | SGLang (RadixAttention reuses KV across similar prefixes) |
| Long shared prefixes, many turns | Any stack with prefix caching; order prompt content static-first, dynamic-last |
| Multi-model on one GPU | vLLM with LoRA adapters |
| Tight TTFT SLO at high load | Prefill/decode disaggregation; keep prefill pool small but compute-dense |
| API, no infra | OpenAI/Anthropic with prompt caching enabled |

## References

- [Efficient Memory Management for LLMs (PagedAttention)](https://arxiv.org/abs/2309.06180) — verified 2026-10-20
- [Orca: iteration-level scheduling (continuous batching), OSDI'22](https://www.usenix.org/conference/osdi22/presentation/yu) — verified 2026-10-20 (canonical source; USENIX site blocks CLI clients)
- [SGLang: RadixAttention prefix caching](https://arxiv.org/abs/2312.07104) — verified 2026-10-20
- [FlashAttention-2](https://arxiv.org/abs/2307.08691) — verified 2026-10-20
- [DeepSeek-V2 (MLA cache reduction)](https://arxiv.org/abs/2405.04434) — verified 2026-10-20
- [vLLM docs](https://docs.vllm.ai/) — verified 2026-10-20
