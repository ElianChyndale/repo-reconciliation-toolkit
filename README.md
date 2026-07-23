# Repo Reconciliation Toolkit

Repo Reconciliation Toolkit is a read-only command-line tool for capturing repository
state and planning safe reconciliation between two local copies. It records Git refs,
dirty and untracked paths, dependency declarations, lock hashes, migrations, schemas,
runtime versions, optional test status, and locally known remote divergence.

Given two snapshots—and preferably a shared-base snapshot—it produces file and symbol
change attribution, conservative conflict candidates, a migration plan, and a backup
checklist.

The toolkit never performs the reconciliation. It contains no automatic `fetch`,
`pull`, `push`, `merge`, `rebase`, `reset`, `checkout`, branch update, dependency
installation, or file deletion path.

## Portfolio role

This is a supporting repository-governance asset, not a fifth flagship project. It
does not import or modify EcoQuant, Auralynq, Green Bond Lending, AI Research
Engineering Lab, PDF Manager, GreenFinanceBench, Research Defence Lab, or Financial
AI Contracts code.

## Quick start

Python 3.11 or newer is required. The default installation is offline and needs no
API key.

```bash
python -m pip install -e ".[dev]"
python -m pytest

repo-reconcile snapshot ../copy-a --output snapshots/copy-a
repo-reconcile snapshot ../copy-b --output snapshots/copy-b

repo-reconcile compare \
  snapshots/copy-a/REPO_SNAPSHOT.json \
  snapshots/copy-b/REPO_SNAPSHOT.json \
  --base snapshots/base/REPO_SNAPSHOT.json \
  --output reports/reconciliation
```

If no base is supplied, the report remains useful for inventory comparison but marks
the absence as a blocker. It cannot reliably attribute which side introduced a
change.

## Public commands

```text
repo-reconcile snapshot REPOSITORY --output DIRECTORY
repo-reconcile compare LEFT RIGHT [--base BASE] --output DIRECTORY
repo-reconcile validate PATH [--type snapshot|comparison]
repo-reconcile report --output reports/v0.1
```

Snapshot options include:

- `--captured-at` for a deterministic RFC 3339 fixture time;
- repeatable `--exclude` directory names;
- `--git-executable` for an explicit Git binary;
- `--test-command ...` plus `--allow-test-execution`.

`--test-command` consumes the remaining arguments and uses `shell=False`. Test suites
are arbitrary programs and may change a repository, so the explicit authorization
flag is required. Output text is not retained—only status, duration, exit code, and a
SHA-256 digest.

## Required reports

- `REPO_SNAPSHOT.json`
- `DEPENDENCY_REPORT.md`
- `DIVERGENCE_REPORT.md`
- `MIGRATION_PLAN.md`
- `BACKUP_CHECKLIST.md`

Machine-readable CSV, JSON, and JSONL release evidence is written under
`research/results/v0.1/`.

## Privacy defaults

- Absolute repository roots are replaced by a one-way fingerprint.
- Known secret-prone paths are replaced by stable redacted tokens.
- Environment-variable values are never collected.
- Remote credentials, query strings, and fragments are removed.
- File contents are never stored.
- Symlinks are recorded but never followed.
- `.git`, virtual environments, dependency folders, caches, and build outputs are
  excluded.

See [SAFETY_MODEL.md](SAFETY_MODEL.md) before using the tool on sensitive work.

## Conflict interpretation

Three-way comparison labels a file `both_different` when left and right both differ
from base and from each other. For Python, JavaScript/TypeScript, and Solidity, the
tool also fingerprints selected declarations to identify same-symbol changes.

These are conservative review signals. They do not prove that Git will emit a textual
conflict, nor do they determine which change is correct.

## Documentation

- [Specification](SPEC.md)
- [Data model](DATA_MODEL.md)
- [Safety model](SAFETY_MODEL.md)
- [Snapshot guide](docs/SNAPSHOT_GUIDE.md)
- [Comparison guide](docs/COMPARISON_GUIDE.md)
- [Acceptance criteria](ACCEPTANCE_CRITERIA.md)
- [Limitations](LIMITATIONS.md)
- [Security policy](SECURITY.md)
- [Contribution guide](CONTRIBUTING.md)

## Synthetic fixture notice

The base, left, and right snapshots under `fixtures/` are synthetic. Their commits,
remotes, dependency constraints, schema hashes, migrations, test results, and
conflicts are teaching and verification inputs, not observations about real
repositories.

## License

MIT. See [LICENSE](LICENSE).

