from __future__ import annotations

from textual.widget import Widget

from quota_dash.models import QuotaInfo


class QuotaPanel(Widget):
    DEFAULT_CSS = """
    QuotaPanel {
        height: auto;
        min-height: 5;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._data: QuotaInfo | None = None

    def update_data(self, data: QuotaInfo) -> None:
        self._data = data
        self.refresh()

    def render(self) -> str:
        if self._data is None:
            return "Quota: loading..."

        d = self._data
        if d.source == "unavailable":
            return f"Quota ({d.provider}): not configured"

        bal = f"${d.balance_usd:.2f}" if d.balance_usd is not None else "N/A"
        lim = f"${d.limit_usd:.2f}" if d.limit_usd is not None else "N/A"
        pct = (d.balance_usd / d.limit_usd * 100) if d.balance_usd is not None and d.limit_usd else 0

        bar_width = 20
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        source_tag = f" [{d.source}]"
        stale_tag = " ⚠ stale" if d.stale else ""

        return f"Quota: {bal} / {lim}  {bar} {pct:.0f}%{source_tag}{stale_tag}"
