from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from quota_dash.config import ProviderConfig
from quota_dash.data.api_client import fetch_openai_usage
from quota_dash.data.log_parser import parse_codex_logs
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData
from quota_dash.providers.base import Provider


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, config: ProviderConfig, db_path: Path | None = None) -> None:
        self._config = config
        self._db_path = db_path

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

    async def get_proxy_data(self) -> ProxyData | None:
        if self._db_path is None or not self._db_path.exists():
            return None
        from quota_dash.proxy.db import query_provider_data
        return await query_provider_data(self._db_path, "openai")

    async def get_token_usage(self) -> TokenUsage:
        proxy = await self.get_proxy_data()
        if proxy is not None:
            return TokenUsage(
                input_tokens=proxy.input_tokens,
                output_tokens=proxy.output_tokens,
                total_tokens=proxy.total_tokens,
                history=[(proxy.last_call, proxy.total_tokens)],
                session_id=None,
                source="proxy",
            )
        log_db = self._config.log_path / "logs_1.sqlite"
        return parse_codex_logs(log_db)

    async def get_context_window(self) -> ContextInfo:
        proxy = await self.get_proxy_data()
        if proxy is not None and proxy.input_tokens > 0:
            return ContextInfo(
                used_tokens=proxy.input_tokens,
                max_tokens=128000,
                percent_used=proxy.input_tokens / 128000 * 100,
                model=proxy.model or "gpt-4",
                note="last call snapshot",
            )
        return ContextInfo(
            used_tokens=0, max_tokens=128000,
            percent_used=0.0, model="gpt-4",
            note="approximation — Codex logs lack per-turn data",
        )
