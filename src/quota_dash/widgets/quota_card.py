from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from quota_dash.models import QuotaInfo


class QuotaCard(Widget):
    DEFAULT_CSS = """
    QuotaCard {
        height: auto;
        min-height: 5;
        padding: 1;
        border: solid $primary-muted;
    }
    QuotaCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Quota", classes="title")
        yield Label("loading...", id="quota-label")
        yield ProgressBar(total=100, show_eta=False, id="quota-bar")

    def update_data(self, data: QuotaInfo) -> None:
        label = self.query_one("#quota-label", Label)
        bar = self.query_one("#quota-bar", ProgressBar)

        if data.source == "unavailable":
            label.update(f"({data.provider}) not configured")
            bar.update(total=100, progress=0)
            return

        bal = f"${data.balance_usd:.2f}" if data.balance_usd is not None else "N/A"
        lim = f"${data.limit_usd:.2f}" if data.limit_usd is not None else "N/A"
        source_tag = f" [{data.source}]"
        stale_tag = " \u26a0 stale" if data.stale else ""
        label.update(f"{bal} / {lim}{source_tag}{stale_tag}")

        if data.limit_usd and data.balance_usd is not None:
            bar.update(total=data.limit_usd, progress=data.balance_usd)
        else:
            bar.update(total=100, progress=0)
