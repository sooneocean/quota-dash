# src/quota_dash/proxy/streaming.py
from __future__ import annotations

import json
import logging

from quota_dash.proxy.db import ApiCallRecord
from quota_dash.proxy.parser import _safe_int

logger = logging.getLogger(__name__)


class StreamingBuffer:
    def __init__(self) -> None:
        self._current_event: str | None = None
        # OpenAI: last chunk with usage
        self._openai_usage: dict | None = None
        # Anthropic: split across events
        self._anthropic_input_tokens: int | None = None
        self._anthropic_output_tokens: int | None = None
        self._model: str | None = None

    def feed_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            self._current_event = None
            return

        if line.startswith("event:"):
            self._current_event = line[6:].strip()
            return

        if not line.startswith("data:"):
            return

        data_str = line[5:].strip()
        if data_str == "[DONE]":
            return

        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            return

        # Extract model from any chunk
        if "model" in data and self._model is None:
            self._model = data.get("model")

        # OpenAI: final chunk has empty choices + usage
        if isinstance(data.get("choices"), list) and len(data["choices"]) == 0 and "usage" in data:
            self._openai_usage = data["usage"]

        # Anthropic: message_start has input_tokens
        if data.get("type") == "message_start":
            msg = data.get("message", {})
            usage = msg.get("usage", {})
            if "input_tokens" in usage:
                self._anthropic_input_tokens = usage["input_tokens"]

        # Anthropic: message_delta has output_tokens
        if data.get("type") == "message_delta":
            usage = data.get("usage", {})
            if "output_tokens" in usage:
                self._anthropic_output_tokens = usage["output_tokens"]

    def extract_usage(
        self,
        headers: dict,
        endpoint: str,
        target_url: str,
    ) -> ApiCallRecord:
        # OpenAI streaming
        if self._openai_usage is not None:
            u = self._openai_usage
            return ApiCallRecord(
                provider="openai",
                model=self._model,
                endpoint=endpoint,
                input_tokens=u.get("prompt_tokens", 0),
                output_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
                ratelimit_remaining_tokens=_safe_int(headers.get("x-ratelimit-remaining-tokens")),
                ratelimit_remaining_requests=_safe_int(headers.get("x-ratelimit-remaining-requests")),
                ratelimit_reset=headers.get("x-ratelimit-reset-tokens"),
                request_id=headers.get("x-request-id"),
                target_url=target_url,
            )

        # Anthropic streaming
        if self._anthropic_input_tokens is not None or self._anthropic_output_tokens is not None:
            inp = self._anthropic_input_tokens or 0
            out = self._anthropic_output_tokens or 0
            return ApiCallRecord(
                provider="anthropic",
                model=self._model,
                endpoint=endpoint,
                input_tokens=inp,
                output_tokens=out,
                total_tokens=inp + out,
                ratelimit_remaining_tokens=_safe_int(headers.get("anthropic-ratelimit-tokens-remaining")),
                ratelimit_remaining_requests=_safe_int(headers.get("anthropic-ratelimit-requests-remaining")),
                ratelimit_reset=None,
                request_id=headers.get("request-id"),
                target_url=target_url,
            )

        # No usage found
        return ApiCallRecord(
            provider="unknown", model=self._model, endpoint=endpoint,
            input_tokens=0, output_tokens=0, total_tokens=0,
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None, target_url=target_url,
        )
