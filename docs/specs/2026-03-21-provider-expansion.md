# quota-dash: Provider Expansion — Design Spec

> Add Google AI (Gemini), Groq, and Mistral providers with proxy parser support.

## Overview

Add 3 new providers following the existing pattern. All use manual quota + proxy data (no billing API integration). Google AI needs a custom parser for its unique response format. Groq and Mistral use OpenAI-compatible responses and share the existing `"openai"` parser detection.

## New Providers

| Provider | API Base URL | Response Format | Parser Detection |
|----------|-------------|-----------------|-----------------|
| Google AI | `generativelanguage.googleapis.com` | Custom (`candidates` + `usageMetadata`) | `"google"` (new) |
| Groq | `api.groq.com/openai` | OpenAI-compatible | `"openai"` (existing) |
| Mistral | `api.mistral.ai` | OpenAI-compatible | `"openai"` (existing) |

## File Changes

### New Files

```
src/quota_dash/providers/google.py     # GoogleProvider
src/quota_dash/providers/groq.py       # GroqProvider
src/quota_dash/providers/mistral.py    # MistralProvider
tests/test_providers_new.py            # Tests for new providers
tests/test_proxy_parser_google.py      # Google parser tests
```

### Modified Files

```
src/quota_dash/proxy/parser.py         # Add Google detection + usage extraction
src/quota_dash/proxy/streaming.py      # Add Google SSE format
src/quota_dash/proxy/handler.py        # Add Google route
src/quota_dash/app.py                  # Register new providers in _init_providers
src/quota_dash/cli.py                  # Register new providers in provider_map_cls
```

## Provider Implementation

All three follow the exact same pattern as `AnthropicProvider`:
- Constructor: `(config: ProviderConfig, db_path: Path | None = None)`
- `get_quota()` → manual config only → `"unavailable"` fallback
- `get_token_usage()` → proxy data first → `"estimated"` fallback
- `get_context_window()` → proxy `input_tokens` snapshot → static fallback
- `get_proxy_data()` → query SQLite by provider name

### Model Context Windows

| Provider | Default Model | Max Context |
|----------|--------------|-------------|
| Google AI | gemini-2.0-flash | 1,048,576 |
| Groq | llama-3.3-70b | 131,072 |
| Mistral | mistral-large | 131,072 |

### Provider Names (used in config, SQLite, parser)

- `"google"` — GoogleProvider
- `"groq"` — GroqProvider
- `"mistral"` — MistralProvider

## Config

```toml
[providers.google]
enabled = true
api_key_env = "GOOGLE_API_KEY"
log_path = "~/"

[providers.groq]
enabled = true
api_key_env = "GROQ_API_KEY"
log_path = "~/"

[providers.mistral]
enabled = true
api_key_env = "MISTRAL_API_KEY"
log_path = "~/"
```

No config schema changes needed — existing `ProviderConfig` works for all three.

## Proxy Parser Changes

### detect_provider — Add Google detection

```python
def detect_provider(body: dict) -> str:
    # Google: has "candidates" and "usageMetadata"
    if "candidates" in body and "usageMetadata" in body:
        return "google"
    # Anthropic (existing)
    if body.get("type") == "message" and "input_tokens" in body.get("usage", {}):
        return "anthropic"
    # OpenAI (existing) — also matches Groq/Mistral
    if "choices" in body and "prompt_tokens" in body.get("usage", {}):
        return "openai"
    return "unknown"
```

Google check comes first because its structure is most distinctive.

### extract_usage — Add Google field mapping

| Field | Google AI |
|-------|----------|
| input_tokens | `usageMetadata.promptTokenCount` |
| output_tokens | `usageMetadata.candidatesTokenCount` |
| total_tokens | `usageMetadata.totalTokenCount` |
| model | `modelVersion` |
| request_id | not available in response body |
| rate limit | not available in response headers |

### Google Streaming (SSE)

Google's streaming format differs from OpenAI/Anthropic:
- Each chunk is a JSON object with `candidates` array
- Usage appears in the **last chunk** as `usageMetadata` at the top level
- No SSE event types — just `data:` lines

StreamingBuffer addition:
```python
# In feed_line(), detect Google streaming usage:
if "usageMetadata" in data:
    self._google_usage = data["usageMetadata"]
```

## Proxy Route Changes

### handler.py — Add Google route

```python
DEFAULT_ROUTES = {
    "/v1/messages": "https://api.anthropic.com",
    "/v1/chat/completions": "https://api.openai.com",
    "/v1/completions": "https://api.openai.com",
    "/v1/embeddings": "https://api.openai.com",
    "/v1beta/models": "https://generativelanguage.googleapis.com",  # NEW
}

_PATH_TO_PROVIDER = {
    "/v1/messages": "anthropic",
    "/v1/chat/completions": "openai",
    "/v1/completions": "openai",
    "/v1/embeddings": "openai",
    "/v1beta/models": "google",  # NEW
}
```

### Groq/Mistral Routing

Groq and Mistral use `/v1/chat/completions` — same path as OpenAI. Users configure their CLI tools to point at the proxy:

```bash
# Groq through proxy
export GROQ_BASE_URL=http://localhost:8300

# Mistral through proxy
export MISTRAL_BASE_URL=http://localhost:8300
```

The proxy forwards to the OpenAI route by default. To use Groq/Mistral backends, users add custom targets:

```toml
[proxy.targets]
groq = "https://api.groq.com/openai"
mistral = "https://api.mistral.ai"
```

Proxy response is detected as `"openai"` — the dashboard shows Groq/Mistral token data through the OpenAI proxy records. The `model` field in the response (e.g. `llama-3.3-70b-versatile`, `mistral-large-latest`) distinguishes them in the HistoryTable.

**Limitation**: Proxy cannot automatically route Groq/Mistral requests to different upstream URLs based on path alone (they share `/v1/chat/completions`). Users must either:
1. Use separate proxy instances per provider, or
2. Accept that proxy records them all as `"openai"` provider

This is documented as a known limitation. The manual config quota values are per-provider regardless.

## App/CLI Registration

```python
# app.py and cli.py — add to provider_map
from quota_dash.providers.google import GoogleProvider
from quota_dash.providers.groq import GroqProvider
from quota_dash.providers.mistral import MistralProvider

provider_map = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,      # NEW
    "groq": GroqProvider,          # NEW
    "mistral": MistralProvider,    # NEW
}
```

## Testing

- Provider unit tests: each new provider returns correct data with manual config, unavailable without config, proxy data when available
- Parser tests: Google detection, Google usage extraction, existing OpenAI/Anthropic tests still pass
- Streaming tests: Google SSE usage extraction
- Handler tests: Google route resolution
- Integration: app with all 5 providers configured

## Non-Goals

- Billing API integration for any of the three providers
- Automatic Groq/Mistral proxy routing differentiation
- Provider-specific log file parsing
