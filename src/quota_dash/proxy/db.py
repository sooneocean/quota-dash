from __future__ import annotations

import importlib.util as _ilu
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from quota_dash.models import ProxyData

logger = logging.getLogger(__name__)

_HAS_AIOSQLITE = _ilu.find_spec("aiosqlite") is not None

SCHEMA = """\
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    provider TEXT NOT NULL,
    model TEXT,
    endpoint TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    ratelimit_remaining_tokens INTEGER,
    ratelimit_remaining_requests INTEGER,
    ratelimit_reset TEXT,
    request_id TEXT,
    target_url TEXT,
    session_tag TEXT
);
CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON api_calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_calls_provider ON api_calls(provider);
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
"""


@dataclass
class ApiCallRecord:
    provider: str
    model: str | None
    endpoint: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    ratelimit_remaining_tokens: int | None
    ratelimit_remaining_requests: int | None
    ratelimit_reset: str | None
    request_id: str | None
    target_url: str | None
    session_tag: str | None = None


async def _migrate_session_column(db: object) -> None:
    """Add session_tag column if it doesn't exist."""
    cursor = await db.execute("PRAGMA table_info(api_calls)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "session_tag" not in columns:
        await db.execute("ALTER TABLE api_calls ADD COLUMN session_tag TEXT")
        await db.commit()


async def init_db(db_path: Path) -> None:
    if not _HAS_AIOSQLITE:
        return
    import aiosqlite
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
        fetched = await cursor.fetchone()
        count = fetched[0] if fetched is not None else 0
        if count == 0:
            await db.execute("INSERT INTO schema_version VALUES (1)")
        await db.commit()
        await _migrate_session_column(db)


async def write_api_call(db_path: Path, record: ApiCallRecord) -> None:
    if not _HAS_AIOSQLITE:
        return
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """INSERT INTO api_calls
                   (provider, model, endpoint, input_tokens, output_tokens,
                    total_tokens, ratelimit_remaining_tokens,
                    ratelimit_remaining_requests, ratelimit_reset,
                    request_id, target_url, session_tag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.provider, record.model, record.endpoint,
                    record.input_tokens, record.output_tokens, record.total_tokens,
                    record.ratelimit_remaining_tokens, record.ratelimit_remaining_requests,
                    record.ratelimit_reset, record.request_id, record.target_url,
                    record.session_tag,
                ),
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to write api_call record")


async def query_provider_data(db_path: Path, provider: str) -> ProxyData | None:
    if not _HAS_AIOSQLITE:
        return None
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT input_tokens, output_tokens, total_tokens,
                          ratelimit_remaining_tokens, ratelimit_remaining_requests,
                          ratelimit_reset, model, timestamp
                   FROM api_calls WHERE provider = ?
                   ORDER BY timestamp DESC, id DESC LIMIT 1""",
                (provider,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            cursor2 = await db.execute(
                """SELECT COUNT(*) as cnt, COALESCE(SUM(total_tokens), 0) as total
                   FROM api_calls
                   WHERE provider = ? AND date(timestamp) = date('now')""",
                (provider,),
            )
            agg = await cursor2.fetchone()

            return ProxyData(
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                total_tokens=row["total_tokens"],
                ratelimit_remaining_tokens=row["ratelimit_remaining_tokens"],
                ratelimit_remaining_requests=row["ratelimit_remaining_requests"],
                ratelimit_reset=row["ratelimit_reset"],
                model=row["model"],
                last_call=datetime.fromisoformat(row["timestamp"]),
                calls_today=agg["cnt"] if agg is not None else 0,
                tokens_today=agg["total"] if agg is not None else 0,
            )
    except Exception:
        logger.exception("Failed to query provider data")
        return None


def _period_cutoff(period: str) -> str:
    """Return an ISO-format UTC cutoff timestamp for the given period string (e.g. '1h', '24h', '7d')."""
    value = int(period[:-1])
    unit = period[-1]
    if unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    else:
        raise ValueError(f"Invalid period: {period}. Use format like '1h', '24h', '7d'")
    return (datetime.now(timezone.utc) - delta).isoformat(sep=" ")


async def query_recent_calls(db_path: Path, provider: str, limit: int = 20, period: str = "24h") -> list[dict]:
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        cutoff = _period_cutoff(period)
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT timestamp, model, total_tokens, endpoint
                   FROM api_calls WHERE provider = ?
                   AND timestamp >= ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (provider, cutoff, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to query recent calls")
        return []


async def query_token_history(
    db_path: Path, provider: str, limit: int = 50, period: str | None = None
) -> list[tuple[datetime, int]]:
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            if period is not None:
                cutoff = _period_cutoff(period)
                cursor = await db.execute(
                    """SELECT timestamp, total_tokens
                       FROM api_calls WHERE provider = ?
                       AND timestamp >= ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (provider, cutoff, limit),
                )
            else:
                cursor = await db.execute(
                    """SELECT timestamp, total_tokens
                       FROM api_calls WHERE provider = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (provider, limit),
                )
            rows = await cursor.fetchall()
            return [(datetime.fromisoformat(ts), tok) for ts, tok in reversed(rows)]
    except Exception:
        logger.exception("Failed to query token history")
        return []


async def query_sessions(db_path: Path) -> list[dict]:
    """Get unique session tags with stats."""
    if not _HAS_AIOSQLITE:
        return []
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        await _migrate_session_column(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT session_tag, COUNT(*) as calls,
                      SUM(total_tokens) as tokens,
                      MIN(timestamp) as started, MAX(timestamp) as ended
               FROM api_calls
               WHERE session_tag IS NOT NULL
               GROUP BY session_tag
               ORDER BY started DESC"""
        )
        return [dict(row) for row in await cursor.fetchall()]


async def query_session_calls(db_path: Path, session_tag: str) -> list[dict]:
    """Get all API calls for a specific session."""
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await _migrate_session_column(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT timestamp, provider, model, endpoint,
                          input_tokens, output_tokens, total_tokens
                   FROM api_calls
                   WHERE session_tag = ?
                   ORDER BY timestamp ASC""",
                (session_tag,),
            )
            return [dict(row) for row in await cursor.fetchall()]
    except Exception:
        logger.exception("Failed to query session calls")
        return []
