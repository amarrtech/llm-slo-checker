from llm_slo_checker.metrics import SLIReport, compute_sli_report
from llm_slo_checker.prober import ProbeResult


def _mk(success, completed, status, ttft, total, tokens=1, error=None):
    return ProbeResult(
        success=success,
        completed=completed,
        status_code=status,
        ttft_ms=ttft,
        total_ms=total,
        tokens_received=tokens,
        error=error,
    )


def test_all_success_all_completed():
    results = [_mk(True, True, 200, 300 + i, 1000 + i * 10) for i in range(100)]
    report = compute_sli_report(results)
    assert isinstance(report, SLIReport)
    assert report.total_samples == 100
    assert report.success_rate == 1.0
    assert report.completion_rate == 1.0
    assert report.ttft_p50_ms is not None
    assert report.ttft_p95_ms is not None
    assert report.ttft_p95_ms > report.ttft_p50_ms


def test_partial_success_counted_separately_from_completion():
    """A stream that got tokens but did not cleanly complete: success=True, completed=False."""
    results = [_mk(True, True, 200, 300, 1000) for _ in range(9)]
    results.append(_mk(True, False, 200, 320, 800, error="stream disconnected"))
    report = compute_sli_report(results)
    assert report.success_rate == 1.0
    assert report.completion_rate == 0.9


def test_mixed_errors():
    """success_rate = 2/4 successful. completion_rate = 2/2 of successful streams completed cleanly.
    Note: completion_rate denominator is successful streams (per DESIGN.md), not total."""
    results = [
        _mk(True, True, 200, 300, 1000),
        _mk(True, True, 200, 400, 1200),
        _mk(False, False, 500, None, 100, tokens=0, error="HTTP 500"),
        _mk(False, False, 429, None, 50, tokens=0, error="HTTP 429"),
    ]
    report = compute_sli_report(results)
    assert report.success_rate == 0.5
    assert report.completion_rate == 1.0  # both successful streams completed
    assert report.ttft_p50_ms is not None


def test_empty_input_returns_zero_report():
    report = compute_sli_report([])
    assert report.total_samples == 0
    assert report.success_rate == 0.0
    assert report.ttft_p95_ms is None


def test_all_failures_no_ttft():
    results = [_mk(False, False, 500, None, 100, tokens=0, error="err") for _ in range(5)]
    report = compute_sli_report(results)
    assert report.success_rate == 0.0
    assert report.ttft_p95_ms is None
