# quota-dash v0.6.0: Real-Time Monitoring — Design Spec

> Event-driven SQLite file watching for instant dashboard updates when proxy captures new API calls.

## Overview

Add a `DBWatcher` that monitors the proxy SQLite database file for changes using `watchfiles`. When the proxy writes a new API call record, the watcher detects the file change and triggers a full dashboard refresh within milliseconds — no polling delay. Coexists with existing interval-based polling (which continues to handle billing API queries on its normal schedule).

## Goals

1. Dashboard updates instantly when proxy captures a new API call
2. Zero changes to proxy code — watcher observes the SQLite file externally
3. Coexist with existing polling (polling for billing, watcher for proxy data)
4. Debounce rapid file changes (500ms window)

## Non-Goals

- Replacing polling entirely (billing APIs still need periodic queries)
- Watching for proxy DB creation at runtime (requires dashboard restart)
- Custom IPC between proxy and dashboard (Unix sockets, named pipes, etc.)
- WebSocket or HTTP push from proxy to dashboard

## Architecture

```
Proxy daemon
    │ writes to SQLite (usage.db / usage.db-wal)
    ▼
File system event (macOS FSEvents / Linux inotify)
    │
    ▼
DBWatcher (watchfiles.awatch, runs in Textual worker)
    │ debounce 500ms
    ▼
App._refresh_all()  ← same as manual 'r' key or polling
```

### Coexistence

| Mechanism | Purpose | Frequency |
|-----------|---------|-----------|
| `set_interval` polling | Billing API, manual config refresh | Every 60s (configurable) |
| `DBWatcher` file watch | Proxy SQLite changes | Event-driven, instant |

Both trigger `_refresh_all()`, which is idempotent. Concurrent triggers are harmless.

## New File

```
src/quota_dash/data/watcher.py    # DBWatcher class
tests/test_watcher.py             # Unit tests
```

## DBWatcher Specification

```python
# data/watcher.py
class DBWatcher:
    def __init__(self, db_path: Path, callback: Callable[[], None]) -> None:
        """
        Args:
            db_path: Path to usage.db. Also watches usage.db-wal.
            callback: Called when file changes detected. Must be sync (e.g. lambda wrapping run_worker).
        """

    async def start(self) -> None:
        """Start watching. Runs forever until stop() is called.
        Uses watchfiles.awatch() with 500ms debounce."""

    def stop(self) -> None:
        """Signal the watcher to stop. Safe to call multiple times."""
```

### Watch Targets

- `{db_path}` — the main SQLite database file
- `{db_path}-wal` — SQLite WAL file (written to on every INSERT in WAL mode)

Both must be watched because SQLite in WAL mode may only modify the WAL file without touching the main DB until checkpoint.

### Debounce

`watchfiles.awatch()` accepts a `debounce` parameter (milliseconds). Set to `500` to batch rapid writes (e.g., streaming responses that produce multiple records quickly) into a single refresh.

### Error Handling

- `watchfiles` import fails → log warning, watcher not started (dashboard falls back to polling only)
- Watched file deleted → watcher stops gracefully, log warning
- Callback exception → catch and log, do not crash watcher loop
- `stop()` called before `start()` → no-op

## App Integration

### on_mount changes

After existing `self.set_interval(...)` and Ghostty setup:

```python
# Start file watcher if proxy DB exists
self._watcher = None
if self._config.proxy.db_path.exists():
    try:
        from quota_dash.data.watcher import DBWatcher
        self._watcher = DBWatcher(
            db_path=self._config.proxy.db_path,
            callback=lambda: self.run_worker(self._refresh_all()),
        )
        self.run_worker(self._watcher.start())
    except Exception:
        pass  # watcher is optional enhancement
```

### on_unmount changes (new method)

```python
def on_unmount(self) -> None:
    if self._watcher:
        self._watcher.stop()
```

### No other changes

- `_refresh_all()` — unchanged (already does full refresh)
- Widgets — unchanged
- Proxy — unchanged
- Config — unchanged

## Dependency

Re-add `watchfiles` to `pyproject.toml`:

```toml
"watchfiles>=0.21.0",
```

This was in the original spec but removed during v0.2 when file watching was deferred to polling.

## Testing Strategy

- **Unit test**: `DBWatcher` with a temp SQLite file — write to file, assert callback is called
- **Unit test**: `DBWatcher.stop()` before `start()` — no error
- **Unit test**: missing `watchfiles` import — graceful fallback (mock import failure)
- **Integration test**: app with watcher — verify watcher starts when DB exists, doesn't start when DB missing
