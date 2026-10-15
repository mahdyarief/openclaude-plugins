# Contributing to journal-scout-mcp

Thanks for your interest! This guide covers the basics.

## Dev setup

```bash
git clone https://github.com/mahdyarief/journal-scout-mcp
cd journal-scout-mcp
uv venv
uv pip install -e ".[dev]"
```

## Workflow

1. Create a branch: `git checkout -b feat/my-feature`
2. Make changes; add tests for new behaviour.
3. Run tests: `pytest -q`
4. Lint: `ruff check .` (run pre-commit hooks or `pre-commit run --all-files`)
5. Commit with a conventional commit message:

   - `feat:` new capability
   - `fix:` bug fix
   - `docs:` docs only
   - `refactor:` no behaviour change
   - `test:` test only

## Adding a new provider

1. Extend `journal_scout_mcp/providers/base.py` (or a new provider file).
2. Register the provider in `journal_scout_mcp/providers/__init__.py`.
3. Add/extend tests in `tests/test_providers/`.
4. Update `README.md` tool table if the tool set changes.

## Pull requests

- Keep PRs small and focused.
- Ensure CI passes (GitHub Actions runs pytest + ruff + mypy).
- One consider: do not commit `config.json` (secrets).
