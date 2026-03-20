# quota-dash

Terminal dashboard for monitoring LLM API quota and token usage across multiple providers.

```
┌──────────────────────┬──────────────────────────────────────────────┐
│ PROVIDERS            │                                              │
│                      │ Quota: $50.00 / $100.00  ██████████░░░░ 50% │
│   ▸ openai           │                                              │
│     anthropic        │ ──────────────────────────────────────────── │
│                      │                                              │
│ QUICK STATS          │ Tokens (session)                             │
│   Total: $50.00      │   Total:     2.5M  █▂▅▂                     │
│   Today: -$0.00      │   Total: 2.5M  [log]                        │
│                      │ ──────────────────────────────────────────── │
│                      │                                              │
│                      │ Context Window (gpt-4)                       │
│                      │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%       │
│                      │   0 / 128K                                   │
├──────────────────────┴──────────────────────────────────────────────┤
│ q Quit  r Refresh  ? Help                              ^p palette  │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-provider** — OpenAI and Anthropic in one view
- **TUI dashboard** — real-time polling with Textual, keyboard navigation
- **CLI mode** — one-shot table or JSON output for scripts
- **Token tracking** — reads Codex SQLite DB and Claude costs.jsonl
- **Connectivity check** — verify API keys and log paths before use
- **Themes** — auto-detect Ghostty terminal, or use default theme

## Requirements

- Python 3.11+
- (Optional) OpenAI API key with org-level admin permissions
- (Optional) Codex CLI installed (`~/.codex/`)
- (Optional) Claude CLI installed (`~/.claude/`)

## Installation

```bash
git clone https://github.com/redredchen01/quota-dash.git
cd quota-dash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

### 1. Create config

```bash
quota-dash --init
```

This copies a default config to `~/.config/quota-dash/config.toml`. Edit it:

```bash
vim ~/.config/quota-dash/config.toml
```

### 2. Configure providers

```toml
[general]
polling_interval = 60    # seconds between refreshes
theme = "auto"           # "auto", "default", or "ghostty"

[providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"   # env var name containing your key
log_path = "~/.codex"            # Codex CLI data directory

# Manual fallback (used when API is unavailable)
# balance_usd = 50.00
# limit_usd = 100.00

[providers.anthropic]
enabled = true
log_path = "~/.claude"           # Claude CLI data directory

# Anthropic has no public usage API — quota is manual only
balance_usd = 100.00
limit_usd = 200.00
```

### 3. Set your API key

```bash
export OPENAI_API_KEY="sk-..."
```

### 4. Verify connectivity

```bash
quota-dash --check
```

Output:

```
openai
  API connection: OK — API key valid
  Codex state DB: found — /Users/you/.codex/state_5.sqlite

anthropic
  costs.jsonl:    found — /Users/you/.claude/metrics/costs.jsonl
  Manual quota:   configured — $100.00
```

### 5. Launch

```bash
# TUI dashboard (default)
quota-dash

# One-shot table
quota-dash --once

# JSON output (for scripts / piping)
quota-dash --once --json

# Single provider only
quota-dash --provider openai
```

## Usage

### TUI Keybindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all providers |
| `↑` / `↓` | Switch provider |
| `Tab` | Focus next panel |
| `?` | Show help |

### CLI Options

```
Usage: quota-dash [OPTIONS]

Options:
  --once           One-shot query, print and exit
  --json           Output as JSON (with --once)
  --provider TEXT   Show only this provider
  --theme TEXT      Force theme: default | ghostty
  --config PATH    Config file path
  --init           Create default config file
  --check          Test provider connectivity
  --help           Show this message and exit
```

### JSON Output Example

```bash
quota-dash --once --json | jq '.openai.quota.balance_usd'
```

```json
{
  "openai": {
    "quota": {
      "provider": "openai",
      "balance_usd": 50.0,
      "limit_usd": 100.0,
      "usage_today_usd": 3.20,
      "source": "api"
    },
    "tokens": {
      "total_tokens": 2470173,
      "source": "log"
    },
    "context": {
      "percent_used": 0.0,
      "model": "gpt-4"
    }
  }
}
```

## Data Sources

| Provider | Quota | Tokens | How |
|----------|-------|--------|-----|
| OpenAI | API (`/v1/organization/usage`) | Codex SQLite (`~/.codex/state_5.sqlite`) | Requires admin API key |
| Anthropic | Manual config only | Claude costs.jsonl (`~/.claude/metrics/costs.jsonl`) | No public API available |

## Project Structure

```
src/quota_dash/
├── cli.py              CLI entry point
├── app.py              Textual TUI app
├── config.py           TOML config loader
├── models.py           Data models (QuotaInfo, TokenUsage, ContextInfo)
├── providers/
│   ├── base.py         Provider ABC
│   ├── openai.py       OpenAI implementation
│   └── anthropic.py    Anthropic implementation
├── data/
│   ├── api_client.py   httpx client for OpenAI API
│   ├── log_parser.py   Claude JSONL + Codex SQLite parsers
│   └── store.py        In-memory data store
├── widgets/
│   ├── provider_list.py
│   ├── quota_panel.py
│   ├── token_panel.py
│   └── context_gauge.py
└── themes/
    ├── default.tcss
    └── ghostty.tcss
```

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

56 tests, all passing.

## License

MIT
