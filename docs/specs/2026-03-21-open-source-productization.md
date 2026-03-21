# quota-dash v0.5.0: Open Source Productization — Design Spec

> README, CI/CD, PyPI auto-publish, documentation, and community-ready project structure.

## Overview

Transform quota-dash from a working tool into a properly packaged open source project. Add MIT license, comprehensive but layered documentation (concise README + detailed docs/), GitHub Actions CI (multi-Python matrix) and release pipeline (tag-triggered PyPI upload), issue templates, and contributing guidelines.

## Goals

1. Installable via `pip install quota-dash` from PyPI
2. CI runs tests on every PR/push across Python 3.11/3.12/3.13
3. Tag push (`v*`) auto-publishes to PyPI + creates GitHub Release
4. README is concise with badges, screenshot, and links to detailed docs
5. Contributors have clear guidance (CONTRIBUTING.md, issue templates)

## Non-Goals

- Linter/formatter setup (no ruff/black — future iteration)
- Test coverage reporting
- Docker images
- Documentation website (GitHub Pages, ReadTheDocs, etc.)
- Logo/branding design

## File Structure

### New Files

```
quota-dash/
├── README.md                          # Concise: badges + features + install + quick start + doc links
├── LICENSE                            # MIT
├── CONTRIBUTING.md                    # Dev setup, PR process, code style notes
├── CHANGELOG.md                       # Keep-a-Changelog format
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                     # PR/push: test matrix
│   │   └── release.yml                # Tag push: build + PyPI + GitHub Release
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── docs/
│   ├── guides/                        # User-facing documentation
│   │   ├── getting-started.md         # Detailed install + config
│   │   ├── proxy-guide.md             # Proxy feature tutorial
│   │   └── ghostty.md                # Ghostty enhancements
│   ├── architecture.md               # Architecture overview for contributors
│   ├── specs/                         # (existing) Internal design specs
│   └── plans/                         # (existing) Internal implementation plans
```

### Modified Files

```
├── pyproject.toml                     # Add metadata: description, license, authors, classifiers, urls
├── .gitignore                         # Ensure dist/, *.egg-info, .superpowers/ excluded
```

## CI Pipeline

### ci.yml (PR + push to main)

- **Trigger**: push to `main`, pull_request to `main`
- **Matrix**: Python 3.11, 3.12, 3.13 on `ubuntu-latest`
- **Steps**:
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` with matrix version
  3. `pip install -e ".[dev]"`
  4. `pytest tests/ -v`

### release.yml (tag push)

- **Trigger**: push tag matching `v*` (e.g., `v0.4.0`)
- **Steps**:
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` with Python 3.11
  3. `pip install build`
  4. `python -m build`
  5. `pypa/gh-action-pypi-publish@release/v1` using PyPI Trusted Publishing (OIDC, no secret needed)
  6. Create GitHub Release with `softprops/action-gh-release@v2` using tag as title

**Permissions block** (required for GitHub Release creation + PyPI trusted publishing):
```yaml
permissions:
  contents: write    # for creating GitHub Releases
  id-token: write    # for PyPI trusted publishing (OIDC)
```

**Required setup**: Configure PyPI Trusted Publisher at pypi.org → project → Publishing → Add new publisher (GitHub, repo: `sooneocean/quota-dash`, workflow: `release.yml`). No API token secret needed.

## pyproject.toml Metadata

```toml
[project]
name = "quota-dash"
version = "0.5.0"
description = "Multi-provider LLM quota monitoring TUI dashboard targeting Ghostty"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [
    {name = "sooneocean"}
]
keywords = ["llm", "quota", "dashboard", "tui", "textual", "ghostty", "openai", "anthropic"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Framework :: Textual",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Utilities",
]

[project.urls]
Homepage = "https://github.com/sooneocean/quota-dash"
Repository = "https://github.com/sooneocean/quota-dash"
Issues = "https://github.com/sooneocean/quota-dash/issues"
```

## README.md Content

Concise README with:
- Badge row: CI status, PyPI version, Python 3.11+, MIT License
- One-line description
- Screenshot placeholder (to be replaced with actual terminal screenshot)
- Features list (4 bullet points)
- Install section (`pip install quota-dash`)
- Quick Start (3 commands: dashboard, one-shot, proxy)
- Documentation links → `docs/`
- Contributing link → CONTRIBUTING.md
- License line

## LICENSE

MIT License, copyright 2026, sooneocean.

## CONTRIBUTING.md Content

- Prerequisites: Python 3.11+, git
- Dev setup: `git clone`, `pip install -e ".[dev]"`, `pytest`
- Branch naming: `feat/`, `fix/`, `docs/`
- PR process: fork → branch → commits → PR → CI must pass
- Code style notes: follow existing patterns, no strict formatter enforced yet
- Issue first: open an issue before large changes

## CHANGELOG.md

Keep-a-Changelog format (`keepachangelog.com`):

```markdown
# Changelog

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
```

## Documentation (docs/)

### getting-started.md
- System requirements (Python 3.11+)
- Install from PyPI (`pip install quota-dash`) or from source
- First run (`quota-dash --once`)
- Configuration file (`~/.config/quota-dash/config.toml`) with full TOML example
- Provider setup (API keys via environment variables)

### proxy-guide.md
- What the proxy does (transparent API response interception)
- Starting the proxy (`quota-dash proxy start`)
- Configuring CLI tools (`OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`)
- Dashboard with proxy (`quota-dash --with-proxy`)
- Proxy config options
- Troubleshooting

### ghostty.md
- What Ghostty enhancements are available
- Threshold colors (how they work, which widgets affected)
- Alert system (three tiers, notification behavior)
- How detection works (`$TERM_PROGRAM`)

### architecture.md
- High-level architecture diagram (text)
- Module overview: models, config, providers, data, proxy, widgets, ghostty
- Data flow: poll → providers → DataStore → widgets
- Proxy data flow: CLI → proxy → SQLite → providers → widgets
- How to add a new provider (step-by-step)

## Issue Templates

### bug_report.md
- Description, steps to reproduce, expected vs actual behavior
- Environment: OS, Python version, terminal, quota-dash version

### feature_request.md
- Problem description, proposed solution, alternatives considered

## CLI --version Support

Add `--version` flag to the CLI using `importlib.metadata`:

```python
from importlib.metadata import version
@main.command()  # or as a click option
click.version_option(version=version("quota-dash"), prog_name="quota-dash")
```

This reads the version from the installed package metadata — single source of truth in `pyproject.toml`.

## .gitignore Updates

Ensure these are excluded:
```
dist/
*.egg-info/
.superpowers/
build/
```

## Testing

No new Python tests — this is documentation and CI configuration. Verification:
- CI workflow syntax validated by GitHub Actions on push
- `python -m build` succeeds locally
- README renders correctly on GitHub
