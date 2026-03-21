from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label


class HistoryTable(Widget):
    DEFAULT_CSS = """
    HistoryTable {
        height: auto;
        max-height: 10;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("History (today)", classes="title")
        yield DataTable(id="history-dt")

    def on_mount(self) -> None:
        dt = self.query_one("#history-dt", DataTable)
        dt.add_column("Time", key="time")
        dt.add_column("Model", key="model")
        dt.add_column("Tokens", key="tokens")
        dt.add_column("Endpoint", key="endpoint")

    def update_data(self, calls: list[dict], period: str = "24h") -> None:
        title = self.query_one(".title", Label)
        title.update(f"History ({period})")
        dt = self.query_one("#history-dt", DataTable)
        dt.clear()

        if not calls:
            dt.add_row("—", "Start proxy to see API call history", "", "")
            return

        for call in calls:
            ts = call.get("timestamp", "")
            if "T" in ts:
                ts = ts.split("T")[1][:5]  # HH:MM
            dt.add_row(
                ts,
                call.get("model", "—"),
                str(call.get("total_tokens", 0)),
                call.get("endpoint", "—"),
            )
