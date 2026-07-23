# Contributing

Changes must preserve the read-only boundary and add evidence proportional to risk.

Run:

```bash
python -m pip install -e ".[dev]"
python scripts/generate-schemas.py --check
python scripts/generate-fixtures.py --check
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/repo_reconciliation_toolkit
repo-reconcile report --output reports/v0.1
python scripts/check-artifacts.py
```

Any new Git command requires a safety review and tests showing why it cannot mutate
the repository. New dependency, migration, schema, or symbol formats need valid,
invalid, boundary, and three-way comparison fixtures.

Do not contribute private repository snapshots, absolute local paths, tokens, cookies,
keys, environment values, or proprietary source.

