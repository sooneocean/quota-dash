"""Tests for error handling in providers, CLI --init, and CLI --check."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from click.testing import CliRunner

from quota_dash.cli import main
from quota_dash.config import ProviderConfig
from quota_dash.data.api_client import check_openai_connection
from quota_dash.providers.anthropic import AnthropicProvider
from quota_dash.providers.openai import OpenAIProvider


# --- Provider error handling ---


@pytest.mark.asyncio
async def test_openai_get_quota_catches_exception():
    config = ProviderConfig(enabled=True, api_key_env="FAKE_KEY", log_path=Path("/tmp"))
    provider = OpenAIProvider(config)

    with patch.object(provider, "_fetch_quota", side_effect=RuntimeError("boom")):
        quota = await provider.get_quota()
        assert quota.source == "error"
        assert quota.stale is True
        assert quota.provider == "openai"


@pytest.mark.asyncio
async def test_openai_get_token_usage_catches_exception():
    config = ProviderConfig(enabled=True, api_key_env="FAKE_KEY", log_path=Path("/nonexistent/path"))
    provider = OpenAIProvider(config)

    with patch("quota_dash.providers.openai.parse_codex_logs", side_effect=OSError("disk error")):
        tokens = await provider.get_token_usage()
        assert tokens.source == "error"
        assert tokens.total_tokens == 0


@pytest.mark.asyncio
async def test_anthropic_get_quota_catches_exception():
    config = ProviderConfig(enabled=True, api_key_env="FAKE_KEY", log_path=Path("/tmp"))
    provider = AnthropicProvider(config)

    with patch.object(provider, "_build_quota", side_effect=RuntimeError("boom")):
        quota = await provider.get_quota()
        assert quota.source == "error"
        assert quota.stale is True
        assert quota.provider == "anthropic"


@pytest.mark.asyncio
async def test_anthropic_get_token_usage_catches_exception():
    config = ProviderConfig(enabled=True, api_key_env="FAKE_KEY", log_path=Path("/tmp"))
    provider = AnthropicProvider(config)

    with patch("quota_dash.providers.anthropic.parse_claude_costs_jsonl", side_effect=OSError("disk error")):
        tokens = await provider.get_token_usage()
        assert tokens.source == "error"
        assert tokens.total_tokens == 0


# --- check_openai_connection ---


@pytest.mark.asyncio
async def test_check_openai_connection_no_key():
    ok, msg = await check_openai_connection("")
    assert ok is False
    assert "No API key" in msg


@pytest.mark.asyncio
async def test_check_openai_connection_success():
    mock_response = httpx.Response(
        200,
        json={"data": []},
        request=httpx.Request("GET", "https://api.openai.com/v1/models"),
    )
    with patch("quota_dash.data.api_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        ok, msg = await check_openai_connection("test-key")
        assert ok is True


@pytest.mark.asyncio
async def test_check_openai_connection_401():
    mock_response = httpx.Response(
        401,
        text="Unauthorized",
        request=httpx.Request("GET", "https://api.openai.com/v1/models"),
    )
    with patch("quota_dash.data.api_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        ok, msg = await check_openai_connection("bad-key")
        assert ok is False
        assert "Invalid" in msg


@pytest.mark.asyncio
async def test_check_openai_connection_timeout():
    with patch("quota_dash.data.api_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        ok, msg = await check_openai_connection("test-key")
        assert ok is False
        assert "timed out" in msg.lower()


# --- CLI --init ---


def test_cli_init_creates_config():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "config.toml"
        with patch("quota_dash.cli.DEFAULT_CONFIG_PATH", target), \
             patch("quota_dash.cli.DEFAULT_CONFIG_DIR", Path(td)):
            result = runner.invoke(main, ["--init"])
            assert result.exit_code == 0
            assert "Config created" in result.output
            assert target.exists()
            content = target.read_text()
            assert "[general]" in content


def test_cli_init_refuses_overwrite():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "config.toml"
        target.write_text("existing")
        with patch("quota_dash.cli.DEFAULT_CONFIG_PATH", target), \
             patch("quota_dash.cli.DEFAULT_CONFIG_DIR", Path(td)):
            result = runner.invoke(main, ["--init"])
            assert result.exit_code == 0
            assert "already exists" in result.output
            assert target.read_text() == "existing"


# --- CLI --check ---


def test_cli_check_runs():
    runner = CliRunner()

    sample_config = """\
[general]
polling_interval = 60

[providers.openai]
enabled = true
api_key_env = "NONEXISTENT_KEY_FOR_TEST"
log_path = "/tmp/nonexistent"

[providers.anthropic]
enabled = true
log_path = "/tmp/nonexistent"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(sample_config)
        config_path = f.name

    result = runner.invoke(main, ["--check", "--config", config_path])
    assert result.exit_code == 0
    assert "openai" in result.output.lower()
    assert "anthropic" in result.output.lower()
