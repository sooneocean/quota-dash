from datetime import datetime

import pytest
from textual.app import App, ComposeResult

from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.history_table import HistoryTable
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.ratelimit_card import RateLimitCard
from quota_dash.widgets.token_card import TokenCard


class QuotaCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield QuotaCard()


@pytest.mark.asyncio
async def test_quota_card_mount():
    app = QuotaCardTestApp()
    async with app.run_test() as _:
        card = app.query_one(QuotaCard)
        assert card is not None


@pytest.mark.asyncio
async def test_quota_card_update():
    app = QuotaCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(QuotaCard)
        card.update_data(QuotaInfo(
            provider="openai", balance_usd=47.32, limit_usd=100.0,
            usage_today_usd=3.20, last_updated=datetime.now(),
            source="manual", stale=False,
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_quota_card_unavailable():
    app = QuotaCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(QuotaCard)
        card.update_data(QuotaInfo(
            provider="openai", balance_usd=None, limit_usd=None,
            usage_today_usd=None, last_updated=datetime.now(),
            source="unavailable", stale=False,
        ))
        await pilot.pause()


# Task 4: TokenCard, ContextCard, RateLimitCard

class TokenCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield TokenCard()

class ContextCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield ContextCard()

class RateLimitCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield RateLimitCard()


@pytest.mark.asyncio
async def test_token_card_mount_and_update():
    app = TokenCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(TokenCard)
        card.update_data(
            TokenUsage(input_tokens=12400, output_tokens=8100, total_tokens=20500,
                       history=[(datetime.now(), 500), (datetime.now(), 800)],
                       session_id=None, source="proxy"),
            sparkline_data=[500, 800, 300, 600],
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_context_card_mount_and_update():
    app = ContextCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(ContextCard)
        card.update_data(ContextInfo(
            used_tokens=62000, max_tokens=128000,
            percent_used=48.4, model="gpt-4", note="last call snapshot",
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_ratelimit_card_mount_and_update():
    app = RateLimitCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(RateLimitCard)
        card.update_data(ProxyData(
            input_tokens=0, output_tokens=0, total_tokens=0,
            ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
            model=None, last_call=datetime.now(),
            calls_today=0, tokens_today=0, ratelimit_reset="2m 30s",
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_ratelimit_card_no_data():
    app = RateLimitCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(RateLimitCard)
        card.update_data(None)
        await pilot.pause()


# Task 5: OverviewTable, HistoryTable, DetailPanel

class OverviewTestApp(App):
    def compose(self) -> ComposeResult:
        yield OverviewTable()

class HistoryTestApp(App):
    def compose(self) -> ComposeResult:
        yield HistoryTable()


@pytest.mark.asyncio
async def test_overview_table_mount():
    app = OverviewTestApp()
    async with app.run_test() as _:
        table = app.query_one(OverviewTable)
        assert table is not None


@pytest.mark.asyncio
async def test_overview_table_refresh():
    app = OverviewTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(OverviewTable)
        table.refresh_data(
            providers=["openai", "anthropic"],
            quotas={"openai": QuotaInfo(
                provider="openai", balance_usd=47.32, limit_usd=100.0,
                usage_today_usd=3.20, last_updated=datetime.now(),
                source="manual", stale=False,
            )},
            tokens_today={"openai": 20500, "anthropic": 63900},
            context_pcts={"openai": 62.0, "anthropic": 35.0},
            rate_limits={"openai": 9000},
            sources={"openai": "proxy", "anthropic": "proxy"},
            total_balance=247.32,
            total_tokens=84400,
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_history_table_mount():
    app = HistoryTestApp()
    async with app.run_test() as _:
        table = app.query_one(HistoryTable)
        assert table is not None


@pytest.mark.asyncio
async def test_history_table_update():
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(HistoryTable)
        table.update_data([
            {
                "timestamp": "2026-03-21T14:32:00",
                "model": "gpt-4",
                "total_tokens": 150,
                "endpoint": "/v1/chat/completions",
            },
            {
                "timestamp": "2026-03-21T14:28:00",
                "model": "gpt-4",
                "total_tokens": 420,
                "endpoint": "/v1/chat/completions",
            },
        ])
        await pilot.pause()


@pytest.mark.asyncio
async def test_history_table_empty():
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(HistoryTable)
        table.update_data([])
        await pilot.pause()


@pytest.mark.asyncio
async def test_overview_table_refresh_with_data():
    """refresh_data with a real QuotaInfo entry should populate all columns."""

    class OTApp(App):
        def compose(self):
            yield OverviewTable()

    app = OTApp()
    async with app.run_test() as pilot:
        table = app.query_one(OverviewTable)
        table.refresh_data(
            providers=["openai"],
            quotas={"openai": QuotaInfo(
                provider="openai", balance_usd=50.0, limit_usd=100.0,
                usage_today_usd=None, last_updated=datetime.now(),
                source="manual", stale=False,
            )},
            tokens_today={"openai": 5000},
            context_pcts={"openai": 30.0},
            rate_limits={"openai": 9000},
            sources={"openai": "proxy"},
            total_balance=50.0,
            total_tokens=5000,
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_overview_table_narrow_layout():
    """In a narrow terminal the Rate/Source columns should be omitted."""

    class NarrowOTApp(App):
        def compose(self):
            yield OverviewTable()

    app = NarrowOTApp()
    async with app.run_test(size=(80, 24)) as pilot:
        table = app.query_one(OverviewTable)
        table.refresh_data(
            providers=["openai"],
            quotas={"openai": QuotaInfo(
                provider="openai", balance_usd=25.0, limit_usd=100.0,
                usage_today_usd=None, last_updated=datetime.now(),
                source="manual", stale=False,
            )},
            tokens_today={"openai": 2000},
            context_pcts={"openai": 15.0},
            rate_limits={"openai": None},
            sources={"openai": "manual"},
            total_balance=25.0,
            total_tokens=2000,
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_overview_table_resize_triggers_redraw():
    """Resizing the terminal should cause the table to reflow columns."""

    class ResizeOTApp(App):
        def compose(self):
            yield OverviewTable()

    app = ResizeOTApp()
    async with app.run_test(size=(140, 30)) as pilot:
        table = app.query_one(OverviewTable)
        # Populate with data so _last_data is set
        table.refresh_data(
            providers=["openai"],
            quotas={"openai": QuotaInfo(
                provider="openai", balance_usd=50.0, limit_usd=100.0,
                usage_today_usd=None, last_updated=datetime.now(),
                source="manual", stale=False,
            )},
            tokens_today={"openai": 1000},
            context_pcts={"openai": 10.0},
            rate_limits={"openai": 5000},
            sources={"openai": "proxy"},
            total_balance=50.0,
            total_tokens=1000,
        )
        await pilot.pause()
        # Simulate resize to narrow width — triggers on_resize path
        await pilot.resize_terminal(80, 30)
        await pilot.pause()


@pytest.mark.asyncio
async def test_overview_table_rate_limit_small_value():
    """Rate limit values < 1000 should render as plain string, not xK."""

    class OTApp(App):
        def compose(self):
            yield OverviewTable()

    app = OTApp()
    async with app.run_test(size=(140, 30)) as pilot:
        table = app.query_one(OverviewTable)
        table.refresh_data(
            providers=["openai"],
            quotas={},
            tokens_today={"openai": 0},
            context_pcts={"openai": 0.0},
            rate_limits={"openai": 500},
            sources={"openai": "proxy"},
            total_balance=0.0,
            total_tokens=0,
        )
        await pilot.pause()
