# quota-dash: Code Quality Infrastructure — Design Spec

> Ruff linter, mypy type checking, pytest-cov with 70% threshold, CI integration.

## Scope

- Ruff: basic rules (E, F, W), line-length 120
- mypy: basic mode, ignore missing imports
- pytest-cov: 70% minimum coverage, fail CI if below
- CI: add lint + type check + coverage steps
- Fix any existing violations

## pyproject.toml Changes

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W"]

[tool.mypy]
python_version = "3.11"
warn_unused_configs = true
ignore_missing_imports = true

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
]
```

## CI Changes

Add ruff, mypy, coverage steps before/after pytest in ci.yml.

## Non-Goals

- ruff format (formatter)
- pre-commit hooks
- coverage badge
- strict mypy
