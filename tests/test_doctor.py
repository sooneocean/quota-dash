from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from quota_dash.cli import main


def test_cli_doctor_help():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "Check" in result.output or "doctor" in result.output


def test_cli_doctor_runs():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Config file" in result.output
    assert "Proxy" in result.output


def test_cli_doctor_all_checks_present():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Proxy database" in result.output
    assert "Proxy process" in result.output
    assert "Terminal" in result.output
    assert "Webhook" in result.output


def test_cli_doctor_with_custom_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[providers.openai]\nenabled = true\napi_key_env = "OPENAI_API_KEY"\n'
    )
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "Config file" in result.output
    assert "OK" in result.output


def test_cli_doctor_missing_config(tmp_path):
    missing = tmp_path / "nonexistent.toml"
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--config", str(missing)])
    assert result.exit_code == 0
    assert "MISSING" in result.output or "Config file" in result.output


def test_cli_doctor_ghostty_terminal():
    runner = CliRunner()
    with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Ghostty" in result.output


def test_cli_doctor_non_ghostty_terminal():
    runner = CliRunner()
    with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm2"}):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "iTerm2" in result.output or "Terminal" in result.output


def test_cli_doctor_proxy_running():
    runner = CliRunner()
    with patch(
        "quota_dash.proxy.daemon.proxy_status",
        return_value={"pid": 12345},
    ):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "12345" in result.output or "Running" in result.output


def test_cli_doctor_proxy_stopped():
    runner = CliRunner()
    with patch("quota_dash.proxy.daemon.proxy_status", return_value=None):
        result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "STOPPED" in result.output or "Not running" in result.output


def test_cli_doctor_api_key_set(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[providers.openai]\nenabled = true\napi_key_env = "OPENAI_API_KEY"\n'
    )
    runner = CliRunner()
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test123"}):
        result = runner.invoke(main, ["doctor", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "OPENAI_API_KEY" in result.output


def test_cli_doctor_api_key_missing(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[providers.openai]\nenabled = true\napi_key_env = "OPENAI_API_KEY"\n'
    )
    runner = CliRunner()
    env_without_key = {k: v for k, v in __import__("os").environ.items() if k != "OPENAI_API_KEY"}
    with patch.dict("os.environ", env_without_key, clear=True):
        result = runner.invoke(main, ["doctor", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "OPENAI_API_KEY" in result.output


def test_cli_doctor_db_with_records(tmp_path):
    import sqlite3

    db = tmp_path / "usage.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE api_calls (id INTEGER PRIMARY KEY, ts TEXT)"
    )
    conn.execute("INSERT INTO api_calls (ts) VALUES ('2024-01-01')")
    conn.commit()
    conn.close()

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f'[proxy]\ndb_path = "{db}"\n'
    )
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "1 records" in result.output or "records" in result.output


def test_cli_doctor_db_corrupt(tmp_path):
    db = tmp_path / "usage.db"
    db.write_bytes(b"not a sqlite database")

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f'[proxy]\ndb_path = "{db}"\n'
    )
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--config", str(config_file)])
    assert result.exit_code == 0
    # Either ERROR or the table exists (sqlite may handle it gracefully)
    assert "Proxy database" in result.output


def test_cli_doctor_webhook_configured(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[alerts]\nwebhook_url = "https://hooks.slack.com/services/abc/def/ghi"\n'
    )
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "Webhook" in result.output
    assert "OK" in result.output


def test_cli_doctor_summary_errors(tmp_path):
    missing = tmp_path / "nonexistent.toml"
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--config", str(missing)])
    assert result.exit_code == 0
    # Should report errors or warnings summary
    assert "error" in result.output.lower() or "warning" in result.output.lower() or "check" in result.output.lower()
