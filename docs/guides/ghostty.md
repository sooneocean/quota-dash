# Ghostty Terminal Enhancements

quota-dash includes optional enhancements that activate automatically when running inside [Ghostty](https://ghostty.org). These features use capabilities specific to Ghostty and are silently skipped in other terminals so the dashboard remains fully functional everywhere.

## Detection

Detection is a single environment variable check:

```python
os.environ.get("TERM_PROGRAM") == "ghostty"
```

Ghostty sets `TERM_PROGRAM=ghostty` in every shell it launches. No user configuration is required — the enhancements activate automatically when this variable is present.

If you want to force Ghostty enhancements off while running inside Ghostty, unset the variable before launching:

```bash
TERM_PROGRAM= quota-dash
```

## Available Enhancements

When running in Ghostty, quota-dash activates two enhancement categories on `on_mount`:

1. **Threshold colors** — progress bars change color dynamically based on usage/balance levels
2. **Alert system** — desktop notifications and visual border changes when quotas fall below thresholds

Both enhancements are applied after the app mounts and are refreshed on every data poll cycle.

## Threshold Colors

The `QuotaCard` and `ContextCard` widgets each contain a `ProgressBar`. When Ghostty is detected, quota-dash injects reactive watchers on those bars that update their color as the value changes.

### Color Logic

| Context  | Threshold        | Color            | Hex       |
|----------|-----------------|------------------|-----------|
| balance  | > 50% remaining | Green (healthy)  | `#22c55e` |
| balance  | 20–50% remaining | Yellow (warning) | `#eab308` |
| balance  | < 20% remaining | Red (critical)   | `#ef4444` |
| usage    | < 50% used      | Green (healthy)  | `#22c55e` |
| usage    | 50–80% used     | Yellow (warning) | `#eab308` |
| usage    | > 80% used      | Red (critical)   | `#ef4444` |

**Balance context** (`QuotaCard` — `#quota-bar`): high values are good, so more remaining = greener.

**Usage context** (`ContextCard` — `#ctx-bar`): high values are bad, so more context window consumed = redder.

The color is recalculated on every progress change via a Textual reactive watcher, so it updates live as fresh data arrives from the poll cycle.

### Affected Widgets

- `QuotaCard` (`#quota-bar`) — balance remaining as a fraction of the limit
- `ContextCard` (`#ctx-bar`) — context window tokens used as a fraction of the model maximum

## Alert System

The `AlertMonitor` checks every provider's balance against three threshold levels on each poll cycle.

### Three Alert Tiers

| Level    | Balance ratio threshold | Actions                                        |
|----------|------------------------|------------------------------------------------|
| warning  | < 50% remaining        | Yellow border on `QuotaCard`                   |
| alert    | < 20% remaining        | Orange border + OSC 9 desktop notification     |
| critical | < 5% remaining         | Red border + OSC 9 desktop notification + bell |

### Notification Behavior

**OSC 9 desktop notification** (alert and critical):

```
quota-dash: anthropic balance at 18%
```

This uses the OSC 9 escape sequence (`\x1b]9;<message>\x07`), which Ghostty renders as a native desktop notification through the OS notification system.

**Terminal bell** (critical only):

An ASCII BEL character (`\x07`) is emitted, triggering Ghostty's bell handling (visual flash or system alert depending on your Ghostty config).

**Border color on `QuotaCard`**:

| Level    | Border color |
|----------|-------------|
| warning  | yellow      |
| alert    | darkorange  |
| critical | red         |

### One-Shot Notifications

Each (provider, level) pair triggers a notification at most once per dashboard session. Once the alert fires, it is recorded in an internal set and will not repeat on subsequent polls — avoiding notification spam during a long session.

When the balance recovers above all thresholds (e.g., after a top-up), the provider's alert history is cleared. The next time the balance drops below a threshold, notifications will fire again.

### No-Config Required

The alert system requires no configuration. It activates whenever Ghostty is detected and quota data with both `balance_usd` and `limit_usd` is available (from config `balance_usd`/`limit_usd` values or from the API). Providers without limit data are silently skipped.
