# Self-Host vs API Breakeven Math

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [vLLM](https://docs.vllm.ai/), [Lambda pricing](https://lambda.ai/pricing)

## Why this matters

"Should we self-host?" is one of the most common questions in 2026 GenAI engineering. The answer is almost always "not yet" — but only rigorous math tells you when "yet" arrives. The expert framing: this is a *capacity-planning* decision, not a cost decision. The real trade is fixed-cost-plus-ops (self-host) vs variable-cost-per-token (API) — a classic make-vs-buy whose answer flips with *volume and utilization*, and whose biggest term (ops) is the one spreadsheets forget.

## The formula

```text
monthly_self_host = gpu_hourly_cost × 730 × num_gpus + ops_overhead
monthly_api = monthly_tokens_input × input_price + monthly_tokens_output × output_price

self_host wins when: monthly_api > monthly_self_host
```

The formula hides three terms that decide real cases:

- **Utilization** — a GPU serving 15% of the time costs 6.7x more per served token than the same GPU at 90%. Bursty API-shaped traffic on dedicated GPUs is the #1 self-hosting money pit. The formula should really read `gpu_hourly × 730 / utilization` for per-token comparisons.
- **Ops is a step function, not a constant** — one cluster is ~0.25 FTE; two regions, multi-model, on-call, and upgrades push it to 1+ FTE. The breakeven that cleared at one cluster can invert when you scale to two.
- **Quality parity is a precondition, not a variable** — the math only compares *equivalent* serving. If your workload needs frontier reasoning quality and no open-weight model matches it, self-hosting isn't cheaper, it's non-functional; the comparison applies to the subset of traffic an open-weight model can carry.

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

### The middle option (where most teams should land)

The decision is a *ladder*, not a binary: API (frontier) → managed open-weight API (Together/Fireworks class — 50-90% savings, zero ops) → self-host (reserved capacity, max savings, full ops burden). Each rung trades ops for margin. The managed tier dominates the honest comparisons: at $7,190/month of self-host cost, the managed tier serving the same 13B tokens at a ~30-50% markup over raw GPU cost is still cheaper *and* you keep your on-call. Self-host from the managed tier only when your bill crosses the threshold where the markup exceeds ops cost — by then you have the traffic shape data to size clusters correctly.

### When API still wins

- Bursty traffic (can't utilize GPU).
- Multi-modal needs (vision, audio).
- Reasoning workloads where the frontier API model has no open-weight equal.
- Need to upgrade model monthly (frontier API > self-hosted open-weight).

## Code: a simple calculator

```python
def breakeven(monthly_tokens_in: int, monthly_tokens_out: int,
              api_input_per_m: float = 1.0, api_output_per_m: float = 2.0,   # open-weight baseline
              gpu_hourly: float = 3.0, num_gpus: int = 1, ops_monthly: float = 5000.0,
              utilization: float = 1.0):
    api_cost = (monthly_tokens_in / 1e6) * api_input_per_m + (monthly_tokens_out / 1e6) * api_output_per_m
    # effective per-token self-host cost scales inversely with utilization
    self_host_cost = gpu_hourly * 730 * num_gpus / utilization + ops_monthly
    return {
        "api_cost": api_cost,
        "self_host_cost": self_host_cost,
        "winner": "self_host" if self_host_cost < api_cost else "api",
        "savings": abs(api_cost - self_host_cost),
    }
```

## Production concerns

- **Latency:** Self-host can be faster (no network, no rate limits) — and its latency is *yours to tune* (batching aggressiveness, queue limits), vs the API's fixed behavior.
- **Cost:** Reserved capacity is 30–50% cheaper than on-demand — but it's a *commitment*: reserved GPUs you outgrow or underuse are the most expensive GPUs you'll ever own.
- **Failure modes:** (1) GPU failures — cluster ops is real work; (2) *scale-up surprise* — traffic grows 3x, the new cluster count changes the ops step function, the economics invert; re-run this math quarterly; (3) model-support lag — the hot new open-weight release needs days-weeks of engine support (vLLM/SGLang PRs) before you can serve it; API providers ship same-day.
- **Security:** Self-hosted = full data control. Big advantage for regulated industries — often *the* reason, independent of cost math (a compliance-driven self-host decision shouldn't be second-guessed by a spreadsheet that doesn't price the regulatory exposure).

## Anti-patterns

- ❌ **Self-hosting for a workload < $5K/month API spend.** Ops overhead dominates.
- ❌ **Ignoring ops cost.** GPUs need babysitting.
- ❌ **One model per GPU.** Multi-LoRA matters.
- ❌ **Utilization-blind breakevens.** Effective cost = cost ÷ utilization; bursty traffic multiplies everything.
- ❌ **Comparing against frontier-API prices.** You'd self-host open-weight models; compare against open-weight serving.
- ❌ **Skipping the managed middle tier.** Most of the savings, none of the on-call.

## References

- [vLLM](https://docs.vllm.ai/) — verified 2026-10-20
- [Lambda pricing](https://lambda.ai/pricing) — verified 2026-10-20
- [GPU pricing — AWS](https://aws.amazon.com/ec2/instance-types/p5/) — verified 2026-10-20
