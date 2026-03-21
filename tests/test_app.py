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
    async with app.run_test() as pilot:
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
    async with app.run_test() as pilot:
        assert app.query_one(OverviewTable) is not None
        assert app.query_one(DetailPanel) is not None
        assert app.query_one(HistoryTable) is not None


@pytest.mark.asyncio
async def test_app_launches_without_ghostty():
    """Non-Ghostty environment should work fine — no ghostty module loaded."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm2"}, clear=False):
        app = QuotaDashApp()
        async with app.run_test() as pilot:
            assert app.title == "quota-dash"
            assert app._alert_monitor is None


@pytest.mark.asyncio
async def test_app_launches_with_ghostty():
    """Ghostty environment should activate color enhancement and alert monitor."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}, clear=False):
        app = QuotaDashApp()
        async with app.run_test() as pilot:
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
