from __future__ import annotations

import logging

from quota_dash.proxy.db import ApiCallRecord

logger = logging.getLogger(__name__)


def detect_provider(body: dict) -> str:
    if body.get("type") == "message" and "input_tokens" in body.get("usage", {}):
        return "anthropic"
    if "choices" in body and "prompt_tokens" in body.get("usage", {}):
        return "openai"
    return "unknown"


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def extract_usage(
    body: dict,
    headers: dict,
    endpoint: str,
    target_url: str,
) -> ApiCallRecord:
    provider = detect_provider(body)
    usage = body.get("usage", {})

    if provider == "openai":
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        request_id = headers.get("x-request-id")
        rl_tokens = _safe_int(headers.get("x-ratelimit-remaining-tokens"))
        rl_requests = _safe_int(headers.get("x-ratelimit-remaining-requests"))
    elif provider == "anthropic":
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        request_id = headers.get("request-id")
        rl_tokens = _safe_int(headers.get("anthropic-ratelimit-tokens-remaining"))
        rl_requests = _safe_int(headers.get("anthropic-ratelimit-requests-remaining"))
    else:
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        request_id = headers.get("x-request-id") or headers.get("request-id")
        rl_tokens = _safe_int(
            headers.get("x-ratelimit-remaining-tokens")
            or headers.get("anthropic-ratelimit-tokens-remaining")
        )
        rl_requests = None

    return ApiCallRecord(
        provider=provider,
        model=body.get("model"),
        endpoint=endpoint,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        ratelimit_remaining_tokens=rl_tokens,
        ratelimit_remaining_requests=rl_requests,
        ratelimit_reset=headers.get("x-ratelimit-reset-tokens"),
        request_id=request_id,
        target_url=target_url,
    )
