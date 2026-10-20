# Mixture of Experts (MoE)

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Mixtral paper](https://arxiv.org/abs/2401.04088), [DeepSeek-V3 technical report](https://github.com/deepseek-ai/DeepSeek-V3)

## Why this matters

Llama 4, DeepSeek V3/V4, Qwen3, Kimi K2/K3, GLM, gpt-oss — essentially every frontier and frontier-adjacent release since 2024 — uses MoE. MoE is why a 671B-parameter DeepSeek V3 serves at the cost of a 37B dense model. If you don't understand MoE, you'll misread model cards and overpay for inference.

## Core concepts

### The idea

Instead of every token passing through every parameter, a **router** sends each token to a small number of **experts** (typically 2 out of 8). Total parameters stay high (knowledge capacity), but active parameters per token stay low (compute cost).

### The math

For a layer with N experts, top-k routing:

```python
gate_scores = softmax(W_gate @ token)  # shape (N,)
top_k_experts = topk(gate_scores, k=2)
output = sum(gate_scores[i] * expert_i(token) for i in top_k_experts)
```

### The 2025-26 MoE roster (verified)

| Model | Total / active params | Notes |
|--------|----------------------|-------|
| Mixtral 8x22B | 141B / 39B | The 2024 reference implementation |
| DeepSeek V3 → V4-Flash | 671B / 37B → 284B / 13B | Fine-grained experts + shared expert + auxiliary-loss-free routing |
| Llama 4 Scout / Maverick | ~109B/400B-class / 17B active | Multimodal MoE |
| Qwen3 MoE line | up to 235B / 22B active | Open-weight, Apache-2.0 (most sizes) |
| Kimi K2 → K3 | 1T-class / 32-50B active | Agentic-specialized MoE |
| gpt-oss-120b / 20b | 117B/5.1B, 21B/3.6B | OpenAI's Apache-2.0 open weights (Aug 2025), MXFP4-quantized |

MoE trades VRAM for throughput. The model is bigger on disk but cheaper per token.

### Serving-side reality

Serving MoE at scale needs **expert parallelism** (experts spread across GPUs with all-to-all token routing) — vLLM and SGLang both support it. Expert offloading fits a big MoE on fewer GPUs at the cost of PCIe traffic. Budget VRAM for *all* experts resident, not just active ones.

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
        topk_vals = topk_vals / topk_vals.sum(dim=-1, keepdim=True)
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
- **Load balancing:** Bad routers send all tokens to one expert, killing throughput. Pretraining includes load-balancing loss; verify your fine-tune doesn't break it.
- **Quantization:** MoE + quantization is finicky. Use FP8/MXFP4-aware pipelines (vLLM + llm-compressor) rather than naive INT4 GPTQ.

## Anti-patterns

- ❌ **Comparing MoE and dense models by total parameter count.** Compare by active params.
- ❌ **Fine-tuning one expert in isolation.** Breaks the routing distribution.
- ❌ **Reading "120B" on gpt-oss-120b and budgeting for a 120B dense model.** Only 5.1B are active per token.

## Decision framework

| Situation | Choose |
|-----------|--------|
| Max quality per serving dollar | Frontier MoE (DeepSeek V4, Qwen3-MoE, Kimi) |
| Single-GPU self-hosting | Small MoE (gpt-oss-20b) or dense small model |
| Fine-tuning on modest hardware | Dense or LoRA-on-MoE with care (router frozen) |
| Comparing models on a leaderboard | Always normalize by active params and price per 1M tokens |

## References

- [Mixtral of Experts](https://arxiv.org/abs/2401.04088) — verified 2026-10-20
- [DeepSeek-V3 Technical Report](https://github.com/deepseek-ai/DeepSeek-V3) — verified 2026-10-20
- [Outrageously Large Neural Networks (original MoE)](https://arxiv.org/abs/1701.06538) — verified 2026-10-20
- [gpt-oss model cards](https://github.com/openai/gpt-oss) — verified 2026-10-20
