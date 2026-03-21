from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class QuotaInfo:
    provider: str
    balance_usd: float | None
    limit_usd: float | None
    usage_today_usd: float | None
    last_updated: datetime
    source: str
    stale: bool = False


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    history: list[tuple[datetime, int]] = field(default_factory=list)
    session_id: str | None = None
    source: str = "estimated"


@dataclass
class ContextInfo:
    used_tokens: int
    max_tokens: int
    percent_used: float
    model: str
    note: str = ""


@dataclass
class ProxyData:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    ratelimit_remaining_tokens: int | None
    ratelimit_remaining_requests: int | None
    model: str | None
    last_call: datetime
    calls_today: int
    tokens_today: int
    ratelimit_reset: str | None = None
