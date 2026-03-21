# src/quota_dash/ghostty/alerts.py
from __future__ import annotations

import logging
import sys
from typing import Any

import httpx as _httpx

from quota_dash.data.store import DataStore

logger = logging.getLogger(__name__)

BORDER_COLORS = {
    "warning": "yellow",
    "alert": "darkorange",
    "critical": "red",
}


def send_notification(message: str) -> None:
    sys.stdout.write(f"\x1b]9;{message}\x07")
    sys.stdout.flush()


def send_bell() -> None:
    sys.stdout.write("\x07")
    sys.stdout.flush()


async def send_webhook(url: str, message: str) -> None:
    """Send alert to webhook URL. Auto-detects Slack/Discord format."""
    try:
        # Detect platform by URL
        if "hooks.slack.com" in url or "slack" in url:
            payload = {"text": message}
        elif "discord.com/api/webhooks" in url:
            payload = {"content": message}
        else:
            # Generic webhook
            payload = {"text": message, "message": message}

        async with _httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception:
        logger.warning("Webhook notification failed: %s", url)


class AlertMonitor:
    def __init__(self, warning: int = 50, alert: int = 20, critical: int = 5, webhook_url: str | None = None) -> None:
        self._notified: set[tuple[str, str]] = set()
        self._thresholds = [
            ("critical", critical / 100),
            ("alert", alert / 100),
            ("warning", warning / 100),
        ]
        self._webhook_url = webhook_url

    def check(self, app: Any, store: DataStore) -> list[dict]:
        """Check all providers against alert thresholds.

        Returns list of actions taken (for testing).
        """
        actions: list[dict] = []

        try:
            for provider_name in store.providers():
                quota = store.get_quota(provider_name)
                if quota is None:
                    continue
                if quota.balance_usd is None or quota.limit_usd is None or quota.limit_usd == 0:
                    continue

                ratio = quota.balance_usd / quota.limit_usd

                # Determine highest triggered level
                triggered_level: str | None = None
                for level, threshold in self._thresholds:
                    if ratio < threshold:
                        triggered_level = level
                        break

                if triggered_level is None:
                    # Balance is healthy — clear any previous notifications
                    self._notified = {
                        (p, lvl) for p, lvl in self._notified if p != provider_name
                    }
                    # Reset border if app has QuotaCard
                    self._reset_border(app, provider_name)
                    continue

                key = (provider_name, triggered_level)
                if key in self._notified:
                    continue

                self._notified.add(key)
                actions.append({"provider": provider_name, "level": triggered_level, "ratio": ratio})

                # Execute actions
                self._set_border(app, provider_name, triggered_level)

                if triggered_level in ("alert", "critical"):
                    pct = f"{ratio * 100:.0f}%"
                    msg = f"quota-dash: {provider_name} balance at {pct}"
                    send_notification(msg)
                    if self._webhook_url:
                        import asyncio
                        asyncio.create_task(send_webhook(self._webhook_url, msg))

                if triggered_level == "critical":
                    send_bell()

        except Exception:
            logger.exception("Alert monitor check failed")

        return actions

    def _set_border(self, app: Any, provider_name: str, level: str) -> None:
        try:
            from quota_dash.widgets.quota_card import QuotaCard
            for card in app.query(QuotaCard):
                color = BORDER_COLORS.get(level, "yellow")
                card.styles.border = ("solid", color)
        except Exception:
            pass

    def _reset_border(self, app: Any, provider_name: str) -> None:
        try:
            from quota_dash.widgets.quota_card import QuotaCard
            for card in app.query(QuotaCard):
                card.styles.border = None
        except Exception:
            pass
