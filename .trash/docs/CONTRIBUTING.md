# Contributing

Thanks for helping improve **team-digest**!

## Setup
- Python 3.11+
- `pip install -e .[dev]`
- `pytest` to run tests

## Branch / PR
- Branch format: `feat/*`, `fix/*`, `docs/*`, `chore/*`
- Run tests locally. For workflow changes, include a screenshot or copy of logs.
- Keep PRs < 400 lines when possible.

## Commit conventions
Use conventional commits:
- `feat: …`, `fix: …`, `docs: …`, `chore: …`, `ci: …`, `refactor: …`, `test: …`

## Code style
- Black + isort + flake8 (or ruff)
- Keep functions small; write unit tests for parsing and date windows.
