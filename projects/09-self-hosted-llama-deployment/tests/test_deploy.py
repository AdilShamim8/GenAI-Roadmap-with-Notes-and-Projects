import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import cli, generate_vllm_config


def test_max_model_len_follows_traffic_not_model_max():
    cfg = generate_vllm_config("m", 80, p99_context_tokens=8192)
    assert cfg["max-model-len"] == 10240  # 8192 * 1.25 headroom, not 131072


def test_capped_at_model_window():
    cfg = generate_vllm_config("m", 80, p99_context_tokens=200000)
    assert cfg["max-model-len"] == 131072


def test_prefix_caching_explicit():
    assert generate_vllm_config("m", 80, 4096)["enable-prefix-caching"] is True


def test_cli_render_contains_core_flags():
    cfg = generate_vllm_config("meta-llama/Llama-3.1-8B-Instruct", 80, 4096)
    out = cli(cfg)
    assert "vllm serve" in out and "--max-model-len" in out
