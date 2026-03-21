# tests/test_proxy_db.py

import pytest

from quota_dash.proxy.db import (
    init_db, write_api_call, query_provider_data,
    query_recent_calls, query_token_history, query_sessions, ApiCallRecord,
)


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


@pytest.mark.asyncio
async def test_query_recent_calls(db_path):
    await init_db(db_path)
    for i in range(3):
        await write_api_call(db_path, ApiCallRecord(
            provider="openai", model="gpt-4",
            endpoint="/v1/chat/completions",
            input_tokens=100 * (i + 1), output_tokens=50,
            total_tokens=150 * (i + 1),
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=f"r-{i}", target_url="https://api.openai.com",
        ))

    calls = await query_recent_calls(db_path, "openai", limit=2)
    assert len(calls) == 2
    assert "model" in calls[0]
    assert "total_tokens" in calls[0]


@pytest.mark.asyncio
async def test_query_token_history(db_path):
    await init_db(db_path)
    for i in range(5):
        await write_api_call(db_path, ApiCallRecord(
            provider="openai", model="gpt-4",
            endpoint="/v1/chat/completions",
            input_tokens=100, output_tokens=50,
            total_tokens=150,
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None, target_url="https://api.openai.com",
        ))

    history = await query_token_history(db_path, "openai", limit=3)
    assert len(history) == 3
    assert isinstance(history[0], tuple)
    assert len(history[0]) == 2  # (datetime, int)


@pytest.mark.asyncio
async def test_query_recent_calls_empty(db_path):
    await init_db(db_path)
    calls = await query_recent_calls(db_path, "openai")
    assert calls == []


@pytest.mark.asyncio
async def test_query_provider_data_includes_ratelimit_reset(db_path):
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        ratelimit_reset="2m 30s", request_id=None, target_url="https://api.openai.com",
    ))
    data = await query_provider_data(db_path, "openai")
    assert data is not None
    assert data.ratelimit_reset == "2m 30s"


@pytest.mark.asyncio
async def test_query_recent_calls_with_period(db_path):
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.openai.com",
    ))
    calls = await query_recent_calls(db_path, "openai", limit=20, period="1h")
    assert len(calls) >= 1  # just inserted, should be within 1h

    calls_7d = await query_recent_calls(db_path, "openai", limit=20, period="7d")
    assert len(calls_7d) >= 1


@pytest.mark.asyncio
async def test_session_tag_migration(db_path):
    await init_db(db_path)
    # Write with session tag
    record = ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.openai.com",
        session_tag="feature-x",
    )
    await write_api_call(db_path, record)

    sessions = await query_sessions(db_path)
    assert len(sessions) == 1
    assert sessions[0]["session_tag"] == "feature-x"


@pytest.mark.asyncio
async def test_session_tag_none_not_in_sessions(db_path):
    await init_db(db_path)
    # Write without session tag
    record = ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.openai.com",
    )
    await write_api_call(db_path, record)

    sessions = await query_sessions(db_path)
    assert len(sessions) == 0


@pytest.mark.asyncio
async def test_query_sessions_empty(db_path):
    await init_db(db_path)
    sessions = await query_sessions(db_path)
    assert sessions == []


@pytest.mark.asyncio
async def test_session_tag_multiple_sessions(db_path):
    await init_db(db_path)
    for tag in ["alpha", "beta", "alpha"]:
        record = ApiCallRecord(
            provider="anthropic", model="claude-opus-4-6", endpoint="/v1/messages",
            input_tokens=50, output_tokens=25, total_tokens=75,
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None, target_url="https://api.anthropic.com",
            session_tag=tag,
        )
        await write_api_call(db_path, record)

    sessions = await query_sessions(db_path)
    assert len(sessions) == 2
    session_tags = {s["session_tag"] for s in sessions}
    assert "alpha" in session_tags
    assert "beta" in session_tags
    alpha = next(s for s in sessions if s["session_tag"] == "alpha")
    assert alpha["calls"] == 2
