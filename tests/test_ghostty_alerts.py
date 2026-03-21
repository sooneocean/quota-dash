# tests/test_ghostty_alerts.py
from datetime import datetime
from unittest.mock import patch, MagicMock

from quota_dash.ghostty.alerts import AlertMonitor, send_notification, send_bell
from quota_dash.data.store import DataStore
from quota_dash.models import QuotaInfo


def _make_store_with_quota(provider: str, balance: float, limit: float) -> DataStore:
    store = DataStore()
    store.update_quota(provider, QuotaInfo(
        provider=provider, balance_usd=balance, limit_usd=limit,
        usage_today_usd=None, last_updated=datetime.now(),
        source="manual", stale=False,
    ))
    return store


def test_no_alert_when_balance_healthy():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 80.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert actions == []


def test_warning_at_50_percent():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 40.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert any(a["level"] == "warning" for a in actions)


def test_alert_at_20_percent():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 15.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert any(a["level"] == "alert" for a in actions)


def test_critical_at_5_percent():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 3.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert any(a["level"] == "critical" for a in actions)


def test_deduplication():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 15.0, 100.0)
    app = MagicMock()
    actions1 = monitor.check(app, store)
    actions2 = monitor.check(app, store)
    assert len(actions1) > 0
    assert len(actions2) == 0  # already notified


def test_rearm_after_recovery():
    monitor = AlertMonitor()
    app = MagicMock()

    # First: trigger alert
    store_low = _make_store_with_quota("openai", 15.0, 100.0)
    monitor.check(app, store_low)

    # Then: balance recovers
    store_high = _make_store_with_quota("openai", 80.0, 100.0)
    monitor.check(app, store_high)

    # Then: drops again — should re-fire
    actions = monitor.check(app, store_low)
    assert len(actions) > 0


def test_skip_none_balance():
    monitor = AlertMonitor()
    store = DataStore()
    store.update_quota("openai", QuotaInfo(
        provider="openai", balance_usd=None, limit_usd=None,
        usage_today_usd=None, last_updated=datetime.now(),
        source="unavailable", stale=False,
    ))
    app = MagicMock()
    actions = monitor.check(app, store)
    assert actions == []


def test_skip_zero_limit():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 50.0, 0.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert actions == []


def test_send_notification_writes_osc9():
    with patch("sys.stdout") as mock_stdout:
        send_notification("quota-dash: OpenAI balance low")
        mock_stdout.write.assert_called_once()
        written = mock_stdout.write.call_args[0][0]
        assert "\x1b]9;" in written
        assert "\x07" in written


def test_send_bell():
    with patch("sys.stdout") as mock_stdout:
        send_bell()
        mock_stdout.write.assert_called_once_with("\x07")


def test_custom_thresholds():
    monitor = AlertMonitor(warning=80, alert=50, critical=10)
    store = _make_store_with_quota("openai", 45.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    # 45% < 50% alert threshold, so should trigger alert
    assert any(a["level"] == "alert" for a in actions)
