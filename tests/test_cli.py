import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from quota_dash.cli import main


SAMPLE_CONFIG = """\
[general]
polling_interval = 60
theme = "default"

[providers.openai]
enabled = true
api_key_env = "NONEXISTENT_KEY_FOR_TEST"
log_path = "/tmp/nonexistent"
balance_usd = 47.32
limit_usd = 100.0

[providers.anthropic]
enabled = true
api_key_env = "NONEXISTENT_KEY_FOR_TEST"
log_path = "/tmp/nonexistent"
balance_usd = 200.0
limit_usd = 500.0
"""


def test_cli_once_mode():
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        config_path = f.name

    result = runner.invoke(main, ["--once", "--config", config_path])
    assert result.exit_code == 0
    assert "openai" in result.output.lower() or "Quota" in result.output


def test_cli_once_json_mode():
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        config_path = f.name

    result = runner.invoke(main, ["--once", "--json", "--config", config_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "openai" in data
    assert "anthropic" in data


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "quota-dash" in result.output.lower() or "--once" in result.output


def test_cli_proxy_help():
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output
    assert "status" in result.output


def test_cli_proxy_status_not_running():
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "status"])
    assert result.exit_code == 0
    # Output is either "No proxy running." or "Proxy running (PID ...)" depending on environment
    assert "proxy" in result.output.lower() or "running" in result.output.lower()


def test_cli_proxy_status_mocked_not_running(monkeypatch):
    """Proxy status when daemon reports no process."""
    import quota_dash.proxy.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod, "proxy_status", lambda: None)
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "status"])
    assert result.exit_code == 0
    assert "No proxy" in result.output


def test_cli_proxy_status_mocked_running(monkeypatch):
    """Proxy status when daemon reports a running process."""
    import quota_dash.proxy.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod, "proxy_status", lambda: {"pid": 12345})
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "status"])
    assert result.exit_code == 0
    assert "12345" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "quota-dash" in result.output


def test_cli_config_init_help():
    runner = CliRunner()
    result = runner.invoke(main, ["config", "init", "--help"])
    assert result.exit_code == 0
    assert "wizard" in result.output.lower() or "Interactive" in result.output


def test_cli_config_init_creates_file(tmp_path):
    runner = CliRunner()
    output = tmp_path / "test_config.toml"
    wizard_input = "y\ny\n\n\n\n\n\n\n\n\n\ny\n8300\nn\n50\n20\n5\n"
    result = runner.invoke(
        main, ["config", "init", "--output", str(output)], input=wizard_input
    )
    assert result.exit_code == 0
    assert output.exists()


def test_cli_proxy_install_help():
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "install", "--help"])
    assert result.exit_code == 0
    assert "launchd" in result.output.lower() or "Install" in result.output


def test_cli_proxy_uninstall_no_service():
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "uninstall"])
    assert result.exit_code == 0
    assert "No proxy" in result.output or "uninstalled" in result.output.lower()


def test_cli_once_with_no_providers():
    """--once with empty config should print an empty table without error."""
    runner = CliRunner()
    result = runner.invoke(main, ["--once"])
    assert result.exit_code == 0


def test_cli_once_json_no_providers():
    """--once --json with empty config should output valid JSON (empty object)."""
    runner = CliRunner()
    result = runner.invoke(main, ["--once", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, dict)


def test_cli_once_provider_filter():
    """--provider filter with sample config should only show that provider."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        config_path = f.name

    result = runner.invoke(main, ["--once", "--json", "--provider", "openai", "--config", config_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "openai" in data
    assert "anthropic" not in data


def test_cli_once_provider_filter_table():
    """--provider filter with table output should succeed."""
    runner = CliRunner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        config_path = f.name

    result = runner.invoke(main, ["--once", "--provider", "anthropic", "--config", config_path])
    assert result.exit_code == 0


def test_cli_proxy_install_executes(tmp_path, monkeypatch):
    """proxy install should write a plist file and attempt launchctl load."""
    import subprocess

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Override home so plist goes into tmp_path
    launch_agents = tmp_path / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "install"])
    assert result.exit_code == 0
    assert "installed" in result.output.lower()
    plist_path = launch_agents / "com.quota-dash.proxy.plist"
    assert plist_path.exists()
    assert any("launchctl" in str(c) for c in calls)


def test_cli_proxy_uninstall_with_service(tmp_path, monkeypatch):
    """proxy uninstall removes the plist and calls launchctl unload."""
    import subprocess

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    launch_agents = tmp_path / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True)
    plist_path = launch_agents / "com.quota-dash.proxy.plist"
    plist_path.write_bytes(b"<plist/>")

    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "uninstall"])
    assert result.exit_code == 0
    assert "uninstalled" in result.output.lower()
    assert not plist_path.exists()
    assert any("launchctl" in str(c) for c in calls)
