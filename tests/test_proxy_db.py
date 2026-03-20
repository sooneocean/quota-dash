# tests/test_proxy_db.py
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from quota_dash.proxy.db import init_db, write_api_call, query_provider_data, ApiCallRecord


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_usage.db"


@pytest.mark.asyncio
async def test_init_db_creates_tables(db_path):
    await init_db(db_path)
    assert db_path.exists()


@pytest.mark.asyncio
async def test_write_and_query(db_path):
    await init_db(db_path)
    record = ApiCallRecord(
        provider="openai",
        model="gpt-4",
        endpoint="/v1/chat/completions",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        ratelimit_remaining_tokens=9000,
        ratelimit_remaining_requests=99,
        ratelimit_reset=None,
        request_id="req-123",
        target_url="https://api.openai.com/v1/chat/completions",
    )
    await write_api_call(db_path, record)

    data = await query_provider_data(db_path, "openai")
    assert data is not None
    assert data.input_tokens == 100
    assert data.total_tokens == 150
    assert data.calls_today == 1
    assert data.tokens_today == 150


@pytest.mark.asyncio
async def test_query_empty_db(db_path):
    await init_db(db_path)
    data = await query_provider_data(db_path, "openai")
    assert data is None


@pytest.mark.asyncio
async def test_write_multiple_records(db_path):
    await init_db(db_path)
    for i in range(3):
        record = ApiCallRecord(
            provider="anthropic", model="claude-opus-4-6",
            endpoint="/v1/messages",
            input_tokens=100 * (i + 1), output_tokens=50 * (i + 1),
            total_tokens=150 * (i + 1),
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None,
            target_url="https://api.anthropic.com/v1/messages",
        )
        await write_api_call(db_path, record)

    data = await query_provider_data(db_path, "anthropic")
    assert data is not None
    assert data.calls_today == 3
    assert data.tokens_today == 150 + 300 + 450
    assert data.input_tokens == 300  # most recent
    assert data.model == "claude-opus-4-6"
