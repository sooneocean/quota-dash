from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.widget import Widget

from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.token_card import TokenCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.ratelimit_card import RateLimitCard


class DetailPanel(Widget):
    DEFAULT_CSS = """
    DetailPanel {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Grid(id="detail-grid"):
            yield QuotaCard()
            yield TokenCard()
            yield ContextCard()
            yield RateLimitCard()
