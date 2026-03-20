"""Tests for the bug fixes: API parsing, Codex SQLite parser, config validation, provider filter."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from quota_dash.config import load_config
from quota_dash.data.api_client import fetch_openai_usage
from quota_dash.data.log_parser import parse_codex_logs


# --- Fix #1: OpenAI API empty data array ---


@pytest.mark.asyncio
async def test_fetch_openai_usage_empty_data_array():
    """Regression: {"data": []} should return 0, not IndexError."""
    mock_response = httpx.Response(
        200,
        json={"data": []},
        request=httpx.Request("GET", "https://api.openai.com/v1/organization/usage"),
    )
    with patch("quota_dash.data.api_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await fetch_openai_usage("test-key")
        assert result is not None
        assert result["usage_usd"] == 0.0


@pytest.mark.asyncio
async def test_fetch_openai_usage_missing_data_key():
    """Response with no 'data' key should return 0."""
    mock_response = httpx.Response(
        200,
        json={"something_else": True},
        request=httpx.Request("GET", "https://api.openai.com/v1/organization/usage"),
    )
    with patch("quota_dash.data.api_client.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await fetch_openai_usage("test-key")
        assert result is not None
        assert result["usage_usd"] == 0.0


# --- Fix #2: Codex SQLite parser ---


def _create_codex_state_db(db_path: Path, threads: list[tuple]) -> None:
    """Create a minimal Codex state_5.sqlite with thread data."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE threads ("
        "id TEXT PRIMARY KEY, tokens_used INTEGER NOT NULL DEFAULT 0, "
        "created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)"
    )
    for tid, tokens, created, updated in threads:
        conn.execute(
            "INSERT INTO threads (id, tokens_used, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (tid, tokens, created, updated),
        )
    conn.commit()
    conn.close()


def test_parse_codex_logs_with_real_data():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "state_5.sqlite"
        _create_codex_state_db(db_path, [
            ("thread-1", 50000, 1700000000, 1700000100),
            ("thread-2", 120000, 1700000200, 1700000300),
        ])

        result = parse_codex_logs(Path(td))
        assert result.total_tokens == 170000
        assert result.source == "log"
        assert result.session_id == "thread-2"  # most recent
        assert len(result.history) == 2


def test_parse_codex_logs_empty_db():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "state_5.sqlite"
        _create_codex_state_db(db_path, [])

        result = parse_codex_logs(Path(td))
        assert result.total_tokens == 0
        assert result.source == "log"


def test_parse_codex_logs_no_db():
    result = parse_codex_logs(Path("/nonexistent/dir"))
    assert result.total_tokens == 0
    assert result.source == "estimated"


def test_parse_codex_logs_accepts_sqlite_path():
    """Passing a .sqlite file path should resolve to parent dir."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "state_5.sqlite"
        _create_codex_state_db(db_path, [
            ("t1", 10000, 1700000000, 1700000100),
        ])

        # Pass the .sqlite path directly (old-style)
        result = parse_codex_logs(Path(td) / "logs_1.sqlite")
        assert result.total_tokens == 10000
        assert result.source == "log"


# --- Fix #4: Config validation ---


def test_config_invalid_polling_interval_zero():
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
        f.write(b'[general]\npolling_interval = 0\n')
        path = Path(f.name)

    config = load_config(path)
    assert config.polling_interval == 60  # reset to default
    path.unlink()


def test_config_invalid_polling_interval_negative():
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
        f.write(b'[general]\npolling_interval = -5\n')
        path = Path(f.name)

    config = load_config(path)
    assert config.polling_interval == 60
    path.unlink()


def test_config_valid_polling_interval():
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
        f.write(b'[general]\npolling_interval = 30\n')
        path = Path(f.name)

    config = load_config(path)
    assert config.polling_interval == 30
    path.unlink()
