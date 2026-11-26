# Fine-Tuning & Self-Hosting — Interview Questions

> **Rung:** [09-fine-tuning-and-self-hosting](../../09-fine-tuning-and-self-hosting/01-when-not-to-finetune.md) · **Last verified:** 2026-10-20

## Q1 — "We should fine-tune so the model knows our product." Respond

**Model answer:** That's the canonical wrong reason. Knowledge belongs in *retrieval* — knowledge in weights is expensive to update (re-train per product change), impossible to cite (RAG gives provenance natively), and doesn't reliably stick (fine-tuning is for behavior, not memorization; the model will still confabulate where retrieval would have shown the doc). The decision matrix: "doesn't know X" → RAG; "wrong format" → structured outputs; "style off" → few-shot; "can't use our API" → tools/MCP; "too slow/expensive" → routing/caching.

Fine-tune only when the fix genuinely lives in weights — three conditions, and I should be able to name which one I'm in: (1) *tacit knowledge* (style/judgment not expressible as documents), (2) *context overflow* (an 8K-token few-shot block on every call — distill it), (3) *latency/cost envelope* (a small model must match a big model on a narrow task). Plus the 2026 nuance: improving *reasoning* on a small model is an RL post-training problem (GRPO-style RLVR), not DPO.

**Senior note:** the hidden costs that make "rarely" the right default — every base-model release re-opens the re-train question (a fine-tune is a fork of model evolution); iteration speed collapses (hours-days per run vs minutes for prompts); and eval burden *before* training, including breadth (catastrophic forgetting degrades capabilities your target-task evals don't cover). And distillation depreciation: fine-tuning toward a moving capability chases yesterday's frontier; narrow-and-stable tasks only.

## Q2 — Explain LoRA to an engineer, including when it stops working

**Model answer:** LoRA trains low-rank adapter matrices (ΔW = BA, rank 8-64) on attention/MLP projections instead of all weights — ~1% of parameters, near-full-FT quality, because the *change* a fine-tune needs is empirically low-rank: adaptation is a low-dimensional adjustment of an already-competent model.

When it stops working: when the change isn't low-rank — genuinely new knowledge (a new language, new modality) hits the rank ceiling. The ladder: bump rank (8-16 for style/format, 32-64 for domain adaptation), expand target modules beyond q/v to k/o and MLP (where domain gains live — at which point savings shrink toward full-FT), and accept that LoRA is for *behavior adjustment of existing capabilities*. Practical knobs: `lora_alpha ≈ 2r` convention; QLoRA (4-bit NF4 frozen base, bf16 adapter math — that's why quality loss is small: the trainable part never sees 4 bits) plus paged optimizers for consumer-GPU training.

**Senior note:** DPO/ORPO literacy — DPO's insight is the reward function has a closed form in the policy, so preference optimization is a classification-style loss on (chosen, rejected) pairs without reward-model-then-RL; ORPO folds the reference anchor into an odds-ratio penalty (one model, one loop). Data quality: diverse preference sources — same-family synthetic pairs train *self-preference*, not your users' preference. And multi-LoRA serving is LoRA's economic payoff: N adapters on one base instead of N models.

## Q3 — "Self-hosting will cut our costs." When is that true?

**Model answer:** Only with volume, utilization, and quality parity. The formula: `gpu_hourly × 730 / utilization + ops` vs `tokens × blended_price` — and three hidden terms decide real cases. **Utilization**: bursty API-shaped traffic on dedicated GPUs is the #1 money pit (15% utilization = 6.7x per-token cost); **ops is a step function** (~0.25 FTE for one cluster; multi-region/on-call pushes 1+ FTE — the breakeven that cleared at one cluster inverts at two); **parity is a precondition** — if the workload needs frontier reasoning and no open-weight model matches, self-hosting isn't cheaper, it's non-functional.

Compare against the right baseline: self-hosting serves *open-weight* models, so the honest comparator is open-weight API pricing (often 10-30x below frontier), not GPT-6 rates. And check the middle rung first: managed open-weight inference (Together/Fireworks class) captures most savings with zero ops — self-host from there only when the managed markup exceeds your ops cost.

**Senior note:** worked example ready — blended $1.20/1M (4:1 in:out) vs $7,190/month self-host (1 H100 on-demand + ops) breaks even at ~6B tokens/month; an H100 serving a 70B-class model at ~5,000 tok/s aggregate has ~13B/month headroom, so savings only materialize near full utilization. Re-run the math quarterly — scale-up changes the ops step function. And compliance as the exception: a regulatory-driven self-host decision isn't second-guessed by a spreadsheet that doesn't price the exposure.

## Q4 — What do you actually measure when picking a quantization format?

**Model answer:** Three families with different jobs: **hardware-native** (FP8 on Hopper, MXFP4/NVFP4 on Blackwell — no calibration drama, near-lossless, the default when the GPU supports it), **post-training weight formats** (AWQ/GPTQ — activation-aware calibration protects the weights the model leans on; AWQ generally edges GPTQ; needed on older hardware or without official quantized releases), **ecosystem** (GGUF — CPU/Mac/edge, the only game there). The era of community quantizers as primary source has passed — official quantized checkpoints from model orgs are the norm.

The measurement everyone skips: your *own* evals, on the *hard tail*, not published perplexity — average deltas of 1-2% hide task-specific failures in math, code, and long-tail entities (the low-frequency, high-precision capabilities that degrade first). And quantization error is noise relative to capacity: 70B@4-bit is nearly free; 8-14B@4-bit usually fine (verify); under 3B, 4-bit visibly degrades — the counter-move is the bigger-model-at-4-bit pattern (14B@4bit beats 8B@fp16 at the same VRAM).

**Senior note:** the speed surprise — 4-bit models often run *faster* because decode is memory-bandwidth-bound and smaller weights move less memory; prefill is compute-bound and gains less. Calibration data matters for domain models (generic text for a code model misallocates protection), and calibrated checkpoints encode traces of the corpus — some orgs treat them as sensitive artifacts.
