# vLLM, SGLang, TGI

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [vLLM](https://docs.vllm.ai/), [SGLang](https://github.com/sgl-project/sglang)

## Why this matters

If you're self-hosting, the serving framework determines your throughput, latency, and cost. The serious open-source options in 2026 are vLLM (v0.30.x) and SGLang, plus NVIDIA's TensorRT-LLM for maximum-throughput NVIDIA deployments. Hugging Face TGI was archived in 2025 — existing guides referencing it are stale. Pick wrong and you'll pay 2–5x more for the same throughput. The expert framing: these engines are not "model loaders" — they are *schedulers* whose product is GPU utilization. The model just sits there; the engine decides which requests batch together, how KV-cache memory is carved up, and when prefill yields to decode. Every differentiator in the comparison is a scheduling policy.

## The comparison

| Dimension | vLLM | SGLang | TGI |
|-----------|------|--------|-----|
| **Throughput** | Industry-leading | Comparable; better for similar-prefix workloads | Good |
| **KV-cache** | PagedAttention | PagedAttention + RadixAttention (prefix sharing) | Paged attention |
| **Multi-LoRA** | Yes | Yes | Yes |
| **Structured output** | xgrammar (default since late 2024) + outlines/JSON schemas | Native (very fast) | N/A |
| **Multimodal** | Yes | Yes | Yes |
| **Maturity** | Very high | High | Very high |
| **Best for** | General high-throughput | Code completion, chatbots with shared prefixes | Enterprise HuggingFace stack |

### Why scheduling dominates (the mental model)

Three engine behaviors explain most real-world throughput numbers (`00-foundations/02-kv-cache-and-inference.md` has the mechanics):

- **Continuous batching** — the engine interleaves new requests into the batch as others finish, instead of waiting for the whole batch (static batching's fatal flaw). Both engines have it; it's the reason naive `transformers` serving is 10-50x behind.
- **PagedAttention** — KV-cache stored in pages like OS virtual memory, eliminating the fragmentation of pre-allocated per-request slots. This is what lets a GPU hold 2-3x more concurrent requests.
- **Prefix caching / RadixAttention** — identical prefixes share KV-cache entries. SGLang's radix-tree organization *evicts intelligently by shared-ness*; vLLM's prefix caching (on by default in the V1 engine) is hash-based. For chatbot workloads where every request shares the same system prompt, this is 2-5x — it's the closest thing to free money in self-hosting.

The scheduling lens also explains *when* benchmarks mislead: throughput benchmarks on single-burst prompts measure compute saturation, but production chatbot traffic is prefix-heavy and bursty — an engine that wins the benchmark can lose your workload. Benchmark *your* traffic shape (your real prefixes, your real length distribution) before choosing.

### The decision heuristics

- **Default: vLLM.** Broadest model support, biggest community, most battle-tested ops paths. When in doubt, start here.
- **SGLang when** your workload is prefix-sharing-heavy (multi-turn chat with long shared system prompts, code completion where the file context repeats per request) — RadixAttention's prefix reuse is the edge — or when you want its structured-output speed.
- **TensorRT-LLM when** you're all-NVIDIA, want maximum throughput per GPU, and can absorb its build/compile complexity and slower iteration on new models.
- **The OpenAI-compatible API is the portability layer** — all engines speak it; your client code shouldn't know which engine is behind the URL. This keeps the engine a swappable component (the same discipline as model config, `08-production/06-model-versioning-migration.md`).

## Code: vLLM serving

```bash
# Start a server
pip install vllm
vllm serve meta-llama/Llama-3.1-8B-Instruct  # or any 2026 open-weight model \
    --port 8000 \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    # prefix caching is ON by default in the V1 engine
```

```python
# Client (OpenAI-compatible)
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

resp = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Code: SGLang with structured output

```python
# pip install sglang
import sglang as sgl

@sgl.function
def classify(s, text):
    s += "Classify the sentiment of this review as 'positive', 'neutral', or 'negative':\n"
    s += text + "\n"
    s += "Sentiment:" + sgl.gen("sentiment", regex=r"(positive|neutral|negative)")  # legacy DSL; prefer the OpenAI-compatible server + /v1/chat/completions with regex/json_schema

state = classify.run(text="This product is amazing!")
print(state["sentiment"])
```

SGLang's regex-constrained decoding is the fastest way to serve structured outputs from open-weight models.

## Production concerns

- **Latency:** vLLM and SGLang are within 10% of each other on most workloads. The bigger latency lever is your *decode length*, not engine choice (`08-production/02-latency-slos.md`).
- **Cost:** Self-hosted cost = GPU hours. Utilize >50% or stick with API (`05-breakeven-math.md`). Watch the two silent utilization killers: `--max-model-len` set to the model max (reserves KV for 200K-token requests nobody sends — set it to your real p99 + headroom), and over-provisioned replicas for peak traffic that idles 20 hours a day.
- **Failure modes:** (1) cold start is slow (model load = minutes) — keep warm pools, health-check with real requests; (2) engine-version regressions — pin versions, benchmark on upgrade like any dependency; (3) silent prefix-cache misses — a client that mutates the system prompt per request (timestamps!) defeats prefix caching; monitor cache-hit metrics.
- **Security:** Self-hosted models have no content filtering. Add your own — you're now the provider; moderation, injection screening, and abuse controls that the API vendor used to handle are your line (`10-safety/`).

## Anti-patterns

- ❌ **HuggingFace `generate()` in production.** Use vLLM/SGLang — 10–50x throughput difference.
- ❌ **One model per GPU.** Multi-LoRA lets you serve N fine-tunes on one GPU.
- ❌ **No prefix caching.** 2–5× cost penalty for chat workloads.
- ❌ **`--max-model-len` at model max.** Reserve KV for real traffic, not theoretical requests.
- ❌ **Engine benchmarks on synthetic traffic.** Benchmark your prefix/length distribution.
- ❌ **Client code coupled to engine specifics.** OpenAI-compatible API keeps engines swappable.

## References

- [vLLM](https://docs.vllm.ai/) — verified 2026-10-20
- [SGLang](https://github.com/sgl-project/sglang) — verified 2026-10-20
- [HuggingFace TGI (archived)](https://github.com/huggingface/text-generation-inference) — verified 2026-10-20
