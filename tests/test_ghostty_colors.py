from quota_dash.ghostty.colors import threshold_color


# Context A: balance-oriented (high = good)
def test_balance_high():
    assert threshold_color(0.8, "balance") == "#22c55e"  # green

def test_balance_medium():
    assert threshold_color(0.35, "balance") == "#eab308"  # yellow

def test_balance_low():
    assert threshold_color(0.1, "balance") == "#ef4444"  # red

def test_balance_boundary_50():
    assert threshold_color(0.5, "balance") == "#eab308"  # 0.5 is NOT > 0.5, so yellow

def test_balance_boundary_20():
    assert threshold_color(0.2, "balance") == "#ef4444"  # 0.2 is NOT > 0.2, so red


# Context B: usage-oriented (high = bad)
def test_usage_low():
    assert threshold_color(0.3, "usage") == "#22c55e"  # green

def test_usage_medium():
    assert threshold_color(0.65, "usage") == "#eab308"  # yellow

def test_usage_high():
    assert threshold_color(0.9, "usage") == "#ef4444"  # red

def test_usage_boundary_50():
    assert threshold_color(0.5, "usage") == "#eab308"  # 0.5 is NOT < 0.5, so yellow

def test_usage_boundary_80():
    assert threshold_color(0.8, "usage") == "#ef4444"  # 0.8 is NOT < 0.8, so red


import pytest
from unittest.mock import patch
from textual.app import App, ComposeResult
from textual.widgets import ProgressBar

from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.ghostty.colors import enhance_widgets
from quota_dash.models import QuotaInfo, ContextInfo
from datetime import datetime


class GhosttyColorTestApp(App):
    def compose(self) -> ComposeResult:
        yield QuotaCard()
        yield ContextCard()


@pytest.mark.asyncio
async def test_enhance_widgets_runs_without_error():
    app = GhosttyColorTestApp()
    async with app.run_test() as pilot:
        enhance_widgets(app)
        # Update quota with data to trigger progress change
        card = app.query_one(QuotaCard)
        card.update_data(QuotaInfo(
            provider="openai", balance_usd=80.0, limit_usd=100.0,
            usage_today_usd=None, last_updated=datetime.now(),
            source="manual", stale=False,
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_enhance_widgets_no_crash_on_empty_app():
    """enhance_widgets should not crash if widgets are missing."""
    app = App()
    async with app.run_test() as pilot:
        enhance_widgets(app)  # should not raise
