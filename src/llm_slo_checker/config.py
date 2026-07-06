"""Config schema and YAML loader for llm-slo-checker."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TargetConfig:
    base_url: str
    model: str
    api_key_env: str


@dataclass(frozen=True)
class ProbingConfig:
    interval_seconds: int
    window_hours: int
    min_samples: int
    concurrent_probes: int
    budget_usd_per_month: float
    request_max_tokens: int = 50
    timeout_seconds: int = 30


@dataclass(frozen=True)
class SamplePromptsConfig:
    file: str


@dataclass(frozen=True)
class SLOThresholds:
    success_rate: float
    completion_rate: float
    ttft_p95_ms: int
    ttft_p99_ms: int
    total_p95_ms: int


@dataclass(frozen=True)
class ReportingConfig:
    json_output: str | None = None
    history_dir: str | None = None
    github_summary: bool = False


@dataclass(frozen=True)
class SLOConfig:
    target: TargetConfig
    probing: ProbingConfig
    sample_prompts: SamplePromptsConfig
    slos: SLOThresholds
    reporting: ReportingConfig = field(default_factory=lambda: ReportingConfig())


def load_config(path: Path) -> SLOConfig:
    """Load and validate SLO config from YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")

    for required in ("target", "probing", "sample_prompts", "slos"):
        if required not in raw:
            raise ValueError(f"{path}: missing required key '{required}'")

    return SLOConfig(
        target=TargetConfig(**raw["target"]),
        probing=ProbingConfig(**raw["probing"]),
        sample_prompts=SamplePromptsConfig(**raw["sample_prompts"]),
        slos=SLOThresholds(**raw["slos"]),
        reporting=ReportingConfig(**raw.get("reporting", {})),
    )
