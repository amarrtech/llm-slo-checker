"""Terminal + JSON reporting for evaluation results."""
import json
from dataclasses import asdict

from .evaluator import EvaluationResult, OverallVerdict


ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"


def render_terminal(result: EvaluationResult, use_color: bool = True) -> str:
    """Render an EvaluationResult as a terminal-friendly report."""
    def color(text: str, code: str) -> str:
        return f"{code}{text}{ANSI_RESET}" if use_color else text

    lines: list[str] = []
    lines.append("")
    banner = f"SLO CHECK: {result.overall.value}"
    if result.overall == OverallVerdict.PASS:
        lines.append(color(f"[ {banner} ]", ANSI_GREEN + ANSI_BOLD))
    elif result.overall == OverallVerdict.FAIL:
        lines.append(color(f"[ {banner} ]", ANSI_RED + ANSI_BOLD))
    else:
        lines.append(color(f"[ {banner} ]", ANSI_YELLOW + ANSI_BOLD))
    lines.append(f"Samples in window: {result.total_samples}")
    if result.reason:
        lines.append(f"Reason: {result.reason}")
    lines.append("")

    if result.verdicts:
        lines.append(f"{'SLI':<25} {'Expected':<12} {'Actual':<15} {'Verdict':<8} {'Budget':<12}")
        lines.append("-" * 78)
        for v in result.verdicts:
            actual = f"{v.actual:.3f}" if v.actual is not None else "n/a"
            verdict = "PASS" if v.passed else "FAIL"
            verdict_colored = color(verdict, ANSI_GREEN if v.passed else ANSI_RED)
            if v.error_budget_remaining_pct is not None:
                budget = f"{v.error_budget_remaining_pct:.1f}% left"
            else:
                budget = "-"
            expected = f"{v.expected}"
            lines.append(
                f"{v.sli:<25} {expected:<12} {actual:<15} {verdict_colored:<20} {budget}"
            )
    lines.append("")
    return "\n".join(lines)


def render_json(result: EvaluationResult) -> str:
    """Render evaluation as a JSON string."""
    return json.dumps(_result_to_dict(result), indent=2, sort_keys=True)


def _result_to_dict(result: EvaluationResult) -> dict:
    return {
        "overall": result.overall.value,
        "total_samples": result.total_samples,
        "reason": result.reason,
        "verdicts": [
            {
                "sli": v.sli,
                "expected": v.expected,
                "actual": v.actual,
                "passed": v.passed,
                "direction": v.direction,
                "error_budget_remaining_pct": v.error_budget_remaining_pct,
            }
            for v in result.verdicts
        ],
    }
