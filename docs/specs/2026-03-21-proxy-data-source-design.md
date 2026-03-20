# quota-dash v0.2: Local Proxy Data Source — Design Spec

> Transparent local HTTP proxy that intercepts LLM API responses to collect real token usage, rate limit, and cost data for the quota-dash dashboard.

## Overview

A local HTTP reverse proxy that sits between CLI tools (Codex, Claude Code, etc.) and LLM provider APIs. It transparently forwards all requests/responses without modification, while reading response bodies and headers to extract token usage data into a SQLite database. The dashboard then queries this database as its primary data source.

## Goals

1. Collect real token usage data (input/output/total) from every API call
2. Capture rate limit information from response headers
3. Track context window usage via `input_tokens` from most recent API call (labeled as "last call snapshot" — not precise context window size, but the best proxy-level approximation)
4. Support OpenAI and Anthropic response formats with auto-detection
5. Handle both streaming (SSE) and non-streaming responses
6. Zero interference — proxy never modifies requests or responses

## Non-Goals (This Iteration)

- TLS termination (users connect to proxy via plain HTTP on localhost)
- Request modification or injection
- Authentication/authorization at the proxy level
- Support for non-HTTP protocols (WebSocket, gRPC)
- Cost calculation (just record what the API returns)

## Tech Stack

- **Proxy**: Starlette ASGI app + httpx (async HTTP client) + uvicorn
- **Storage**: SQLite via aiosqlite
- **CLI**: click (extending existing quota-dash CLI)
- **Config**: existing TOML config system
- **Logging**: Python stdlib `logging` to file (`~/.config/quota-dash/proxy.log`)

### New Dependencies

```toml
# Added to pyproject.toml (httpx already exists as a dependency)
"starlette>=0.40.0",
"uvicorn>=0.30.0",
"aiosqlite>=0.20.0",
```

## Architecture

```
User CLI Tool (Codex / Claude Code / custom)
    │
    │  HTTP request → http://localhost:8300
    ▼
┌─────────────────────────────────────┐
│  quota-dash-proxy (uvicorn ASGI)    │
│                                     │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Passthrough│  │ Response       │  │
│  │ Handler    │──▶ Parser Router  │  │
│  │            │  │                │  │
│  │ req → API  │  │ auto-detect:   │  │
│  │ res ← API  │  │ • OpenAI       │  │
│  └───────────┘  │ • Anthropic    │  │
│                  │ • Unknown→skip │  │
│                  └───────┬────────┘  │
│                          │           │
│                  ┌───────▼────────┐  │
│                  │ SQLite Writer  │  │
│                  │ usage.db       │  │
│                  └────────────────┘  │
└─────────────────────────────────────┘
    │
    │  Original response returned unchanged
    ▼
User CLI Tool receives response
```

### Core Principles

1. **Transparent** — proxy never modifies any request or response
2. **Auto-detect** — parser router infers provider from response JSON structure
3. **Fault-tolerant** — parsing failures never block proxy operation
4. **Non-blocking** — SQLite writes use `asyncio.create_task()` after response is fully sent to client; a shutdown hook awaits pending writes before exit
5. **HTTPS upstream** — proxy receives plain HTTP on localhost, forwards to upstream APIs over HTTPS (handled naturally by httpx)

### Request Routing

The proxy routes requests to the correct upstream based on **URL path prefix**. OpenAI and Anthropic use non-overlapping API paths:

| Path Prefix | Target |
|-------------|--------|
| `/v1/messages` | Anthropic (`https://api.anthropic.com`) |
| `/v1/chat/completions` | OpenAI (`https://api.openai.com`) |
| `/v1/completions` | OpenAI |
| `/v1/embeddings` | OpenAI |
| Any other path | Attempt to match against `[proxy.targets]` config; if no match, return 404 |

When `--target` flag is set (e.g., `--target openai`), requests matching other providers return 404 with a clear error message: `"Proxy is configured for openai only. This path routes to anthropic."`

The path-to-target mapping is stored in `handler.py` and is extensible via `[proxy.targets]` config for future providers.

## File Structure

```
src/quota_dash/
├── proxy/
│   ├── __init__.py
│   ├── app.py           # Starlette ASGI application + routing
│   ├── handler.py       # Request passthrough + response capture
│   ├── parser.py        # Provider auto-detection + usage extraction
│   ├── streaming.py     # SSE chunk buffering + final usage extraction
│   ├── db.py            # SQLite schema + async write operations
│   └── daemon.py        # Start/stop/status daemon management
├── ...existing files...
```

## SQLite Schema

File: `~/.config/quota-dash/usage.db`

```sql
CREATE TABLE api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),  -- ISO-8601 UTC
    provider TEXT NOT NULL,
    model TEXT,
    endpoint TEXT,

    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,

    ratelimit_remaining_tokens INTEGER,
    ratelimit_remaining_requests INTEGER,
    ratelimit_reset TEXT,

    request_id TEXT,
    target_url TEXT
);

-- Schema version for future migrations
CREATE TABLE schema_version (
    version INTEGER NOT NULL
);
INSERT INTO schema_version VALUES (1);

CREATE INDEX idx_api_calls_timestamp ON api_calls(timestamp);
CREATE INDEX idx_api_calls_provider ON api_calls(provider);
```

## Response Parser Auto-Detection

Detection logic based on response JSON structure:

```python
def detect_provider(body: dict, headers: dict) -> str:
    # Anthropic: has "type": "message" and usage with input_tokens
    if body.get("type") == "message" and "input_tokens" in body.get("usage", {}):
        return "anthropic"

    # OpenAI: has "choices" and usage with prompt_tokens
    if "choices" in body and "prompt_tokens" in body.get("usage", {}):
        return "openai"

    return "unknown"
```

### Usage Field Mapping

| Field | OpenAI | Anthropic |
|-------|--------|-----------|
| input_tokens | `usage.prompt_tokens` | `usage.input_tokens` |
| output_tokens | `usage.completion_tokens` | `usage.output_tokens` |
| total_tokens | `usage.total_tokens` | sum of above |
| model | `model` | `model` |
| request_id | `x-request-id` header | `request-id` header |
| rate limit tokens | `x-ratelimit-remaining-tokens` | `anthropic-ratelimit-tokens-remaining` |
| rate limit requests | `x-ratelimit-remaining-requests` | `anthropic-ratelimit-requests-remaining` |

### Fault Tolerance

- Response body is not valid JSON → skip, do not record
- `detect_provider` returns `"unknown"` → attempt to extract rate limit from headers, other fields NULL
- Any parser exception → log warning, do not affect proxy operation
- SQLite write failure → log error, do not affect proxy operation

## Streaming (SSE) Handling

**Detection**: Response `content-type: text/event-stream` or request body contains `"stream": true`.

**Strategy**: Forward chunks to client in real-time while buffering internally. Extract usage from the final chunk.

### Streaming Usage Extraction

**OpenAI**: When `stream_options.include_usage=true`, the final chunk before `data: [DONE]` has `choices: []` (empty array) and **top-level** `usage` field:
```json
{"id":"...","choices":[],"usage":{"prompt_tokens":50,"completion_tokens":20,"total_tokens":70}}
```
Extract: `chunk.usage.prompt_tokens`, `chunk.usage.completion_tokens`, `chunk.usage.total_tokens`.

**Anthropic**: Usage data is split across two events:
1. `event: message_start` — contains `message.usage.input_tokens` (capture this)
2. `event: message_delta` (before `message_stop`) — contains `usage.output_tokens` (capture this)

The proxy buffers both values and combines them into a single `api_calls` record.

**If streaming response has no usage data** (e.g., OpenAI without `include_usage`): record with `total_tokens=NULL`, dashboard shows "partial data". Never fabricate numbers.

## CLI Interface

### New Commands

```bash
# Proxy management
quota-dash proxy start                          # localhost:8300
quota-dash proxy start --port 9000              # custom port
quota-dash proxy start --target openai          # forward to OpenAI only
quota-dash proxy start --target anthropic       # forward to Anthropic only
quota-dash proxy status                         # show running proxy info
quota-dash proxy stop                           # stop daemon

# Dashboard with proxy
quota-dash --with-proxy                         # auto-start proxy
quota-dash --with-proxy --proxy-port 9000
```

### PID File

Daemon writes PID to `~/.config/quota-dash/proxy.pid` for status/stop commands.

## Configuration

New section in `~/.config/quota-dash/config.toml`:

```toml
[proxy]
enabled = false
port = 8300
db_path = "~/.config/quota-dash/usage.db"
log_path = "~/.config/quota-dash/proxy.log"

[proxy.targets]
openai = "https://api.openai.com"
anthropic = "https://api.anthropic.com"
```

### Config Code Changes

`AppConfig` gains a new `ProxyConfig` field:

```python
@dataclass
class ProxyConfig:
    enabled: bool = False
    port: int = 8300
    db_path: Path = field(default_factory=lambda: Path.home() / ".config" / "quota-dash" / "usage.db")
    log_path: Path = field(default_factory=lambda: Path.home() / ".config" / "quota-dash" / "proxy.log")
    targets: dict[str, str] = field(default_factory=lambda: {
        "openai": "https://api.openai.com",
        "anthropic": "https://api.anthropic.com",
    })

@dataclass
class AppConfig:
    # ...existing fields...
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
```

`load_config()` is updated to parse `[proxy]` and `[proxy.targets]` sections.

## Dashboard Integration

Provider data source priority (highest to lowest):

1. **SQLite** (proxy-collected real-time data) — NEW
2. **API** (billing endpoint) — existing
3. **Local log** (CLI tool logs) — existing
4. **Manual config** — existing

### Data Source Merging Strategy

SQLite (proxy) and manual config serve **different purposes** and do not conflict:

| Data Type | Source |
|-----------|--------|
| Token usage (in/out/total, sparkline) | SQLite (proxy) → fallback to log/estimated |
| Context window (last call snapshot) | SQLite (proxy) `input_tokens` from most recent call, labeled "last call snapshot" |
| Quota/billing ($balance, $limit) | Manual config or billing API (proxy cannot capture billing info) |
| Rate limits | SQLite (proxy) headers |

### Changes to Existing Providers

The `Provider` ABC gains an optional method (not abstract — default returns None):

```python
class Provider(ABC):
    # ...existing abstract methods...

    async def get_proxy_data(self) -> ProxyData | None:
        """Query SQLite for proxy-collected data. Default: None."""
        return None
```

Both `OpenAIProvider` and `AnthropicProvider` override this method. Their `get_token_usage()` and `get_context_window()` methods now call `get_proxy_data()` first, falling back to existing sources if it returns None.

**Constructor change**: `db_path` is injected at construction time and stored as `self._db_path`:

```python
# Updated constructor signature (both providers)
def __init__(self, config: ProviderConfig, db_path: Path | None = None) -> None:
    self._config = config
    self._db_path = db_path
```

**Callsite changes**: `app.py`'s `_init_providers()` and `cli.py`'s provider construction pass `db_path=config.proxy.db_path` (or `None` if proxy is not configured).

### New Data Model

```python
@dataclass
class ProxyData:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    ratelimit_remaining_tokens: int | None
    ratelimit_remaining_requests: int | None
    model: str | None
    last_call: datetime
    calls_today: int              # COUNT(*) WHERE date(timestamp) = date('now', 'localtime')
    tokens_today: int             # SUM(total_tokens) same filter
```

## User Setup Flow

1. `quota-dash proxy start`
2. Configure CLI tool API base URL:
   - Codex: `export OPENAI_BASE_URL=http://localhost:8300`
   - Claude Code: `export ANTHROPIC_BASE_URL=http://localhost:8300`
3. Use CLI tools normally — proxy collects data transparently
4. `quota-dash` shows real data from SQLite

## Error Handling

- Proxy cannot reach target API → return 502 Bad Gateway to client
- SQLite database locked → retry with backoff (3 attempts), then skip write
- Malformed request → forward as-is, let target API return the error
- Proxy port already in use → clear error message with PID of occupying process

## Testing Strategy

- Unit tests: parser detection, usage field extraction, SQLite read/write
- Integration tests: proxy end-to-end with mock upstream (httpx MockTransport)
- Streaming tests: SSE chunk buffering with mock event streams
- Fault tolerance tests: malformed responses, network errors, SQLite failures
