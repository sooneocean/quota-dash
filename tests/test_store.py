from datetime import datetime

from quota_dash.data.store import DataStore
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData


def test_store_update_provider():
    store = DataStore()
    quota = QuotaInfo(
        provider="openai", balance_usd=47.32, limit_usd=100.0,
        usage_today_usd=3.20, last_updated=datetime.now(),
        source="api", stale=False,
    )
    store.update_quota("openai", quota)
    assert store.get_quota("openai") == quota


def test_store_get_missing_provider():
    store = DataStore()
    assert store.get_quota("nonexistent") is None


def test_store_aggregate_balance():
    store = DataStore()
    store.update_quota("openai", QuotaInfo(
        provider="openai", balance_usd=47.32, limit_usd=100.0,
        usage_today_usd=3.20, last_updated=datetime.now(),
        source="api", stale=False,
    ))
    store.update_quota("anthropic", QuotaInfo(
        provider="anthropic", balance_usd=100.0, limit_usd=200.0,
        usage_today_usd=1.50, last_updated=datetime.now(),
        source="manual", stale=False,
    ))
    assert store.total_balance() == 147.32
    assert store.total_usage_today() == 4.70


def test_store_aggregate_skips_none():
    store = DataStore()
    store.update_quota("openai", QuotaInfo(
        provider="openai", balance_usd=47.32, limit_usd=100.0,
        usage_today_usd=3.20, last_updated=datetime.now(),
        source="api", stale=False,
    ))
    store.update_quota("anthropic", QuotaInfo(
        provider="anthropic", balance_usd=None, limit_usd=None,
        usage_today_usd=None, last_updated=datetime.now(),
        source="unavailable", stale=False,
    ))
    assert store.total_balance() == 47.32
    assert store.total_usage_today() == 3.20


def test_store_update_and_get_proxy():
    store = DataStore()
    pd = ProxyData(
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        model="gpt-4", last_call=datetime.now(),
        calls_today=5, tokens_today=1500,
    )
    store.update_proxy("openai", pd)
    assert store.get_proxy("openai") == pd
    assert store.get_proxy("missing") is None


def test_store_total_tokens_today():
    store = DataStore()
    store.update_proxy("openai", ProxyData(
        input_tokens=0, output_tokens=0, total_tokens=0,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        model=None, last_call=datetime.now(),
        calls_today=5, tokens_today=1500,
    ))
    store.update_proxy("anthropic", ProxyData(
        input_tokens=0, output_tokens=0, total_tokens=0,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        model=None, last_call=datetime.now(),
        calls_today=3, tokens_today=2000,
    ))
    assert store.total_tokens_today() == 3500


def test_store_total_tokens_today_no_proxy():
    store = DataStore()
    store.update_tokens("openai", TokenUsage(
        input_tokens=500, output_tokens=200, total_tokens=700,
        history=[], session_id=None, source="estimated",
    ))
    assert store.total_tokens_today() == 700
