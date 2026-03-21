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
    assert "not running" in result.output.lower() or "No proxy" in result.output


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
    result = runner.invoke(main, ["config", "init", "--output", str(output)], input="y\ny\n\n\n\nn\nn\nn\ny\n8300\nn\n50\n20\n5\n")
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
