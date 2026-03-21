from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from quota_dash.models import QuotaInfo


class OverviewTable(Widget):
    DEFAULT_CSS = """
    OverviewTable {
        height: auto;
        max-height: 12;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._last_data: dict | None = None
        self._is_wide: bool = True

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row", id="overview-dt")

    def on_mount(self) -> None:
        dt = self.query_one("#overview-dt", DataTable)
        self._is_wide = self.app.size.width >= 120
        self._setup_columns(dt, wide=self._is_wide)

    def on_resize(self) -> None:
        new_wide = self.app.size.width >= 120
        if new_wide != self._is_wide:
            self._is_wide = new_wide
            dt = self.query_one("#overview-dt", DataTable)
            self._setup_columns(dt, wide=new_wide)
            if self._last_data:
                self.refresh_data(**self._last_data)

    def _setup_columns(self, dt: DataTable, wide: bool) -> None:
        dt.clear(columns=True)
        dt.add_column("Provider", key="provider")
        dt.add_column("Balance", key="balance")
        dt.add_column("Tokens", key="tokens")
        dt.add_column("Ctx", key="ctx")
        if wide:
            dt.add_column("Rate", key="rate")
            dt.add_column("Source", key="source")

    def refresh_data(
        self,
        providers: list[str],
        quotas: dict[str, QuotaInfo],
        tokens_today: dict[str, int],
        context_pcts: dict[str, float],
        rate_limits: dict[str, int | None],
        sources: dict[str, str],
        total_balance: float,
        total_tokens: int,
    ) -> None:
        self._last_data = {
            "providers": providers,
            "quotas": quotas,
            "tokens_today": tokens_today,
            "context_pcts": context_pcts,
            "rate_limits": rate_limits,
            "sources": sources,
            "total_balance": total_balance,
            "total_tokens": total_tokens,
        }
        dt = self.query_one("#overview-dt", DataTable)
        dt.clear()

        def fmt_usd(v: float | None) -> str:
            return f"${v:.2f}" if v is not None else "N/A"

        def fmt_tok(v: int) -> str:
            return f"{v / 1000:.1f}K" if v >= 1000 else str(v)

        wide = self.app.size.width >= 120 if self.app else True

        for name in providers:
            q = quotas.get(name)
            bal = fmt_usd(q.balance_usd) if q else "N/A"
            tok = fmt_tok(tokens_today.get(name, 0))
            ctx = f"{context_pcts.get(name, 0):.0f}%"
            row = [name, bal, tok, ctx]
            if wide:
                rl = rate_limits.get(name)
                row.append(f"{rl // 1000}K" if rl and rl >= 1000 else str(rl or "—"))
                row.append(sources.get(name, "—"))
            dt.add_row(*row, key=name)

        # Total row
        total_row = ["Total", fmt_usd(total_balance), fmt_tok(total_tokens), ""]
        if wide:
            total_row.extend(["", ""])
        dt.add_row(*total_row, key="__total__")
