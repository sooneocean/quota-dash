from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Sparkline

from quota_dash.models import TokenUsage


class TokenCard(Widget):
    DEFAULT_CSS = """
    TokenCard {
        height: auto;
        min-height: 6;
        padding: 1;
        border: solid $primary-muted;
    }
    TokenCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Tokens (session)", classes="title")
        yield Sparkline([], id="token-spark")
        yield Label("loading...", id="token-stats")

    def update_data(self, usage: TokenUsage, sparkline_data: list[float] | None = None) -> None:
        spark = self.query_one("#token-spark", Sparkline)
        label = self.query_one("#token-stats", Label)

        data = sparkline_data or [t for _, t in usage.history] or []
        spark.data = data

        def fmt(n: int) -> str:
            return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

        label.update(
            f"In: {fmt(usage.input_tokens)} | Out: {fmt(usage.output_tokens)} "
            f"| Total: {fmt(usage.total_tokens)} [{usage.source}]"
        )
