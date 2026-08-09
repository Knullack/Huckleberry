<!-- markdownlint-disable -->

# Contributing

## Development setup
1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Install pre-commit hooks:

```bash
pre-commit install
```

## Common commands
```bash
ruff check .
ruff format .
mypy custom_components/huckleberry
pytest
```

## Contribution expectations
- Keep changes focused and typed.
- Add or update tests for behavior changes.
- Preserve user privacy and avoid logging sensitive payloads.
- Keep predictions framed as probabilistic observations.

## Commit quality
- Keep commits atomic.
- Use clear messages.
- Ensure CI passes before release.
