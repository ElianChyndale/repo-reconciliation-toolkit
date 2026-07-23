# Divergence Report

Comparison: `sha256:8aaa2bba3da99b239c943faba93f7028397b4fd03cb4653e5301698d74b12a69`

- Mode: `three_way`
- Risk: `high`
- Repository identity established: `true`
- Git relation: Commit graphs share history, but neither HEAD is present in the other snapshot's bounded graph.
- Changed files: 8
- Conflict candidates: 11

## Blockers

- At least one snapshot has uncommitted or untracked work.
- Potential both-sided conflicts require manual review.

## Conflict candidates

| Kind | Path | Symbol | Severity | Reason |
| --- | --- | --- | --- | --- |
| file | `contracts/Vault.sol` | `-` | high | Both snapshots changed the file differently from the shared base. |
| symbol | `contracts/Vault.sol` | `function:settle` | high | The same symbol changed differently from the shared base. |
| file | `migrations/002_add.sql` | `-` | high | Both snapshots changed the file differently from the shared base. |
| migration | `migrations/002_add.sql` | `-` | high | Both snapshots changed the same migration differently. |
| dependency | `pyproject.toml` | `pydantic` | medium | Both snapshots changed the dependency or lock state differently. |
| file | `pyproject.toml` | `-` | high | Both snapshots changed the file differently from the shared base. |
| file | `schemas/risk.schema.json` | `-` | high | Both snapshots changed the file differently from the shared base. |
| schema | `schemas/risk.schema.json` | `-` | high | Both snapshots changed the same schema differently. |
| file | `src/model.py` | `-` | high | Both snapshots changed the file differently from the shared base. |
| symbol | `src/model.py` | `function:score` | high | The same symbol changed differently from the shared base. |
| file | `uv.lock` | `-` | high | Both snapshots changed the file differently from the shared base. |

Conflict candidates are conservative review signals, not predictions that Git will necessarily emit a textual conflict.
