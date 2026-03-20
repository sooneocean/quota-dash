from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from quota_dash.models import TokenUsage

logger = logging.getLogger(__name__)


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

    with open(path) as f:
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
    """Parse Codex state SQLite for token usage.

    Codex stores token data in state_5.sqlite (threads table),
    not in logs_1.sqlite. The caller should pass the Codex data
    directory (e.g. ~/.codex); we look for state_5.sqlite there.
    If the caller passes a direct .sqlite path, we try the parent dir.
    """
    # Resolve to the directory containing Codex DBs
    if path.suffix == ".sqlite":
        codex_dir = path.parent
    else:
        codex_dir = path

    state_db = codex_dir / "state_5.sqlite"
    if not state_db.exists():
        # Fallback: maybe the old path convention (logs_1.sqlite dir)
        state_db = codex_dir.parent / "state_5.sqlite" if codex_dir.name != ".codex" else state_db
        if not state_db.exists():
            logger.debug("Codex state DB not found at %s", state_db)
            return TokenUsage(
                input_tokens=0, output_tokens=0, total_tokens=0,
                history=[], session_id=None, source="estimated",
            )

    try:
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        cursor = conn.execute(
            "SELECT id, tokens_used, created_at FROM threads "
            "WHERE tokens_used > 0 ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        logger.warning("Failed to read Codex state DB: %s", exc)
        return TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0,
            history=[], session_id=None, source="error",
        )

    if not rows:
        return TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0,
            history=[], session_id=None, source="log",
        )

    total_tokens = sum(r[1] for r in rows)
    session_id = rows[0][0]  # most recent thread id

    history: list[tuple[datetime, int]] = []
    for row in rows:
        ts = datetime.fromtimestamp(row[2])
        history.append((ts, row[1]))

    # Codex threads table only has total tokens, no in/out split
    return TokenUsage(
        input_tokens=0,
        output_tokens=0,
        total_tokens=total_tokens,
        history=history,
        session_id=session_id,
        source="log",
    )
