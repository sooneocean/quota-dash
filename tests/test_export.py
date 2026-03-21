# tests/test_export.py
import asyncio
import json
from datetime import timedelta

import pytest
from click.testing import CliRunner

from quota_dash.cli import main
from quota_dash.export import _parse_period, build_summary, format_csv, format_json, query_calls
from quota_dash.proxy.db import ApiCallRecord, init_db, write_api_call


@pytest.fixture
def db_with_data(tmp_path):
    db_path = tmp_path / "test.db"

    async def setup():
        await init_db(db_path)
        for i in range(5):
            await write_api_call(db_path, ApiCallRecord(
                provider="openai" if i % 2 == 0 else "anthropic",
                model="gpt-4" if i % 2 == 0 else "claude-opus-4-6",
                endpoint="/v1/chat/completions" if i % 2 == 0 else "/v1/messages",
                input_tokens=100 * (i + 1),
                output_tokens=50 * (i + 1),
                total_tokens=150 * (i + 1),
                ratelimit_remaining_tokens=None,
                ratelimit_remaining_requests=None,
                ratelimit_reset=None,
                request_id=None,
                target_url="https://example.com",
            ))

    asyncio.run(setup())
    return db_path


def test_parse_period_hours():
    assert _parse_period("24h") == timedelta(hours=24)


def test_parse_period_days():
    assert _parse_period("7d") == timedelta(days=7)


def test_parse_period_invalid():
    with pytest.raises(ValueError):
        _parse_period("5x")


@pytest.mark.asyncio
async def test_query_calls_all(db_with_data):
    calls = await query_calls(db_with_data, period="24h")
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_query_calls_filter_provider(db_with_data):
    calls = await query_calls(db_with_data, period="24h", provider="openai")
    assert all(c["provider"] == "openai" for c in calls)
    assert len(calls) == 3  # indices 0, 2, 4


@pytest.mark.asyncio
async def test_query_calls_empty_db(tmp_path):
    db_path = tmp_path / "empty.db"
    await init_db(db_path)
    calls = await query_calls(db_path, period="24h")
    assert calls == []


def test_build_summary():
    calls = [
        {"provider": "openai", "total_tokens": 100},
        {"provider": "openai", "total_tokens": 200},
        {"provider": "anthropic", "total_tokens": 300},
    ]
    summary = build_summary(calls, "24h")
    assert summary["total_calls"] == 3
    assert summary["total_tokens"] == 600
    assert summary["by_provider"]["openai"]["calls"] == 2
    assert summary["by_provider"]["anthropic"]["tokens"] == 300


def test_format_csv():
    calls = [
        {
            "timestamp": "2026-03-21T10:00:00",
            "provider": "openai",
            "model": "gpt-4",
            "endpoint": "/v1/chat/completions",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }
    ]
    summary = build_summary(calls, "24h")
    csv_str = format_csv(calls, summary)
    assert "timestamp" in csv_str
    assert "openai" in csv_str
    assert "# Total calls: 1" in csv_str


def test_format_json():
    calls = [{"timestamp": "2026-03-21T10:00:00", "provider": "openai", "total_tokens": 150}]
    summary = build_summary(calls, "7d")
    json_str = format_json(calls, summary)
    data = json.loads(json_str)
    assert data["period"] == "7d"
    assert data["total_calls"] == 1
    assert len(data["calls"]) == 1


def test_cli_export_help():
    runner = CliRunner()
    result = runner.invoke(main, ["export", "--help"])
    assert result.exit_code == 0
    assert "--period" in result.output
    assert "--format" in result.output


def test_cli_export_no_db(tmp_path):
    # Write a config pointing to a db path that does not exist
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[proxy]\ndb_path = "/nonexistent/path/usage.db"\n'
    )
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "export"])
    assert result.exit_code == 0
    assert "No proxy database" in result.output
