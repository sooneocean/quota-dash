# Contributing to quota-dash

Thank you for your interest in contributing! This document covers how to set up a dev environment, branch naming conventions, and the PR process.

## Prerequisites

- Python 3.11 or later
- git

## Dev Setup

```bash
# Clone the repo
git clone https://github.com/sooneocean/quota-dash.git
cd quota-dash

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest tests/ -v
```

## Branch Naming

Use one of the following prefixes:

| Prefix   | Use for                        |
|----------|-------------------------------|
| `feat/`  | New features                   |
| `fix/`   | Bug fixes                      |
| `docs/`  | Documentation changes          |
| `chore/` | Maintenance, deps, CI changes  |

Example: `feat/add-gemini-provider`, `fix/proxy-port-conflict`

## PR Process

1. **Open an issue first** for any significant change so the approach can be discussed before you invest time in code.
2. Fork the repo and create a branch from `main` using the naming convention above.
3. Make your commits (small, focused, with clear messages).
4. Ensure `pytest tests/ -v` passes locally.
5. Open a pull request against `main`. Fill in the PR description with what changed and why.
6. CI must pass (Python 3.11/3.12/3.13 matrix) before a maintainer will review.

## Code Style

- Follow the existing patterns in each module — consistency with surrounding code matters more than a particular style rule.
- No strict formatter is enforced yet (ruff/black is a future iteration). Keep diffs readable.
- Add tests for new behaviour in `tests/`.

## Issue-First Policy

Please open an issue before submitting a PR for large changes (new providers, architectural changes, new CLI commands). This avoids duplicate effort and keeps the project direction coherent.
