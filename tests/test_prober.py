import pytest

from llm_slo_checker.prober import ProbeError, ProbeResult


def test_probe_result_success_case():
    result = ProbeResult(
        success=True,
        completed=True,
        status_code=200,
        ttft_ms=340.5,
        total_ms=1420.0,
        tokens_received=47,
        error=None,
    )
    assert result.success
    assert result.completed
    assert result.ttft_ms == 340.5


def test_probe_result_partial_success():
    """Server returned 200 and started streaming but the stream cut off midway.
    This is the partial-success case. success=True, completed=False."""
    result = ProbeResult(
        success=True,
        completed=False,
        status_code=200,
        ttft_ms=320.0,
        total_ms=800.0,
        tokens_received=47,
        error="stream disconnected",
    )
    assert result.success  # server accepted, we got tokens
    assert not result.completed  # but stream didn't complete cleanly


def test_probe_result_error_case():
    result = ProbeResult(
        success=False,
        completed=False,
        status_code=500,
        ttft_ms=None,
        total_ms=125.0,
        tokens_received=0,
        error="HTTP 500",
    )
    assert not result.success
    assert result.ttft_ms is None


import httpx
import respx

from llm_slo_checker.config import ProbingConfig, TargetConfig
from llm_slo_checker.prober import probe_anthropic

TARGET = TargetConfig(
    base_url="https://api.anthropic.com",
    model="claude-sonnet-4-6",
    api_key_env="TEST_KEY",
)
PROBING = ProbingConfig(
    interval_seconds=900,
    window_hours=24,
    min_samples=30,
    concurrent_probes=3,
    budget_usd_per_month=5.0,
    request_max_tokens=50,
    timeout_seconds=30,
)


@respx.mock
async def test_probe_happy_path_streams_tokens(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sk-test")

    stream_body = (
        b'event: message_start\ndata: {"type":"message_start"}\n\n'
        b'event: content_block_start\ndata: {"type":"content_block_start"}\n\n'
        b'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}\n\n'
        b'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":" world"}}\n\n'
        b'event: content_block_stop\ndata: {"type":"content_block_stop"}\n\n'
        b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    )

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=stream_body,
        )
    )

    result = await probe_anthropic(TARGET, PROBING, prompt="hi")
    assert result.success is True
    assert result.completed is True
    assert result.status_code == 200
    assert result.ttft_ms is not None
    assert result.tokens_received == 2
    assert result.error is None


@respx.mock
async def test_probe_5xx_error(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sk-test")
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(500, text="server error")
    )

    result = await probe_anthropic(TARGET, PROBING, prompt="hi")
    assert result.success is False
    assert result.status_code == 500
    assert result.tokens_received == 0
    assert result.ttft_ms is None
    assert "500" in result.error


async def test_probe_missing_api_key_env(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    with pytest.raises(ProbeError, match="TEST_KEY"):
        await probe_anthropic(TARGET, PROBING, prompt="hi")
