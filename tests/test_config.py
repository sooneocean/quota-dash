import os
import tempfile
from pathlib import Path

from quota_dash.config import load_config, AppConfig, ProviderConfig, ProxyConfig


SAMPLE_TOML = """\
[general]
polling_interval = 30
theme = "ghostty"
mode = "dashboard"

[providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"
log_path = "~/.codex/"

[providers.anthropic]
enabled = false
api_key_env = "ANTHROPIC_API_KEY"
log_path = "~/.claude/"
"""


def test_load_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_TOML)
        f.flush()
        config = load_config(Path(f.name))
    os.unlink(f.name)

    assert config.polling_interval == 30
    assert config.theme == "ghostty"
    assert config.mode == "dashboard"
    assert "openai" in config.providers
    assert config.providers["openai"].enabled is True
    assert config.providers["anthropic"].enabled is False


def test_load_config_defaults():
    config = load_config(None)
    assert config.polling_interval == 60
    assert config.theme == "auto"
    assert config.mode == "dashboard"
    assert config.providers == {}


def test_provider_config_log_path_expanded():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_TOML)
        f.flush()
        config = load_config(Path(f.name))
    os.unlink(f.name)

    assert "~" not in str(config.providers["openai"].log_path)


PROXY_TOML = """\
[general]
polling_interval = 60

[proxy]
enabled = true
port = 9000
db_path = "~/.config/quota-dash/usage.db"
log_path = "~/.config/quota-dash/proxy.log"

[proxy.targets]
openai = "https://api.openai.com"
anthropic = "https://api.anthropic.com"

[providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"
log_path = "~/.codex/"
"""


def test_load_proxy_config():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(PROXY_TOML)
        f.flush()
        config = load_config(Path(f.name))
    os.unlink(f.name)
    assert config.proxy.enabled is True
    assert config.proxy.port == 9000
    assert "openai" in config.proxy.targets
    assert "~" not in str(config.proxy.db_path)


def test_load_config_proxy_defaults():
    config = load_config(None)
    assert config.proxy.enabled is False
    assert config.proxy.port == 8300
    assert config.proxy.targets["openai"] == "https://api.openai.com"


def test_load_config_alert_defaults():
    config = load_config(None)
    assert config.alerts.warning == 50
    assert config.alerts.alert == 20
    assert config.alerts.critical == 5
