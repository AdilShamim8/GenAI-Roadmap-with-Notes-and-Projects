# Mixture of Experts (MoE)

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Mixtral paper](https://arxiv.org/abs/2401.04088), [DeepSeek-V3 technical report](https://arxiv.org/abs/2412.19437), [GShard](https://arxiv.org/abs/2006.16668), [Switch Transformer](https://arxiv.org/abs/2101.03961)

## Why this matters

Llama 4, DeepSeek V3/V4, Qwen3, Kimi K2/K3, GLM, gpt-oss — essentially every frontier and frontier-adjacent release since 2024 — uses MoE. MoE is why a 671B-parameter DeepSeek V3 serves at the cost of a 37B dense model. If you don't understand MoE, you'll misread model cards and overpay for inference.

## Core concepts

### The idea

Instead of every token passing through every parameter, a **router** sends each token to a small number of **experts** (typically 2 out of 8, or 8 out of 256 in fine-grained designs). Total parameters stay high (knowledge capacity), but active parameters per token stay low (compute cost). The router is a single linear layer per MoE block — tiny, but it decides everything.

### The math

For a layer with N experts, top-k routing:

```python
gate_scores = softmax(W_gate @ token)  # shape (N,)
top_k_experts = topk(gate_scores, k=2)
output = sum(gate_scores[i] * expert_i(token) for i in top_k_experts)
```

Two details the pseudocode hides:

- **Renormalization.** Mixtral softmaxes over all experts, takes top-k, then *renormalizes the k weights to sum to 1* (the top-k weights from a full softmax don't). Get this wrong in a reimplementation and outputs drift subtly.
- **Load balancing is the hard part.** An untrained router collapses onto a few experts and the model becomes a dense model with dead weights. The historical fix was auxiliary load-balancing losses ([Shazeer et al. 2017](https://arxiv.org/abs/1701.06538), refined through [GShard](https://arxiv.org/abs/2006.16668) and ST-MoE's router z-loss), which fight quality for balance. DeepSeek-V3's **auxiliary-loss-free** scheme instead adds a per-expert bias term used *only* for top-k selection (not for the gate value) — nudging routing toward under-used experts without distorting outputs. This is the load-balancing design to know in 2026 because it's what the serving-cheap models actually run.

### The design lineage (why 2026 configs look like they do)

- **GShard** ([Lepikhin et al. 2020](https://arxiv.org/abs/2006.16668)) introduced expert **capacity**: each expert gets a token budget of `capacity_factor × (tokens_in_batch / n_experts)`; tokens over budget are **dropped** (residual still carries them). Capacity factor is still the throughput-vs-quality knob in MoE serving — drop too many tokens and quality falls; set it too high and you waste the padding.
- **Switch Transformer** ([Fedus et al. 2021](https://arxiv.org/abs/2101.03961)) showed top-1 routing works (simpler, faster) with the right training recipe.
- **Mixtral 8x7B/8x22B** ([2024](https://arxiv.org/abs/2401.04088)) made plain softmax top-2 with renormalization the default open recipe.
- **DeepSeek V3/V4** push fine-grained routing: 256 small routed experts per layer with top-8 selection, plus **1 always-on shared expert** (keeps common computation out of the routing path), and **node-limited routing** — a token's experts are constrained to ≤4 nodes so the all-to-all traffic stays inside NVLink domains where possible.

### The 2025-26 MoE roster (verified)

| Model | Total / active params | Notes |
|--------|----------------------|-------|
| Mixtral 8x22B | 141B / 39B | The 2024 reference implementation |
| DeepSeek V3 → V4-Flash | 671B / 37B → 284B / 13B | Fine-grained experts + shared expert + auxiliary-loss-free routing |
| Llama 4 Scout / Maverick | ~109B/400B-class / 17B active | Multimodal MoE |
| Qwen3 MoE line | up to 235B / 22B active | Open-weight, Apache-2.0 (most sizes) |
| Kimi K2 → K3 | 1T-class / 32-50B active | Agentic-specialized MoE |
| gpt-oss-120b / 20b | 117B/5.1B, 21B/3.6B | OpenAI's Apache-2.0 open weights (Aug 2025), MXFP4-quantized |

MoE trades VRAM for throughput. The model is bigger on disk but cheaper per token — *per token at sufficient batch*.

### Serving-side reality

Serving MoE at scale needs **expert parallelism**: experts spread across GPUs, tokens dispatched to their routed experts with an all-to-all, computed, and combined with a second all-to-all. The consequences that surprise people:

- **MoE's advantage is batch-size dependent.** At large batch, the all-to-all amortizes and MoE throughput per GPU is spectacular. At batch 1-4, you still pay the dispatch latency and per-expert kernel launches, and the model's full weight set still streams through memory — a dense model of equal *active* params can win at low concurrency. Benchmark at your real concurrency, not the vendor's.
- **All experts must be resident.** Budget VRAM for *total* params (quantized: DeepSeek-V3 FP8 ≈ ~671 GB; gpt-oss-120b MXFP4 ≈ ~60 GB), not the active count. Expert offloading fits big MoE on fewer GPUs by paging cold experts over PCIe — fine for batch-1 demos, a bottleneck under load.
- **Expert imbalance is a production failure mode.** Real traffic can concentrate on a few experts (one domain, one language), overflowing capacity and dropping tokens. Watch per-expert utilization; DeepSeek's bias-adjusted routing mitigates but doesn't eliminate it.

## Code: see the router

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class MoELayer(nn.Module):
    def __init__(self, d_model, n_experts=8, k=2):
        super().__init__()
        self.gate = nn.Linear(d_model, n_experts)
        self.experts = nn.ModuleList([nn.Linear(d_model, d_model) for _ in range(n_experts)])
        self.k = k

    def forward(self, x):  # x: (batch, seq, d_model)
        gate_scores = F.softmax(self.gate(x), dim=-1)  # (batch, seq, n_experts)
        topk_vals, topk_idx = gate_scores.topk(self.k, dim=-1)
        topk_vals = topk_vals / topk_vals.sum(dim=-1, keepdim=True)  # Mixtral-style renorm
        out = torch.zeros_like(x)
        for i in range(self.k):
            for b in range(x.size(0)):
                for s in range(x.size(1)):
                    expert_idx = topk_idx[b, s, i].item()
                    out[b, s] += topk_vals[b, s, i] * self.experts[expert_idx](x[b, s])
        return out
```

(Real implementations vectorize this; the loop is for clarity.)

## Production concerns

- **VRAM:** MoE models need more VRAM than dense models of equivalent throughput — all experts must be resident. Plan for it.
- **Load balancing:** Bad routers send all tokens to one expert, killing throughput. Pretraining includes load-balancing (loss-based or bias-adjusted); verify your fine-tune doesn't break it — watch routing entropy before/after.
- **Quantization:** MoE + quantization is finicky. Use FP8/MXFP4-aware pipelines (vLLM + llm-compressor) rather than naive INT4 GPTQ; DeepSeek V3 was *trained* in FP8 and gpt-oss ships MXFP4 natively, so those stacks are the well-trodden path.
- **Fine-tuning:** freeze the router unless you have a load-balancing strategy; LoRA on attention only is the safe default, LoRA on experts works with router frozen and expert-balanced data.

## Anti-patterns

- ❌ **Comparing MoE and dense models by total parameter count.** Compare by active params — and then by $/1M tokens at your concurrency.
- ❌ **Fine-tuning one expert in isolation.** Breaks the routing distribution.
- ❌ **Reading "120B" on gpt-oss-120b and budgeting for a 120B dense model.** Only 5.1B are active per token — but ~60 GB of MXFP4 weights still need to sit in VRAM.
- ❌ **Benchmarking MoE at batch 1 and extrapolating.** The all-to-all and residency economics invert with batch size; measure the concurrency you'll actually run.

## Decision framework

| Situation | Choose |
|-----------|--------|
| Max quality per serving dollar | Frontier MoE (DeepSeek V4, Qwen3-MoE, Kimi) |
| Single-GPU self-hosting | Small MoE (gpt-oss-20b) or dense small model |
| Low-concurrency latency-critical serving | Compare against dense at *your* batch; MoE's win shrinks at batch 1-4 |
| Fine-tuning on modest hardware | Dense or LoRA-on-MoE with care (router frozen) |
| Comparing models on a leaderboard | Always normalize by active params and price per 1M tokens |

## References

- [Mixtral of Experts](https://arxiv.org/abs/2401.04088) — verified 2026-10-20
- [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437) — verified 2026-10-20
- [GShard: expert capacity + conditional computation](https://arxiv.org/abs/2006.16668) — verified 2026-10-20
- [Switch Transformers (top-1 routing)](https://arxiv.org/abs/2101.03961) — verified 2026-10-20
- [Outrageously Large Neural Networks (original MoE)](https://arxiv.org/abs/1701.06538) — verified 2026-10-20
- [gpt-oss model cards](https://github.com/openai/gpt-oss) — verified 2026-10-20
