from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

import uvicorn

from quota_dash.proxy.app import create_proxy_app

logger = logging.getLogger(__name__)


def _pid_path() -> Path:
    return Path.home() / ".config" / "quota-dash" / "proxy.pid"


def start_proxy(
    port: int = 8300,
    db_path: Path | None = None,
    log_path: Path | None = None,
    config_targets: dict[str, str] | None = None,
    target_filter: str | None = None,
    foreground: bool = False,
) -> None:
    db = db_path or Path.home() / ".config" / "quota-dash" / "usage.db"
    log = log_path or Path.home() / ".config" / "quota-dash" / "proxy.log"

    # Check if already running
    pid_file = _pid_path()
    if pid_file.exists():
        old_pid = int(pid_file.read_text().strip())
        try:
            os.kill(old_pid, 0)
            print(f"Proxy already running (PID {old_pid}). Use 'quota-dash proxy stop' first.")
            sys.exit(1)
        except OSError:
            pid_file.unlink()

    # Setup logging
    log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Write PID
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))

    app = create_proxy_app(db_path=db, config_targets=config_targets, target_filter=target_filter)

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        if pid_file.exists():
            pid_file.unlink()


def stop_proxy() -> bool:
    pid_file = _pid_path()
    if not pid_file.exists():
        print("No proxy running (PID file not found).")
        return False

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Proxy stopped (PID {pid}).")
        pid_file.unlink()
        return True
    except OSError:
        print(f"Process {pid} not found. Cleaning up stale PID file.")
        pid_file.unlink()
        return False


def proxy_status() -> dict | None:
    pid_file = _pid_path()
    if not pid_file.exists():
        return None

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, 0)
        return {"pid": pid, "pid_file": str(pid_file)}
    except OSError:
        return None
