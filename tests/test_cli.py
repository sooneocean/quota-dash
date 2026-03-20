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
