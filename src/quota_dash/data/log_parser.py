from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from quota_dash.models import TokenUsage


def parse_claude_costs_jsonl(path: Path) -> TokenUsage:
    if not path.exists():
        return TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0,
            history=[], session_id=None, source="estimated",
        )

    total_in = 0
    total_out = 0
    history: list[tuple[datetime, int]] = []
    session_id: str | None = None

    try:
        f = open(path)
    except (OSError, PermissionError):
        return TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0,
            history=[], session_id=None, source="estimated",
        )

    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            inp = entry.get("input_tokens", 0)
            out = entry.get("output_tokens", 0)
            total_in += inp
            total_out += out

            ts_str = entry.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = datetime.now()

            history.append((ts, inp + out))

            if session_id is None:
                session_id = entry.get("session_id")

    return TokenUsage(
        input_tokens=total_in,
        output_tokens=total_out,
        total_tokens=total_in + total_out,
        history=history,
        session_id=session_id,
        source="log",
    )


def parse_codex_logs(path: Path) -> TokenUsage:
    """Parse Codex SQLite logs. Token data is not available in current schema."""
    return TokenUsage(
        input_tokens=0, output_tokens=0, total_tokens=0,
        history=[], session_id=None, source="estimated",
    )
