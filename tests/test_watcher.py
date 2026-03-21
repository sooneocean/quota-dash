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
