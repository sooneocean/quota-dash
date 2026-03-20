from datetime import datetime
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData


def test_quota_info_creation():
    q = QuotaInfo(
        provider="openai",
        balance_usd=47.32,
        limit_usd=100.0,
        usage_today_usd=3.20,
        last_updated=datetime(2026, 3, 20, 12, 0),
        source="api",
        stale=False,
    )
    assert q.provider == "openai"
    assert q.balance_usd == 47.32
    assert q.stale is False


def test_quota_info_unavailable():
    q = QuotaInfo(
        provider="anthropic",
        balance_usd=None,
        limit_usd=None,
        usage_today_usd=None,
        last_updated=datetime(2026, 3, 20, 12, 0),
        source="unavailable",
        stale=False,
    )
    assert q.balance_usd is None
    assert q.source == "unavailable"


def test_token_usage_creation():
    t = TokenUsage(
        input_tokens=12400,
        output_tokens=8100,
        total_tokens=20500,
        history=[(datetime(2026, 3, 20, 12, 0), 500)],
        session_id="abc123",
        source="log",
    )
    assert t.total_tokens == 20500
    assert len(t.history) == 1


def test_token_usage_empty_history():
    t = TokenUsage(
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        history=[],
        session_id=None,
        source="estimated",
    )
    assert t.history == []


def test_context_info_creation():
    c = ContextInfo(
        used_tokens=62000,
        max_tokens=100000,
        percent_used=62.0,
        model="gpt-4",
        note="",
    )
    assert c.percent_used == 62.0


def test_context_info_approximation():
    c = ContextInfo(
        used_tokens=0,
        max_tokens=200000,
        percent_used=0.0,
        model="claude-opus-4-6",
        note="approximation — CLI logs lack per-turn data",
    )
    assert "approximation" in c.note


def test_proxy_data_creation():
    pd = ProxyData(
        input_tokens=1500,
        output_tokens=800,
        total_tokens=2300,
        ratelimit_remaining_tokens=50000,
        ratelimit_remaining_requests=100,
        model="gpt-4",
        last_call=datetime(2026, 3, 21, 10, 0),
        calls_today=15,
        tokens_today=35000,
    )
    assert pd.total_tokens == 2300
    assert pd.calls_today == 15


def test_proxy_data_nullable_fields():
    pd = ProxyData(
        input_tokens=0, output_tokens=0, total_tokens=0,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        model=None, last_call=datetime(2026, 3, 21, 10, 0),
        calls_today=0, tokens_today=0,
    )
    assert pd.model is None
