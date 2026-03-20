# Architecture — quota-dash

Multi-provider LLM quota monitoring dashboard.
TUI (Textual) + CLI one-shot mode, Python 3.11+.

## Layer Diagram

```
CLI (click)              TUI (Textual App)
 └─ --once / --json       └─ keybindings, polling, themes
        │                         │
        └────────┬────────────────┘
                 ▼
          Provider Layer (ABC)
          ├── OpenAIProvider   ← httpx API client
          └── AnthropicProvider← log parser (local files)
                 │
                 ▼
           Data Layer
           ├── DataStore     ← in-memory, revision-tracked
           ├── api_client    ← httpx async for OpenAI org usage
           └── log_parser    ← Claude/Codex log file parsing
                 │
                 ▼
           Models (dataclasses)
           ├── QuotaInfo     ← balance, limit, daily usage
           ├── TokenUsage    ← in/out tokens, history
           └── ContextInfo   ← used/max tokens, model
```

## Directory Layout

```
src/quota_dash/
├── cli.py              Click entry point: --once, --json, --provider, --theme
├── app.py              Textual App: compose, keybindings, polling loop
├── config.py           TOML config loader (AppConfig, ProviderConfig)
├── models.py           QuotaInfo, TokenUsage, ContextInfo dataclasses
├── providers/
│   ├── base.py         Provider ABC (get_quota, get_token_usage, get_context_window)
│   ├── openai.py       OpenAI impl — calls org usage API via httpx
│   └── anthropic.py    Anthropic impl — parses local Claude/Codex logs
├── data/
│   ├── store.py        In-memory DataStore with revision counter
│   ├── api_client.py   httpx async client for OpenAI endpoints
│   └── log_parser.py   Log file parser for Claude/Codex usage
├── widgets/
│   ├── provider_list.py Sidebar: provider selector + quick stats
│   ├── quota_panel.py   Balance/limit/usage display
│   ├── token_panel.py   Token usage breakdown
│   └── context_gauge.py Context window usage bar
└── themes/
    ├── default.tcss     Standard theme
    └── ghostty.tcss     Ghostty terminal optimized
```

## Data Flow

1. **Config** loads from `~/.config/quota-dash/config.toml` (TOML, optional)
2. **Providers** are instantiated per config; each implements the `Provider` ABC
3. **Polling** (`_refresh_all`) runs on interval, fetches quota/tokens/context from each provider
4. **DataStore** caches latest state per provider, tracks revision for change detection
5. **Widgets** receive data via `update_data()` calls from the app refresh loop

## Entry Points

- `quota-dash` — TUI dashboard (default)
- `quota-dash --once` — one-shot table output
- `quota-dash --once --json` — one-shot JSON output

## Dependencies

- **textual** — TUI framework
- **httpx** — async HTTP client (OpenAI API)
- **click** — CLI framework
- **tomli-w** — TOML writing (config persistence)
