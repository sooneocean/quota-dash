from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from quota_dash.config import ProviderConfig
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData
from quota_dash.providers.base import Provider


class MistralProvider(Provider):
    name = "mistral"

    def __init__(self, config: ProviderConfig, db_path: Path | None = None) -> None:
        self._config = config
        self._db_path = db_path

    async def get_quota(self) -> QuotaInfo:
        now = datetime.now(timezone.utc)

        if self._config.balance_usd is not None:
            return QuotaInfo(
                provider="mistral",
                balance_usd=self._config.balance_usd,
                limit_usd=self._config.limit_usd,
                usage_today_usd=None,
                last_updated=now,
                source="manual",
                stale=False,
            )

        return QuotaInfo(
            provider="mistral",
            balance_usd=None, limit_usd=None, usage_today_usd=None,
            last_updated=now, source="unavailable", stale=False,
        )

    async def get_proxy_data(self) -> ProxyData | None:
        if self._db_path is None or not self._db_path.exists():
            return None
        from quota_dash.proxy.db import query_provider_data
        return await query_provider_data(self._db_path, "mistral")

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
        return TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0,
            history=[], session_id=None, source="estimated",
        )

    async def get_context_window(self) -> ContextInfo:
        proxy = await self.get_proxy_data()
        if proxy is not None and proxy.input_tokens > 0:
            return ContextInfo(
                used_tokens=proxy.input_tokens,
                max_tokens=131072,
                percent_used=proxy.input_tokens / 131072 * 100,
                model=proxy.model or "mistral-large",
                note="last call snapshot",
            )
        return ContextInfo(
            used_tokens=0, max_tokens=131072,
            percent_used=0.0, model="mistral-large",
            note="approximation",
        )
