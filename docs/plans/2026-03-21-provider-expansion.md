# Provider Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google AI, Groq, and Mistral providers with proxy parser support for Google's unique response format.

**Architecture:** 3 new provider files (same pattern as AnthropicProvider), Google parser/streaming additions, Google proxy route, app/cli registration.

**Tech Stack:** Existing — no new dependencies.

**Spec:** `docs/specs/2026-03-21-provider-expansion.md`

---

### Task 1: Google Parser + Streaming

**Files:**
- Modify: `src/quota_dash/proxy/parser.py`
- Modify: `src/quota_dash/proxy/streaming.py`
- Create: `tests/test_proxy_parser_google.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_proxy_parser_google.py
from quota_dash.proxy.parser import detect_provider, extract_usage
from quota_dash.proxy.streaming import StreamingBuffer
import json


def test_detect_google():
    body = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}}
    assert detect_provider(body) == "google"


def test_detect_google_no_false_positive_openai():
    body = {"choices": [{}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    assert detect_provider(body) == "openai"


def test_extract_google_usage():
    body = {"modelVersion": "gemini-2.0-flash", "candidates": [{}], "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50, "totalTokenCount": 150}}
    headers = {}
    record = extract_usage(body, headers, endpoint="/v1beta/models/gemini-2.0-flash:generateContent", target_url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent")
    assert record.provider == "google"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    assert record.model == "gemini-2.0-flash"


def test_extract_google_no_usage():
    body = {"candidates": [{}]}
    record = extract_usage(body, {}, endpoint="/v1beta/models/test", target_url="https://example.com")
    assert record.provider == "unknown"


def test_streaming_google_usage():
    buf = StreamingBuffer()
    buf.feed_line("data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}))
    buf.feed_line("data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": " world"}]}}], "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 20, "totalTokenCount": 70}}))

    record = buf.extract_usage(headers={}, endpoint="/v1beta/models/gemini:generateContent", target_url="https://generativelanguage.googleapis.com")
    assert record.provider == "google"
    assert record.input_tokens == 50
    assert record.output_tokens == 20
    assert record.total_tokens == 70
```

- [ ] **Step 2:** Run tests, confirm failure.

- [ ] **Step 3: Update parser.py**

Add Google detection as first check in `detect_provider()`:
```python
    # Google: has "candidates" and "usageMetadata"
    if "candidates" in body and "usageMetadata" in body:
        return "google"
```

Add Google extraction in `extract_usage()`:
```python
    elif provider == "google":
        usage_meta = body.get("usageMetadata", {})
        input_tokens = usage_meta.get("promptTokenCount", 0)
        output_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", 0)
        request_id = None
        rl_tokens = None
        rl_requests = None
        model = body.get("modelVersion")
```

- [ ] **Step 4: Update streaming.py**

Add `_google_usage` field to `StreamingBuffer.__init__`:
```python
self._google_usage: dict | None = None
```

In `feed_line()`, add Google detection:
```python
# Google: usageMetadata in any chunk
if "usageMetadata" in data:
    self._google_usage = data["usageMetadata"]
```

In `extract_usage()`, add Google case before the "no usage" fallback:
```python
# Google streaming
if self._google_usage is not None:
    u = self._google_usage
    return ApiCallRecord(
        provider="google",
        model=self._model,
        endpoint=endpoint,
        input_tokens=u.get("promptTokenCount", 0),
        output_tokens=u.get("candidatesTokenCount", 0),
        total_tokens=u.get("totalTokenCount", 0),
        ratelimit_remaining_tokens=None,
        ratelimit_remaining_requests=None,
        ratelimit_reset=None,
        request_id=None,
        target_url=target_url,
    )
```

- [ ] **Step 5:** Run tests, confirm all pass. Run `ruff check src/` and `mypy src/quota_dash/`.

- [ ] **Step 6: Commit**

```bash
git add src/quota_dash/proxy/parser.py src/quota_dash/proxy/streaming.py tests/test_proxy_parser_google.py && git commit -m "feat: Google AI response parser and streaming support"
```

---

### Task 2: Google Route + 3 Provider Files

**Files:**
- Modify: `src/quota_dash/proxy/handler.py`
- Create: `src/quota_dash/providers/google.py`
- Create: `src/quota_dash/providers/groq.py`
- Create: `src/quota_dash/providers/mistral.py`
- Create: `tests/test_providers_new.py`

- [ ] **Step 1: Update handler.py**

Add Google route to `DEFAULT_ROUTES` and `_PATH_TO_PROVIDER`:
```python
"/v1beta/models": "https://generativelanguage.googleapis.com",
```
```python
"/v1beta/models": "google",
```

- [ ] **Step 2: Write provider tests**

```python
# tests/test_providers_new.py
import pytest
from pathlib import Path
from quota_dash.config import ProviderConfig
from quota_dash.providers.google import GoogleProvider
from quota_dash.providers.groq import GroqProvider
from quota_dash.providers.mistral import MistralProvider


@pytest.mark.asyncio
async def test_google_quota_manual():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"), balance_usd=50.0, limit_usd=100.0)
    p = GoogleProvider(config)
    q = await p.get_quota()
    assert q.provider == "google"
    assert q.balance_usd == 50.0
    assert q.source == "manual"

@pytest.mark.asyncio
async def test_google_quota_unavailable():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config)
    q = await p.get_quota()
    assert q.source == "unavailable"

@pytest.mark.asyncio
async def test_google_token_usage_no_proxy():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config, db_path=None)
    t = await p.get_token_usage()
    assert t.source == "estimated"

@pytest.mark.asyncio
async def test_google_context_window():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GoogleProvider(config)
    c = await p.get_context_window()
    assert c.max_tokens == 1048576
    assert c.model == "gemini-2.0-flash"

@pytest.mark.asyncio
async def test_groq_quota_manual():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"), balance_usd=10.0, limit_usd=50.0)
    p = GroqProvider(config)
    q = await p.get_quota()
    assert q.provider == "groq"
    assert q.source == "manual"

@pytest.mark.asyncio
async def test_groq_context_window():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = GroqProvider(config)
    c = await p.get_context_window()
    assert c.max_tokens == 131072

@pytest.mark.asyncio
async def test_mistral_quota_manual():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"), balance_usd=25.0, limit_usd=100.0)
    p = MistralProvider(config)
    q = await p.get_quota()
    assert q.provider == "mistral"
    assert q.source == "manual"

@pytest.mark.asyncio
async def test_mistral_context_window():
    config = ProviderConfig(enabled=True, api_key_env="NONEXISTENT", log_path=Path("/tmp"))
    p = MistralProvider(config)
    c = await p.get_context_window()
    assert c.max_tokens == 131072
```

- [ ] **Step 3: Implement GoogleProvider**

```python
# src/quota_dash/providers/google.py
# Same pattern as AnthropicProvider:
# - name = "google"
# - get_quota() → manual or unavailable
# - get_token_usage() → proxy first, else estimated
# - get_context_window() → proxy snapshot or static (max_tokens=1048576, model="gemini-2.0-flash")
# - get_proxy_data() → query SQLite for "google"
```

- [ ] **Step 4: Implement GroqProvider**

```python
# src/quota_dash/providers/groq.py
# Same pattern, name = "groq", max_tokens=131072, model="llama-3.3-70b"
```

- [ ] **Step 5: Implement MistralProvider**

```python
# src/quota_dash/providers/mistral.py
# Same pattern, name = "mistral", max_tokens=131072, model="mistral-large"
```

- [ ] **Step 6:** Run tests, confirm all pass. Run ruff + mypy.

- [ ] **Step 7: Commit**

```bash
git add src/quota_dash/providers/google.py src/quota_dash/providers/groq.py src/quota_dash/providers/mistral.py src/quota_dash/proxy/handler.py tests/test_providers_new.py && git commit -m "feat: add Google AI, Groq, and Mistral providers"
```

---

### Task 3: App/CLI Registration + Final Verification

**Files:**
- Modify: `src/quota_dash/app.py`
- Modify: `src/quota_dash/cli.py`

- [ ] **Step 1: Update app.py _init_providers**

Add imports and update `provider_map`:
```python
from quota_dash.providers.google import GoogleProvider
from quota_dash.providers.groq import GroqProvider
from quota_dash.providers.mistral import MistralProvider

provider_map = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "groq": GroqProvider,
    "mistral": MistralProvider,
}
```

- [ ] **Step 2: Update cli.py provider_map_cls**

Same imports and map update in the CLI's provider construction.

- [ ] **Step 3: Run full test suite**

```bash
cd quota-dash && pytest tests/ -v --cov=quota_dash --cov-fail-under=70 --tb=short
```

- [ ] **Step 4: Run ruff + mypy**

```bash
ruff check src/ && mypy src/quota_dash/
```

- [ ] **Step 5: Commit and push**

```bash
git add src/quota_dash/app.py src/quota_dash/cli.py && git commit -m "feat: register Google/Groq/Mistral providers in app and CLI"
git push
```
