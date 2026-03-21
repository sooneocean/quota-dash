# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - 2026-03-21

### Added
- Google AI (Gemini), Groq, and Mistral provider support
- Configurable alert thresholds via `[alerts]` config section
- Interactive config wizard (`quota-dash config init`)
- Proxy auto-start (`[proxy] auto_start = true`)
- macOS launchd service install/uninstall (`quota-dash proxy install/uninstall`)
- Usage data export (`quota-dash export --format csv/json --period 7d`)
- Usage statistics command (`quota-dash stats`)
- Webhook notifications for Slack/Discord/generic endpoints
- Dashboard time range switching (1h/24h/7d with keyboard shortcuts 1/2/3)
- Event-driven real-time monitoring via SQLite file watching
- MkDocs Material documentation site

### Changed
- Provider refresh parallelized with asyncio.gather
- Test coverage improved from 82% to 93%+ (224 tests)

### Fixed
- Code quality: ruff linter + mypy type checking enforced in CI
- CI coverage threshold set to 90%

## [0.5.0] - 2026-03-21

### Added
- Open source packaging: README, LICENSE (MIT), CONTRIBUTING.md, CHANGELOG.md
- GitHub Actions CI (Python 3.11/3.12/3.13 test matrix)
- Automated PyPI release on tag push via trusted publishing
- User documentation (getting-started, proxy-guide, ghostty)
- Architecture documentation for contributors
- Issue templates (bug report, feature request)

## [0.4.0] - 2026-03-21

### Added
- Ghostty terminal detection and threshold color enhancement
- Three-tier quota alert system with OSC 9 desktop notifications
- Local HTTP proxy for real-time token usage collection
- SQLite storage for API call history
- Overview+Detail dashboard layout with Textual native widgets
- Response parser with OpenAI/Anthropic auto-detection
- SSE streaming support for usage extraction
- Proxy CLI subcommands (start/stop/status)
- `--with-proxy` flag for dashboard
- `--once --json` one-shot mode

### Changed
- Replaced text-render widgets with Textual DataTable, ProgressBar, Sparkline
- All-provider refresh (previously single-provider)
- Provider data source priority: proxy → API → log → manual

## [0.1.0] - 2026-03-20

### Added
- Initial release: TUI dashboard with OpenAI and Anthropic providers
- TOML configuration
- Manual quota entry fallback
- Default and Ghostty CSS themes
- CLI with --once and --json modes
