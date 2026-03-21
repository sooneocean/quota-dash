from __future__ import annotations

import importlib.util as _ilu
import logging
from dataclasses import dataclass
from datetime import datetime
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
    target_url TEXT
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
                    request_id, target_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.provider, record.model, record.endpoint,
                    record.input_tokens, record.output_tokens, record.total_tokens,
                    record.ratelimit_remaining_tokens, record.ratelimit_remaining_requests,
                    record.ratelimit_reset, record.request_id, record.target_url,
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


async def query_recent_calls(db_path: Path, provider: str, limit: int = 20) -> list[dict]:
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT timestamp, model, total_tokens, endpoint
                   FROM api_calls WHERE provider = ?
                   AND date(timestamp) = date('now')
                   ORDER BY timestamp DESC LIMIT ?""",
                (provider, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to query recent calls")
        return []


async def query_token_history(db_path: Path, provider: str, limit: int = 50) -> list[tuple[datetime, int]]:
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                """SELECT timestamp, total_tokens
                   FROM api_calls WHERE provider = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (provider, limit),
            )
            rows = await cursor.fetchall()
            return [(datetime.fromisoformat(ts), tok) for ts, tok in reversed(list(rows))]
    except Exception:
        logger.exception("Failed to query token history")
        return []
