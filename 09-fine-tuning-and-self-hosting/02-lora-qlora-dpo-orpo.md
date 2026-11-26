# LoRA, QLoRA, DPO, ORPO

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [LoRA](https://arxiv.org/abs/2106.09685), [QLoRA](https://arxiv.org/abs/2305.14314), [TRL](https://github.com/huggingface/trl)

## Why this matters

When you do fine-tune, these four techniques cover ~95% of use cases. They're the standard toolkit of 2026 — full fine-tuning is reserved for frontier labs and rare cases. The expert framing: all four are answers to the same constraint — *parameter-efficient change of behavior* — along two axes: what you change (task capability via SFT vs preference via alignment) and how cheaply you change it (LoRA's low-rank trick vs QLoRA's quantized-base trick). Understanding *why* each trick works tells you when its savings stop applying.

## Core concepts

### The four techniques

| Technique | What | Compute | Quality |
|-----------|------|---------|---------|
| **LoRA** | Low-rank adapters on attention weights | 1 GPU, hours | Near-full-FT quality |
| **QLoRA** | LoRA on a quantized base (4-bit) | 1 consumer GPU | Slight quality loss |
| **DPO** | Direct Preference Optimization (no reward model) | 2× LoRA | Better for alignment |
| **ORPO** | DPO without reference model | 1.5× LoRA | Better than DPO, simpler |

### LoRA in one paragraph — and the intuition

Instead of updating all weights of the base model, LoRA adds small "adapter" matrices (rank 8–64) to attention layers. Train only the adapters (~1% of parameters). At inference, merge adapters into the base or serve them separately.

Why low-rank works: the *change* in weights needed for a fine-tune (ΔW) empirically has low intrinsic rank — adaptation is a low-dimensional adjustment of an already-competent model, not new knowledge. That's also the precise limit: if your fine-tune genuinely needs to add *high-rank* information (a new language, a new modality), LoRA's rank becomes the binding constraint — the fix is higher rank (64-256) and expanding target modules beyond attention to the MLP layers, at which point parameter savings shrink and you approach full-FT compute anyway. LoRA is for *behavior adjustment of existing capabilities*; that's the deal.

Rank/alpha heuristics that matter in practice: r=8-16 suits narrow style/format tasks; r=32-64 for domain adaptation; `lora_alpha ≈ 2r` is the common convention (α scales the adapter's contribution); targeting only q_proj/v_proj is the *cheap* original paper setup — adding k_proj/o_proj and the MLP projections costs more but is usually where domain-adaptation gains live.

### QLoRA

LoRA on a 4-bit quantized base. Lets you fine-tune a 7-14B model comfortably on a single 24GB GPU (70B needs ~48GB in practice). The catch: slight quality loss vs full-precision LoRA.

The mechanism worth knowing: NF4 (4-bit NormalFloat) quantizes *storage* while gradients and adapter math run in bf16 — the frozen base is compressed, but the trainable part never sees 4-bit precision. That's why quality loss is small: the numbers that *change* stay precise. The other trick — paged optimizers — spills optimizer state to CPU RAM on memory spikes, which is what makes long-sequence training feasible on consumer cards.

### DPO / ORPO — what "preference optimization" actually does

For alignment ("prefer this output over that one"). DPO needs a reference model; ORPO doesn't. Both beat RLHF for small teams.

The conceptual jump DPO made: RLHF is reward-model-then-RL (train a critic, then optimize against it — two stages, both unstable). DPO's insight is that the reward function has a *closed-form expression in the policy itself*, so you can optimize preference directly from (chosen, rejected) pairs with a classification-style loss — no reward model, no RL instability. ORPO goes further: it folds the reference model (DPO's way of saying "don't drift from the base") into the training loss as an odds-ratio penalty — one model in memory, one training loop.

What this means for your data budget: these methods are *hungry for pairs, not gold answers*. 5K excellent (prompt, chosen, rejected) triples beat 50K mediocre ones — and the common failure is generating pairs synthetically with one model and preference-labeling with the same model family, which teaches the model "what my family already prefers" (self-preference, `07-evals/02-llm-as-judge.md`) rather than your users' preference. Diverse preference sources (real user feedback, different-family judges) are the quality lever.

## Code: QLoRA fine-tune with TRL

```python
# pip install trl transformers peft bitsandbytes datasets
from trl import SFTTrainer, SFTConfig
from peft import LoraConfig
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)
model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B", quantization_config=bnb_config)
tok = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B")

peft_config = LoraConfig(r=16, lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],  # + MLP modules for quality
    task_type="CAUSAL_LM")

dataset = load_dataset("your/dataset", split="train")

trainer = SFTTrainer(
    model=model,
    tokenizer=tok,
    train_dataset=dataset,
    peft_config=peft_config,
    args=SFTConfig(output_dir="./out", per_device_train_batch_size=4, num_train_epochs=3, learning_rate=2e-4),
)
trainer.train()
trainer.save_model("./out")
```

## Code: DPO alignment

```python
from trl import DPOTrainer, DPOConfig

# dataset: {"prompt": ..., "chosen": ..., "rejected": ...}
trainer = DPOTrainer(
    model=model,
    args=DPOConfig(output_dir="./dpo-out", beta=0.1, num_train_epochs=1),
    train_dataset=dpo_dataset,
    tokenizer=tok,
)
trainer.train()
```

`beta` intuition: it controls how hard the model is pulled toward preferences vs anchored to the reference — low β (0.05) = aggressive shift (more drift risk), high β (0.3) = conservative. Start at 0.1; if the model barely moves on your preference evals, lower it.

### TRL API note

TRL's trainer signatures move (e.g. `tokenizer=` → `processing_class=`, argument relocations across 2025 releases). Treat the snippet above as the shape, pin your `trl`/`peft`/`transformers` versions, and copy from the TRL examples directory for your pinned release. For reasoning-style post-training, look at TRL's GRPO trainer rather than DPO.

## Production concerns

- **Latency:** LoRA adapters add <5% inference overhead — and *multi-LoRA serving* (many adapters on one base, `03-vllm-sglang-tgi.md`) is where LoRA's economics shine: N customer-specific adapters on one GPU instead of N models.
- **Cost:** QLoRA on 8B = ~$5 in compute. On 70B = ~$50. The training run is the cheap part; the expensive parts are dataset curation and the eval loop around it.
- **Failure modes:** (1) catastrophic forgetting — always eval base vs fine-tuned on a *broad* suite, not just your target task; (2) rank ceiling — see above; (3) preference-data self-preference — diverse sources; (4) the merged-adapter trap: merging LoRA into the base makes your artifact a full model (storage, license terms of the base apply to your merged weights); keep adapters separate when you need the swap flexibility.
- **Security:** Training data lives in adapters; treat as sensitive — adapters trained on user data are subject to the same retention/deletion policies as that data.

## Anti-patterns

- ❌ **Full fine-tuning when LoRA suffices.** Wastes compute.
- ❌ **No eval set.** Can't measure improvement — or degradation elsewhere.
- ❌ **High learning rate.** Destroys the base model's knowledge.
- ❌ **Minimum rank everywhere.** Domain adaptation needs the MLP modules and higher rank.
- ❌ **Same-family synthetic preference pairs.** You'll train self-preference, not user preference.
- ❌ **Narrow evals.** Forgetting strikes outside your target task; measure breadth.

## References

- [LoRA](https://arxiv.org/abs/2106.09685) — verified 2026-10-20
- [QLoRA](https://arxiv.org/abs/2305.14314) — verified 2026-10-20
- [DPO](https://arxiv.org/abs/2305.18290) — verified 2026-10-20
- [TRL library](https://github.com/huggingface/trl) — verified 2026-10-20
