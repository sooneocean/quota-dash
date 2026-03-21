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
            from watchfiles import awatch
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
