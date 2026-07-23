# Comparison Guide

## Prefer three snapshots

A left and right snapshot show that files differ. A base snapshot allows the toolkit
to classify one-sided, identical both-sided, and different both-sided changes.

```bash
repo-reconcile compare left.json right.json \
  --base base.json \
  --output reports/reconciliation
```

## Status meanings

| Status | Meaning |
| --- | --- |
| `left_only` / `right_only` | path exists on one side in a two-way comparison |
| `modified` | hashes differ without a base |
| `left_only_change` | only left differs from base |
| `right_only_change` | only right differs from base |
| `both_same` | both differ from base in the same way |
| `both_different` | both differ from base and each other |
| `deleted_both` | both removed a base path |

Dependency values include declared constraints and lock hashes. Migration values
include framework, order key, and file hash. Schema values include kind and file
hash.

## Recommended order

The generated plan starts with identity, freshness, and backups; then addresses
schemas, migrations, dependencies, and source code before validation and publication.
Every action remains manual.

