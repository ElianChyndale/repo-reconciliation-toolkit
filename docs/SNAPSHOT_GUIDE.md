# Snapshot Guide

## Before capture

Identify the exact repository copy and choose an output directory outside it. The
tool can write inside the repository when explicitly requested, but doing so creates
new untracked output and can contaminate later snapshots.

```bash
repo-reconcile snapshot /path/to/repository --output /path/to/audit/copy-a
```

The snapshot uses only locally available information. It does not fetch remote refs,
so ahead/behind counts may be stale. This is recorded in the snapshot model.

## Captured state

- HEAD, branch, detached state, local branches, tags, sanitized remotes;
- upstream ahead/behind counts from local tracking refs;
- staged, modified, deleted, renamed, copied, conflicted, and untracked paths;
- filtered file metadata and SHA-256 hashes;
- declared dependencies and lockfile hashes;
- migration and schema hashes;
- Python, Git, and available Node runtime versions;
- allowlisted environment-variable names;
- optional test status.

## Exclusions and redaction

Use repeatable `--exclude` values for repository-specific generated folders:

```bash
repo-reconcile snapshot . --output ../audit --exclude local-data --exclude model-cache
```

Secret-prone paths are redacted before content access. If a repository uses an
unusual secret filename, exclude its directory explicitly.

## Optional tests

```bash
repo-reconcile snapshot . \
  --output ../audit \
  --allow-test-execution \
  --test-timeout 120 \
  --test-command python -m pytest -q
```

The test command must be last because it consumes all remaining arguments. It runs
without a shell, but the test program itself is outside the toolkit's safety
guarantee.

