from __future__ import annotations

from textual.widget import Widget

from quota_dash.models import TokenUsage

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[int], width: int = 10) -> str:
    if not values:
        return "no history"
    mx = max(values) or 1
    return "".join(SPARK_CHARS[min(int(v / mx * 7), 7)] for v in values[-width:])


class TokenPanel(Widget):
    DEFAULT_CSS = """
    TokenPanel {
        height: auto;
        min-height: 5;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._data: TokenUsage | None = None

    def update_data(self, data: TokenUsage) -> None:
        self._data = data
        self.refresh()

    def render(self) -> str:
        if self._data is None:
            return "Tokens: loading..."

        d = self._data
        hist_vals = [total for _, total in d.history]
        spark = sparkline(hist_vals)

        def fmt(n: int) -> str:
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n / 1_000:.1f}K"
            return str(n)

        has_split = d.input_tokens > 0 or d.output_tokens > 0
        lines = ["Tokens (session)"]
        if has_split:
            lines.append(f"  In:  {fmt(d.input_tokens):>8}  {spark}")
            lines.append(f"  Out: {fmt(d.output_tokens):>8}")
        else:
            lines.append(f"  Total: {fmt(d.total_tokens):>8}  {spark}")
        lines.append(f"  Total: {fmt(d.total_tokens)}  [{d.source}]")
        return "\n".join(lines)
