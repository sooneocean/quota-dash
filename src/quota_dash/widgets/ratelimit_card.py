from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from quota_dash.models import ProxyData


class RateLimitCard(Widget):
    DEFAULT_CSS = """
    RateLimitCard {
        height: auto;
        min-height: 5;
        padding: 1;
        border: solid $primary-muted;
    }
    RateLimitCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Rate Limits", classes="title")
        yield Label("no data", id="rl-content")

    def update_data(self, data: ProxyData | None) -> None:
        label = self.query_one("#rl-content", Label)
        if data is None or (data.ratelimit_remaining_tokens is None and data.ratelimit_remaining_requests is None):
            label.update("no data")
            return

        lines = []
        if data.ratelimit_remaining_tokens is not None:
            lines.append(f"Tokens: {data.ratelimit_remaining_tokens:,} remaining")
        if data.ratelimit_remaining_requests is not None:
            lines.append(f"Requests: {data.ratelimit_remaining_requests} remaining")
        if data.ratelimit_reset:
            lines.append(f"Reset: {data.ratelimit_reset}")
        label.update("\n".join(lines) if lines else "no data")
