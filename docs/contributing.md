# Contributing

See also: [CONTRIBUTING.md](https://github.com/jddavenportOpen/fleetwright/blob/main/CONTRIBUTING.md) in the repo root.

## Development setup

```bash
git clone https://github.com/jddavenportOpen/fleetwright.git
cd fleetwright
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

For the cockpit:
```bash
cd cockpit && npm install
```

## Running tests

```bash
pytest              # full suite (69 tests)
pytest tests/test_fleet.py   # one module
pytest -x           # stop on first failure
```

## Code style

```bash
ruff check . && ruff format --check . && mypy fleetwright/
```

## PR process

1. Fork → branch → implement → `pytest` → PR against `main`
2. PRs adding a new feature should include tests and docs updates
3. The gitleaks CI gate blocks any secret in the diff

## Docs

The docs site lives in `docs/` and is built with MkDocs Material:

```bash
pip install mkdocs-material
mkdocs serve        # live preview at http://localhost:8000
mkdocs build        # build to site/
```

GitHub Actions deploys docs to GitHub Pages on every push to `main`.
