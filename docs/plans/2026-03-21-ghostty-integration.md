# Ghostty Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ghostty-exclusive enhancements — true color threshold coloring on ProgressBars and three-tier quota alert notifications with desktop notification support.

**Architecture:** Isolated `ghostty/` module detects Ghostty via `$TERM_PROGRAM`, injects threshold colors onto existing ProgressBars by watching their `progress` reactive, and monitors quota thresholds to trigger dashboard border changes + OSC 9 desktop notifications + terminal bell. Zero intrusion into core widgets.

**Tech Stack:** Textual (existing), no new dependencies

**Spec:** `docs/specs/2026-03-21-ghostty-integration.md`

---

## File Structure

```
src/quota_dash/
├── ghostty/
│   ├── __init__.py       # NEW
│   ├── detect.py         # NEW — is_ghostty()
│   ├── colors.py         # NEW — threshold_color() + enhance_widgets()
│   └── alerts.py         # NEW — AlertMonitor + send_notification() + send_bell()
├── app.py                # MODIFY — add ghostty activation in on_mount + alert check in _refresh_all
tests/
├── test_ghostty_detect.py    # NEW
├── test_ghostty_colors.py    # NEW
├── test_ghostty_alerts.py    # NEW
```

---

### Task 1: Detection Module

**Files:**
- Create: `src/quota_dash/ghostty/__init__.py`
- Create: `src/quota_dash/ghostty/detect.py`
- Create: `tests/test_ghostty_detect.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ghostty_detect.py
from unittest.mock import patch
from quota_dash.ghostty.detect import is_ghostty


def test_is_ghostty_true():
    with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}):
        assert is_ghostty() is True


def test_is_ghostty_false_other_terminal():
    with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm2"}):
        assert is_ghostty() is False


def test_is_ghostty_false_no_env():
    with patch.dict("os.environ", {}, clear=True):
        assert is_ghostty() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_ghostty_detect.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/quota_dash/ghostty/__init__.py
```

```python
# src/quota_dash/ghostty/detect.py
from __future__ import annotations

import os


def is_ghostty() -> bool:
    return os.environ.get("TERM_PROGRAM") == "ghostty"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_ghostty_detect.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/ghostty/ tests/test_ghostty_detect.py && git commit -m "feat: Ghostty terminal detection module"
```

---

### Task 2: Threshold Color System

**Files:**
- Create: `src/quota_dash/ghostty/colors.py`
- Create: `tests/test_ghostty_colors.py`

- [ ] **Step 1: Write failing test for threshold_color**

```python
# tests/test_ghostty_colors.py
from quota_dash.ghostty.colors import threshold_color


# Context A: balance-oriented (high = good)
def test_balance_high():
    assert threshold_color(0.8, "balance") == "#22c55e"  # green

def test_balance_medium():
    assert threshold_color(0.35, "balance") == "#eab308"  # yellow

def test_balance_low():
    assert threshold_color(0.1, "balance") == "#ef4444"  # red

def test_balance_boundary_50():
    assert threshold_color(0.5, "balance") == "#eab308"  # 0.5 is NOT > 0.5, so yellow

def test_balance_boundary_20():
    assert threshold_color(0.2, "balance") == "#ef4444"  # 0.2 is NOT > 0.2, so red


# Context B: usage-oriented (high = bad)
def test_usage_low():
    assert threshold_color(0.3, "usage") == "#22c55e"  # green

def test_usage_medium():
    assert threshold_color(0.65, "usage") == "#eab308"  # yellow

def test_usage_high():
    assert threshold_color(0.9, "usage") == "#ef4444"  # red

def test_usage_boundary_50():
    assert threshold_color(0.5, "usage") == "#eab308"  # 0.5 is NOT < 0.5, so yellow

def test_usage_boundary_80():
    assert threshold_color(0.8, "usage") == "#ef4444"  # 0.8 is NOT < 0.8, so red
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_ghostty_colors.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement colors.py**

```python
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

        for card in app.query(ContextCard):
            bar = card.query_one("#ctx-bar", ProgressBar)
            watcher = _make_color_watcher(bar, "usage")
            app.watch(bar, "progress", watcher)

    except Exception:
        logger.exception("Failed to enhance widgets with Ghostty colors")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_ghostty_colors.py -v`
Expected: All 10 PASS

- [ ] **Step 5: Write integration test for enhance_widgets**

```python
# Append to tests/test_ghostty_colors.py
import pytest
from unittest.mock import patch
from textual.app import App, ComposeResult
from textual.widgets import ProgressBar

from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.ghostty.colors import enhance_widgets
from quota_dash.models import QuotaInfo, ContextInfo
from datetime import datetime


class GhosttyColorTestApp(App):
    def compose(self) -> ComposeResult:
        yield QuotaCard()
        yield ContextCard()


@pytest.mark.asyncio
async def test_enhance_widgets_runs_without_error():
    app = GhosttyColorTestApp()
    async with app.run_test() as pilot:
        enhance_widgets(app)
        # Update quota with data to trigger progress change
        card = app.query_one(QuotaCard)
        card.update_data(QuotaInfo(
            provider="openai", balance_usd=80.0, limit_usd=100.0,
            usage_today_usd=None, last_updated=datetime.now(),
            source="manual", stale=False,
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_enhance_widgets_no_crash_on_empty_app():
    """enhance_widgets should not crash if widgets are missing."""
    app = App()
    async with app.run_test() as pilot:
        enhance_widgets(app)  # should not raise
```

- [ ] **Step 6: Run all color tests**

Run: `cd quota-dash && pytest tests/test_ghostty_colors.py -v`
Expected: All 12 PASS

- [ ] **Step 7: Commit**

```bash
cd quota-dash && git add src/quota_dash/ghostty/colors.py tests/test_ghostty_colors.py && git commit -m "feat: Ghostty threshold color system with widget injection"
```

---

### Task 3: Alert System

**Files:**
- Create: `src/quota_dash/ghostty/alerts.py`
- Create: `tests/test_ghostty_alerts.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ghostty_alerts.py
from datetime import datetime
from unittest.mock import patch, MagicMock

from quota_dash.ghostty.alerts import AlertMonitor, send_notification, send_bell
from quota_dash.data.store import DataStore
from quota_dash.models import QuotaInfo


def _make_store_with_quota(provider: str, balance: float, limit: float) -> DataStore:
    store = DataStore()
    store.update_quota(provider, QuotaInfo(
        provider=provider, balance_usd=balance, limit_usd=limit,
        usage_today_usd=None, last_updated=datetime.now(),
        source="manual", stale=False,
    ))
    return store


def test_no_alert_when_balance_healthy():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 80.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert actions == []


def test_warning_at_50_percent():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 40.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert any(a["level"] == "warning" for a in actions)


def test_alert_at_20_percent():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 15.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert any(a["level"] == "alert" for a in actions)


def test_critical_at_5_percent():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 3.0, 100.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert any(a["level"] == "critical" for a in actions)


def test_deduplication():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 15.0, 100.0)
    app = MagicMock()
    actions1 = monitor.check(app, store)
    actions2 = monitor.check(app, store)
    assert len(actions1) > 0
    assert len(actions2) == 0  # already notified


def test_rearm_after_recovery():
    monitor = AlertMonitor()
    app = MagicMock()

    # First: trigger alert
    store_low = _make_store_with_quota("openai", 15.0, 100.0)
    monitor.check(app, store_low)

    # Then: balance recovers
    store_high = _make_store_with_quota("openai", 80.0, 100.0)
    monitor.check(app, store_high)

    # Then: drops again — should re-fire
    actions = monitor.check(app, store_low)
    assert len(actions) > 0


def test_skip_none_balance():
    monitor = AlertMonitor()
    store = DataStore()
    store.update_quota("openai", QuotaInfo(
        provider="openai", balance_usd=None, limit_usd=None,
        usage_today_usd=None, last_updated=datetime.now(),
        source="unavailable", stale=False,
    ))
    app = MagicMock()
    actions = monitor.check(app, store)
    assert actions == []


def test_skip_zero_limit():
    monitor = AlertMonitor()
    store = _make_store_with_quota("openai", 50.0, 0.0)
    app = MagicMock()
    actions = monitor.check(app, store)
    assert actions == []


def test_send_notification_writes_osc9():
    with patch("sys.stdout") as mock_stdout:
        send_notification("quota-dash: OpenAI balance low")
        mock_stdout.write.assert_called_once()
        written = mock_stdout.write.call_args[0][0]
        assert "\x1b]9;" in written
        assert "\x07" in written


def test_send_bell():
    with patch("sys.stdout") as mock_stdout:
        send_bell()
        mock_stdout.write.assert_called_once_with("\x07")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_ghostty_alerts.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement alerts.py**

```python
# src/quota_dash/ghostty/alerts.py
from __future__ import annotations

import logging
import sys
from typing import Any

from textual.app import App

from quota_dash.data.store import DataStore

logger = logging.getLogger(__name__)

THRESHOLDS = [
    ("critical", 0.05),
    ("alert", 0.20),
    ("warning", 0.50),
]

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


class AlertMonitor:
    def __init__(self) -> None:
        self._notified: set[tuple[str, str]] = set()

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
                for level, threshold in THRESHOLDS:
                    if ratio < threshold:
                        triggered_level = level
                        break

                if triggered_level is None:
                    # Balance is healthy — clear any previous notifications
                    self._notified = {
                        (p, l) for p, l in self._notified if p != provider_name
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
                    send_notification(f"quota-dash: {provider_name} balance at {pct}")

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_ghostty_alerts.py -v`
Expected: All 10 PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/ghostty/alerts.py tests/test_ghostty_alerts.py && git commit -m "feat: three-tier alert system with OSC 9 notification and terminal bell"
```

---

### Task 4: App Integration

**Files:**
- Modify: `src/quota_dash/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_app.py
from unittest.mock import patch


@pytest.mark.asyncio
async def test_app_launches_without_ghostty():
    """Non-Ghostty environment should work fine — no ghostty module loaded."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm2"}, clear=False):
        app = QuotaDashApp()
        async with app.run_test() as pilot:
            assert app.title == "quota-dash"
            assert app._alert_monitor is None


@pytest.mark.asyncio
async def test_app_launches_with_ghostty():
    """Ghostty environment should activate color enhancement and alert monitor."""
    with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}, clear=False):
        app = QuotaDashApp()
        async with app.run_test() as pilot:
            assert app.title == "quota-dash"
            assert app._alert_monitor is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_app.py::test_app_launches_with_ghostty -v`
Expected: FAIL — `AttributeError: 'QuotaDashApp' object has no attribute '_alert_monitor'`

- [ ] **Step 3: Modify app.py**

In `__init__`, add after `self._selected_provider = None`:
```python
        self._alert_monitor = None
```

In `on_mount`, add after the existing `self.set_interval(...)` line:
```python
        # Ghostty enhancements (lazy import, only if detected)
        from quota_dash.ghostty.detect import is_ghostty
        if is_ghostty():
            try:
                from quota_dash.ghostty.colors import enhance_widgets
                from quota_dash.ghostty.alerts import AlertMonitor
                enhance_widgets(self)
                self._alert_monitor = AlertMonitor()
            except Exception:
                pass  # silently skip if ghostty module fails

```

In `_refresh_all`, add at the very end (after the `_update_detail` call):
```python
        # Alert monitoring (Ghostty only)
        if self._alert_monitor:
            self._alert_monitor.check(self, self._store)
```

- [ ] **Step 4: Run all app tests**

Run: `cd quota-dash && pytest tests/test_app.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd quota-dash && pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd quota-dash && git add src/quota_dash/app.py tests/test_app.py && git commit -m "feat: integrate Ghostty colors + alerts into app lifecycle"
```

---

### Task 5: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
cd quota-dash && pytest tests/ -v --tb=short
```
Expected: All PASS

- [ ] **Step 2: Verify non-Ghostty launch**

```bash
cd quota-dash && TERM_PROGRAM=xterm quota-dash --once
```
Expected: Normal output, no errors

- [ ] **Step 3: Verify Ghostty detection**

```bash
cd quota-dash && TERM_PROGRAM=ghostty quota-dash --once
```
Expected: Normal output (colors not visible in --once mode, but no errors)

- [ ] **Step 4: Commit if any changes needed**
