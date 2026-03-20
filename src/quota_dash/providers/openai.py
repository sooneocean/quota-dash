from __future__ import annotations

import os
from datetime import datetime

from quota_dash.config import ProviderConfig
from quota_dash.data.api_client import fetch_openai_usage
from quota_dash.data.log_parser import parse_codex_logs
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo
from quota_dash.providers.base import Provider


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    async def get_quota(self) -> QuotaInfo:
        now = datetime.now()

        api_key = os.environ.get(self._config.api_key_env, "")
        if api_key:
            result = await fetch_openai_usage(api_key)
            if result is not None:
                return QuotaInfo(
                    provider="openai",
                    balance_usd=self._config.balance_usd,
                    limit_usd=self._config.limit_usd,
                    usage_today_usd=result["usage_usd"],
                    last_updated=now,
                    source="api",
                    stale=False,
                )

        if self._config.balance_usd is not None:
            return QuotaInfo(
                provider="openai",
                balance_usd=self._config.balance_usd,
                limit_usd=self._config.limit_usd,
                usage_today_usd=None,
                last_updated=now,
                source="manual",
                stale=False,
            )

        return QuotaInfo(
            provider="openai",
            balance_usd=None, limit_usd=None, usage_today_usd=None,
            last_updated=now, source="unavailable", stale=False,
        )

    async def get_token_usage(self) -> TokenUsage:
        log_db = self._config.log_path / "logs_1.sqlite"
        return parse_codex_logs(log_db)

    async def get_context_window(self) -> ContextInfo:
        return ContextInfo(
            used_tokens=0, max_tokens=128000,
            percent_used=0.0, model="gpt-4",
            note="approximation — Codex logs lack per-turn data",
        )
