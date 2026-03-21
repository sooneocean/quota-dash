import pytest
from pathlib import Path
from quota_dash.config import ProviderConfig
from quota_dash.providers.google import GoogleProvider
from quota_dash.providers.groq import GroqProvider
from quota_dash.providers.mistral import MistralProvider
from quota_dash.proxy.db import init_db, write_api_call, ApiCallRecord


@pytest.mark.asyncio
async def test_google_quota_manual():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"),
        balance_usd=50.0, limit_usd=100.0,
    )
    p = GoogleProvider(config)
    q = await p.get_quota()
    assert q.provider == "google"
    assert q.balance_usd == 50.0
    assert q.source == "manual"

@pytest.mark.asyncio
async def test_google_quota_unavailable():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config)
    q = await p.get_quota()
    assert q.source == "unavailable"

@pytest.mark.asyncio
async def test_google_token_usage_no_proxy():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config, db_path=None)
    t = await p.get_token_usage()
    assert t.source == "estimated"

@pytest.mark.asyncio
async def test_google_context_window():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config)
    c = await p.get_context_window()
    assert c.max_tokens == 1048576
    assert c.model == "gemini-2.0-flash"

@pytest.mark.asyncio
async def test_groq_quota_manual():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"),
        balance_usd=10.0, limit_usd=50.0,
    )
    p = GroqProvider(config)
    q = await p.get_quota()
    assert q.provider == "groq"
    assert q.source == "manual"

@pytest.mark.asyncio
async def test_groq_context_window():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config)
    c = await p.get_context_window()
    assert c.max_tokens == 131072

@pytest.mark.asyncio
async def test_mistral_quota_manual():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"),
        balance_usd=25.0, limit_usd=100.0,
    )
    p = MistralProvider(config)
    q = await p.get_quota()
    assert q.provider == "mistral"
    assert q.source == "manual"

@pytest.mark.asyncio
async def test_mistral_context_window():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config)
    c = await p.get_context_window()
    assert c.max_tokens == 131072


# ---------------------------------------------------------------------------
# Groq proxy data tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="groq", model="llama-3.3-70b", endpoint="/v1/chat/completions",
        input_tokens=300, output_tokens=100, total_tokens=400,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.groq.com",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config, db_path=db_path)
    t = await p.get_token_usage()
    assert t.input_tokens == 300
    assert t.output_tokens == 100
    assert t.total_tokens == 400
    assert t.source == "proxy"


@pytest.mark.asyncio
async def test_groq_context_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="groq", model="llama-3.3-70b", endpoint="/v1/chat/completions",
        input_tokens=5000, output_tokens=100, total_tokens=5100,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.groq.com",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config, db_path=db_path)
    c = await p.get_context_window()
    assert c.used_tokens == 5000
    assert "last call snapshot" in c.note


@pytest.mark.asyncio
async def test_groq_quota_unavailable():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config)
    q = await p.get_quota()
    assert q.provider == "groq"
    assert q.source == "unavailable"


@pytest.mark.asyncio
async def test_groq_token_usage_no_proxy():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config, db_path=None)
    t = await p.get_token_usage()
    assert t.source == "estimated"
    assert t.input_tokens == 0


@pytest.mark.asyncio
async def test_groq_proxy_data_no_db(tmp_path):
    """get_proxy_data returns None when db_path does not exist."""
    db_path = tmp_path / "nonexistent.db"
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config, db_path=db_path)
    result = await p.get_proxy_data()
    assert result is None


# ---------------------------------------------------------------------------
# Mistral proxy data tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mistral_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="mistral", model="mistral-large", endpoint="/v1/chat/completions",
        input_tokens=500, output_tokens=200, total_tokens=700,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.mistral.ai",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config, db_path=db_path)
    t = await p.get_token_usage()
    assert t.input_tokens == 500
    assert t.output_tokens == 200
    assert t.total_tokens == 700
    assert t.source == "proxy"


@pytest.mark.asyncio
async def test_mistral_context_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="mistral", model="mistral-large", endpoint="/v1/chat/completions",
        input_tokens=8000, output_tokens=200, total_tokens=8200,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.mistral.ai",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config, db_path=db_path)
    c = await p.get_context_window()
    assert c.used_tokens == 8000
    assert "last call snapshot" in c.note


@pytest.mark.asyncio
async def test_mistral_quota_unavailable():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config)
    q = await p.get_quota()
    assert q.provider == "mistral"
    assert q.source == "unavailable"


@pytest.mark.asyncio
async def test_mistral_token_usage_no_proxy():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config, db_path=None)
    t = await p.get_token_usage()
    assert t.source == "estimated"
    assert t.input_tokens == 0


@pytest.mark.asyncio
async def test_mistral_proxy_data_no_db(tmp_path):
    """get_proxy_data returns None when db_path does not exist."""
    db_path = tmp_path / "nonexistent.db"
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config, db_path=db_path)
    result = await p.get_proxy_data()
    assert result is None


# ---------------------------------------------------------------------------
# Google proxy data tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_google_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="google", model="gemini-2.0-flash", endpoint="/v1/chat/completions",
        input_tokens=1000, output_tokens=400, total_tokens=1400,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://generativelanguage.googleapis.com",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config, db_path=db_path)
    t = await p.get_token_usage()
    assert t.input_tokens == 1000
    assert t.output_tokens == 400
    assert t.total_tokens == 1400
    assert t.source == "proxy"


@pytest.mark.asyncio
async def test_google_context_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="google", model="gemini-2.0-flash", endpoint="/v1/chat/completions",
        input_tokens=50000, output_tokens=1000, total_tokens=51000,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://generativelanguage.googleapis.com",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config, db_path=db_path)
    c = await p.get_context_window()
    assert c.used_tokens == 50000
    assert c.max_tokens == 1048576
    assert "last call snapshot" in c.note


@pytest.mark.asyncio
async def test_google_proxy_data_no_db(tmp_path):
    """get_proxy_data returns None when db_path does not exist."""
    db_path = tmp_path / "nonexistent.db"
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config, db_path=db_path)
    result = await p.get_proxy_data()
    assert result is None
