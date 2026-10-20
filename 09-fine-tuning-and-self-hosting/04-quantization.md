# Quantization

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [llama.cpp](https://github.com/ggml-org/llama.cpp), [vLLM quantization docs](https://docs.vllm.ai/)

## Why this matters

A 70B model in fp16 needs 140GB VRAM — out of reach for most GPUs. Quantized to 4-bit, the same model fits in 35GB — within reach of a single H100. Quantization is the lever that makes self-hosting economical.

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

### The tradeoff

Lower bits = less VRAM = more throughput = lower quality. The sweet spot for production inference in 2026 is **4-bit (AWQ, or MXFP4/NVFP4 on Blackwell) or FP8**.

### Calibration

Quantization isn't free: you need a small calibration dataset to choose quantization parameters. Most libraries ship with a default; bring your own for domain-specific models.

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

# Calibration data
calib_data = ["sample text 1", "sample text 2", ...]  # 128–256 examples

model.quantize(tokenizer, quant_config={"w_bit": 4, "q_group_size": 128}, calib_data=calib_data)
model.save_quantized(quant_path)
```

## Production concerns

- **Latency:** Quantized models can be FASTER (less memory bandwidth).
- **Cost:** 4× VRAM reduction = 4× throughput per GPU.
- **Failure modes:** Quality drop on out-of-distribution inputs.
- **Security:** No special concerns.

## Anti-patterns

- ❌ **INT4 on small models (<3B).** Quality drop too steep.
- ❌ **Mixing quantization formats.** Pick one per deployment.
- ❌ **Not benchmarking quantized vs full.** Quality loss varies by model.

## References

- [AutoAWQ](https://github.com/casper-hansen/AutoAWQ) — verified 2026-10-20
- [AutoAWQ](https://github.com/casper-hansen/AutoAWQ) — verified 2026-10-20
- [llm-compressor (vLLM ecosystem)](https://github.com/vllm-project/llm-compressor) — verified 2026-10-20 — the maintained quantization path; AutoGPTQ is archived and TheBloke checkpoints are frozen ~2024
- [llama.cpp GGUF](https://github.com/ggerganov/llama.cpp) — verified 2026-10-20
