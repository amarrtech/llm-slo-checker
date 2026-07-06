"""Click CLI for llm-slo-checker."""
import asyncio
import random
import sys
from pathlib import Path

import click

from . import __version__
from .config import load_config
from .evaluator import evaluate
from .metrics import compute_sli_report
from .prober import probe_anthropic
from .reporter import render_json, render_terminal


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """SLOs as code for LLM endpoints. Probe, measure, verdict."""


@cli.command()
@click.option("--config", "-c", "config_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="Path to SLO config YAML")
@click.option("--samples", "-n", type=int, default=None,
              help="How many probes to run (default: from config or 30)")
@click.option("--output", type=click.Choice(["terminal", "json"]), default="terminal")
@click.option("--no-color", is_flag=True, help="Disable ANSI color in terminal output")
def check(config_path: Path, samples: int | None, output: str, no_color: bool) -> None:
    """Probe the configured endpoint and evaluate SLOs. Exits 0 on PASS, 1 on FAIL, 2 on INCONCLUSIVE."""
    config = load_config(config_path)
    prompts = _load_prompts(config_path, config.sample_prompts.file)
    n = samples if samples is not None else max(config.probing.min_samples, 30)

    if len(prompts) < 30:
        click.echo(
            f"WARNING: only {len(prompts)} sample prompts; recommend 30+ to defeat "
            f"server-side prompt caching for realistic TTFT measurement.",
            err=True,
        )

    results = asyncio.run(_run_probes(config, prompts, n))
    report = compute_sli_report(results)
    verdict = evaluate(report, config.slos, min_samples=config.probing.min_samples)

    if output == "terminal":
        click.echo(render_terminal(verdict, use_color=not no_color))
    else:
        click.echo(render_json(verdict))

    if verdict.overall.value == "PASS":
        sys.exit(0)
    elif verdict.overall.value == "FAIL":
        sys.exit(1)
    else:
        sys.exit(2)


def _load_prompts(config_path: Path, prompts_file: str) -> list[str]:
    """Load prompts, resolving relative to the config file's directory."""
    p = Path(prompts_file)
    if not p.is_absolute():
        p = config_path.parent / p
    with open(p) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


async def _run_probes(config, prompts: list[str], n: int) -> list:
    semaphore = asyncio.Semaphore(config.probing.concurrent_probes)

    async def one(prompt: str):
        async with semaphore:
            return await probe_anthropic(config.target, config.probing, prompt=prompt)

    tasks = [one(random.choice(prompts)) for _ in range(n)]
    return await asyncio.gather(*tasks)
