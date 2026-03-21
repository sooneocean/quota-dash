# Architecture

This document describes the internal structure of quota-dash for contributors and anyone extending the project.

## High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                            │
│  quota-dash [--once] [--json] [--with-proxy] [proxy start|stop] │
└──────────┬──────────────────────────────────┬───────────────────┘
           │ dashboard                        │ proxy subcommand
           ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────────────┐
│   QuotaDashApp       │          │   Proxy Daemon (uvicorn)     │
│   (app.py)           │          │   daemon.py + app.py         │
│                      │          │                              │
│  ┌────────────────┐  │          │  Starlette ASGI app          │
│  │  DataStore     │  │          │  Routes: /v1/messages        │
│  │  (store.py)    │◄─┼──────────┤         /v1/chat/completions │
│  └────────────────┘  │  reads   │         /v1/completions      │
│          │           │  SQLite  │         /v1/embeddings       │
│  ┌───────▼────────┐  │          │         /health              │
│  │  Providers     │  │          │                              │
│  │  openai.py     │  │          │  parser.py (usage extract)   │
│  │  anthropic.py  │  │          │  streaming.py (SSE buffer)   │
│  └───────┬────────┘  │          │  db.py (SQLite writes)       │
│          │           │          └──────────────┬───────────────┘
│  ┌───────▼────────┐  │                         │
│  │  Widgets       │  │          ┌──────────────▼───────────────┐
│  │  OverviewTable │  │          │  SQLite DB                   │
│  │  DetailPanel   │  │          │  ~/.config/quota-dash/       │
│  │  QuotaCard     │  │          │  usage.db                    │
│  │  TokenCard     │  │          │                              │
│  │  ContextCard   │  │          │  api_calls table             │
│  │  RateLimitCard │  │          └──────────────────────────────┘
│  │  HistoryTable  │  │
│  └────────────────┘  │
│                      │
│  Ghostty layer       │
│  detect.py           │
│  colors.py           │
│  alerts.py           │
└──────────────────────┘
```

## Module Overview

### `src/quota_dash/`

| Module / Package   | Purpose                                                             |
|--------------------|---------------------------------------------------------------------|
| `models.py`        | Shared dataclasses: `QuotaInfo`, `TokenUsage`, `ContextInfo`, `ProxyData` |
| `config.py`        | Load and parse `config.toml` into `AppConfig`, `ProviderConfig`, `ProxyConfig` |
| `cli.py`           | Click CLI entry point: main group, `--once`, `--with-proxy`, `proxy` subgroup |
| `app.py`           | `QuotaDashApp` — Textual application, polling loop, provider orchestration |

### `providers/`

| Module            | Purpose                                                             |
|-------------------|---------------------------------------------------------------------|
| `base.py`         | `Provider` ABC: `get_quota()`, `get_token_usage()`, `get_context_window()`, `get_proxy_data()` |
| `openai.py`       | `OpenAIProvider`: OpenAI usage API → manual config → Codex log fallback |
| `anthropic.py`    | `AnthropicProvider`: manual config → Claude CLI JSONL fallback; proxy for tokens |

### `data/`

| Module            | Purpose                                                             |
|-------------------|---------------------------------------------------------------------|
| `store.py`        | `DataStore`: in-memory store for quota, token, context, and proxy data with revision counter |
| `api_client.py`   | Async HTTP calls to the OpenAI usage API                           |
| `log_parser.py`   | Parse Codex SQLite logs and Claude CLI `costs.jsonl` for offline token data |

### `proxy/`

| Module            | Purpose                                                             |
|-------------------|---------------------------------------------------------------------|
| `app.py`          | Starlette ASGI app: route matching, request forwarding, streaming interception |
| `handler.py`      | Route table (path prefix → upstream URL), provider name resolution  |
| `parser.py`       | `extract_usage()`: parse usage from JSON response body + headers for OpenAI/Anthropic |
| `streaming.py`    | `StreamingBuffer`: accumulate SSE lines and extract usage at stream end |
| `db.py`           | `init_db()`, `write_api_call()`, `query_provider_data()`, `query_recent_calls()`, `query_token_history()` |
| `daemon.py`       | `start_proxy()`, `stop_proxy()`, `proxy_status()` with PID file management |

### `widgets/`

| Module            | Purpose                                                             |
|-------------------|---------------------------------------------------------------------|
| `overview_table.py` | `OverviewTable`: Textual `DataTable` showing all providers in one row each |
| `detail_panel.py` | `DetailPanel`: container composing the four detail cards            |
| `quota_card.py`   | `QuotaCard`: balance/limit progress bar (`#quota-bar`)              |
| `token_card.py`   | `TokenCard`: input/output/total token counts + sparkline            |
| `context_card.py` | `ContextCard`: context window progress bar (`#ctx-bar`)             |
| `ratelimit_card.py` | `RateLimitCard`: rate limit remaining tokens/requests from proxy  |
| `history_table.py` | `HistoryTable`: recent API calls from SQLite (today only)          |

### `ghostty/`

| Module            | Purpose                                                             |
|-------------------|---------------------------------------------------------------------|
| `detect.py`       | `is_ghostty()`: check `$TERM_PROGRAM == "ghostty"`                 |
| `colors.py`       | `threshold_color()`, `enhance_widgets()`: inject reactive color watchers on `ProgressBar`s |
| `alerts.py`       | `AlertMonitor`: three-tier alert system with OSC 9 notifications and border coloring |

## Data Flow

### Normal Dashboard Poll

```
set_interval(polling_interval) → _poll() → _refresh_all()
    │
    ├─ for each Provider:
    │      get_quota()        → QuotaInfo
    │      get_token_usage()  → TokenUsage
    │      get_context_window() → ContextInfo
    │      get_proxy_data()   → ProxyData | None  (reads SQLite)
    │
    ├─ DataStore.update_quota/tokens/context/proxy()
    │
    ├─ OverviewTable.refresh_data()   (all providers, summary row)
    │
    ├─ _update_detail(selected_provider)
    │      QuotaCard.update_data(quota)
    │      TokenCard.update_data(tokens, sparkline)
    │      ContextCard.update_data(context)
    │      RateLimitCard.update_data(proxy)
    │      HistoryTable.update_data(recent_calls from SQLite)
    │
    └─ AlertMonitor.check(app, store)   [Ghostty only]
```

### Data Source Priority (per provider)

Providers implement a waterfall: each method tries the highest-quality source first and falls back gracefully.

```
get_token_usage():
    1. ProxyData from SQLite       (source = "proxy")
    2. Log file parsing            (source = "log")
    3. Return zeros                (source = "estimated")

get_quota():
    1. OpenAI usage API            (source = "api")       [OpenAI only]
    2. Manual config values        (source = "manual")
    3. Return None fields          (source = "unavailable")
```

## Proxy Data Flow

```
CLI tool (Claude Code, Codex, etc.)
    │
    │  OPENAI_BASE_URL=http://127.0.0.1:8300
    │  ANTHROPIC_BASE_URL=http://127.0.0.1:8300
    ▼
Starlette proxy (proxy/app.py)
    │
    ├─ resolve_target(path, routes)
    │      /v1/messages        → https://api.anthropic.com/v1/messages
    │      /v1/chat/completions → https://api.openai.com/v1/chat/completions
    │      ...
    │
    ├─ httpx.AsyncClient forwards request with original headers
    │
    ├─ Response:
    │    Non-streaming:
    │      extract_usage(body_json, resp_headers) → ApiCallRecord
    │      write_api_call(db_path, record)
    │      return Response (unchanged)
    │
    │    Streaming (SSE):
    │      StreamingResponse: yield chunks to client
    │      StreamingBuffer.feed_line(line) accumulates
    │      On stream end: buf.extract_usage() → ApiCallRecord
    │                     write_api_call(db_path, record)
    │
    └─ SQLite api_calls table
           └─ Dashboard reads on next poll via query_provider_data()
```

## How to Add a New Provider

Follow these steps to add support for a new AI provider (e.g., `mistral`):

### 1. Add a provider class

Create `src/quota_dash/providers/mistral.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from quota_dash.config import ProviderConfig
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData
from quota_dash.providers.base import Provider


class MistralProvider(Provider):
    name = "mistral"

    def __init__(self, config: ProviderConfig, db_path: Path | None = None) -> None:
        self._config = config
        self._db_path = db_path

    async def get_quota(self) -> QuotaInfo:
        now = datetime.now()
        if self._config.balance_usd is not None:
            return QuotaInfo(
                provider="mistral",
                balance_usd=self._config.balance_usd,
                limit_usd=self._config.limit_usd,
                usage_today_usd=None,
                last_updated=now,
                source="manual",
            )
        return QuotaInfo(
            provider="mistral",
            balance_usd=None, limit_usd=None, usage_today_usd=None,
            last_updated=now, source="unavailable",
        )

    async def get_token_usage(self) -> TokenUsage:
        # Add proxy DB lookup here if you add Mistral routes to the proxy
        return TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)

    async def get_context_window(self) -> ContextInfo:
        return ContextInfo(used_tokens=0, max_tokens=32000, percent_used=0.0, model="mistral-large")
```

### 2. Register the provider in the CLI and app

In `src/quota_dash/cli.py`, add to `provider_map_cls`:

```python
from quota_dash.providers.mistral import MistralProvider

provider_map_cls = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "mistral": MistralProvider,   # add this
}
```

Repeat the same addition in `src/quota_dash/app.py` inside `_init_providers()`.

### 3. Add proxy routing (optional)

If Mistral uses an OpenAI-compatible API, add its path prefix to `proxy/handler.py`:

```python
DEFAULT_ROUTES: dict[str, str] = {
    ...
    "/v1/chat/completions": "https://api.openai.com",  # already handles OpenAI-compat
}
```

If Mistral uses a distinct path (e.g., `/v1/mistral/chat`), add it to both `DEFAULT_ROUTES` and `_PATH_TO_PROVIDER`.

### 4. Configure in config.toml

```toml
[providers.mistral]
enabled = true
balance_usd = 10.00
limit_usd = 20.00
```

### 5. Write tests

Add `tests/test_providers_mistral.py` with at least:
- A test that `get_quota()` returns `source="manual"` when `balance_usd` is set
- A test that `get_quota()` returns `source="unavailable"` when no config is present
- A test that `get_token_usage()` returns a `TokenUsage` dataclass instance
