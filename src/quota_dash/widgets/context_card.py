from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from quota_dash.models import ContextInfo


class ContextCard(Widget):
    DEFAULT_CSS = """
    ContextCard {
        height: auto;
        min-height: 5;
        padding: 1;
        border: solid $primary-muted;
    }
    ContextCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Context Window", classes="title")
        yield ProgressBar(total=100, show_eta=False, id="ctx-bar")
        yield Label("loading...", id="ctx-label")
        yield Label("", id="ctx-note")

    def update_data(self, data: ContextInfo) -> None:
        bar = self.query_one("#ctx-bar", ProgressBar)
        label = self.query_one("#ctx-label", Label)
        note = self.query_one("#ctx-note", Label)

        bar.update(total=data.max_tokens or 1, progress=data.used_tokens)

        def fmt(n: int) -> str:
            return f"{n // 1000}K" if n >= 1000 else str(n)

        label.update(f"{data.percent_used:.0f}% ({fmt(data.used_tokens)} / {fmt(data.max_tokens)}) — {data.model}")
        note.update(data.note if data.note else "")
