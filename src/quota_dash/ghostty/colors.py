# src/quota_dash/ghostty/colors.py
from __future__ import annotations

import logging
from textual.app import App
from textual.widgets import ProgressBar

logger = logging.getLogger(__name__)

GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"


def threshold_color(percentage: float, context: str) -> str:
    """Return hex color based on percentage and context type.

    Args:
        percentage: 0.0 to 1.0 (caller computes as progress/total)
        context: "balance" (high=good) or "usage" (high=bad)
    """
    if context == "balance":
        if percentage > 0.5:
            return GREEN
        elif percentage > 0.2:
            return YELLOW
        else:
            return RED
    else:  # usage
        if percentage < 0.5:
            return GREEN
        elif percentage < 0.8:
            return YELLOW
        else:
            return RED


def _make_color_watcher(bar: ProgressBar, context: str):
    """Create a callback that updates bar color when progress changes."""
    def on_progress_change(progress: float) -> None:
        total = bar.total or 1
        pct = progress / total
        color = threshold_color(pct, context)
        bar.styles.color = color
    return on_progress_change


def enhance_widgets(app: App) -> None:
    """Find ProgressBars in QuotaCard/ContextCard and inject threshold colors."""
    try:
        from quota_dash.widgets.quota_card import QuotaCard
        from quota_dash.widgets.context_card import ContextCard

        for card in app.query(QuotaCard):
            bar = card.query_one("#quota-bar", ProgressBar)
            watcher = _make_color_watcher(bar, "balance")
            app.watch(bar, "progress", watcher)

        for card in app.query(ContextCard):  # type: ignore[assignment]
            bar = card.query_one("#ctx-bar", ProgressBar)
            watcher = _make_color_watcher(bar, "usage")
            app.watch(bar, "progress", watcher)

    except Exception:
        logger.exception("Failed to enhance widgets with Ghostty colors")
