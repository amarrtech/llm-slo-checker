# Design Decisions

This document explains the non-obvious choices in llm-slo-checker. Each choice trades off between competing goals — the goal here is to make the tradeoff explicit so operators can decide whether their situation warrants a different call.

## TTFT stopwatch stops at first non-empty text_delta

Streaming responses emit multiple event types before user-visible content:
1. `message_start` — protocol metadata
2. `content_block_start` — still no content
3. `content_block_delta` with `text_delta.text == ""` — empty text delta
4. `content_block_delta` with actual text — **this is what a user sees as "the first token"**

The clock stops at (4). Stopping earlier flatters your TTFT number by 5-50ms but doesn't match customer experience. Honest measurement over favorable measurement.

## Partial success and completion are separate SLIs

A stream that got 47 tokens then disconnected is not the same as a failed 500. It succeeded from the customer's point of view (they got usable content) but did not complete cleanly (they may have received a truncated response). We track:

- `success_rate` — server returned 200 and we got at least one token
- `completion_rate` — successful streams that terminated with `message_stop`

A production incident could show `success_rate` at 99.9% while `completion_rate` drops to 60%, revealing a mid-stream disconnect issue that a single success/failure SLI would hide.

## Statistical significance floor: inconclusive below `min_samples`

Small windows produce percentiles that swing wildly on outliers. When sample count falls below `min_samples`, the tool returns `INCONCLUSIVE` rather than `PASS` or `FAIL`. This is a policy choice that avoids two failure modes:

- False alarms from a single slow probe pulling p95 above threshold
- False confidence from a lucky streak of fast probes

Default `min_samples: 30`. Users can lower for demo purposes but should understand the risk.

## Prompt rotation to defeat server-side prompt caching

Anthropic caches prompt prefixes server-side. Probing with the same 3 prompts hourly would give artificially low TTFT after the first probe. The tool loads a pool of prompts and rotates them per probe. The tool warns if fewer than 30 prompts are supplied — that's the minimum reasonable pool size to avoid cache bias with hourly probing over a 24-hour window.

The alternative — explicitly disabling prompt caching via API — costs more per probe and doesn't reflect real production traffic patterns. Rotation is closer to reality.

## Error budget percentages computed only for rate SLOs

For rate SLIs (success_rate, completion_rate) we report `error_budget_remaining_pct` — the fraction of the allowed error budget still unused. For latency SLIs, headroom is a conceptually different measurement (how much slack before p95 crosses the threshold, in ms), and mixing them under one term would be misleading. So we report None for latency SLIs and leave that as a v0.2 addition.

## Concurrency semaphore for probes

Async probes could run all-at-once, but that would look like a small burst to the server and could hit rate limits. A semaphore caps concurrency at `concurrent_probes` (default 3). This roughly matches customer traffic patterns and stays polite to the probed endpoint.

## Non-goals for v0.1 (see README)

Documented explicitly to prevent scope creep. If you're a contributor: PRs adding these features will be considered for v0.2+ but not v0.1. The point of v0.1 is a small, working, opinionated tool — not comprehensive coverage.
