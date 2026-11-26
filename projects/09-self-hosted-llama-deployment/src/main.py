"""Self-hosted Llama deployment — config generator + readiness healthcheck.

Encodes 09-fine-tuning/03+05: vllm serve flags chosen by real traffic math
(max-model-len from p99 context, NOT model max — KV reservation trap);
healthcheck verifies a real completion, not just /health."""
from __future__ import annotations

import json


def generate_vllm_config(model: str, gpu_mem_gb: int, p99_context_tokens: int,
                         max_batch: int = 64, quantization: str | None = None) -> dict:
    """max-model-len follows YOUR traffic (p99 + headroom), never the model's
    advertised max — reserving KV for 200K-token requests nobody sends is the
    #1 silent utilization killer."""
    max_model_len = min(int(p99_context_tokens * 1.25), 131072)
    cfg = {
        "model": model,
        "max-model-len": max_model_len,
        "max-num-seqs": max_batch,
        "tensor-parallel-size": 1,
        "port": 8000,
        # prefix caching is ON by default in the V1 engine; stated explicitly
        "enable-prefix-caching": True,
    }
    if quantization:
        cfg["quantization"] = quantization
    return cfg


def cli(cfg: dict) -> str:
    flags = " ".join(f"--{k} {v}" for k, v in cfg.items())
    return f"vllm serve {cfg['model']} \\\n    {flags.replace('--model ' + cfg['model'] + ' ', '')}"


def healthcheck(base_url: str = "http://localhost:8000/v1", timeout_s: float = 5.0) -> dict:
    """Real-completion healthcheck: /health can lie (engine up, model broken)."""
    import urllib.request

    req = urllib.request.Request(
        base_url.replace("/v1", "") + "/v1/chat/completions",
        data=json.dumps({
            "model": "any", "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            ok = r.status == 200
            return {"healthy": ok, "detail": "completion ok" if ok else f"status {r.status}"}
    except Exception as e:  # noqa: BLE001
        return {"healthy": False, "detail": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    print(json.dumps(generate_vllm_config("meta-llama/Llama-3.1-8B-Instruct", 80, 8192), indent=2))
