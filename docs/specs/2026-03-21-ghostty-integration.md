# quota-dash v0.4: Ghostty Deep Integration — Design Spec

> Ghostty-exclusive enhancements: true color threshold gauges and three-tier alert notifications with desktop notification support.

## Overview

An isolated `ghostty/` module that detects Ghostty terminal and injects visual enhancements into existing widgets without modifying their core logic. Two features: dynamic threshold colors on ProgressBars, and multi-tier quota alert notifications (dashboard + desktop + bell).

## Goals

1. True color threshold coloring on ProgressBars with context-aware semantics (green=safe, yellow=warning, red=danger)
2. Three-tier quota alerts: dashboard-only warning (50%), desktop notification (20%), critical with bell (5%)
3. Zero impact on non-Ghostty terminals — module doesn't load at all

## Non-Goals

- Supporting other terminals' proprietary features (iTerm2 inline images, Sixel, etc.)
- Custom shaders or GPU-accelerated rendering
- Alert configuration in config.toml (fixed thresholds for now)
- Kitty image protocol / PNG gauge rendering (deferred — Textual's render pipeline does not pass raw escape sequences through its compositor, making this infeasible without significant hacks)
- Smooth gradient interpolation (stepped threshold colors are sufficient)

## Architecture

### File Structure

```
src/quota_dash/ghostty/
├── __init__.py
├── detect.py          # Ghostty detection
├── colors.py          # Threshold color calculation + widget injection
└── alerts.py          # Three-tier threshold alerts + OSC 9 notification
```

### Activation Flow

```
App.on_mount()
  → detect.is_ghostty() → True/False
  → if True:
      → colors.enhance_widgets(app)    # inject threshold colors
      → alerts.start_monitoring(app)   # start threshold monitoring
```

### Core Principles

1. **Zero intrusion** — core widgets never import ghostty module; ghostty depends on widgets, not the other way around
2. **Silent fallback** — non-Ghostty environment = module never loads, no errors

## Detection

```python
# ghostty/detect.py
import os

def is_ghostty() -> bool:
    return os.environ.get("TERM_PROGRAM") == "ghostty"
```

## Color Enhancement

### Gradient Calculation

Two color contexts, each mapping a 0.0-1.0 value to a color:

**Context A — Balance-oriented (QuotaCard)**:
- `> 0.5` → green `#22c55e` (plenty remaining)
- `0.2 ~ 0.5` → yellow `#eab308` (getting low)
- `< 0.2` → red `#ef4444` (critically low)

Semantics: high percentage = good (more money left)

**Context B — Usage-oriented (ContextCard)**:
- `< 0.5` → green `#22c55e` (plenty of room)
- `0.5 ~ 0.8` → yellow `#eab308` (filling up)
- `> 0.8` → red `#ef4444` (nearly full)

Semantics: high percentage = bad (running out of space)

### Injection Mechanism

```python
# ghostty/colors.py
def enhance_widgets(app: App) -> None:
    """Find ProgressBars in QuotaCard/ContextCard and watch their percentage."""
```

- Runs once at app mount
- Finds all `QuotaCard` and `ContextCard` instances via `app.query()`
- For each, locates the internal `ProgressBar`
- Sets up a `watch` on `ProgressBar.progress` (Textual reactive — note: `percentage` is a computed property, NOT reactive, so we watch `progress` and compute the ratio as `progress / total`)
- On each change, calculates threshold color and sets `bar.styles.color`

**Does NOT modify widget source code** — purely external style injection.

### Color Function

```python
def threshold_color(percentage: float, context: str) -> str:
    """Return hex color based on percentage and context type.

    Args:
        percentage: 0.0 to 1.0 (caller computes as progress/total)
        context: "balance" (high=good) or "usage" (high=bad)
    """
    if context == "balance":
        if percentage > 0.5:
            return "#22c55e"
        elif percentage > 0.2:
            return "#eab308"
        else:
            return "#ef4444"
    else:  # usage
        if percentage < 0.5:
            return "#22c55e"
        elif percentage < 0.8:
            return "#eab308"
        else:
            return "#ef4444"
```

## Alert System

### Three-Tier Thresholds

| Level | Condition | Actions |
|-------|-----------|---------|
| Warning | balance < 50% of limit | QuotaCard border turns yellow |
| Alert | balance < 20% of limit | QuotaCard border turns orange + OSC 9 desktop notification |
| Critical | balance < 5% of limit | QuotaCard border turns red + desktop notification + terminal bell |

### OSC 9 Desktop Notification

```python
import sys

def send_notification(message: str) -> None:
    # OSC 9 is a single message string (no title/body separation)
    sys.stdout.write(f"\x1b]9;{message}\x07")
    sys.stdout.flush()

def send_bell() -> None:
    sys.stdout.write("\x07")
    sys.stdout.flush()
```

Ghostty renders OSC 9 as a native macOS notification.

### Deduplication

- Tracks notified `set[tuple[str, str]]` of `(provider_name, alert_level)`
- Each (provider, level) combination fires only once
- When balance rises above a threshold, the corresponding entry is cleared (re-arms the alert)

### Monitoring

```python
# ghostty/alerts.py
class AlertMonitor:
    def __init__(self) -> None:
        self._notified: set[tuple[str, str]] = set()

    def check(self, app: App, store: DataStore) -> None:
        """Called after each _refresh_all(). Checks all providers."""
```

- Iterates all providers via `store.providers()`
- For each `QuotaInfo`, skips if `balance_usd is None or limit_usd is None or limit_usd == 0`
- Otherwise calculates `balance_usd / limit_usd`
- Triggers appropriate actions based on thresholds
- Modifies QuotaCard border color via `card.styles.border` (Textual inline styles override TCSS, so this takes precedence over the ghostty.tcss theme border)
- When alert clears (balance recovers above threshold), reset border by setting `card.styles.border = None` to restore TCSS default

### Integration Point

In `app.py`, after `_refresh_all()` completes:
```python
if self._alert_monitor:
    self._alert_monitor.check(self, self._store)
```

`_alert_monitor` is set to `AlertMonitor()` only when `is_ghostty()` returns True. Otherwise it's `None`.

## App Changes

Minimal changes to `app.py`:

```python
# In __init__:
self._alert_monitor: AlertMonitor | None = None

# In on_mount, after existing setup:
from quota_dash.ghostty.detect import is_ghostty
if is_ghostty():
    from quota_dash.ghostty.colors import enhance_widgets
    from quota_dash.ghostty.alerts import AlertMonitor
    enhance_widgets(self)
    self._alert_monitor = AlertMonitor()

# In _refresh_all, at the end:
if self._alert_monitor:
    self._alert_monitor.check(self, self._store)
```

All ghostty imports are lazy (inside `if is_ghostty()` block). Non-Ghostty users never import the module.

## Testing Strategy

- **detect.py**: mock `os.environ` to test `is_ghostty()`
- **colors.py**: unit test `threshold_color()` with boundary values; test `enhance_widgets()` in a Textual test app with mock Ghostty env
- **alerts.py**: test threshold logic with mock `DataStore`; test deduplication (same alert not fired twice); test re-arm when balance recovers; test skip when balance/limit is None
- **Integration**: test that non-Ghostty environment loads app without errors (no ghostty module side effects)

## Error Handling

- `is_ghostty()` returns False on any env var issue → no ghostty features
- OSC 9 output to non-Ghostty terminal → harmless (terminal ignores unknown escape sequences)
- Alert monitor exception → catch, log warning, skip alert check (don't crash app)
- `enhance_widgets()` exception → catch, log warning, colors stay default
