# Proxy Data Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a transparent local HTTP reverse proxy to quota-dash that intercepts LLM API responses and records real token usage into SQLite, replacing estimated/zero data with actual usage metrics.

**Architecture:** Starlette ASGI app receives HTTP from CLI tools, forwards to upstream LLM APIs over HTTPS via httpx, auto-detects provider from response JSON structure, extracts usage fields, and writes to SQLite asynchronously. Dashboard providers query SQLite as primary data source, falling back to existing log/manual sources.

**Tech Stack:** Starlette, uvicorn, aiosqlite, httpx (existing), click (existing)

**Spec:** `docs/specs/2026-03-21-proxy-data-source-design.md`

---

## File Structure

```
src/quota_dash/
├── proxy/
│   ├── __init__.py
│   ├── db.py            # SQLite schema init + async read/write
│   ├── parser.py        # Provider auto-detection + usage field extraction
│   ├── streaming.py     # SSE chunk buffer + final usage extraction
│   ├── handler.py       # Path-based routing + request passthrough
│   ├── app.py           # Starlette ASGI app factory
│   └── daemon.py        # Start/stop/status process management
├── models.py            # +ProxyData dataclass
├── config.py            # +ProxyConfig dataclass, load_config update
├── providers/
│   ├── base.py          # +get_proxy_data() default method
│   ├── openai.py        # +db_path constructor, proxy-first token/context
│   └── anthropic.py     # +db_path constructor, proxy-first token/context
├── app.py               # +db_path in _init_providers
└── cli.py               # +proxy subcommand group, +--with-proxy flag
tests/
├── test_proxy_db.py
├── test_proxy_parser.py
├── test_proxy_streaming.py
├── test_proxy_handler.py
├── test_proxy_app.py
├── test_config.py       # +proxy config tests
├── test_providers.py    # +proxy data tests
└── test_cli.py          # +proxy CLI tests
```

---

### Task 1: Dependencies & ProxyData Model

**Files:**
- Modify: `quota-dash/pyproject.toml`
- Modify: `quota-dash/src/quota_dash/models.py`
- Modify: `quota-dash/tests/test_models.py`

- [ ] **Step 1: Write failing test for ProxyData**

```python
# Append to tests/test_models.py
from quota_dash.models import ProxyData

def test_proxy_data_creation():
    pd = ProxyData(
        input_tokens=1500,
        output_tokens=800,
        total_tokens=2300,
        ratelimit_remaining_tokens=50000,
        ratelimit_remaining_requests=100,
        model="gpt-4",
        last_call=datetime(2026, 3, 21, 10, 0),
        calls_today=15,
        tokens_today=35000,
    )
    assert pd.total_tokens == 2300
    assert pd.calls_today == 15

def test_proxy_data_nullable_fields():
    pd = ProxyData(
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        ratelimit_remaining_tokens=None,
        ratelimit_remaining_requests=None,
        model=None,
        last_call=datetime(2026, 3, 21, 10, 0),
        calls_today=0,
        tokens_today=0,
    )
    assert pd.model is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_models.py::test_proxy_data_creation -v`
Expected: FAIL — `ImportError: cannot import name 'ProxyData'`

- [ ] **Step 3: Add ProxyData to models.py and update pyproject.toml**

Append to `src/quota_dash/models.py`:
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
    calls_today: int
    tokens_today: int
```

Update `pyproject.toml` dependencies:
```toml
dependencies = [
    "textual>=0.80.0",
    "httpx>=0.27.0",
    "click>=8.1.0",
    "tomli-w>=1.0.0",
    "starlette>=0.40.0",
    "uvicorn>=0.30.0",
    "aiosqlite>=0.20.0",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pip install -e ".[dev]" && pytest tests/test_models.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add pyproject.toml src/quota_dash/models.py tests/test_models.py && git commit -m "feat: add ProxyData model and proxy dependencies"
```

---

### Task 2: ProxyConfig & Config Loading

**Files:**
- Modify: `quota-dash/src/quota_dash/config.py`
- Modify: `quota-dash/tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_config.py::test_load_proxy_config -v`
Expected: FAIL — `AttributeError: 'AppConfig' object has no attribute 'proxy'`

- [ ] **Step 3: Implement ProxyConfig**

Add to `src/quota_dash/config.py` before `AppConfig`:
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
```

Add `proxy` field to `AppConfig`:
```python
@dataclass
class AppConfig:
    polling_interval: int = 60
    theme: str = "auto"
    mode: str = "dashboard"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
```

Update `load_config()` to parse `[proxy]`:
```python
    proxy_raw = raw.get("proxy", {})
    proxy_targets = proxy_raw.get("targets", {})
    proxy = ProxyConfig(
        enabled=proxy_raw.get("enabled", False),
        port=proxy_raw.get("port", 8300),
        db_path=Path(proxy_raw.get("db_path", "~/.config/quota-dash/usage.db")).expanduser(),
        log_path=Path(proxy_raw.get("log_path", "~/.config/quota-dash/proxy.log")).expanduser(),
        targets={**ProxyConfig().targets, **proxy_targets},
    )

    return AppConfig(
        polling_interval=general.get("polling_interval", 60),
        theme=general.get("theme", "auto"),
        mode=general.get("mode", "dashboard"),
        providers=providers,
        proxy=proxy,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_config.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/config.py tests/test_config.py && git commit -m "feat: add ProxyConfig with targets and load_config support"
```

---

### Task 3: SQLite Database Layer

**Files:**
- Create: `quota-dash/src/quota_dash/proxy/__init__.py`
- Create: `quota-dash/src/quota_dash/proxy/db.py`
- Create: `quota-dash/tests/test_proxy_db.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_proxy_db.py
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from quota_dash.proxy.db import init_db, write_api_call, query_provider_data, ApiCallRecord


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_usage.db"


@pytest.mark.asyncio
async def test_init_db_creates_tables(db_path):
    await init_db(db_path)
    assert db_path.exists()


@pytest.mark.asyncio
async def test_write_and_query(db_path):
    await init_db(db_path)
    record = ApiCallRecord(
        provider="openai",
        model="gpt-4",
        endpoint="/v1/chat/completions",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        ratelimit_remaining_tokens=9000,
        ratelimit_remaining_requests=99,
        ratelimit_reset=None,
        request_id="req-123",
        target_url="https://api.openai.com/v1/chat/completions",
    )
    await write_api_call(db_path, record)

    data = await query_provider_data(db_path, "openai")
    assert data is not None
    assert data.input_tokens == 100
    assert data.total_tokens == 150
    assert data.calls_today == 1
    assert data.tokens_today == 150


@pytest.mark.asyncio
async def test_query_empty_db(db_path):
    await init_db(db_path)
    data = await query_provider_data(db_path, "openai")
    assert data is None


@pytest.mark.asyncio
async def test_write_multiple_records(db_path):
    await init_db(db_path)
    for i in range(3):
        record = ApiCallRecord(
            provider="anthropic", model="claude-opus-4-6",
            endpoint="/v1/messages",
            input_tokens=100 * (i + 1), output_tokens=50 * (i + 1),
            total_tokens=150 * (i + 1),
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None,
            target_url="https://api.anthropic.com/v1/messages",
        )
        await write_api_call(db_path, record)

    data = await query_provider_data(db_path, "anthropic")
    assert data is not None
    assert data.calls_today == 3
    assert data.tokens_today == 150 + 300 + 450
    assert data.input_tokens == 300  # most recent
    assert data.model == "claude-opus-4-6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_proxy_db.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement db.py**

```python
# src/quota_dash/proxy/__init__.py
```

```python
# src/quota_dash/proxy/db.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite

from quota_dash.models import ProxyData

logger = logging.getLogger(__name__)

SCHEMA = """\
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
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
CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON api_calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_calls_provider ON api_calls(provider);
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
"""


@dataclass
class ApiCallRecord:
    provider: str
    model: str | None
    endpoint: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    ratelimit_remaining_tokens: int | None
    ratelimit_remaining_requests: int | None
    ratelimit_reset: str | None
    request_id: str | None
    target_url: str | None


async def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        # Set schema version if empty
        cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.execute("INSERT INTO schema_version VALUES (1)")
        await db.commit()


async def write_api_call(db_path: Path, record: ApiCallRecord) -> None:
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """INSERT INTO api_calls
                   (provider, model, endpoint, input_tokens, output_tokens,
                    total_tokens, ratelimit_remaining_tokens,
                    ratelimit_remaining_requests, ratelimit_reset,
                    request_id, target_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.provider, record.model, record.endpoint,
                    record.input_tokens, record.output_tokens, record.total_tokens,
                    record.ratelimit_remaining_tokens, record.ratelimit_remaining_requests,
                    record.ratelimit_reset, record.request_id, record.target_url,
                ),
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to write api_call record")


async def query_provider_data(db_path: Path, provider: str) -> ProxyData | None:
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            # Most recent call for this provider
            cursor = await db.execute(
                """SELECT input_tokens, output_tokens, total_tokens,
                          ratelimit_remaining_tokens, ratelimit_remaining_requests,
                          model, timestamp
                   FROM api_calls WHERE provider = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (provider,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            # Today's aggregates
            cursor2 = await db.execute(
                """SELECT COUNT(*) as cnt, COALESCE(SUM(total_tokens), 0) as total
                   FROM api_calls
                   WHERE provider = ? AND date(timestamp) = date('now', 'localtime')""",
                (provider,),
            )
            agg = await cursor2.fetchone()

            return ProxyData(
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                total_tokens=row["total_tokens"],
                ratelimit_remaining_tokens=row["ratelimit_remaining_tokens"],
                ratelimit_remaining_requests=row["ratelimit_remaining_requests"],
                model=row["model"],
                last_call=datetime.fromisoformat(row["timestamp"]),
                calls_today=agg["cnt"],
                tokens_today=agg["total"],
            )
    except Exception:
        logger.exception("Failed to query provider data")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_proxy_db.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/ tests/test_proxy_db.py && git commit -m "feat: SQLite database layer for proxy usage data"
```

---

### Task 4: Response Parser (Auto-Detection + Field Extraction)

**Files:**
- Create: `quota-dash/src/quota_dash/proxy/parser.py`
- Create: `quota-dash/tests/test_proxy_parser.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_proxy_parser.py
from quota_dash.proxy.parser import detect_provider, extract_usage
from quota_dash.proxy.db import ApiCallRecord


def test_detect_openai():
    body = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    assert detect_provider(body) == "openai"


def test_detect_anthropic():
    body = {"type": "message", "usage": {"input_tokens": 10, "output_tokens": 5}}
    assert detect_provider(body) == "anthropic"


def test_detect_unknown():
    body = {"foo": "bar"}
    assert detect_provider(body) == "unknown"


def test_extract_openai_usage():
    body = {"model": "gpt-4", "choices": [{}], "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
    headers = {"x-request-id": "req-abc", "x-ratelimit-remaining-tokens": "9000", "x-ratelimit-remaining-requests": "99"}
    record = extract_usage(body, headers, endpoint="/v1/chat/completions", target_url="https://api.openai.com/v1/chat/completions")
    assert record.provider == "openai"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    assert record.model == "gpt-4"
    assert record.request_id == "req-abc"
    assert record.ratelimit_remaining_tokens == 9000


def test_extract_anthropic_usage():
    body = {"type": "message", "model": "claude-opus-4-6", "usage": {"input_tokens": 200, "output_tokens": 80}}
    headers = {"request-id": "req-xyz", "anthropic-ratelimit-tokens-remaining": "50000"}
    record = extract_usage(body, headers, endpoint="/v1/messages", target_url="https://api.anthropic.com/v1/messages")
    assert record.provider == "anthropic"
    assert record.input_tokens == 200
    assert record.output_tokens == 80
    assert record.total_tokens == 280
    assert record.ratelimit_remaining_tokens == 50000


def test_extract_unknown_provider():
    body = {"random": "data"}
    headers = {"x-ratelimit-remaining-tokens": "5000"}
    record = extract_usage(body, headers, endpoint="/v1/foo", target_url="https://example.com")
    assert record.provider == "unknown"
    assert record.input_tokens == 0


def test_extract_malformed_body():
    record = extract_usage({}, {}, endpoint="/v1/test", target_url="https://example.com")
    assert record.provider == "unknown"
    assert record.total_tokens == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_proxy_parser.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement parser.py**

```python
# src/quota_dash/proxy/parser.py
from __future__ import annotations

import logging

from quota_dash.proxy.db import ApiCallRecord

logger = logging.getLogger(__name__)


def detect_provider(body: dict) -> str:
    if body.get("type") == "message" and "input_tokens" in body.get("usage", {}):
        return "anthropic"
    if "choices" in body and "prompt_tokens" in body.get("usage", {}):
        return "openai"
    return "unknown"


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def extract_usage(
    body: dict,
    headers: dict,
    endpoint: str,
    target_url: str,
) -> ApiCallRecord:
    provider = detect_provider(body)
    usage = body.get("usage", {})

    if provider == "openai":
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        request_id = headers.get("x-request-id")
        rl_tokens = _safe_int(headers.get("x-ratelimit-remaining-tokens"))
        rl_requests = _safe_int(headers.get("x-ratelimit-remaining-requests"))
    elif provider == "anthropic":
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        request_id = headers.get("request-id")
        rl_tokens = _safe_int(headers.get("anthropic-ratelimit-tokens-remaining"))
        rl_requests = _safe_int(headers.get("anthropic-ratelimit-requests-remaining"))
    else:
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        request_id = headers.get("x-request-id") or headers.get("request-id")
        rl_tokens = _safe_int(
            headers.get("x-ratelimit-remaining-tokens")
            or headers.get("anthropic-ratelimit-tokens-remaining")
        )
        rl_requests = None

    return ApiCallRecord(
        provider=provider,
        model=body.get("model"),
        endpoint=endpoint,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        ratelimit_remaining_tokens=rl_tokens,
        ratelimit_remaining_requests=rl_requests,
        ratelimit_reset=headers.get("x-ratelimit-reset-tokens"),
        request_id=request_id,
        target_url=target_url,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_proxy_parser.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/parser.py tests/test_proxy_parser.py && git commit -m "feat: response parser with auto-detection and usage field extraction"
```

---

### Task 5: SSE Streaming Handler

**Files:**
- Create: `quota-dash/src/quota_dash/proxy/streaming.py`
- Create: `quota-dash/tests/test_proxy_streaming.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_proxy_streaming.py
import json
from quota_dash.proxy.streaming import StreamingBuffer


def test_openai_streaming_usage():
    buf = StreamingBuffer()
    # Simulate OpenAI SSE chunks
    buf.feed_line("data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}))
    buf.feed_line("data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}}))
    buf.feed_line("data: [DONE]")

    record = buf.extract_usage(headers={}, endpoint="/v1/chat/completions", target_url="https://api.openai.com/v1/chat/completions")
    assert record is not None
    assert record.provider == "openai"
    assert record.input_tokens == 50
    assert record.output_tokens == 20
    assert record.total_tokens == 70


def test_anthropic_streaming_usage():
    buf = StreamingBuffer()
    # message_start with input_tokens
    buf.feed_line("event: message_start")
    buf.feed_line("data: " + json.dumps({"type": "message_start", "message": {"usage": {"input_tokens": 100}}}))
    # content delta
    buf.feed_line("event: content_block_delta")
    buf.feed_line("data: " + json.dumps({"type": "content_block_delta"}))
    # message_delta with output_tokens
    buf.feed_line("event: message_delta")
    buf.feed_line("data: " + json.dumps({"type": "message_delta", "usage": {"output_tokens": 45}}))
    # message_stop
    buf.feed_line("event: message_stop")
    buf.feed_line("data: " + json.dumps({"type": "message_stop"}))

    record = buf.extract_usage(headers={"request-id": "r-1"}, endpoint="/v1/messages", target_url="https://api.anthropic.com/v1/messages")
    assert record is not None
    assert record.provider == "anthropic"
    assert record.input_tokens == 100
    assert record.output_tokens == 45
    assert record.total_tokens == 145
    assert record.request_id == "r-1"


def test_streaming_no_usage():
    buf = StreamingBuffer()
    buf.feed_line("data: " + json.dumps({"choices": [{"delta": {"content": "hi"}}]}))
    buf.feed_line("data: [DONE]")

    record = buf.extract_usage(headers={}, endpoint="/v1/chat/completions", target_url="https://api.openai.com/v1/chat/completions")
    assert record is not None
    assert record.total_tokens == 0
    assert record.provider == "unknown"


def test_streaming_malformed_lines():
    buf = StreamingBuffer()
    buf.feed_line("not valid sse")
    buf.feed_line("data: {not json}")
    buf.feed_line("data: [DONE]")

    record = buf.extract_usage(headers={}, endpoint="/v1/test", target_url="https://example.com")
    assert record is not None
    assert record.total_tokens == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_proxy_streaming.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement streaming.py**

```python
# src/quota_dash/proxy/streaming.py
from __future__ import annotations

import json
import logging

from quota_dash.proxy.db import ApiCallRecord
from quota_dash.proxy.parser import _safe_int

logger = logging.getLogger(__name__)


class StreamingBuffer:
    def __init__(self) -> None:
        self._current_event: str | None = None
        # OpenAI: last chunk with usage
        self._openai_usage: dict | None = None
        # Anthropic: split across events
        self._anthropic_input_tokens: int | None = None
        self._anthropic_output_tokens: int | None = None
        self._model: str | None = None

    def feed_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            self._current_event = None
            return

        if line.startswith("event:"):
            self._current_event = line[6:].strip()
            return

        if not line.startswith("data:"):
            return

        data_str = line[5:].strip()
        if data_str == "[DONE]":
            return

        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            return

        # Extract model from any chunk
        if "model" in data and self._model is None:
            self._model = data.get("model")

        # OpenAI: final chunk has empty choices + usage
        if isinstance(data.get("choices"), list) and len(data["choices"]) == 0 and "usage" in data:
            self._openai_usage = data["usage"]

        # Anthropic: message_start has input_tokens
        if data.get("type") == "message_start":
            msg = data.get("message", {})
            usage = msg.get("usage", {})
            if "input_tokens" in usage:
                self._anthropic_input_tokens = usage["input_tokens"]

        # Anthropic: message_delta has output_tokens
        if data.get("type") == "message_delta":
            usage = data.get("usage", {})
            if "output_tokens" in usage:
                self._anthropic_output_tokens = usage["output_tokens"]

    def extract_usage(
        self,
        headers: dict,
        endpoint: str,
        target_url: str,
    ) -> ApiCallRecord:
        # OpenAI streaming
        if self._openai_usage is not None:
            u = self._openai_usage
            return ApiCallRecord(
                provider="openai",
                model=self._model,
                endpoint=endpoint,
                input_tokens=u.get("prompt_tokens", 0),
                output_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
                ratelimit_remaining_tokens=_safe_int(headers.get("x-ratelimit-remaining-tokens")),
                ratelimit_remaining_requests=_safe_int(headers.get("x-ratelimit-remaining-requests")),
                ratelimit_reset=headers.get("x-ratelimit-reset-tokens"),
                request_id=headers.get("x-request-id"),
                target_url=target_url,
            )

        # Anthropic streaming
        if self._anthropic_input_tokens is not None or self._anthropic_output_tokens is not None:
            inp = self._anthropic_input_tokens or 0
            out = self._anthropic_output_tokens or 0
            return ApiCallRecord(
                provider="anthropic",
                model=self._model,
                endpoint=endpoint,
                input_tokens=inp,
                output_tokens=out,
                total_tokens=inp + out,
                ratelimit_remaining_tokens=_safe_int(headers.get("anthropic-ratelimit-tokens-remaining")),
                ratelimit_remaining_requests=_safe_int(headers.get("anthropic-ratelimit-requests-remaining")),
                ratelimit_reset=None,
                request_id=headers.get("request-id"),
                target_url=target_url,
            )

        # No usage found
        return ApiCallRecord(
            provider="unknown", model=self._model, endpoint=endpoint,
            input_tokens=0, output_tokens=0, total_tokens=0,
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None, target_url=target_url,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_proxy_streaming.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/streaming.py tests/test_proxy_streaming.py && git commit -m "feat: SSE streaming buffer with OpenAI and Anthropic usage extraction"
```

---

### Task 6: Route Resolver

**Files:**
- Create: `quota-dash/src/quota_dash/proxy/handler.py`
- Create: `quota-dash/tests/test_proxy_handler.py`

> Note: This file contains only the routing logic (`resolve_target` + `DEFAULT_ROUTES`). The actual request passthrough is in `app.py` (Task 7) which is the Starlette ASGI handler.

- [ ] **Step 1: Write failing test**

```python
# tests/test_proxy_handler.py
from quota_dash.proxy.handler import resolve_target, DEFAULT_ROUTES, build_routes


def test_resolve_openai_chat():
    url = resolve_target("/v1/chat/completions", DEFAULT_ROUTES)
    assert url == "https://api.openai.com/v1/chat/completions"


def test_resolve_openai_embeddings():
    url = resolve_target("/v1/embeddings", DEFAULT_ROUTES)
    assert url == "https://api.openai.com/v1/embeddings"


def test_resolve_anthropic_messages():
    url = resolve_target("/v1/messages", DEFAULT_ROUTES)
    assert url == "https://api.anthropic.com/v1/messages"


def test_resolve_unknown_path():
    url = resolve_target("/v2/something", DEFAULT_ROUTES)
    assert url is None


def test_resolve_with_custom_targets():
    routes = {**DEFAULT_ROUTES, "/v1/custom": "https://custom.api.com"}
    url = resolve_target("/v1/custom/endpoint", routes)
    assert url == "https://custom.api.com/v1/custom/endpoint"


def test_build_routes_merges_config():
    config_targets = {"openai": "https://custom-openai.com", "anthropic": "https://custom-anthropic.com"}
    routes = build_routes(config_targets)
    assert routes["/v1/chat/completions"] == "https://custom-openai.com"
    assert routes["/v1/messages"] == "https://custom-anthropic.com"


def test_build_routes_defaults():
    routes = build_routes(None)
    assert routes == DEFAULT_ROUTES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_proxy_handler.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement handler.py**

```python
# src/quota_dash/proxy/handler.py
from __future__ import annotations

DEFAULT_ROUTES: dict[str, str] = {
    "/v1/messages": "https://api.anthropic.com",
    "/v1/chat/completions": "https://api.openai.com",
    "/v1/completions": "https://api.openai.com",
    "/v1/embeddings": "https://api.openai.com",
}

# Maps path prefix -> which config target key it belongs to
_PATH_TO_PROVIDER: dict[str, str] = {
    "/v1/messages": "anthropic",
    "/v1/chat/completions": "openai",
    "/v1/completions": "openai",
    "/v1/embeddings": "openai",
}


def resolve_target(path: str, routes: dict[str, str]) -> str | None:
    for prefix, base_url in routes.items():
        if path.startswith(prefix):
            return base_url + path
    return None


def build_routes(config_targets: dict[str, str] | None) -> dict[str, str]:
    """Merge config targets into default routes."""
    if not config_targets:
        return dict(DEFAULT_ROUTES)

    routes: dict[str, str] = {}
    for path_prefix, provider_name in _PATH_TO_PROVIDER.items():
        base = config_targets.get(provider_name, DEFAULT_ROUTES[path_prefix])
        routes[path_prefix] = base
    return routes


def provider_for_path(path: str) -> str | None:
    """Return provider name for a given path, or None."""
    for prefix, provider in _PATH_TO_PROVIDER.items():
        if path.startswith(prefix):
            return provider
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_proxy_handler.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/handler.py tests/test_proxy_handler.py && git commit -m "feat: path-based route resolver with config target merging"
```

---

### Task 7: Starlette ASGI App

**Files:**
- Create: `quota-dash/src/quota_dash/proxy/app.py`
- Create: `quota-dash/tests/test_proxy_app.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_proxy_app.py
import json

import pytest
from httpx import ASGITransport, AsyncClient

from quota_dash.proxy.app import create_proxy_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_usage.db"


@pytest.mark.asyncio
async def test_proxy_app_404_unknown_route(db_path):
    app = create_proxy_app(db_path=db_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/unknown/path")
    assert resp.status_code == 404
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_proxy_app_health(db_path):
    app = create_proxy_app(db_path=db_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_proxy_app.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement app.py**

```python
# src/quota_dash/proxy/app.py
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

import httpx

from quota_dash.proxy.db import init_db, write_api_call
from quota_dash.proxy.handler import resolve_target, build_routes, provider_for_path
from quota_dash.proxy.parser import extract_usage
from quota_dash.proxy.streaming import StreamingBuffer

logger = logging.getLogger(__name__)


def create_proxy_app(
    db_path: Path,
    config_targets: dict[str, str] | None = None,
    target_filter: str | None = None,
) -> Starlette:
    _routes = build_routes(config_targets)
    _db_path = db_path

    async def startup():
        await init_db(_db_path)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "db_path": str(_db_path)})

    async def proxy_handler(request: Request) -> Response:
        path = request.url.path
        target_url = resolve_target(path, _routes)

        if target_url is None:
            return JSONResponse({"error": "No route for path"}, status_code=404)

        # Target filter check
        if target_filter:
            prov = provider_for_path(path)
            if prov and prov != target_filter:
                return JSONResponse(
                    {"error": f"Proxy is configured for {target_filter} only. This path routes to {prov}."},
                    status_code=404,
                )

        body = await request.body()
        fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "transfer-encoding")}

        try:
            client = httpx.AsyncClient(timeout=120.0)
            req = client.build_request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                content=body,
            )
            resp = await client.send(req, stream=True)
        except httpx.HTTPError as e:
            logger.error("Upstream error: %s", e)
            return JSONResponse({"error": "Bad Gateway"}, status_code=502)

        resp_headers = dict(resp.headers)
        is_streaming = "text/event-stream" in resp_headers.get("content-type", "")

        if is_streaming:
            buf = StreamingBuffer()

            async def stream_and_capture():
                try:
                    async for chunk in resp.aiter_text():
                        yield chunk
                        for line in chunk.splitlines():
                            buf.feed_line(line)
                finally:
                    await resp.aclose()
                    await client.aclose()
                    record = buf.extract_usage(resp_headers, endpoint=path, target_url=target_url)
                    try:
                        await write_api_call(_db_path, record)
                    except Exception:
                        logger.exception("Failed to write streaming usage")

            return StreamingResponse(
                stream_and_capture(),
                status_code=resp.status_code,
                headers={k: v for k, v in resp_headers.items() if k.lower() != "transfer-encoding"},
                media_type=resp_headers.get("content-type", "text/event-stream"),
            )
        else:
            resp_body = await resp.aread()
            await resp.aclose()
            await client.aclose()

            try:
                body_json = json.loads(resp_body)
            except (json.JSONDecodeError, ValueError):
                body_json = {}

            record = extract_usage(body_json, resp_headers, endpoint=path, target_url=target_url)
            asyncio.create_task(_safe_write(_db_path, record))

            return Response(
                content=resp_body,
                status_code=resp.status_code,
                headers={k: v for k, v in resp_headers.items() if k.lower() not in ("transfer-encoding", "content-encoding")},
                media_type=resp_headers.get("content-type"),
            )

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/{path:path}", proxy_handler, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]),
        ],
        on_startup=[startup],
    )
    return app


async def _safe_write(db_path: Path, record) -> None:
    try:
        await write_api_call(db_path, record)
    except Exception:
        logger.exception("Failed to write usage record")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quota-dash && pytest tests/test_proxy_app.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/app.py tests/test_proxy_app.py && git commit -m "feat: Starlette ASGI proxy app with streaming support"
```

---

### Task 8: Daemon Management

**Files:**
- Create: `quota-dash/src/quota_dash/proxy/daemon.py`

- [ ] **Step 1: Implement daemon.py**

```python
# src/quota_dash/proxy/daemon.py
from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

import uvicorn

from quota_dash.proxy.app import create_proxy_app

logger = logging.getLogger(__name__)


def _pid_path() -> Path:
    return Path.home() / ".config" / "quota-dash" / "proxy.pid"


def start_proxy(
    port: int = 8300,
    db_path: Path | None = None,
    log_path: Path | None = None,
    config_targets: dict[str, str] | None = None,
    target_filter: str | None = None,
    foreground: bool = False,
) -> None:
    db = db_path or Path.home() / ".config" / "quota-dash" / "usage.db"
    log = log_path or Path.home() / ".config" / "quota-dash" / "proxy.log"

    # Check if already running
    pid_file = _pid_path()
    if pid_file.exists():
        old_pid = int(pid_file.read_text().strip())
        try:
            os.kill(old_pid, 0)
            print(f"Proxy already running (PID {old_pid}). Use 'quota-dash proxy stop' first.")
            sys.exit(1)
        except OSError:
            pid_file.unlink()

    # Setup logging
    log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Write PID
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))

    app = create_proxy_app(db_path=db, config_targets=config_targets, target_filter=target_filter)

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        if pid_file.exists():
            pid_file.unlink()


def stop_proxy() -> bool:
    pid_file = _pid_path()
    if not pid_file.exists():
        print("No proxy running (PID file not found).")
        return False

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Proxy stopped (PID {pid}).")
        pid_file.unlink()
        return True
    except OSError:
        print(f"Process {pid} not found. Cleaning up stale PID file.")
        pid_file.unlink()
        return False


def proxy_status() -> dict | None:
    pid_file = _pid_path()
    if not pid_file.exists():
        return None

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, 0)
        return {"pid": pid, "pid_file": str(pid_file)}
    except OSError:
        return None
```

- [ ] **Step 2: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/daemon.py && git commit -m "feat: proxy daemon start/stop/status management"
```

---

### Task 9: Proxy CLI Subcommands

**Files:**
- Modify: `quota-dash/src/quota_dash/cli.py`
- Modify: `quota-dash/tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_cli.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_cli.py::test_cli_proxy_help -v`
Expected: FAIL — `Error: No such command 'proxy'`

- [ ] **Step 3: Update cli.py to add proxy subcommand group**

Convert `main` from `@click.command` to `@click.group` with a default command, and add proxy subcommands:

```python
# Replace the existing @click.command and main function in cli.py with:

@click.group(invoke_without_command=True)
@click.option("--once", is_flag=True, help="One-shot query, print and exit")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (with --once)")
@click.option("--provider", default=None, help="Show only this provider")
@click.option("--theme", default=None, help="Force theme: default | ghostty")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path")
@click.option("--with-proxy", is_flag=True, help="Auto-start proxy with dashboard")
@click.option("--proxy-port", default=None, type=int, help="Proxy port (with --with-proxy)")
@click.pass_context
def main(ctx, once, as_json, provider, theme, config_path, with_proxy, proxy_port):
    """Multi-provider LLM quota monitoring dashboard."""
    if ctx.invoked_subcommand is not None:
        ctx.ensure_object(dict)
        ctx.obj["config_path"] = config_path
        return

    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    # Always pass db_path — providers check existence at query time
    db_path = config.proxy.db_path

    provider_map_cls = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}
    providers: dict[str, Provider] = {}
    for name, pconfig in config.providers.items():
        if not pconfig.enabled:
            continue
        if provider and name != provider:
            continue
        if name in provider_map_cls:
            providers[name] = provider_map_cls[name](pconfig, db_path=db_path)

    if once:
        asyncio.run(_run_once(providers, as_json))
    else:
        if with_proxy:
            import subprocess, time
            port = proxy_port or config.proxy.port
            subprocess.Popen(
                ["quota-dash", "proxy", "start", "--port", str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(1)  # wait for proxy to initialize DB

        from quota_dash.app import QuotaDashApp
        app = QuotaDashApp(config=config, theme_override=theme)
        app.run()


@main.group()
@click.pass_context
def proxy(ctx):
    """Manage the local API proxy."""
    pass


@proxy.command()
@click.option("--port", default=8300, help="Proxy port")
@click.option("--target", default=None, help="Only forward to this provider")
@click.pass_context
def start(ctx, port, target):
    """Start the proxy daemon."""
    from quota_dash.proxy.daemon import start_proxy
    config_path = ctx.obj.get("config_path") if ctx.obj else None
    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    start_proxy(
        port=port,
        db_path=config.proxy.db_path,
        log_path=config.proxy.log_path,
        config_targets=config.proxy.targets,
        target_filter=target,
    )


@proxy.command()
def stop():
    """Stop the proxy daemon."""
    from quota_dash.proxy.daemon import stop_proxy
    stop_proxy()


@proxy.command()
def status():
    """Show proxy status."""
    from quota_dash.proxy.daemon import proxy_status
    info = proxy_status()
    if info:
        click.echo(f"Proxy running (PID {info['pid']})")
    else:
        click.echo("No proxy running.")
```

- [ ] **Step 4: Run ALL CLI tests to verify nothing broke**

Run: `cd quota-dash && pytest tests/test_cli.py -v`
Expected: All 5 tests PASS (3 existing + 2 new). The existing `test_cli_once_mode`, `test_cli_once_json_mode`, and `test_cli_help` tests must still pass after the `@click.command` → `@click.group(invoke_without_command=True)` refactor. Click handles this transparently — when no subcommand is invoked, the group's main function runs.

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/cli.py tests/test_cli.py && git commit -m "feat: proxy CLI subcommands (start/stop/status) and --with-proxy flag"
```

---

### Task 10: Provider Integration (Proxy-First Data)

**Files:**
- Modify: `quota-dash/src/quota_dash/providers/base.py`
- Modify: `quota-dash/src/quota_dash/providers/openai.py`
- Modify: `quota-dash/src/quota_dash/providers/anthropic.py`
- Modify: `quota-dash/src/quota_dash/app.py`
- Modify: `quota-dash/tests/test_providers.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_providers.py
import aiosqlite
from quota_dash.proxy.db import init_db, write_api_call, ApiCallRecord


@pytest.mark.asyncio
async def test_openai_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=500, output_tokens=200, total_tokens=700,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        ratelimit_reset=None, request_id="r-1",
        target_url="https://api.openai.com/v1/chat/completions",
    ))

    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp/nonexistent"))
    provider = OpenAIProvider(config, db_path=db_path)
    tokens = await provider.get_token_usage()
    assert tokens.input_tokens == 500
    assert tokens.output_tokens == 200
    assert tokens.source == "proxy"


@pytest.mark.asyncio
async def test_openai_falls_back_without_proxy():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp/nonexistent"))
    provider = OpenAIProvider(config, db_path=None)
    tokens = await provider.get_token_usage()
    assert tokens.source == "estimated"


@pytest.mark.asyncio
async def test_anthropic_get_token_usage_from_proxy(tmp_path):
    db_path = tmp_path / "usage.db"
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="anthropic", model="claude-opus-4-6", endpoint="/v1/messages",
        input_tokens=1000, output_tokens=400, total_tokens=1400,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        ratelimit_reset=None, request_id=None,
        target_url="https://api.anthropic.com/v1/messages",
    ))

    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp/nonexistent"))
    provider = AnthropicProvider(config, db_path=db_path)
    tokens = await provider.get_token_usage()
    assert tokens.input_tokens == 1000
    assert tokens.source == "proxy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quota-dash && pytest tests/test_providers.py::test_openai_get_token_usage_from_proxy -v`
Expected: FAIL — `TypeError: OpenAIProvider.__init__() got an unexpected keyword argument 'db_path'`

- [ ] **Step 3: Update Provider ABC**

```python
# src/quota_dash/providers/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData


class Provider(ABC):
    name: str

    @abstractmethod
    async def get_quota(self) -> QuotaInfo:
        ...

    @abstractmethod
    async def get_token_usage(self) -> TokenUsage:
        ...

    @abstractmethod
    async def get_context_window(self) -> ContextInfo:
        ...

    async def get_proxy_data(self) -> ProxyData | None:
        return None
```

- [ ] **Step 4: Update OpenAIProvider**

Update constructor and `get_token_usage` / `get_context_window` to check proxy first:

```python
# In openai.py, update __init__:
def __init__(self, config: ProviderConfig, db_path: Path | None = None) -> None:
    self._config = config
    self._db_path = db_path

# Add get_proxy_data:
async def get_proxy_data(self) -> ProxyData | None:
    if self._db_path is None or not self._db_path.exists():
        return None
    from quota_dash.proxy.db import query_provider_data
    return await query_provider_data(self._db_path, "openai")

# Update get_token_usage:
async def get_token_usage(self) -> TokenUsage:
    proxy = await self.get_proxy_data()
    if proxy is not None:
        return TokenUsage(
            input_tokens=proxy.input_tokens,
            output_tokens=proxy.output_tokens,
            total_tokens=proxy.total_tokens,
            history=[(proxy.last_call, proxy.total_tokens)],
            session_id=None,
            source="proxy",
        )
    log_db = self._config.log_path / "logs_1.sqlite"
    return parse_codex_logs(log_db)

# Update get_context_window:
async def get_context_window(self) -> ContextInfo:
    proxy = await self.get_proxy_data()
    if proxy is not None and proxy.input_tokens > 0:
        return ContextInfo(
            used_tokens=proxy.input_tokens,
            max_tokens=128000,
            percent_used=proxy.input_tokens / 128000 * 100,
            model=proxy.model or "gpt-4",
            note="last call snapshot",
        )
    return ContextInfo(
        used_tokens=0, max_tokens=128000,
        percent_used=0.0, model="gpt-4",
        note="approximation — Codex logs lack per-turn data",
    )
```

- [ ] **Step 5: Update AnthropicProvider (same pattern)**

Same changes: add `db_path` to constructor, implement `get_proxy_data`, update `get_token_usage` and `get_context_window` to check proxy first. Use `"anthropic"` as provider name and `200000` as max_tokens.

- [ ] **Step 6: Update app.py _init_providers**

```python
# In app.py, update _init_providers:
def _init_providers(self) -> None:
    provider_map = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}
    # Always pass db_path — providers check existence at query time, not construction
    db_path = self._config.proxy.db_path
    for name, pconfig in self._config.providers.items():
        if pconfig.enabled and name in provider_map:
            self._providers[name] = provider_map[name](pconfig, db_path=db_path)
```

- [ ] **Step 7: Run full test suite**

Run: `cd quota-dash && pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 8: Commit**

```bash
cd quota-dash && git add src/quota_dash/providers/ src/quota_dash/app.py tests/test_providers.py && git commit -m "feat: proxy-first data source in providers with fallback chain"
```

---

### Task 11: Full Integration Test

**Files:**
- Modify: `quota-dash/tests/test_proxy_app.py` (add end-to-end test)

- [ ] **Step 1: Add integration test**

```python
# Append to tests/test_proxy_app.py
from quota_dash.proxy.db import query_provider_data


@pytest.mark.asyncio
async def test_proxy_records_non_streaming_usage(db_path):
    """End-to-end: proxy forwards, records usage, dashboard queries it."""
    import httpx as _httpx
    from unittest.mock import AsyncMock, patch

    mock_upstream = _httpx.Response(
        200,
        json={
            "model": "gpt-4",
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        },
        headers={"x-request-id": "test-req", "x-ratelimit-remaining-tokens": "8000"},
        request=_httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    app = create_proxy_app(db_path=db_path)

    # Mock the httpx client to return our fake upstream response
    with patch("quota_dash.proxy.app.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.headers = dict(mock_upstream.headers)
        mock_resp.aread = AsyncMock(return_value=mock_upstream.content)
        mock_resp.aclose = AsyncMock()
        mock_client.build_request.return_value = _httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        mock_client.send = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        async with _httpx.AsyncClient(transport=_httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Trigger startup
            resp = await client.get("/health")
            assert resp.status_code == 200

            resp = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
            )

    # Now query the DB
    import asyncio
    await asyncio.sleep(0.1)  # let async write complete

    data = await query_provider_data(db_path, "openai")
    assert data is not None
    assert data.input_tokens == 100
    assert data.total_tokens == 150
```

- [ ] **Step 2: Run full test suite**

Run: `cd quota-dash && pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd quota-dash && git add tests/ && git commit -m "test: end-to-end proxy integration test"
```

---

### Task 12: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Reinstall and verify entry point**

```bash
cd quota-dash && pip install -e ".[dev]" && quota-dash --help
```
Expected: Help shows `proxy` subcommand group and `--with-proxy` flag

- [ ] **Step 2: Verify proxy CLI**

```bash
cd quota-dash && quota-dash proxy --help
```
Expected: Shows `start`, `stop`, `status` subcommands

- [ ] **Step 3: Run full test suite**

```bash
cd quota-dash && pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 4: Commit if any changes**

```bash
cd quota-dash && git add -u && git status && git diff --cached --stat
```
Only commit if there are actual changes.
