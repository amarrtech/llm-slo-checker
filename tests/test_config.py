from pathlib import Path

from llm_slo_checker.config import SLOConfig, load_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_valid_config():
    config = load_config(FIXTURES / "example-config.yaml")
    assert isinstance(config, SLOConfig)
    assert config.target.base_url == "https://api.anthropic.com"
    assert config.target.model == "claude-sonnet-4-6"
    assert config.target.api_key_env == "ANTHROPIC_API_KEY"
    assert config.probing.interval_seconds == 900
    assert config.probing.window_hours == 24
    assert config.probing.budget_usd_per_month == 5.00
    assert config.slos.success_rate == 0.995
    assert config.slos.ttft_p95_ms == 1500


import pytest


def test_missing_target_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("probing:\n  interval_seconds: 60\n")
    with pytest.raises(ValueError, match="missing required key 'target'"):
        load_config(bad)


def test_non_mapping_top_level_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just a list\n")
    with pytest.raises(ValueError, match="top-level YAML must be a mapping"):
        load_config(bad)


def test_unknown_field_raises(tmp_path):
    """Frozen dataclasses reject unknown fields — belt-and-suspenders schema check."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "target:\n"
        "  base_url: https://x\n"
        "  model: y\n"
        "  api_key_env: Z\n"
        "  bogus_field: true\n"
        "probing:\n"
        "  interval_seconds: 60\n"
        "  window_hours: 1\n"
        "  min_samples: 10\n"
        "  concurrent_probes: 1\n"
        "  budget_usd_per_month: 1.0\n"
        "sample_prompts:\n"
        "  file: prompts.txt\n"
        "slos:\n"
        "  success_rate: 0.99\n"
        "  completion_rate: 0.98\n"
        "  ttft_p95_ms: 1000\n"
        "  ttft_p99_ms: 2000\n"
        "  total_p95_ms: 10000\n"
    )
    with pytest.raises(TypeError):
        load_config(bad)
