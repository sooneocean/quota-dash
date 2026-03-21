# quota-dash: Feature Polish — Design Spec

> Configurable alert thresholds, config init wizard, proxy auto-start + launchd install.

## Features

### 1. Configurable Alert Thresholds

**Config**:
```toml
[alerts]
warning = 50
alert = 20
critical = 5
```

**New model**: `AlertConfig(warning=50, alert=20, critical=5)` dataclass in `config.py`. `AppConfig` gains `alerts: AlertConfig` field. `load_config` parses `[alerts]` section with defaults.

**alerts.py change**: `AlertMonitor.__init__(self, thresholds: AlertConfig)` reads thresholds from config instead of hardcoded `THRESHOLDS` list. App passes `config.alerts` when constructing `AlertMonitor`.

### 2. Config Init Wizard

**CLI command**: `quota-dash config init`

Interactive click.prompt flow:
1. Select providers (openai, anthropic, google, groq, mistral)
2. For each: API key env var name, optional balance/limit
3. Proxy: enable? port?
4. Alerts: warning/alert/critical thresholds
5. Write `~/.config/quota-dash/config.toml` using `tomli_w.dumps()`

If file exists, prompt to overwrite.

### 3. Proxy Auto-Start

**Config addition**: `[proxy] auto_start = false`

**ProxyConfig change**: Add `auto_start: bool = False` field.

**Dashboard behavior**: In `app.py` `on_mount`, check `config.proxy.auto_start`. If True, start proxy subprocess (same logic as `--with-proxy`). The `--with-proxy` CLI flag continues to work as override.

**launchd install**: `quota-dash proxy install`
- Generates `~/Library/LaunchAgents/com.quota-dash.proxy.plist`
- `RunAtLoad = true`, `KeepAlive = true`
- Runs `quota-dash proxy start --port {port}`
- Calls `launchctl load` to activate

**launchd uninstall**: `quota-dash proxy uninstall`
- Calls `launchctl unload`
- Removes plist file

## File Changes

```
src/quota_dash/config.py           # +AlertConfig, +auto_start on ProxyConfig
src/quota_dash/ghostty/alerts.py   # thresholds from AlertConfig
src/quota_dash/app.py              # auto_start logic
src/quota_dash/cli.py              # config init, proxy install/uninstall
tests/test_config.py               # +AlertConfig tests
tests/test_ghostty_alerts.py       # +configurable threshold tests
tests/test_cli.py                  # +config init, proxy install/uninstall tests
```

## Non-Goals

- Linux systemd service generation (macOS launchd only for now)
- Config migration from older versions
- GUI config editor
