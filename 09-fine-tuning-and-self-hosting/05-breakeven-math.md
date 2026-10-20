# Self-Host vs API Breakeven Math

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [vLLM](https://docs.vllm.ai/), [Lambda pricing](https://lambda.ai/pricing)

## Why this matters

"Should we self-host?" is one of the most common questions in 2026 GenAI engineering. The answer is almost always "not yet" — but only rigorous math tells you when "yet" arrives.

## The formula

```text
monthly_self_host = gpu_hourly_cost × 730 × num_gpus + ops_overhead
monthly_api = monthly_tokens_input × input_price + monthly_tokens_output × output_price

self_host wins when: monthly_api > monthly_self_host
```

### The numbers (2026, illustrative)

- 1× H100 on-demand (Lambda/RunPod-class): ~$3/hr → ~$2,190/month
- 1× H100 reserved (1yr): ~$1.50/hr → ~$1,095/month
- Ops overhead for a single cluster: ~0.25 FTE ≈ $5,000/month
- **Compare against the right baseline**: self-hosting serves *open-weight* models, so the honest comparison is open-weight API pricing (DeepSeek/Qwen/GLM via Together/Nebius — often 10–30x cheaper than frontier APIs), not GPT-6 pricing. Use frontier-API pricing only if you truly need frontier quality.

### Breakeven worked example (4:1 input:output mix)

At $1/1M input and $2/1M output blended open-weight API pricing, 4 input tokens per output token gives a blended cost of `(4×1 + 1×2)/5 = $1.20/1M` tokens. Self-host cost of $7,190/month therefore breaks even at:

```text
$7,190 / $1.20 per 1M blended tokens ≈ 6.0B tokens/month (4.8B in / 1.2B out)
```

**Do not** add input and output per-1M prices together as if they were one number — that dimensional error understates breakeven volume several-fold.

### Reality check

- Self-hosting a 70B-class model on 1× H100: ~100–200 tokens/sec/req, batched to ~5,000 tokens/sec total → ~13B tokens/month max throughput (throughput headroom is real).
- At the open-weight API baseline above, 13B blended tokens ≈ $15,600/month — self-hosting saves ~$8,400/month only at full utilization, *before* ops growth.
- Also check the middle option first: managed open-weight inference (Together/Fireworks/Bedrock custom) gets you most savings with zero ops.

### When API still wins

- Bursty traffic (can't utilize GPU).
- Multi-modal needs (vision, audio).
- Reasoning workloads where the frontier API model has no open-weight equal.
- Need to upgrade model monthly (frontier API > self-hosted open-weight).

## Code: a simple calculator

```python
def breakeven(monthly_tokens_in: int, monthly_tokens_out: int,
              api_input_per_m: float = 1.0, api_output_per_m: float = 2.0,   # open-weight baseline
              gpu_hourly: float = 3.0, num_gpus: int = 1, ops_monthly: float = 5000.0):
    api_cost = (monthly_tokens_in / 1e6) * api_input_per_m + (monthly_tokens_out / 1e6) * api_output_per_m
    self_host_cost = gpu_hourly * 730 * num_gpus + ops_monthly
    return {
        "api_cost": api_cost,
        "self_host_cost": self_host_cost,
        "winner": "self_host" if self_host_cost < api_cost else "api",
        "savings": abs(api_cost - self_host_cost),
    }
```

## Production concerns

- **Latency:** Self-host can be faster (no network, no rate limits).
- **Cost:** Reserved capacity is 30–50% cheaper than on-demand.
- **Failure modes:** GPU failures; cluster ops is real work.
- **Security:** Self-hosted = full data control. Big advantage for regulated industries.

## Anti-patterns

- ❌ **Self-hosting for a workload < $5K/month API spend.** Ops overhead dominates.
- ❌ **Ignoring ops cost.** GPUs need babysitting.
- ❌ **One model per GPU.** Multi-LoRA matters.

## References

- [vLLM](https://docs.vllm.ai/) — verified 2026-10-20
- [GPU pricing — AWS](https://aws.amazon.com/ec2/instance-types/p5/) — verified 2026-10-20
