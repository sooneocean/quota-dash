# tests/test_proxy_daemon.py
"""Tests for proxy/daemon.py — start_proxy, stop_proxy, proxy_status."""
from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock, patch

import pytest

from quota_dash.proxy.daemon import proxy_status, stop_proxy, start_proxy


# ---------------------------------------------------------------------------
# proxy_status
# ---------------------------------------------------------------------------

def test_proxy_status_no_pid_file(tmp_path):
    """proxy_status returns None when PID file does not exist."""
    missing = tmp_path / "nonexistent.pid"
    with patch("quota_dash.proxy.daemon._pid_path", return_value=missing):
        result = proxy_status()
    assert result is None


def test_proxy_status_with_live_process(tmp_path):
    """proxy_status returns dict when PID file exists and process is alive."""
    pid_file = tmp_path / "proxy.pid"
    pid = os.getpid()  # Use our own PID — it's definitely running
    pid_file.write_text(str(pid))

    with patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file):
        result = proxy_status()

    assert result is not None
    assert result["pid"] == pid
    assert "pid_file" in result


def test_proxy_status_with_stale_pid_file(tmp_path):
    """proxy_status returns None when PID file exists but process is dead."""
    pid_file = tmp_path / "proxy.pid"
    # Use a PID that definitely doesn't exist (very high value)
    pid_file.write_text("9999999")

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("os.kill", side_effect=OSError("no such process")),
    ):
        result = proxy_status()

    assert result is None


# ---------------------------------------------------------------------------
# stop_proxy
# ---------------------------------------------------------------------------

def test_stop_proxy_no_pid_file(tmp_path):
    """stop_proxy returns False when PID file does not exist."""
    missing = tmp_path / "nonexistent.pid"
    with patch("quota_dash.proxy.daemon._pid_path", return_value=missing):
        result = stop_proxy()
    assert result is False


def test_stop_proxy_sends_sigterm(tmp_path):
    """stop_proxy sends SIGTERM to the PID and returns True."""
    pid_file = tmp_path / "proxy.pid"
    pid_file.write_text("12345")

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("os.kill") as mock_kill,
    ):
        result = stop_proxy()

    assert result is True
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)
    # PID file should be removed
    assert not pid_file.exists()


def test_stop_proxy_cleans_stale_pid_file(tmp_path):
    """stop_proxy cleans up stale PID file and returns False when process not found."""
    pid_file = tmp_path / "proxy.pid"
    pid_file.write_text("12345")

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("os.kill", side_effect=OSError("no such process")),
    ):
        result = stop_proxy()

    assert result is False
    # PID file should be removed
    assert not pid_file.exists()


# ---------------------------------------------------------------------------
# start_proxy
# ---------------------------------------------------------------------------

def test_start_proxy_exits_if_already_running(tmp_path):
    """start_proxy exits with SystemExit if PID file exists and process is alive."""
    pid_file = tmp_path / "proxy.pid"
    pid = os.getpid()
    pid_file.write_text(str(pid))

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("os.kill"),  # pretend the process exists
        pytest.raises(SystemExit),
    ):
        start_proxy(port=8300, db_path=tmp_path / "usage.db")


def test_start_proxy_cleans_stale_pid_and_starts(tmp_path):
    """start_proxy removes stale PID file and proceeds to run uvicorn."""
    pid_file = tmp_path / "proxy.pid"
    pid_file.write_text("99999999")  # stale

    mock_app = MagicMock()

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("os.kill", side_effect=OSError("no such process")),
        patch("quota_dash.proxy.daemon.create_proxy_app", return_value=mock_app),
        patch("quota_dash.proxy.daemon.uvicorn.run") as mock_run,
        patch("logging.basicConfig"),
    ):
        start_proxy(port=8301, db_path=tmp_path / "usage.db", foreground=False)

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    port_passed = (
        call_args.kwargs.get("port") == 8301
        or (len(call_args.args) > 1 and call_args.args[1] == 8301)
    )
    assert port_passed


def test_start_proxy_no_existing_pid_file(tmp_path):
    """start_proxy writes PID file and runs uvicorn when no existing PID file."""
    pid_file = tmp_path / "proxy.pid"
    # pid_file does NOT exist

    mock_app = MagicMock()

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("quota_dash.proxy.daemon.create_proxy_app", return_value=mock_app),
        patch("quota_dash.proxy.daemon.uvicorn.run") as mock_run,
        patch("logging.basicConfig"),
    ):
        start_proxy(port=8302, db_path=tmp_path / "usage.db")

    mock_run.assert_called_once()
    # PID file cleaned up in the finally block
    assert not pid_file.exists()


def test_start_proxy_cleanup_pid_on_uvicorn_exception(tmp_path):
    """PID file is removed even if uvicorn raises an exception."""
    pid_file = tmp_path / "proxy.pid"

    mock_app = MagicMock()

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("quota_dash.proxy.daemon.create_proxy_app", return_value=mock_app),
        patch("quota_dash.proxy.daemon.uvicorn.run", side_effect=RuntimeError("boom")),
        patch("logging.basicConfig"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        start_proxy(port=8303, db_path=tmp_path / "usage.db")

    # Finally block should have removed the PID file
    assert not pid_file.exists()


def test_start_proxy_passes_config_targets(tmp_path):
    """start_proxy forwards config_targets and target_filter to create_proxy_app."""
    pid_file = tmp_path / "proxy.pid"
    mock_app = MagicMock()

    with (
        patch("quota_dash.proxy.daemon._pid_path", return_value=pid_file),
        patch("quota_dash.proxy.daemon.create_proxy_app", return_value=mock_app) as mock_create,
        patch("quota_dash.proxy.daemon.uvicorn.run"),
        patch("logging.basicConfig"),
    ):
        start_proxy(
            port=8304,
            db_path=tmp_path / "usage.db",
            config_targets={"openai": "http://myproxy"},
            target_filter="openai",
        )

    mock_create.assert_called_once()
    _, kwargs = mock_create.call_args
    assert kwargs["config_targets"] == {"openai": "http://myproxy"}
    assert kwargs["target_filter"] == "openai"
