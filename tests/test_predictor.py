import pytest
from pathlib import Path

from quota_dash.data.predictor import predict_rate_limit_exhaustion, _format_eta
from quota_dash.proxy.db import init_db, write_api_call, ApiCallRecord


def test_format_eta_seconds():
    assert _format_eta(30) == "~30s"

def test_format_eta_minutes():
    assert _format_eta(300) == "~5m"

def test_format_eta_hours():
    assert "h" in _format_eta(7200)

def test_format_eta_days():
    assert "d" in _format_eta(100000)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.mark.asyncio
async def test_predict_no_db():
    result = await predict_rate_limit_exhaustion(
        Path("/nonexistent"), "openai", 5000, 100
    )
    assert result["tokens_eta"] is None
    assert result["requests_eta"] is None


@pytest.mark.asyncio
async def test_predict_insufficient_data(db_path):
    await init_db(db_path)
    # Only 1 call — need at least 2
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None, target_url="https://api.openai.com",
    ))
    result = await predict_rate_limit_exhaustion(db_path, "openai", 5000, 100)
    assert result["tokens_eta"] is None


@pytest.mark.asyncio
async def test_predict_with_no_remaining():
    """No remaining tokens = no prediction."""
    result = await predict_rate_limit_exhaustion(
        Path("/nonexistent"), "openai", None, None
    )
    assert result["tokens_eta"] is None
