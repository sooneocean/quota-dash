from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from quota_dash.i18n import t
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
        yield Label(t("rate_limits"), classes="title")
        yield Label(t("no_data"), id="rl-content")

    def update_data(self, data: ProxyData | None) -> None:
        label = self.query_one("#rl-content", Label)
        if data is None or (data.ratelimit_remaining_tokens is None and data.ratelimit_remaining_requests is None):
            label.update(t("no_data"))
            return

        lines = []
        if data.ratelimit_remaining_tokens is not None:
            lines.append(f"Tokens: {data.ratelimit_remaining_tokens:,} remaining")
        if data.ratelimit_remaining_requests is not None:
            lines.append(f"Requests: {data.ratelimit_remaining_requests} remaining")
        if data.ratelimit_reset:
            lines.append(f"Reset: {data.ratelimit_reset}")
        label.update("\n".join(lines) if lines else t("no_data"))

    def update_prediction(self, prediction: dict[str, str | None]) -> None:
        """Update with rate limit prediction data."""
        label = self.query_one("#rl-content", Label)
        current = label.renderable if hasattr(label, 'renderable') else ""

        lines = str(current).split("\n") if str(current) != "no data" else []

        # Remove old prediction lines
        lines = [line for line in lines if not line.startswith("ETA:")]

        # Add prediction
        tok_eta = prediction.get("tokens_eta")
        req_eta = prediction.get("requests_eta")
        if tok_eta:
            lines.append(f"ETA: tokens exhaust in {tok_eta}")
        if req_eta:
            lines.append(f"ETA: requests exhaust in {req_eta}")

        if lines:
            label.update("\n".join(lines))
