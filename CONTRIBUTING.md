# Contributing

Thanks for your interest in contributing.

## Development Setup

1. Create a virtual environment:

```bash
python3 -m venv .venv
```

2. Install dependencies:

```bash
.venv/bin/pip install -e '.[dev]'
```

3. Copy environment defaults:

```bash
cp .env.example .env
```

4. Run tests:

```bash
.venv/bin/pytest
```

## Pull Requests

- Keep changes focused and well-scoped.
- Add or update tests for behavioral changes.
- Update README/docs when config or behavior changes.
- Ensure all tests pass before opening a PR.

## Commit Style

Use clear, imperative commit messages describing what changed.
