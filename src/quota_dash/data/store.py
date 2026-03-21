from __future__ import annotations

from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData


class DataStore:
    """Data store with change tracking.

    When used inside a Textual app, the app's _refresh_all method
    pushes data here AND notifies widgets via reactive message posting.
    The store itself is the single source of truth for aggregation.
    """

    def __init__(self) -> None:
        self._quotas: dict[str, QuotaInfo] = {}
        self._tokens: dict[str, TokenUsage] = {}
        self._contexts: dict[str, ContextInfo] = {}
        self._proxy: dict[str, ProxyData] = {}
        self._revision: int = 0  # bumped on every update, used by reactive watchers

    @property
    def revision(self) -> int:
        return self._revision

    def update_quota(self, provider: str, quota: QuotaInfo) -> None:
        self._quotas[provider] = quota
        self._revision += 1

    def update_tokens(self, provider: str, tokens: TokenUsage) -> None:
        self._tokens[provider] = tokens
        self._revision += 1

    def update_context(self, provider: str, context: ContextInfo) -> None:
        self._contexts[provider] = context
        self._revision += 1

    def get_quota(self, provider: str) -> QuotaInfo | None:
        return self._quotas.get(provider)

    def get_tokens(self, provider: str) -> TokenUsage | None:
        return self._tokens.get(provider)

    def get_context(self, provider: str) -> ContextInfo | None:
        return self._contexts.get(provider)

    def providers(self) -> list[str]:
        return sorted(set(self._quotas) | set(self._tokens) | set(self._contexts))

    def update_proxy(self, provider: str, proxy: ProxyData) -> None:
        self._proxy[provider] = proxy
        self._revision += 1

    def get_proxy(self, provider: str) -> ProxyData | None:
        return self._proxy.get(provider)

    def total_tokens_today(self) -> int:
        # Per-provider: prefer proxy data, fall back to token usage
        total = 0
        all_providers = set(self._proxy) | set(self._tokens)
        for name in all_providers:
            if name in self._proxy:
                total += self._proxy[name].tokens_today
            elif name in self._tokens:
                total += self._tokens[name].total_tokens
        return total

    def total_balance(self) -> float:
        return sum(q.balance_usd for q in self._quotas.values() if q.balance_usd is not None)

    def total_usage_today(self) -> float:
        return sum(q.usage_today_usd for q in self._quotas.values() if q.usage_today_usd is not None)
