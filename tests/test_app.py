import pytest
from pathlib import Path
from unittest.mock import patch
from quota_dash.app import QuotaDashApp
from quota_dash.config import AppConfig, ProviderConfig
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.detail_panel import DetailPanel
from quota_dash.widgets.history_table import HistoryTable


@pytest.mark.asyncio
async def test_app_launches():
    app = QuotaDashApp()
    async with app.run_test() as _:
        assert app.title == "quota-dash"


@pytest.mark.asyncio
async def test_app_quit_binding():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_refresh_binding():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        await pilot.press("r")


@pytest.mark.asyncio
async def test_app_has_new_widgets():
    app = QuotaDashApp()
    async with app.run_test() as _:
        assert app.query_one(OverviewTable) is not None
        assert app.query_one(DetailPanel) is not None
        assert app.query_one(HistoryTable) is not None


@pytest.mark.asyncio
async def test_app_launches_without_ghostty():
    """Non-Ghostty environment should work fine — no ghostty module loaded."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm2"}, clear=False):
        app = QuotaDashApp()
        async with app.run_test() as _:
            assert app.title == "quota-dash"
            assert app._alert_monitor is None


@pytest.mark.asyncio
async def test_app_launches_with_ghostty():
    """Ghostty environment should activate color enhancement and alert monitor."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}, clear=False):
        app = QuotaDashApp()
        async with app.run_test() as _:
            assert app.title == "quota-dash"
            assert app._alert_monitor is not None


@pytest.mark.asyncio
async def test_app_with_manual_config():
    config = AppConfig(
        polling_interval=60,
        theme="default",
        providers={
            "openai": ProviderConfig(
                enabled=True, api_key_env="NONEXISTENT",
                log_path=Path("/tmp/nonexistent"),
                balance_usd=50.0, limit_usd=100.0,
            ),
        },
    )
    app = QuotaDashApp(config=config)
    async with app.run_test() as pilot:
        assert app.title == "quota-dash"
        await pilot.press("r")
        await pilot.pause()


@pytest.mark.asyncio
async def test_app_watcher_not_started_without_db(tmp_path):
    """No proxy DB = no watcher."""
    from quota_dash.config import ProxyConfig
    db_path = tmp_path / "nonexistent_usage.db"  # guaranteed not to exist
    proxy_cfg = ProxyConfig(db_path=db_path)
    config = AppConfig(polling_interval=9999, theme="default", proxy=proxy_cfg)
    app = QuotaDashApp(config=config)
    async with app.run_test() as _:
        assert app._watcher is None


@pytest.mark.asyncio
async def test_app_with_providers_refreshes():
    """App with configured providers should refresh data on mount."""
    config = AppConfig(
        polling_interval=9999,
        theme="default",
        providers={
            "openai": ProviderConfig(
                enabled=True, api_key_env="NONEXISTENT",
                log_path=Path("/tmp/nonexistent"),
                balance_usd=50.0, limit_usd=100.0,
            ),
            "anthropic": ProviderConfig(
                enabled=True, api_key_env="NONEXISTENT",
                log_path=Path("/tmp/nonexistent"),
                balance_usd=200.0, limit_usd=500.0,
            ),
        },
    )
    app = QuotaDashApp(config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Both providers should appear in overview
        table = app.query_one(OverviewTable)
        assert table is not None


@pytest.mark.asyncio
async def test_app_row_highlighted_updates_detail():
    """Highlighting a provider row should update the selected provider."""
    config = AppConfig(
        polling_interval=9999,
        theme="default",
        providers={
            "openai": ProviderConfig(
                enabled=True, api_key_env="NONEXISTENT",
                log_path=Path("/tmp/nonexistent"),
                balance_usd=50.0, limit_usd=100.0,
            ),
        },
    )
    app = QuotaDashApp(config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Press down arrow to navigate — triggers row highlighted
        await pilot.press("down")
        await pilot.pause()
        # The selected provider should be set (either openai or __total__)
        assert app._selected_provider is not None


@pytest.mark.asyncio
async def test_app_toggle_help():
    """? binding should trigger help notification."""
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()


@pytest.mark.asyncio
async def test_app_auto_start_proxy_skipped_when_db_exists(tmp_path):
    """auto_start should be attempted but handled gracefully when db doesn't exist."""
    from quota_dash.config import ProxyConfig
    db_path = tmp_path / "nonexistent.db"
    proxy_cfg = ProxyConfig(auto_start=True, db_path=db_path)
    config = AppConfig(polling_interval=9999, theme="default", proxy=proxy_cfg)
    app = QuotaDashApp(config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        # App should still launch without errors even if auto_start subprocess fails
        assert app.title == "quota-dash"


@pytest.mark.asyncio
async def test_app_watcher_started_when_db_exists(tmp_path):
    """A proxy DB file on disk should trigger watcher initialisation."""
    from quota_dash.config import ProxyConfig
    import sqlite3
    db_path = tmp_path / "usage.db"
    # Create a minimal DB so the path exists
    conn = sqlite3.connect(str(db_path))
    conn.close()
    proxy_cfg = ProxyConfig(db_path=db_path)
    config = AppConfig(polling_interval=9999, theme="default", proxy=proxy_cfg)
    app = QuotaDashApp(config=config)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._watcher is not None


@pytest.mark.asyncio
async def test_app_time_range_default():
    app = QuotaDashApp()
    async with app.run_test() as _:
        assert app._time_range == "24h"


@pytest.mark.asyncio
async def test_app_time_range_switch():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        await pilot.press("1")
        assert app._time_range == "1h"
        await pilot.press("3")
        assert app._time_range == "7d"
        await pilot.press("2")
        assert app._time_range == "24h"


@pytest.mark.asyncio
async def test_app_theme_toggle():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        initial_theme = app.theme
        await pilot.press("t")
        assert app.theme != initial_theme
