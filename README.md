# quota-dash

[![CI](https://github.com/sooneocean/quota-dash/actions/workflows/ci.yml/badge.svg)](https://github.com/sooneocean/quota-dash/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/quota-dash)](https://pypi.org/project/quota-dash/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Multi-provider LLM quota monitoring TUI dashboard targeting Ghostty.

## Preview

```
╔══════════════════════════════════════════════════════════════╗
║  quota-dash                                          v1.0.0 ║
╠══════════════════════════════════════════════════════════════╣
║ Provider  │ Balance  │ Tokens  │ Ctx  │ Rate   │ Source     ║
║ ▸ openai  │ $47.32   │ 20.5K   │ 62%  │ 9.0K   │ proxy     ║
║   anthro  │ $200.00  │ 63.9K   │ 35%  │ 50.0K  │ proxy     ║
║   google  │ N/A      │ 0       │ 0%   │ —      │ manual    ║
║   Total   │ $247.32  │ 84.4K   │      │        │           ║
╠══════════════════════════════════════════════════════════════╣
║ Quota              │ Tokens (session)                       ║
║ $47.32/$100 [proxy]│ In: 12.4K | Out: 8.1K | Total: 20.5K  ║
║ ████████░░░░ 47%   │ ▁▂▃▅▇█▆▄▃▂▁▃▅▇ [proxy]               ║
║────────────────────┼────────────────────────────────────────║
║ Context Window     │ Rate Limits                            ║
║ ██████░░░░ 62%     │ Tokens: 9,000 remaining                ║
║ 80K/128K — gpt-4   │ Requests: 99 remaining                 ║
╠══════════════════════════════════════════════════════════════╣
║ History (24h)                                                ║
║ 14:32  gpt-4    150 tok  /v1/chat/completions               ║
║ 14:28  gpt-4    420 tok  /v1/chat/completions               ║
║ 14:15  gpt-4    280 tok  /v1/chat/completions               ║
╠══════════════════════════════════════════════════════════════╣
║ [1/2/3] range  [r] refresh  [q] quit  [?] help              ║
╚══════════════════════════════════════════════════════════════╝
```

## Features

- Live dashboard monitoring 5 providers: OpenAI, Anthropic, Google, Mistral, and Groq
- Local HTTP proxy intercepts API calls to collect real-time usage data
- Export usage stats with `quota-dash stats` and `--export` flag
- Ghostty terminal enhancements: threshold-based colors and three-tier desktop alerts
- Webhook alerts for quota and rate-limit thresholds
- Time range switching (1 h / 6 h / 24 h) with `[1/2/3]` keys
- `quota-dash doctor` command to validate configuration and connectivity
- One-shot mode (`--once --json`) for scripting and automation

## Install

```bash
pip install quota-dash
```

## Quick Start

```bash
# Launch the live dashboard
quota-dash

# One-shot output (JSON)
quota-dash --once --json

# Start the proxy, then launch dashboard with proxy data
quota-dash proxy start
quota-dash --with-proxy
```

## Documentation

- [Getting Started](docs/guides/getting-started.md) — install, configuration, first run
- [Proxy Guide](docs/guides/proxy-guide.md) — transparent API interception for real-time usage
- [Ghostty Guide](docs/guides/ghostty.md) — terminal colors and alert system

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, branch naming, and PR process.

## License

MIT — see [LICENSE](LICENSE).
