# Contributing to Fleetwright

## Development setup

```bash
git clone https://github.com/jddavenportOpen/fleetwright.git
cd fleetwright
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs `fleetwright` in editable mode plus the dev tools: pytest, ruff, and mypy.

For the cockpit:

```bash
cd cockpit
npm install
```

## Running tests

```bash
pytest              # full suite
pytest tests/test_fleet.py   # one file
pytest -x           # stop on first failure
```

The test suite uses real filesystem operations (tmpdir fixtures). No mocks for the DB adapters — tests hit SQLite directly. If you add a new adapter, add matching tests.

## Code style

- **Python:** `ruff check .` and `ruff format .` — 100-char line length, `I` (isort), `E`/`F`/`W` rules. Run before committing.
- **TypeScript:** `cd cockpit && npm run lint` (next lint).
- **Type annotations:** `mypy fleetwright/` — `ignore_missing_imports = true` so third-party stubs don't block you, but new code should be fully annotated.

```bash
# All checks in one shot
ruff check . && ruff format --check . && mypy fleetwright/ && pytest
```

## Project layout quick reference

```
fleetwright/        Python package (bridge, fleet, orchestrator, sdk)
cockpit/            Next.js 15 UI
agents/             Agent definitions + registry
config/             domains.yaml, model-registry.yaml
tests/              pytest — one file per fleetwright module
scripts/            bootstrap.sh, scan-secrets.py
docs/               MkDocs source
```

## Security: no secrets in commits

A gitleaks CI gate blocks any commit that contains API keys, tokens, or secrets. Run locally before pushing:

```bash
./gitleaks git .
```

or via the pre-commit hook (see `.gitleaks.toml`). The `.env` file is gitignored — never commit it.

## Pull request process

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes. Add or update tests.
3. Run the full check suite (`ruff`, `mypy`, `pytest`).
4. Open a PR against `main`. Describe what changed and why.
5. A maintainer will review within a few days.

PRs that add a new agent kind, SDK module, or fleet feature should include:
- The implementation
- At least one new test
- Updated docs in `docs/` if the user-facing behavior changes

## Adding a new domain agent example

1. Create `agents/examples/<name>/CLAUDE.md` — see existing examples for the pattern.
2. Add an entry to `agents/registry.json`.
3. Add an entry to `config/domains.example.yaml`.
4. If the agent introduces new SDK calls, document them in `docs/agent-authoring.md`.

## Reporting issues

Open an issue on GitHub with:
- Fleetwright version (`fleetwright-bridge --version` or `pip show fleetwright`)
- OS and Python version
- What you did, what you expected, what happened
- Relevant log output (bridge logs, pytest output, etc.)

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
