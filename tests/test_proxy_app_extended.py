# tests/test_proxy_app_extended.py
"""Extended tests for proxy/app.py covering streaming, non-streaming, error paths."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from quota_dash.proxy.app import create_proxy_app, _safe_write
from quota_dash.proxy.db import init_db, query_provider_data, ApiCallRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_usage.db"


def _make_fake_response(
    body: bytes,
    status_code: int = 200,
    headers: dict | None = None,
    content_type: str = "application/json",
) -> MagicMock:
    """Build a fake httpx Response-like object suitable for client.send(stream=True)."""
    resp = MagicMock()
    resp.status_code = status_code
    _headers = {"content-type": content_type, "x-request-id": "req-test-123"}
    if headers:
        _headers.update(headers)
    resp.headers = _headers

    # aread returns the body bytes
    resp.aread = AsyncMock(return_value=body)
    resp.aclose = AsyncMock()

    # aiter_text yields the body decoded (for streaming path)
    decoded = body.decode()

    async def _aiter_text():
        yield decoded

    resp.aiter_text = _aiter_text
    return resp


# ---------------------------------------------------------------------------
# Non-streaming: OpenAI JSON response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_forwards_non_streaming_openai(db_path):
    """Non-streaming OpenAI response is forwarded and usage is written to DB."""
    await init_db(db_path)

    upstream_body = json.dumps({
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "model": "gpt-4o",
    }).encode()

    fake_resp = _make_fake_response(
        upstream_body,
        headers={"x-request-id": "req-abc", "x-ratelimit-remaining-tokens": "9000"},
    )

    # Patch httpx.AsyncClient so no real network call is made
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(return_value=fake_resp)
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path)

    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            )

    # Proxy should forward the upstream status and body
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data

    # Allow background task to complete
    await asyncio.sleep(0.05)

    # Check DB was written
    provider_data = await query_provider_data(db_path, "openai")
    assert provider_data is not None
    assert provider_data.input_tokens == 10
    assert provider_data.output_tokens == 5
    assert provider_data.total_tokens == 15


# ---------------------------------------------------------------------------
# Non-streaming: Anthropic JSON response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_forwards_non_streaming_anthropic(db_path):
    """Non-streaming Anthropic response writes correct tokens to DB."""
    await init_db(db_path)

    upstream_body = json.dumps({
        "type": "message",
        "usage": {"input_tokens": 20, "output_tokens": 30},
        "model": "claude-3-5-haiku-20241022",
    }).encode()

    fake_resp = _make_fake_response(upstream_body)

    mock_client = MagicMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(return_value=fake_resp)
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path)

    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/messages", json={"model": "claude-3-5-haiku-20241022"})

    assert resp.status_code == 200

    await asyncio.sleep(0.05)

    provider_data = await query_provider_data(db_path, "anthropic")
    assert provider_data is not None
    assert provider_data.input_tokens == 20
    assert provider_data.output_tokens == 30
    assert provider_data.total_tokens == 50


# ---------------------------------------------------------------------------
# Non-streaming: invalid JSON body from upstream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_handles_non_json_upstream_response(db_path):
    """Non-JSON upstream body is handled gracefully (no crash, still returns response)."""
    await init_db(db_path)

    fake_resp = _make_fake_response(b"not-json-at-all", content_type="text/plain")

    mock_client = MagicMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(return_value=fake_resp)
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path)

    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", content=b"hello")

    # Should still return a response with the raw body
    assert resp.status_code == 200
    assert resp.content == b"not-json-at-all"


# ---------------------------------------------------------------------------
# 404 with target filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_target_filter_rejects_wrong_provider(db_path):
    """When target_filter='openai', Anthropic paths return 404."""
    app = create_proxy_app(db_path=db_path, target_filter="openai")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/messages", json={})

    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "openai" in body["error"]


@pytest.mark.asyncio
async def test_proxy_target_filter_allows_matching_provider(db_path):
    """When target_filter='anthropic', Anthropic path is not rejected by filter."""
    await init_db(db_path)

    upstream_body = json.dumps({
        "type": "message",
        "usage": {"input_tokens": 5, "output_tokens": 5},
        "model": "claude-3-haiku",
    }).encode()

    fake_resp = _make_fake_response(upstream_body)
    mock_client = MagicMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(return_value=fake_resp)
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path, target_filter="anthropic")

    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/messages", json={})

    # Should NOT be rejected by the filter
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 502 when upstream raises HTTPError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_returns_502_on_upstream_error(db_path):
    """When httpx raises HTTPError, proxy returns 502 Bad Gateway."""
    mock_client = MagicMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path)

    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", json={"model": "gpt-4"})

    assert resp.status_code == 502
    assert resp.json()["error"] == "Bad Gateway"


@pytest.mark.asyncio
async def test_proxy_returns_502_on_timeout(db_path):
    """Timeout from httpx also results in 502."""
    mock_client = MagicMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path)

    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/chat/completions", json={"model": "gpt-4"})

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Streaming response path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_streaming_response(db_path):
    """Streaming (text/event-stream) response is forwarded as StreamingResponse."""
    await init_db(db_path)

    # Simulate an OpenAI-style SSE stream with usage in the last chunk
    _chunk1 = (
        'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"Hi"},"index":0}],'
        '"model":"gpt-4o"}\n\n'
    )
    _chunk2 = (
        'data: {"id":"chatcmpl-1","choices":[],'
        '"usage":{"prompt_tokens":8,"completion_tokens":3,"total_tokens":11},'
        '"model":"gpt-4o"}\n\n'
    )
    sse_chunks = [_chunk1, _chunk2, "data: [DONE]\n\n"]

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {
        "content-type": "text/event-stream",
        "x-request-id": "req-stream-1",
        "x-ratelimit-remaining-tokens": "8000",
    }
    fake_resp.aclose = AsyncMock()

    async def _aiter_text():
        for chunk in sse_chunks:
            yield chunk

    fake_resp.aiter_text = _aiter_text

    mock_client = MagicMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.send = AsyncMock(return_value=fake_resp)
    mock_client.aclose = AsyncMock()

    app = create_proxy_app(db_path=db_path)

    collected = []
    with patch("quota_dash.proxy.app.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/v1/chat/completions", json={"stream": True}) as resp:
                assert resp.status_code == 200
                async for chunk in resp.aiter_text():
                    collected.append(chunk)

    # All chunks should have been forwarded
    full = "".join(collected)
    assert "Hi" in full
    assert "[DONE]" in full

    # Allow the finally block (write_api_call) to execute
    await asyncio.sleep(0.1)

    provider_data = await query_provider_data(db_path, "openai")
    assert provider_data is not None
    assert provider_data.input_tokens == 8
    assert provider_data.total_tokens == 11


# ---------------------------------------------------------------------------
# _safe_write helper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safe_write_does_not_raise_on_error(tmp_path):
    """_safe_write swallows exceptions silently."""
    db_path = tmp_path / "bad.db"
    record = ApiCallRecord(
        provider="openai", model=None, endpoint="/v1/chat/completions",
        input_tokens=0, output_tokens=0, total_tokens=0,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url=None,
    )
    # Should not raise even if DB isn't initialised (write_api_call handles errors internally)
    await _safe_write(db_path, record)


# ---------------------------------------------------------------------------
# 404 for completely unknown path (no route match)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_returns_404_for_unknown_path(db_path):
    app = create_proxy_app(db_path=db_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/totally/unknown/path")
    assert resp.status_code == 404
    assert "error" in resp.json()
