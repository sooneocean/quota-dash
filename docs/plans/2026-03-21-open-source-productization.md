# Open Source Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package quota-dash as a proper open source project with README, LICENSE, CI/CD, PyPI auto-publish, documentation, and community infrastructure.

**Architecture:** Static files (README, LICENSE, CONTRIBUTING, CHANGELOG, CI workflows, issue templates, docs) + pyproject.toml metadata update + CLI --version flag.

**Tech Stack:** GitHub Actions, PyPI trusted publishing, Keep-a-Changelog

**Spec:** `docs/specs/2026-03-21-open-source-productization.md`

---

### Task 1: LICENSE + pyproject.toml Metadata + .gitignore

**Files:**
- Create: `LICENSE`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Create MIT LICENSE**

```
MIT License

Copyright (c) 2026 sooneocean

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Update pyproject.toml metadata**

Read current `pyproject.toml`. Update `[project]` section to add: `version = "0.5.0"`, `description`, `readme`, `license`, `authors`, `keywords`, `classifiers`, `[project.urls]`. Keep existing `dependencies`, `scripts`, `build-system`, `optional-dependencies` unchanged.

- [ ] **Step 3: Update .gitignore**

Ensure these lines exist (append if missing):
```
dist/
build/
*.egg-info/
.superpowers/
```

- [ ] **Step 4: Commit**

```bash
cd quota-dash && git add LICENSE pyproject.toml .gitignore && git commit -m "chore: add MIT license, update pyproject.toml metadata, update .gitignore"
```

---

### Task 2: GitHub Actions CI + Release Workflows

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create ci.yml**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v
```

- [ ] **Step 2: Create release.yml**

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write
  id-token: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
```

- [ ] **Step 3: Commit**

```bash
cd quota-dash && git add .github/ && git commit -m "ci: add GitHub Actions CI and release workflows"
```

---

### Task 3: README + CONTRIBUTING + CHANGELOG

**Files:**
- Create: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `CHANGELOG.md`

- [ ] **Step 1: Create README.md**

See spec for content structure. Key elements:
- Badge row (CI, PyPI, Python, License)
- One-line description
- Features (4 bullets)
- Install (`pip install quota-dash`)
- Quick Start (dashboard, one-shot, proxy)
- Doc links → `docs/guides/`
- Contributing → CONTRIBUTING.md
- License: MIT

- [ ] **Step 2: Create CONTRIBUTING.md**

See spec for content: prerequisites, dev setup, branch naming, PR process, code style notes, issue-first policy.

- [ ] **Step 3: Create CHANGELOG.md**

See spec for full content — v0.5.0, v0.4.0, v0.1.0 entries in Keep-a-Changelog format.

- [ ] **Step 4: Commit**

```bash
cd quota-dash && git add README.md CONTRIBUTING.md CHANGELOG.md && git commit -m "docs: add README, CONTRIBUTING, and CHANGELOG"
```

---

### Task 4: Issue Templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`

- [ ] **Step 1: Create bug_report.md**

```markdown
---
name: Bug Report
about: Report a bug or unexpected behavior
title: "[Bug] "
labels: bug
---

## Description

A clear description of the bug.

## Steps to Reproduce

1.
2.
3.

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened.

## Environment

- OS:
- Python version:
- Terminal:
- quota-dash version (`quota-dash --version`):
```

- [ ] **Step 2: Create feature_request.md**

```markdown
---
name: Feature Request
about: Suggest a new feature or improvement
title: "[Feature] "
labels: enhancement
---

## Problem

What problem does this solve?

## Proposed Solution

How would you like it to work?

## Alternatives Considered

Other approaches you've thought of.
```

- [ ] **Step 3: Commit**

```bash
cd quota-dash && git add .github/ISSUE_TEMPLATE/ && git commit -m "docs: add issue templates for bug reports and feature requests"
```

---

### Task 5: User Documentation

**Files:**
- Create: `docs/guides/getting-started.md`
- Create: `docs/guides/proxy-guide.md`
- Create: `docs/guides/ghostty.md`
- Create: `docs/architecture.md`

- [ ] **Step 1: Create getting-started.md**

Content: system requirements, install from PyPI and source, first run, config file example with full TOML, provider setup (env vars).

- [ ] **Step 2: Create proxy-guide.md**

Content: what the proxy does, starting it, configuring CLI tools (OPENAI_BASE_URL, ANTHROPIC_BASE_URL), dashboard with proxy, config options, troubleshooting.

- [ ] **Step 3: Create ghostty.md**

Content: available enhancements, threshold colors, alert system (three tiers), detection mechanism.

- [ ] **Step 4: Create architecture.md**

Content: high-level diagram, module overview, data flow, proxy data flow, how to add a new provider.

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add docs/guides/ docs/architecture.md && git commit -m "docs: add user guides and architecture documentation"
```

---

### Task 6: CLI --version + Final Verification

**Files:**
- Modify: `src/quota_dash/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add --version to CLI**

In `cli.py`, add to the `@main.group` decorator chain:
```python
from importlib.metadata import version as pkg_version

# Add before @click.pass_context:
@click.version_option(version=pkg_version("quota-dash"), prog_name="quota-dash")
```

- [ ] **Step 2: Add test**

```python
# Append to tests/test_cli.py
def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "quota-dash" in result.output
```

- [ ] **Step 3: Run full test suite**

```bash
cd quota-dash && pip install -e ".[dev]" && pytest tests/ -v --tb=short
```
Expected: All PASS

- [ ] **Step 4: Verify build**

```bash
cd quota-dash && pip install build && python -m build
```
Expected: `dist/quota_dash-0.5.0.tar.gz` and `dist/quota_dash-0.5.0-py3-none-any.whl` created

- [ ] **Step 5: Commit and push**

```bash
cd quota-dash && git add src/quota_dash/cli.py tests/test_cli.py && git commit -m "feat: add --version flag to CLI"
cd quota-dash && git push
```
