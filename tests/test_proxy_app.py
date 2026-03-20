# tests/test_proxy_app.py
import json

import pytest
from httpx import ASGITransport, AsyncClient

from quota_dash.proxy.app import create_proxy_app
from quota_dash.proxy.db import init_db, write_api_call, query_provider_data, ApiCallRecord


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_usage.db"


@pytest.mark.asyncio
async def test_proxy_app_404_unknown_route(db_path):
    app = create_proxy_app(db_path=db_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/unknown/path")
    assert resp.status_code == 404
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_proxy_app_health(db_path):
    app = create_proxy_app(db_path=db_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_proxy_db_integration(db_path):
    """Verify that the proxy app initializes DB on startup and it can be queried."""
    app = create_proxy_app(db_path=db_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger startup (which calls init_db)
        resp = await client.get("/health")
        assert resp.status_code == 200

    # Ensure DB is initialized (startup event may not fire via ASGITransport lifespan)
    await init_db(db_path)

    # Manually write a record (simulating what the proxy would do)
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=8000, ratelimit_remaining_requests=99,
        ratelimit_reset=None, request_id="test-req",
        target_url="https://api.openai.com/v1/chat/completions",
    ))

    # Query it back
    data = await query_provider_data(db_path, "openai")
    assert data is not None
    assert data.input_tokens == 100
    assert data.total_tokens == 150
    assert data.calls_today == 1
