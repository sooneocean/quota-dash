import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from quota_dash.config import ProviderConfig
from quota_dash.providers.openai import OpenAIProvider
from quota_dash.providers.anthropic import AnthropicProvider
from quota_dash.proxy.db import init_db, write_api_call, ApiCallRecord


@pytest.mark.asyncio
async def test_openai_get_quota_manual_fallback():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT_KEY",
        log_path=Path("/tmp"), balance_usd=50.0, limit_usd=100.0,
    )
    provider = OpenAIProvider(config)
    quota = await provider.get_quota()
    assert quota.provider == "openai"
    assert quota.balance_usd == 50.0
    assert quota.source == "manual"


@pytest.mark.asyncio
async def test_openai_get_quota_unavailable():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT_KEY",
        log_path=Path("/tmp"),
    )
    provider = OpenAIProvider(config)
    quota = await provider.get_quota()
    assert quota.source == "unavailable"
    assert quota.balance_usd is None


@pytest.mark.asyncio
async def test_openai_get_token_usage():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT_KEY",
        log_path=Path("/tmp/nonexistent"),
    )
    provider = OpenAIProvider(config)
    tokens = await provider.get_token_usage()
    assert tokens.source == "estimated"
    assert tokens.total_tokens == 0


@pytest.mark.asyncio
async def test_anthropic_get_quota_manual():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT_KEY",
        log_path=Path("/tmp"), balance_usd=200.0, limit_usd=500.0,
    )
    provider = AnthropicProvider(config)
    quota = await provider.get_quota()
    assert quota.provider == "anthropic"
    assert quota.balance_usd == 200.0
    assert quota.source == "manual"


@pytest.mark.asyncio
async def test_anthropic_get_quota_unavailable():
    config = ProviderConfig(
        enabled=True, api_key_env="NONEXISTENT_KEY",
        log_path=Path("/tmp"),
    )
    provider = AnthropicProvider(config)
    quota = await provider.get_quota()
    assert quota.source == "unavailable"


@pytest.mark.asyncio
async def test_anthropic_get_token_usage_from_log():
    entries = [
        {"timestamp": "2026-03-20T10:00:00Z", "session_id": "s1", "model": "claude-opus-4-6", "input_tokens": 1000, "output_tokens": 500, "cost_usd": 0.03},
    ]
    with tempfile.TemporaryDirectory() as td:
        costs_path = Path(td) / "metrics" / "costs.jsonl"
        costs_path.parent.mkdir(parents=True)
        with open(costs_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        config = ProviderConfig(
            enabled=True, api_key_env="NONEXISTENT_KEY",
            log_path=Path(td),
        )
        provider = AnthropicProvider(config)
        tokens = await provider.get_token_usage()
        assert tokens.input_tokens == 1000
        assert tokens.output_tokens == 500
        assert tokens.source == "log"


@pytest.mark.asyncio
async def test_openai_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=500, output_tokens=200, total_tokens=700,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        ratelimit_reset=None, request_id="r-1",
        target_url="https://api.openai.com/v1/chat/completions",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp/nonexistent"))
    provider = OpenAIProvider(config, db_path=db_path)
    tokens = await provider.get_token_usage()
    assert tokens.input_tokens == 500
    assert tokens.output_tokens == 200
    assert tokens.source == "proxy"


@pytest.mark.asyncio
async def test_openai_falls_back_without_proxy():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp/nonexistent"))
    provider = OpenAIProvider(config, db_path=None)
    tokens = await provider.get_token_usage()
    assert tokens.source == "estimated"


@pytest.mark.asyncio
async def test_anthropic_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="anthropic", model="claude-opus-4-6", endpoint="/v1/messages",
        input_tokens=1000, output_tokens=400, total_tokens=1400,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None,
        target_url="https://api.anthropic.com/v1/messages",
    ))
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp/nonexistent"))
    provider = AnthropicProvider(config, db_path=db_path)
    tokens = await provider.get_token_usage()
    assert tokens.input_tokens == 1000
    assert tokens.source == "proxy"
