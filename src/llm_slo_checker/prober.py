"""Prober module: issues probes against OpenAI-compatible LLM endpoints and
measures streaming-aware SLIs.

TTFT design decision: the clock stops at the first content_block_delta event
with a non-empty text_delta.text field. Earlier SSE frames (message_start,
content_block_start, empty deltas) are protocol overhead and are not what a
user experiences as "the first token." This is the honest TTFT.
"""
import json
import os
import time
from dataclasses import dataclass

import httpx

from .config import ProbingConfig, TargetConfig


class ProbeError(Exception):
    """Raised for internal probe errors (config, not network)."""


@dataclass(frozen=True)
class ProbeResult:
    """Single probe outcome.

    success: server returned 200 AND we got at least one token
    completed: stream terminated cleanly with message_stop
    ttft_ms: time to first non-empty text delta (None if no tokens received)
    total_ms: full request duration
    tokens_received: count of text delta tokens observed
    error: human-readable failure reason, if any
    """

    success: bool
    completed: bool
    status_code: int | None
    ttft_ms: float | None
    total_ms: float
    tokens_received: int
    error: str | None


async def probe_anthropic(
    target: TargetConfig,
    probing: ProbingConfig,
    prompt: str,
) -> ProbeResult:
    """Issue a single probe against an Anthropic Messages API endpoint.

    Compatible with OpenAI-style endpoints that use SSE `content_block_delta`
    events for streaming (Anthropic's format).
    """
    api_key = os.environ.get(target.api_key_env)
    if not api_key:
        raise ProbeError(
            f"API key env var {target.api_key_env!r} not set. "
            f"Export it before running probes."
        )

    url = f"{target.base_url.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "accept": "text/event-stream",
    }
    payload = {
        "model": target.model,
        "max_tokens": probing.request_max_tokens,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }

    start = time.perf_counter()
    ttft_ms: float | None = None
    tokens_received = 0
    completed = False
    status_code: int | None = None
    error: str | None = None

    try:
        async with httpx.AsyncClient(timeout=probing.timeout_seconds) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                status_code = response.status_code
                if response.status_code != 200:
                    body = await response.aread()
                    body_text = body[:200].decode("utf-8", errors="replace")
                    error = f"HTTP {response.status_code}: {body_text}"
                    total_ms = (time.perf_counter() - start) * 1000
                    return ProbeResult(
                        success=False,
                        completed=False,
                        status_code=status_code,
                        ttft_ms=None,
                        total_ms=total_ms,
                        tokens_received=0,
                        error=error,
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):].strip()
                    if not data_str:
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text and ttft_ms is None:
                                ttft_ms = (time.perf_counter() - start) * 1000
                            if text:
                                tokens_received += 1
                    elif event_type == "message_stop":
                        completed = True

    except httpx.TimeoutException:
        error = f"timeout after {probing.timeout_seconds}s"
    except httpx.HTTPError as e:
        error = f"network error: {e.__class__.__name__}: {e}"

    total_ms = (time.perf_counter() - start) * 1000

    success = tokens_received > 0 and status_code == 200
    if not success and error is None:
        error = f"no tokens received (status={status_code})"

    return ProbeResult(
        success=success,
        completed=completed,
        status_code=status_code,
        ttft_ms=ttft_ms,
        total_ms=total_ms,
        tokens_received=tokens_received,
        error=error,
    )
