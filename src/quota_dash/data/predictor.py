from __future__ import annotations

from datetime import datetime
from pathlib import Path


async def predict_rate_limit_exhaustion(
    db_path: Path,
    provider: str,
    remaining_tokens: int | None,
    remaining_requests: int | None,
) -> dict[str, str | None]:
    """Predict when rate limits will be exhausted based on recent velocity.

    Returns {"tokens_eta": "~12m", "requests_eta": "~45m"} or None values.
    """
    if not db_path.exists():
        return {"tokens_eta": None, "requests_eta": None}

    try:
        import aiosqlite
    except ImportError:
        return {"tokens_eta": None, "requests_eta": None}

    try:
        async with aiosqlite.connect(db_path) as db:
            # Get calls from last 10 minutes to calculate velocity
            cursor = await db.execute(
                """SELECT COUNT(*) as cnt,
                          COALESCE(SUM(total_tokens), 0) as total_tok,
                          MIN(timestamp) as first_ts, MAX(timestamp) as last_ts
                   FROM api_calls
                   WHERE provider = ?
                   AND timestamp >= datetime('now', '-10 minutes')""",
                (provider,),
            )
            row = await cursor.fetchone()
            if not row or row[0] < 2:  # Need at least 2 calls to calculate velocity
                return {"tokens_eta": None, "requests_eta": None}

            call_count = row[0]
            total_tokens = row[1]
            first_ts = datetime.fromisoformat(row[2])
            last_ts = datetime.fromisoformat(row[3])

            elapsed = (last_ts - first_ts).total_seconds()
            if elapsed <= 0:
                return {"tokens_eta": None, "requests_eta": None}

            # Velocity: tokens per second, requests per second
            tok_per_sec = total_tokens / elapsed if total_tokens > 0 else 0
            req_per_sec = call_count / elapsed

            # Predict ETA
            tokens_eta = None
            if remaining_tokens is not None and tok_per_sec > 0:
                seconds_left = remaining_tokens / tok_per_sec
                tokens_eta = _format_eta(seconds_left)

            requests_eta = None
            if remaining_requests is not None and req_per_sec > 0:
                seconds_left = remaining_requests / req_per_sec
                requests_eta = _format_eta(seconds_left)

            return {"tokens_eta": tokens_eta, "requests_eta": requests_eta}
    except Exception:
        return {"tokens_eta": None, "requests_eta": None}


def _format_eta(seconds: float) -> str:
    """Format seconds into human-readable ETA."""
    if seconds < 60:
        return f"~{int(seconds)}s"
    elif seconds < 3600:
        return f"~{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"~{seconds / 3600:.1f}h"
    else:
        return f"~{seconds / 86400:.1f}d"
