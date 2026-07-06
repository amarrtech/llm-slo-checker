"""SLI aggregation from probe results.

Percentile computation uses statistics.quantiles (stdlib) with n=100
to enable percentile lookups at 50/95/99. Uses inclusive method for
small-sample stability.
"""
import statistics
from dataclasses import dataclass
from typing import Optional

from .prober import ProbeResult


@dataclass(frozen=True)
class SLIReport:
    total_samples: int
    success_rate: float          # 200 responses with tokens / total
    completion_rate: float       # cleanly-terminated streams / successful streams
    ttft_p50_ms: Optional[float]
    ttft_p95_ms: Optional[float]
    ttft_p99_ms: Optional[float]
    total_p50_ms: Optional[float]
    total_p95_ms: Optional[float]
    total_p99_ms: Optional[float]
    error_counts: dict[str, int]  # error string prefix -> count


def _percentile(sorted_values: list[float], pct: float) -> Optional[float]:
    """Return the pct percentile (0-100) using linear interpolation.
    For a full statsy tool we'd use numpy; stdlib is fine for our purposes.
    """
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    # Uses statistics.quantiles at n=100
    quantiles = statistics.quantiles(sorted_values, n=100, method="inclusive")
    # quantiles[i] is the (i+1)th percentile; pct is 1..99
    idx = int(pct) - 1
    idx = max(0, min(idx, len(quantiles) - 1))
    return quantiles[idx]


def compute_sli_report(results: list[ProbeResult]) -> SLIReport:
    """Aggregate a list of probe results into an SLIReport."""
    n = len(results)
    if n == 0:
        return SLIReport(
            total_samples=0,
            success_rate=0.0,
            completion_rate=0.0,
            ttft_p50_ms=None,
            ttft_p95_ms=None,
            ttft_p99_ms=None,
            total_p50_ms=None,
            total_p95_ms=None,
            total_p99_ms=None,
            error_counts={},
        )

    successful = [r for r in results if r.success]
    completed = [r for r in successful if r.completed]
    success_rate = len(successful) / n
    completion_rate = (len(completed) / len(successful)) if successful else 0.0

    ttft_samples = sorted(r.ttft_ms for r in successful if r.ttft_ms is not None)
    total_samples = sorted(r.total_ms for r in results)

    error_counts: dict[str, int] = {}
    for r in results:
        if r.error:
            key = r.error.split(":")[0][:32]
            error_counts[key] = error_counts.get(key, 0) + 1

    return SLIReport(
        total_samples=n,
        success_rate=round(success_rate, 6),
        completion_rate=round(completion_rate, 6),
        ttft_p50_ms=_percentile(ttft_samples, 50),
        ttft_p95_ms=_percentile(ttft_samples, 95),
        ttft_p99_ms=_percentile(ttft_samples, 99),
        total_p50_ms=_percentile(total_samples, 50),
        total_p95_ms=_percentile(total_samples, 95),
        total_p99_ms=_percentile(total_samples, 99),
        error_counts=error_counts,
    )
