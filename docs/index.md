# quota-dash

**quota-dash** is a multi-provider LLM quota monitoring TUI dashboard targeting Ghostty. It gives you a live, terminal-native view of your token usage across OpenAI and Anthropic accounts, with an optional local HTTP proxy that intercepts API calls to collect real-time data — all without sending credentials anywhere outside your machine.

## Features

- **Live dashboard** — real-time token usage across OpenAI and Anthropic accounts in a clean TUI
- **Local HTTP proxy** — transparently intercepts API calls to capture usage data the moment requests complete
- **Ghostty integration** — threshold-based terminal colors and three-tier desktop alerts tied to quota consumption
- **One-shot mode** — `--once --json` for scripting, cron jobs, and automation pipelines
- **Zero cloud dependency** — all data stays local; the proxy stores usage in a local SQLite database

## Install

```bash
pip install quota-dash
```

## Quick Start

```bash
# Launch the live dashboard
quota-dash

# One-shot JSON output (for scripting)
quota-dash --once --json

# Start the proxy, then launch dashboard with proxy data
quota-dash proxy start
quota-dash --with-proxy
```

## Guides

- [Getting Started](guides/getting-started.md) — install, configuration, and first run
- [Proxy Guide](guides/proxy-guide.md) — transparent API interception for real-time usage tracking
- [Ghostty Guide](guides/ghostty.md) — terminal colors and the three-tier alert system
