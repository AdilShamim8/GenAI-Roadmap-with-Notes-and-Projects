# Quantization

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [llama.cpp](https://github.com/ggml-org/llama.cpp), [vLLM quantization docs](https://docs.vllm.ai/)

## Why this matters

A 70B model in fp16 needs 140GB VRAM — out of reach for most GPUs. Quantized to 4-bit, the same model fits in 35GB — within reach of a single H100. Quantization is the lever that makes self-hosting economical. The expert framing: quantization trades *numerical precision* for *memory bandwidth* — and on inference, bandwidth is usually the bottleneck (`00-foundations/02-kv-cache-and-inference.md`: decode is memory-bound). That's why 4-bit models often run *faster*, not slower — you're spending precision on the resource that was constraining you.

## Core concepts

### The formats

| Format | Bits | Quality loss | Use |
|--------|------|--------------|-----|
| fp16 | 16 | None | Baseline |
| bf16 | 16 | None | Training; preferred over fp16 |
| fp8 | 8 | ~1% | Modern inference (H100/Blackwell) |
| MXFP4 / NVFP4 | 4 | ~1-2% | Blackwell-native 4-bit; gpt-oss ships MXFP4 |
| INT8 | 8 | ~1–2% | Older GPUs |
| GPTQ | 4 | ~2–3% | Inference |
| AWQ | 4 | ~1–2% | Inference; better than GPTQ |
| GGUF | 4–8 | varies | llama.cpp; CPU/Mac |
| bitsandbytes nf4 | 4 | ~2% | QLoRA training |

### Reading the table: three families with different jobs

- **Hardware-native formats (FP8, MXFP4/NVFP4):** quantization baked into the GPU's tensor cores (H100 does FP8 math natively; Blackwell adds 4-bit). These are the *default* on modern hardware — no calibration drama, near-lossless, and the ecosystem (vLLM/SGLang) supports them first. If your GPU is 2024+ and the model ships an official FP8/MXFP4 checkpoint, take it.
- **Post-training weight formats (GPTQ, AWQ):** algorithmic 4/8-bit encodings of weights, calibrated on sample data to decide which weight clusters matter. Needed on pre-native hardware or for models without official quantized releases. AWQ (activation-aware — protects weights that activations are sensitive to) generally edges GPTQ.
- **Ecosystem formats (GGUF):** llama.cpp's container for CPU/Mac/edge inference, with a quality ladder (Q4_K_M, Q5_K_M, Q6_K...) trading size vs fidelity. The only game in town for laptop/Mac serving; not the throughput play for datacenter GPUs.

The convergence trend worth knowing: the field is consolidating on *officially-shipped quantized checkpoints* from model orgs (Qwen, Meta, gpt-oss all ship them) — the era of community quantizers (TheBloke-style) as the primary source has passed, and with it much of the calibration guesswork.

### The tradeoff

Lower bits = less VRAM = more throughput = lower quality. The sweet spot for production inference in 2026 is **4-bit (AWQ, or MXFP4/NVFP4 on Blackwell) or FP8**.

But read the sweet spot as *model-size-conditioned*: quantization error is noise relative to the model's capacity, and small models have less capacity to absorb it. The practical ladder: 70B+ at 4-bit is nearly free (noise drowns in capability); 8-14B at 4-bit is usually fine (verify on your evals); under ~3B, 4-bit visibly degrades — you're quantizing away a meaningful fraction of what the model *is*. The counter-move for small models: FP8/INT8 instead of 4-bit, or a *bigger* model quantized to 4-bit (a 14B@4bit often beats an 8B@fp16 at the same VRAM — the "bigger-but-quantized" pattern that dominates edge serving).

### Calibration

Quantization isn't free: you need a small calibration dataset to choose quantization parameters. Most libraries ship with a default; bring your own for domain-specific models.

What calibration actually does: GPTQ/AWQ use sample forward passes to observe *activation distributions* — which weight columns the model actually leans on — and spend precision budget protecting those. Two consequences: (1) calibrating on domain-mismatched data (generic text for a code model) misallocates the protection; (2) calibration data can *leak behavior* — a model quantized on your proprietary corpus encodes traces of it (mild, but it's why some orgs treat calibrated checkpoints as sensitive artifacts).

## Code: serving a quantized model with vLLM

```bash
# AWQ quantized model from HuggingFace
vllm serve Qwen/Qwen3-8B-AWQ  # modern quantized checkpoints ship from the model org \
    --quantization awq \
    --dtype float16
```

## Code: quantize your own with AutoAWQ

```python
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model_path = "meta-llama/Llama-3.1-8B"  # or a current open-weight base
quant_path = "Llama-3.1-8B-awq"

model = AutoAWQForCausalLM.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Calibration data — use YOUR domain text, not generic samples
calib_data = ["sample text 1", "sample text 2", ...]  # 128–256 examples

model.quantize(tokenizer, quant_config={"w_bit": 4, "q_group_size": 128}, calib_data=calib_data)
model.save_quantized(quant_path)
```

## Production concerns

- **Latency:** Quantized models can be FASTER (less memory bandwidth) — the memory-bound-decode fact above; prefill is more compute-bound and gains less.
- **Cost:** 4× VRAM reduction = 4× throughput per GPU (more concurrent KV-caches fit; `03-vllm-sglang-tgi.md`).
- **Failure modes:** (1) quality drop on out-of-distribution inputs — quantization error is not uniform; eval on your *hard* tail, not the average; (2) format/runtime mismatch (a GPTQ checkpoint on a runtime expecting fp8) — pin checkpoint format to serving stack; (3) silent version drift in community quantizations — prefer official checkpoints, pin hashes.
- **Security:** No special concerns beyond the calibration-leak note above.
- **The eval rule:** never deploy a quantized model on published perplexity deltas alone — run *your* golden set (`07-evals/01-golden-datasets.md`) at full and quantized precision and compare. Perplexity differences of "1-2%" hide task-specific failures (usually in math, code, or long-tail entities — the low-frequency, high-precision capabilities that degrade first).

## Anti-patterns

- ❌ **INT4 on small models (<3B).** Quality drop too steep — use 8-bit or a bigger model at 4-bit.
- ❌ **Mixing quantization formats.** Pick one per deployment.
- ❌ **Not benchmarking quantized vs full.** Quality loss varies by model and by *task*.
- ❌ **Generic calibration data for domain models.** Calibration protects what it sees.
- ❌ **Trusting published perplexity over your evals.** Average loss hides tail failures.

## References

- [llm-compressor (vLLM ecosystem)](https://github.com/vllm-project/llm-compressor) — verified 2026-10-20 — the maintained quantization path; AutoGPTQ is archived and TheBloke checkpoints are frozen ~2024
- [AutoAWQ](https://github.com/casper-hansen/AutoAWQ) — verified 2026-10-20
- [llama.cpp GGUF](https://github.com/ggerganov/llama.cpp) — verified 2026-10-20
