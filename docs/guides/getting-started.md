# Getting Started

This guide walks you through installing quota-dash, running it for the first time, and configuring it for your providers.

## System Requirements

- **Python 3.11 or later**
- macOS, Linux, or any POSIX system (Windows is untested)
- A terminal emulator (Ghostty recommended for full feature set; any modern terminal works)
- API credentials for the providers you want to monitor

## Installation

### From PyPI (recommended)

```bash
pip install quota-dash
```

Verify the installation:

```bash
quota-dash --version
```

### From Source

```bash
git clone https://github.com/sooneocean/quota-dash.git
cd quota-dash
pip install -e .
```

To also install development dependencies:

```bash
pip install -e ".[dev]"
```

## First Run

Run a one-shot query to confirm everything is working before launching the dashboard:

```bash
quota-dash --once
```

This fetches quota and token data from all configured providers and prints a summary table. Pass `--json` for machine-readable output:

```bash
quota-dash --once --json
```

Launch the interactive dashboard:

```bash
quota-dash
```

Use `q` to quit, `r` to refresh manually, arrow keys to navigate providers, and `?` to show the keybinding help overlay.

## Configuration File

quota-dash reads its configuration from `~/.config/quota-dash/config.toml`. The file is optional — without it, the app starts with defaults and no providers configured (all data will show as unavailable).

Create the directory and file:

```bash
mkdir -p ~/.config/quota-dash
touch ~/.config/quota-dash/config.toml
```

### Full config.toml Example

```toml
# ~/.config/quota-dash/config.toml

[general]
# How often the dashboard polls providers, in seconds.
polling_interval = 60

# Theme: "auto" detects Ghostty and applies Ghostty CSS; "default" or "ghostty" force a theme.
theme = "auto"

# Dashboard mode (currently only "dashboard" is implemented).
mode = "dashboard"

# ─── Providers ────────────────────────────────────────────────────────────────

[providers.openai]
enabled = true

# Name of the environment variable that holds your OpenAI API key.
api_key_env = "OPENAI_API_KEY"

# Optional: path to Codex CLI log directory (for offline token parsing).
# Defaults to $HOME. Codex stores logs at <log_path>/logs_1.sqlite.
log_path = "~"

# Optional: manual quota fallback when the API is unreachable.
# balance_usd is your current prepaid credit balance.
# limit_usd is your monthly/total spend cap.
balance_usd = 50.00
limit_usd   = 100.00

[providers.anthropic]
enabled = true

# Anthropic does not expose a balance API; use manual values.
# Leave these unset if you do not want quota bars shown.
balance_usd = 25.00
limit_usd   = 50.00

# Path to the Claude CLI data directory (for offline JSONL cost log parsing).
# Claude CLI writes metrics/costs.jsonl inside this directory.
log_path = "~/.claude"

# ─── Proxy ────────────────────────────────────────────────────────────────────

[proxy]
# Set to true to auto-enable proxy features without needing --with-proxy.
enabled = false

# Port the local proxy listens on.
port = 8300

# SQLite database where API call history is stored.
db_path = "~/.config/quota-dash/usage.db"

# Proxy process log file.
log_path = "~/.config/quota-dash/proxy.log"

# Override upstream API base URLs (useful for private deployments or testing).
[proxy.targets]
openai    = "https://api.openai.com"
anthropic = "https://api.anthropic.com"
```

### Minimal config.toml

If you only want to monitor Anthropic with manual quota values:

```toml
[providers.anthropic]
balance_usd = 25.00
limit_usd   = 50.00
log_path    = "~/.claude"
```

## Provider Setup

### OpenAI

Export your API key so quota-dash can query the usage API:

```bash
export OPENAI_API_KEY="sk-..."
```

Set `api_key_env = "OPENAI_API_KEY"` in `[providers.openai]` (this is the default). The provider will call the OpenAI usage API to retrieve today's spend. If the API call fails, it falls back to manual `balance_usd`/`limit_usd` values from the config, and then to Codex CLI log parsing.

### Anthropic

Anthropic does not provide a public balance/usage API. Set manual values in config:

```toml
[providers.anthropic]
balance_usd = 25.00
limit_usd   = 50.00
log_path    = "~/.claude"
```

Token usage is read from the Claude CLI cost log at `<log_path>/metrics/costs.jsonl`. When the proxy is running, token data comes from live API response interception instead — see [proxy-guide.md](proxy-guide.md).

### Data Source Priority

For each metric, providers use the highest-quality source available:

| Priority | Source  | Description                                |
|----------|---------|--------------------------------------------|
| 1        | proxy   | Live token counts from intercepted responses |
| 2        | api     | OpenAI usage API (quota only)              |
| 3        | log     | Claude CLI JSONL or Codex SQLite logs      |
| 4        | manual  | `balance_usd` / `limit_usd` from config   |
| 5        | unavailable | No data available                      |

The `source` column in the dashboard and `--once` output shows which source is active.

## Next Steps

- [proxy-guide.md](proxy-guide.md) — Enable the local proxy for real-time token tracking
- [ghostty.md](ghostty.md) — Learn about Ghostty terminal enhancements
- [../architecture.md](../architecture.md) — Understand the system architecture
