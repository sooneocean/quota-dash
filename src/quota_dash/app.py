from __future__ import annotations

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from quota_dash.config import AppConfig
from quota_dash.data.store import DataStore
from quota_dash.providers.anthropic import AnthropicProvider
from quota_dash.providers.base import Provider
from quota_dash.providers.openai import OpenAIProvider
from quota_dash.widgets.context_gauge import ContextGauge
from quota_dash.widgets.provider_list import ProviderList
from quota_dash.widgets.quota_panel import QuotaPanel
from quota_dash.widgets.token_panel import TokenPanel


class QuotaDashApp(App):
    TITLE = "quota-dash"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("up", "prev_provider", "Previous", show=False),
        Binding("down", "next_provider", "Next", show=False),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("question_mark", "toggle_help", "Help"),
    ]

    def __init__(
        self,
        config: AppConfig | None = None,
        theme_override: str | None = None,
    ) -> None:
        self._config = config or AppConfig()
        self._theme_override = theme_override
        self._store = DataStore()
        self._providers: dict[str, Provider] = {}

        css_path = self._resolve_theme()
        css_path_arg = [str(css_path)] if css_path else None

        super().__init__(css_path=css_path_arg)

    def _resolve_theme(self) -> Path | None:
        theme = self._theme_override or self._config.theme
        themes_dir = Path(__file__).parent / "themes"

        if theme == "auto":
            term = os.environ.get("TERM_PROGRAM", "")
            theme = "ghostty" if term == "ghostty" else "default"

        theme_file = themes_dir / f"{theme}.tcss"
        return theme_file if theme_file.exists() else None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ProviderList()
            with Vertical(id="main-panel"):
                yield QuotaPanel()
                yield TokenPanel()
                yield ContextGauge()
        yield Footer()

    async def on_mount(self) -> None:
        self._init_providers()
        provider_names = list(self._providers.keys())
        self.query_one(ProviderList).set_providers(provider_names)
        await self._refresh_all()
        self.set_interval(self._config.polling_interval, self._poll)

    def _init_providers(self) -> None:
        provider_map = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}
        for name, pconfig in self._config.providers.items():
            if pconfig.enabled and name in provider_map:
                self._providers[name] = provider_map[name](pconfig)

    def _poll(self) -> None:
        """Sync wrapper for set_interval — schedules async refresh."""
        self.run_worker(self._refresh_all())

    async def _refresh_all(self) -> None:
        plist = self.query_one(ProviderList)
        selected = plist.selected_provider
        if not selected and self._providers:
            selected = list(self._providers.keys())[0]

        if selected and selected in self._providers:
            provider = self._providers[selected]
            quota = await provider.get_quota()
            tokens = await provider.get_token_usage()
            context = await provider.get_context_window()

            self._store.update_quota(selected, quota)
            self._store.update_tokens(selected, tokens)
            self._store.update_context(selected, context)

            self.query_one(QuotaPanel).update_data(quota)
            self.query_one(TokenPanel).update_data(tokens)
            self.query_one(ContextGauge).update_data(context)

        # Update sidebar quick stats from all providers
        plist = self.query_one(ProviderList)
        plist.set_quick_stats(
            self._store.total_balance(),
            self._store.total_usage_today(),
        )

    async def action_refresh(self) -> None:
        await self._refresh_all()

    def action_next_provider(self) -> None:
        self.query_one(ProviderList).select_next()
        self.run_worker(self._refresh_all())

    def action_prev_provider(self) -> None:
        self.query_one(ProviderList).select_prev()
        self.run_worker(self._refresh_all())

    def action_toggle_help(self) -> None:
        self.notify(
            "[b]Keybindings[/b]\n"
            "↑↓  Switch provider\n"
            "r   Refresh\n"
            "Tab Focus next panel\n"
            "q   Quit\n"
            "?   This help",
            title="Help",
            timeout=8,
        )
