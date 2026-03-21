# Real-Time Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add event-driven SQLite file watching so dashboard updates instantly when proxy writes new data.

**Architecture:** `DBWatcher` uses `watchfiles.awatch()` to monitor proxy SQLite DB. On file change, triggers `_refresh_all()` via callback. Coexists with existing polling.

**Tech Stack:** watchfiles (re-added dependency), Textual workers

**Spec:** `docs/specs/2026-03-21-realtime-monitoring.md`

---

### Task 1: DBWatcher Module

**Files:**
- Create: `src/quota_dash/data/watcher.py`
- Create: `tests/test_watcher.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add watchfiles dependency to pyproject.toml**

Add `"watchfiles>=0.21.0"` to the dependencies list. Run `pip install -e ".[dev]"`.

- [ ] **Step 2: Write failing test**

```python
# tests/test_watcher.py
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from quota_dash.data.watcher import DBWatcher


@pytest.fixture
def db_file(tmp_path):
    f = tmp_path / "test.db"
    f.write_text("init")
    return f


@pytest.mark.asyncio
async def test_watcher_detects_file_change(db_file):
    callback = MagicMock()
    watcher = DBWatcher(db_path=db_file, callback=callback)

    # Start watcher in background
    task = asyncio.create_task(watcher.start())
    await asyncio.sleep(0.3)

    # Modify the file
    db_file.write_text("changed")
    await asyncio.sleep(1.5)  # wait for debounce + detection

    watcher.stop()
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert callback.call_count >= 1


@pytest.mark.asyncio
async def test_watcher_stop_before_start():
    watcher = DBWatcher(db_path=Path("/tmp/nonexistent.db"), callback=lambda: None)
    watcher.stop()  # should not raise


@pytest.mark.asyncio
async def test_watcher_callback_exception(db_file):
    """Callback exception should not crash the watcher."""
    def bad_callback():
        raise RuntimeError("boom")

    watcher = DBWatcher(db_path=db_file, callback=bad_callback)
    task = asyncio.create_task(watcher.start())
    await asyncio.sleep(0.3)

    db_file.write_text("trigger")
    await asyncio.sleep(1.5)

    # Watcher should still be alive (not crashed)
    watcher.stop()
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # If we got here, the watcher didn't crash — test passes
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_watcher.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 4: Implement watcher.py**

```python
# src/quota_dash/data/watcher.py
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class DBWatcher:
    """Watch a SQLite DB file for changes and trigger a callback."""

    def __init__(self, db_path: Path, callback: Callable[[], None]) -> None:
        self._db_path = db_path
        self._callback = callback
        self._should_stop = False

    async def start(self) -> None:
        """Start watching. Blocks until stop() is called."""
        try:
            from watchfiles import awatch, Change
        except ImportError:
            logger.warning("watchfiles not installed — file watching disabled")
            return

        # Watch both the DB file and its WAL file
        watch_path = self._db_path.parent
        db_name = self._db_path.name
        wal_name = f"{db_name}-wal"

        logger.info("Watching %s for changes", self._db_path)

        try:
            async for changes in awatch(
                watch_path,
                debounce=500,
                stop_event=self._make_stop_event(),
            ):
                # Filter to only our DB files
                relevant = any(
                    Path(path).name in (db_name, wal_name)
                    for _, path in changes
                )
                if relevant:
                    try:
                        self._callback()
                    except Exception:
                        logger.exception("Watcher callback failed")
        except Exception:
            if not self._should_stop:
                logger.exception("File watcher error")

    def stop(self) -> None:
        """Signal the watcher to stop."""
        self._should_stop = True

    def _make_stop_event(self) -> asyncio.Event:
        """Create an event that is set when stop() is called."""
        event = asyncio.Event()
        original_stop = self.stop

        def enhanced_stop() -> None:
            original_stop()
            event.set()

        self.stop = enhanced_stop  # type: ignore
        return event
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_watcher.py -v`
Expected: All 3 PASS

- [ ] **Step 6: Commit**

```bash
cd quota-dash && git add pyproject.toml src/quota_dash/data/watcher.py tests/test_watcher.py && git commit -m "feat: DBWatcher for event-driven SQLite file monitoring"
```

---

### Task 2: App Integration

**Files:**
- Modify: `src/quota_dash/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_app.py
@pytest.mark.asyncio
async def test_app_watcher_not_started_without_db():
    """No proxy DB = no watcher."""
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        assert app._watcher is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_app.py::test_app_watcher_not_started_without_db -v`
Expected: FAIL — `AttributeError: '_watcher'`

- [ ] **Step 3: Modify app.py**

In `__init__`, add after `self._alert_monitor = None`:
```python
        self._watcher = None
```

In `on_mount`, add after the Ghostty setup block:
```python
        # Start file watcher if proxy DB exists
        if self._config.proxy.db_path.exists():
            try:
                from quota_dash.data.watcher import DBWatcher
                self._watcher = DBWatcher(
                    db_path=self._config.proxy.db_path,
                    callback=lambda: self.run_worker(self._refresh_all()),
                )
                self.run_worker(self._watcher.start())
            except Exception:
                pass
```

Add `on_unmount` method:
```python
    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()
```

- [ ] **Step 4: Run all app tests**

Run: `cd quota-dash && pytest tests/test_app.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd quota-dash && pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd quota-dash && git add src/quota_dash/app.py tests/test_app.py && git commit -m "feat: integrate DBWatcher into app for real-time proxy updates"
```

---

### Task 3: Final Verification

- [ ] **Step 1: Full test suite**

```bash
cd quota-dash && pytest tests/ -v --tb=short
```

- [ ] **Step 2: Verify build**

```bash
cd quota-dash && python -m build
```

- [ ] **Step 3: Push**

```bash
cd quota-dash && git push
```
