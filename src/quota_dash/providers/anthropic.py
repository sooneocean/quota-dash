from __future__ import annotations

from datetime import datetime

from quota_dash.config import ProviderConfig
from quota_dash.data.log_parser import parse_claude_costs_jsonl
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo
from quota_dash.providers.base import Provider


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    async def get_quota(self) -> QuotaInfo:
        now = datetime.now()

        if self._config.balance_usd is not None:
            return QuotaInfo(
                provider="anthropic",
                balance_usd=self._config.balance_usd,
                limit_usd=self._config.limit_usd,
                usage_today_usd=None,
                last_updated=now,
                source="manual",
                stale=False,
            )

        return QuotaInfo(
            provider="anthropic",
            balance_usd=None, limit_usd=None, usage_today_usd=None,
            last_updated=now, source="unavailable", stale=False,
        )

    async def get_token_usage(self) -> TokenUsage:
        costs_path = self._config.log_path / "metrics" / "costs.jsonl"
        return parse_claude_costs_jsonl(costs_path)

    async def get_context_window(self) -> ContextInfo:
        return ContextInfo(
            used_tokens=0, max_tokens=200000,
            percent_used=0.0, model="claude-opus-4-6",
            note="approximation — CLI logs lack per-turn data",
        )
