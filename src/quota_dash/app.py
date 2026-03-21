from __future__ import annotations

import asyncio
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header
from textual.widgets import DataTable

from quota_dash.config import AppConfig
from quota_dash.data.store import DataStore
from quota_dash.providers.anthropic import AnthropicProvider
from quota_dash.providers.base import Provider
from quota_dash.providers.google import GoogleProvider
from quota_dash.providers.groq import GroqProvider
from quota_dash.providers.mistral import MistralProvider
from quota_dash.providers.openai import OpenAIProvider
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.detail_panel import DetailPanel
from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.token_card import TokenCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.ratelimit_card import RateLimitCard
from quota_dash.widgets.history_table import HistoryTable


class QuotaDashApp(App):
    TITLE = "quota-dash"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
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
        self._selected_provider: str | None = None
        self._alert_monitor: object = None
        self._watcher: object = None

        css_path = self._resolve_theme()
        css_path_arg: list[str] | None = [str(css_path)] if css_path else None
        super().__init__(css_path=css_path_arg)  # type: ignore[arg-type]

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
        yield OverviewTable()
        yield DetailPanel()
        yield HistoryTable()
        yield Footer()

    async def on_mount(self) -> None:
        self._init_providers()
        await self._refresh_all()
        self.set_interval(self._config.polling_interval, self._poll)

        # Ghostty enhancements (lazy import, only if detected)
        from quota_dash.ghostty.detect import is_ghostty
        if is_ghostty():
            try:
                from quota_dash.ghostty.colors import enhance_widgets
                from quota_dash.ghostty.alerts import AlertMonitor
                enhance_widgets(self)
                self._alert_monitor = AlertMonitor(  # type: ignore[assignment]
                    warning=self._config.alerts.warning,
                    alert=self._config.alerts.alert,
                    critical=self._config.alerts.critical,
                    webhook_url=self._config.alerts.webhook_url,
                )
            except Exception:
                pass  # silently skip if ghostty module fails

        # Auto-start proxy if configured
        if self._config.proxy.auto_start and not self._config.proxy.db_path.exists():
            try:
                import subprocess
                subprocess.Popen(
                    ["quota-dash", "proxy", "start", "--port", str(self._config.proxy.port)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                import time
                time.sleep(1)
            except Exception:
                pass

        # Start file watcher if proxy DB exists
        if self._config.proxy.db_path.exists():
            try:
                from quota_dash.data.watcher import DBWatcher
                self._watcher = DBWatcher(  # type: ignore[assignment]
                    db_path=self._config.proxy.db_path,
                    callback=lambda: self.run_worker(self._refresh_all()),  # type: ignore[arg-type]
                )
                self.run_worker(self._watcher.start())  # type: ignore[union-attr]
            except Exception:
                pass

    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()  # type: ignore[attr-defined]

    def _init_providers(self) -> None:
        provider_map = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "google": GoogleProvider,
            "groq": GroqProvider,
            "mistral": MistralProvider,
        }
        db_path = self._config.proxy.db_path
        for name, pconfig in self._config.providers.items():
            if pconfig.enabled and name in provider_map:
                self._providers[name] = provider_map[name](pconfig, db_path=db_path)

    def _poll(self) -> None:
        self.run_worker(self._refresh_all())

    async def _fetch_provider(self, name: str, provider: Provider) -> tuple:
        """Fetch all data for a single provider."""
        quota = await provider.get_quota()
        tokens = await provider.get_token_usage()
        context = await provider.get_context_window()
        proxy_data = await provider.get_proxy_data()
        return name, quota, tokens, context, proxy_data

    async def _refresh_all(self) -> None:
        # Refresh ALL providers in parallel
        provider_names = list(self._providers.keys())
        tokens_today: dict[str, int] = {}
        context_pcts: dict[str, float] = {}
        rate_limits: dict[str, int | None] = {}
        sources: dict[str, str] = {}

        # Fetch all providers concurrently
        results = await asyncio.gather(
            *(self._fetch_provider(name, prov) for name, prov in self._providers.items()),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, BaseException):
                continue  # skip failed providers
            name, quota, tokens, context, proxy_data = result

            self._store.update_quota(name, quota)
            self._store.update_tokens(name, tokens)
            self._store.update_context(name, context)

            # Get proxy data if available
            if proxy_data:
                self._store.update_proxy(name, proxy_data)
                tokens_today[name] = proxy_data.tokens_today
                rate_limits[name] = proxy_data.ratelimit_remaining_tokens
                sources[name] = "proxy"
            else:
                tokens_today[name] = tokens.total_tokens
                rate_limits[name] = None
                sources[name] = tokens.source

            context_pcts[name] = context.percent_used

        # Update OverviewTable
        quotas = {n: self._store.get_quota(n) for n in provider_names if self._store.get_quota(n)}
        self.query_one(OverviewTable).refresh_data(
            providers=provider_names,
            quotas=quotas,  # type: ignore[arg-type]
            tokens_today=tokens_today,
            context_pcts=context_pcts,
            rate_limits=rate_limits,
            sources=sources,
            total_balance=self._store.total_balance(),
            total_tokens=self._store.total_tokens_today(),
        )

        # Update DetailPanel for selected provider
        if not self._selected_provider and provider_names:
            self._selected_provider = provider_names[0]

        if self._selected_provider:
            await self._update_detail(self._selected_provider)

        # Alert monitoring (Ghostty only)
        if self._alert_monitor:
            self._alert_monitor.check(self, self._store)  # type: ignore[attr-defined]

    async def _update_detail(self, provider_name: str) -> None:
        quota = self._store.get_quota(provider_name)
        tokens = self._store.get_tokens(provider_name)
        context = self._store.get_context(provider_name)
        proxy = self._store.get_proxy(provider_name)

        panel = self.query_one(DetailPanel)
        if quota:
            panel.query_one(QuotaCard).update_data(quota)
        if tokens:
            # Try to get sparkline data from proxy DB
            sparkline_data = None
            db_path = self._config.proxy.db_path
            if db_path and db_path.exists():
                from quota_dash.proxy.db import query_token_history
                history = await query_token_history(db_path, provider_name)
                if history:
                    sparkline_data = [float(tok) for _, tok in history]
            panel.query_one(TokenCard).update_data(tokens, sparkline_data=sparkline_data)
        if context:
            panel.query_one(ContextCard).update_data(context)

        panel.query_one(RateLimitCard).update_data(proxy)

        # Update HistoryTable
        history_table = self.query_one(HistoryTable)
        db_path = self._config.proxy.db_path
        if db_path and db_path.exists():
            from quota_dash.proxy.db import query_recent_calls
            calls = await query_recent_calls(db_path, provider_name)
            history_table.update_data(calls)
        else:
            history_table.update_data([])

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value != "__total__":
            self._selected_provider = str(event.row_key.value)
            self.run_worker(self._update_detail(self._selected_provider))

    async def action_refresh(self) -> None:
        await self._refresh_all()

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
