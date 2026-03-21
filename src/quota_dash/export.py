from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _parse_period(period: str) -> timedelta:
    """Parse period string like '24h', '7d', '30d' to timedelta."""
    value = int(period[:-1])
    unit = period[-1]
    if unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    raise ValueError(f"Invalid period: {period}. Use format like '24h', '7d', '30d'")


async def query_calls(
    db_path: Path,
    period: str = "24h",
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """Query api_calls within the given period."""
    delta = _parse_period(period)
    since = (datetime.now(timezone.utc) - delta).isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        if provider:
            cursor = await db.execute(
                """SELECT timestamp, provider, model, endpoint,
                          input_tokens, output_tokens, total_tokens
                   FROM api_calls
                   WHERE timestamp >= ? AND provider = ?
                   ORDER BY timestamp""",
                (since, provider),
            )
        else:
            cursor = await db.execute(
                """SELECT timestamp, provider, model, endpoint,
                          input_tokens, output_tokens, total_tokens
                   FROM api_calls
                   WHERE timestamp >= ?
                   ORDER BY timestamp""",
                (since,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


def build_summary(calls: list[dict], period: str) -> dict[str, Any]:
    """Build summary statistics from calls."""
    total_tokens = sum(c.get("total_tokens", 0) or 0 for c in calls)
    by_provider: dict[str, dict[str, int]] = {}
    for c in calls:
        prov = c.get("provider", "unknown")
        if prov not in by_provider:
            by_provider[prov] = {"calls": 0, "tokens": 0}
        by_provider[prov]["calls"] += 1
        by_provider[prov]["tokens"] += c.get("total_tokens", 0) or 0

    return {
        "period": period,
        "total_calls": len(calls),
        "total_tokens": total_tokens,
        "by_provider": by_provider,
    }


def format_csv(calls: list[dict], summary: dict) -> str:
    """Format calls as CSV with summary footer."""
    output = io.StringIO()
    fields = ["timestamp", "provider", "model", "endpoint", "input_tokens", "output_tokens", "total_tokens"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for call in calls:
        writer.writerow(call)

    # Summary footer
    output.write(f"\n# Summary: {summary['period']}\n")
    output.write(f"# Total calls: {summary['total_calls']}\n")
    output.write(f"# Total tokens: {summary['total_tokens']}\n")
    for prov, stats in summary["by_provider"].items():
        output.write(f"# {prov}: {stats['calls']} calls, {stats['tokens']} tokens\n")

    return output.getvalue()


def format_json(calls: list[dict], summary: dict) -> str:
    """Format calls as JSON with summary."""
    data = {**summary, "calls": calls}
    return json.dumps(data, indent=2, default=str)
