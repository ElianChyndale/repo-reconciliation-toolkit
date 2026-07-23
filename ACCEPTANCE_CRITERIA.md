# Acceptance Criteria

v0.1 is complete only when:

- snapshot and comparison JSON Schemas use Draft 2020-12 and match Pydantic models;
- Git inspection is enforced by an allowlist and tested against forbidden commands;
- credentials and secret-prone paths are redacted;
- symlinks are not followed and absolute roots are absent from public output;
- Git branches, tags, dirty/untracked state, dependencies, migration hashes, schema
  hashes, runtime versions, test status, and local-ref divergence are represented;
- two-way and three-way file comparison is covered by hand-computable fixtures;
- Python, TypeScript, and Solidity symbol conflicts have fixtures;
- the five named reports are generated;
- all CSV, JSON, and JSONL results parse and contain records;
- repeated fixture report generation changes zero hashes;
- CI passes on Ubuntu and Windows with Python 3.11 and 3.12.

Required commands:

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/repo_reconciliation_toolkit
repo-reconcile validate fixtures/snapshots
repo-reconcile compare fixtures/snapshots/left.json fixtures/snapshots/right.json --base fixtures/snapshots/base.json --output reports/v0.1
repo-reconcile report --output reports/v0.1
```

