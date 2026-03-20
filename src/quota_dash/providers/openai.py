from __future__ import annotations

import logging
import os
from datetime import datetime

from quota_dash.config import ProviderConfig
from quota_dash.data.api_client import fetch_openai_usage
from quota_dash.data.log_parser import parse_codex_logs
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo
from quota_dash.providers.base import Provider

logger = logging.getLogger(__name__)


def _error_quota(msg: str) -> QuotaInfo:
    logger.warning("openai get_quota failed: %s", msg)
    return QuotaInfo(
        provider="openai",
        balance_usd=None, limit_usd=None, usage_today_usd=None,
        last_updated=datetime.now(), source="error", stale=True,
    )


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    async def get_quota(self) -> QuotaInfo:
        try:
            return await self._fetch_quota()
        except Exception as exc:
            return _error_quota(str(exc))

    async def _fetch_quota(self) -> QuotaInfo:
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
        try:
            return parse_codex_logs(self._config.log_path)
        except Exception as exc:
            logger.warning("openai get_token_usage failed: %s", exc)
            return TokenUsage(
                input_tokens=0, output_tokens=0, total_tokens=0,
                history=[], session_id=None, source="error",
            )

    async def get_context_window(self) -> ContextInfo:
        return ContextInfo(
            used_tokens=0, max_tokens=128000,
            percent_used=0.0, model="gpt-4",
            note="approximation — Codex logs lack per-turn data",
        )
