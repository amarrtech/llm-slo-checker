import json

from llm_slo_checker.evaluator import EvaluationResult, OverallVerdict, Verdict
from llm_slo_checker.reporter import render_terminal, render_json


_VERDICTS = [
    Verdict(sli="success_rate", expected=0.995, actual=0.997, passed=True,
            direction="gte", error_budget_remaining_pct=40.0),
    Verdict(sli="ttft_p95_ms", expected=1500, actual=1200.0, passed=True,
            direction="lte", error_budget_remaining_pct=None),
]


def test_terminal_render_pass_no_color():
    result = EvaluationResult(
        overall=OverallVerdict.PASS,
        verdicts=_VERDICTS,
        total_samples=100,
    )
    output = render_terminal(result, use_color=False)
    assert "PASS" in output
    assert "success_rate" in output
    assert "0.997" in output
    assert "40" in output  # error budget %


def test_terminal_render_fail():
    fail_verdict = Verdict(sli="ttft_p95_ms", expected=1000, actual=2500.0,
                           passed=False, direction="lte",
                           error_budget_remaining_pct=None)
    result = EvaluationResult(
        overall=OverallVerdict.FAIL,
        verdicts=[fail_verdict],
        total_samples=100,
    )
    output = render_terminal(result, use_color=False)
    assert "FAIL" in output
    assert "2500" in output


def test_terminal_render_inconclusive():
    result = EvaluationResult(
        overall=OverallVerdict.INCONCLUSIVE,
        verdicts=[],
        total_samples=5,
        reason="not enough samples",
    )
    output = render_terminal(result, use_color=False)
    assert "INCONCLUSIVE" in output
    assert "not enough samples" in output


def test_json_render_roundtrips():
    result = EvaluationResult(
        overall=OverallVerdict.PASS,
        verdicts=_VERDICTS,
        total_samples=100,
    )
    j = render_json(result)
    parsed = json.loads(j)
    assert parsed["overall"] == "PASS"
    assert parsed["total_samples"] == 100
    assert len(parsed["verdicts"]) == 2
    assert parsed["verdicts"][0]["sli"] == "success_rate"
