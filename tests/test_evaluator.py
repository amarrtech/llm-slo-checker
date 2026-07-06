from llm_slo_checker.evaluator import evaluate, Verdict, OverallVerdict
from llm_slo_checker.metrics import SLIReport
from llm_slo_checker.config import SLOThresholds


THRESHOLDS = SLOThresholds(
    success_rate=0.995,
    completion_rate=0.99,
    ttft_p95_ms=1500,
    ttft_p99_ms=3000,
    total_p95_ms=15000,
)


def _mk_report(**overrides):
    defaults = dict(
        total_samples=100,
        success_rate=1.0,
        completion_rate=1.0,
        ttft_p50_ms=300.0,
        ttft_p95_ms=800.0,
        ttft_p99_ms=1500.0,
        total_p50_ms=1500.0,
        total_p95_ms=8000.0,
        total_p99_ms=12000.0,
        error_counts={},
    )
    defaults.update(overrides)
    return SLIReport(**defaults)


def test_all_slos_pass():
    result = evaluate(_mk_report(), THRESHOLDS, min_samples=30)
    assert result.overall == OverallVerdict.PASS
    for v in result.verdicts:
        assert v.passed


def test_ttft_p95_fails():
    report = _mk_report(ttft_p95_ms=2500.0)
    result = evaluate(report, THRESHOLDS, min_samples=30)
    assert result.overall == OverallVerdict.FAIL
    ttft_verdict = next(v for v in result.verdicts if v.sli == "ttft_p95_ms")
    assert not ttft_verdict.passed
    assert ttft_verdict.actual == 2500.0
    assert ttft_verdict.expected == 1500


def test_insufficient_samples_is_inconclusive():
    report = _mk_report(total_samples=5)
    result = evaluate(report, THRESHOLDS, min_samples=30)
    assert result.overall == OverallVerdict.INCONCLUSIVE


def test_error_budget_remaining_reported_for_success_rate():
    """If SLO is 99.5% and actual is 99.7%, error budget remaining is 40%
    (0.2% headroom out of 0.5% total budget)."""
    report = _mk_report(success_rate=0.997)
    result = evaluate(report, THRESHOLDS, min_samples=30)
    success_verdict = next(v for v in result.verdicts if v.sli == "success_rate")
    assert success_verdict.passed
    assert success_verdict.error_budget_remaining_pct is not None
    assert success_verdict.error_budget_remaining_pct > 30
    assert success_verdict.error_budget_remaining_pct < 50
