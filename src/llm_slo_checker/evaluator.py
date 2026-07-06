"""Evaluate an SLIReport against SLO thresholds and produce verdicts."""
from dataclasses import dataclass
from enum import StrEnum

from .config import SLOThresholds
from .metrics import SLIReport


class OverallVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Verdict:
    sli: str
    expected: float
    actual: float | None
    passed: bool
    direction: str  # "gte" or "lte"
    error_budget_remaining_pct: float | None


@dataclass(frozen=True)
class EvaluationResult:
    overall: OverallVerdict
    verdicts: list[Verdict]
    total_samples: int
    reason: str | None = None


def _error_budget_remaining(sli_name: str, expected: float, actual: float) -> float | None:
    """Fraction of error budget still available, as a percentage.

    For rate SLOs (expected > 0.5), budget = 1 - expected, actual excess = actual - expected.
    Remaining pct = (excess / budget) * 100, clamped to [0, 100].
    Returns None for latency SLOs (headroom concept differs).
    """
    if expected >= 0.5:  # a rate SLO
        budget = 1.0 - expected
        if budget <= 0:
            return None
        excess = actual - expected
        remaining_pct = (excess / budget) * 100
        return max(0.0, min(100.0, remaining_pct))
    return None


def evaluate(report: SLIReport, slos: SLOThresholds, min_samples: int) -> EvaluationResult:
    """Evaluate an SLI report against SLO thresholds."""
    if report.total_samples < min_samples:
        return EvaluationResult(
            overall=OverallVerdict.INCONCLUSIVE,
            verdicts=[],
            total_samples=report.total_samples,
            reason=(
                f"insufficient samples ({report.total_samples} < {min_samples}); "
                f"probe longer before evaluating"
            ),
        )

    verdicts = [
        _check_gte("success_rate", slos.success_rate, report.success_rate),
        _check_gte("completion_rate", slos.completion_rate, report.completion_rate),
        _check_lte("ttft_p95_ms", slos.ttft_p95_ms, report.ttft_p95_ms),
        _check_lte("ttft_p99_ms", slos.ttft_p99_ms, report.ttft_p99_ms),
        _check_lte("total_p95_ms", slos.total_p95_ms, report.total_p95_ms),
    ]

    overall = OverallVerdict.PASS if all(v.passed for v in verdicts) else OverallVerdict.FAIL
    return EvaluationResult(
        overall=overall,
        verdicts=verdicts,
        total_samples=report.total_samples,
    )


def _check_gte(name: str, expected: float, actual: float | None) -> Verdict:
    passed = actual is not None and actual >= expected
    budget = _error_budget_remaining(name, expected, actual) if actual is not None else None
    return Verdict(
        sli=name,
        expected=expected,
        actual=actual,
        passed=passed,
        direction="gte",
        error_budget_remaining_pct=budget,
    )


def _check_lte(name: str, expected: float, actual: float | None) -> Verdict:
    passed = actual is not None and actual <= expected
    return Verdict(
        sli=name,
        expected=expected,
        actual=actual,
        passed=passed,
        direction="lte",
        error_budget_remaining_pct=None,
    )
