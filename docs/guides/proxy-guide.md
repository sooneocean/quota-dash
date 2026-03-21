# Proxy Guide

The quota-dash local proxy is an HTTP server that sits between your CLI tools and the upstream AI provider APIs. It intercepts API responses, extracts token usage data in real time, and persists it to a local SQLite database. The dashboard then reads from that database for accurate, up-to-date token counts — no polling delay, no rate limit on quota queries.

## What the Proxy Does

Without the proxy, token data comes from log file parsing or manual config values. With the proxy:

- Every API response flowing through it is parsed for token usage (input, output, total)
- Rate limit headers (`x-ratelimit-remaining-tokens`, `anthropic-ratelimit-tokens-remaining`, etc.) are captured
- Model names, request IDs, and endpoints are recorded
- All data is written to a SQLite database at `~/.config/quota-dash/usage.db`
- The dashboard reads from this database and shows live token counts, call history, and rate limit status

The proxy is fully transparent — responses are forwarded unchanged to the calling application. SSE streaming responses are also supported: the proxy streams chunks to the client while simultaneously buffering them to extract the final usage summary.

### Supported Endpoints

| Path prefix         | Forwarded to            | Provider  |
|---------------------|-------------------------|-----------|
| `/v1/messages`      | `https://api.anthropic.com` | Anthropic |
| `/v1/chat/completions` | `https://api.openai.com` | OpenAI |
| `/v1/completions`   | `https://api.openai.com` | OpenAI    |
| `/v1/embeddings`    | `https://api.openai.com` | OpenAI    |

A `GET /health` endpoint returns `{"status": "ok", "db_path": "..."}`.

## Starting the Proxy

### Foreground (for testing)

```bash
quota-dash proxy start
```

The proxy listens on `127.0.0.1:8300` by default. Press `Ctrl+C` to stop it.

### Background daemon

The proxy manages its own PID file at `~/.config/quota-dash/proxy.pid`. To run it in the background:

```bash
quota-dash proxy start &
```

Or use a process manager of your choice (launchd, systemd, tmux, etc.).

### Check status

```bash
quota-dash proxy status
```

Output: `Proxy running (PID 12345)` or `No proxy running.`

### Stop the proxy

```bash
quota-dash proxy stop
```

This sends `SIGTERM` to the proxy process and removes the PID file.

### Custom port

```bash
quota-dash proxy start --port 9000
```

### Target a single provider

If you only want to intercept Anthropic traffic:

```bash
quota-dash proxy start --target anthropic
```

Requests for other providers will return a 404 from the proxy.

## Configuring CLI Tools

Point your AI CLI tools at the local proxy by overriding the base URL environment variable. The proxy preserves all headers (including your API key), so no credentials need to change.

### OpenAI / Codex CLI

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8300"
```

All requests to `/v1/chat/completions`, `/v1/completions`, and `/v1/embeddings` will route through the proxy.

### Anthropic / Claude CLI

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8300"
```

All requests to `/v1/messages` will route through the proxy.

Add these exports to your shell profile (`~/.zshrc`, `~/.bashrc`) to make them permanent.

### Verify interception

After running a prompt through a CLI tool, check that a record was written:

```bash
sqlite3 ~/.config/quota-dash/usage.db "SELECT timestamp, provider, model, total_tokens FROM api_calls ORDER BY timestamp DESC LIMIT 5;"
```

Or run quota-dash in one-shot mode and check the source column:

```bash
quota-dash --once
```

A `source: proxy` entry confirms the proxy is intercepting successfully.

## Dashboard with Proxy

### Auto-start proxy with dashboard

```bash
quota-dash --with-proxy
```

This launches the proxy as a background subprocess before opening the dashboard, waits one second for it to initialize, then starts the TUI. When you quit the dashboard, the proxy continues running.

### Custom proxy port with dashboard

```bash
quota-dash --with-proxy --proxy-port 9000
```

### Pre-started proxy

If the proxy is already running, just launch the dashboard normally:

```bash
quota-dash
```

The dashboard reads from the SQLite database regardless of how the proxy was started.

## Proxy Config Options

All proxy settings live under `[proxy]` in `~/.config/quota-dash/config.toml`:

```toml
[proxy]
enabled  = false          # Set true to treat proxy as always-on in the app
port     = 8300           # Listening port (127.0.0.1 only)
db_path  = "~/.config/quota-dash/usage.db"   # SQLite database location
log_path = "~/.config/quota-dash/proxy.log"  # Process log file

[proxy.targets]
openai    = "https://api.openai.com"     # Override OpenAI upstream
anthropic = "https://api.anthropic.com"  # Override Anthropic upstream
```

`proxy.targets` lets you point the proxy at alternative API endpoints (e.g., an Azure OpenAI deployment or a local model server that speaks the OpenAI API).

## Troubleshooting

### Proxy won't start — "already running"

```
Proxy already running (PID 12345). Use 'quota-dash proxy stop' first.
```

Either stop the existing proxy with `quota-dash proxy stop`, or if the process is gone but the PID file is stale, delete it manually:

```bash
rm ~/.config/quota-dash/proxy.pid
```

### No proxy data in dashboard

1. Confirm the proxy is running: `quota-dash proxy status`
2. Confirm your CLI tool is using the proxy URL: `echo $OPENAI_BASE_URL` / `echo $ANTHROPIC_BASE_URL`
3. Run a prompt, then check the database: `sqlite3 ~/.config/quota-dash/usage.db "SELECT COUNT(*) FROM api_calls;"`
4. Check the proxy log for errors: `tail -f ~/.config/quota-dash/proxy.log`

### Streaming responses show 0 tokens

The proxy buffers SSE chunks in a `StreamingBuffer` and extracts usage at the end of the stream. Some providers omit the usage summary from streaming responses. In that case, token counts for streaming calls will be zero — this is a provider limitation, not a proxy bug.

### Port already in use

If port 8300 is taken, choose a different port:

```bash
quota-dash proxy start --port 8400
export OPENAI_BASE_URL="http://127.0.0.1:8400"
export ANTHROPIC_BASE_URL="http://127.0.0.1:8400"
```

Update `proxy.port` in `config.toml` so the dashboard knows which port to associate with the proxy database.

### Connection refused from CLI tool

The proxy only binds to `127.0.0.1` (loopback). Ensure your `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` uses `127.0.0.1` and not `localhost` if your system resolves `localhost` to `::1` (IPv6).
