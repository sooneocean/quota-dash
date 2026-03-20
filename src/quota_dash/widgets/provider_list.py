from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget


class ProviderList(Widget):
    providers: reactive[list[str]] = reactive(list, layout=True)
    selected: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    ProviderList {
        width: 24;
        height: 100%;
        border-right: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._total_balance: float = 0.0
        self._usage_today: float = 0.0

    def set_providers(self, names: list[str]) -> None:
        self.providers = names

    def select_next(self) -> None:
        if self.providers:
            self.selected = (self.selected + 1) % len(self.providers)

    def select_prev(self) -> None:
        if self.providers:
            self.selected = (self.selected - 1) % len(self.providers)

    @property
    def selected_provider(self) -> str | None:
        if self.providers and 0 <= self.selected < len(self.providers):
            return self.providers[self.selected]
        return None

    def set_quick_stats(self, total_balance: float, usage_today: float) -> None:
        self._total_balance = total_balance
        self._usage_today = usage_today
        self.refresh()

    def render(self) -> str:
        lines = ["PROVIDERS", ""]
        for i, name in enumerate(self.providers):
            marker = "▸" if i == self.selected else " "
            lines.append(f"  {marker} {name}")
        lines.append("")
        lines.append("QUICK STATS")
        total = self._total_balance
        today = self._usage_today
        lines.append(f"  Total: ${total:.2f}")
        lines.append(f"  Today: -${today:.2f}")
        return "\n".join(lines)
