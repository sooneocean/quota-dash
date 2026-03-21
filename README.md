# quota-dash

[![CI](https://github.com/sooneocean/quota-dash/actions/workflows/ci.yml/badge.svg)](https://github.com/sooneocean/quota-dash/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/quota-dash)](https://pypi.org/project/quota-dash/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Multi-provider LLM quota monitoring TUI dashboard targeting Ghostty.

## Features

- Live dashboard showing token usage across OpenAI and Anthropic accounts
- Local HTTP proxy intercepts API calls to collect real-time usage data
- Ghostty terminal enhancements: threshold-based colors and three-tier desktop alerts
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
