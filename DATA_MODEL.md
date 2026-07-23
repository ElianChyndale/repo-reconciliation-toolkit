# Data Model

## RepositorySnapshot

The snapshot schema version is `1.0.0`.

| Section | Contents |
| --- | --- |
| identity | repository name and privacy-preserving root fingerprint |
| git | branch, bounded parent graph, detached state, branches, tags, remotes, upstream divergence |
| working_tree | staged, modified, deleted, renamed, conflicted, and untracked paths |
| files | relative path or redacted token, kind, size, SHA-256, symbols, link metadata |
| dependencies | ecosystem, manifest, group, package, declared constraint, lock hash |
| migrations | relative path, SHA-256, framework, order key |
| schemas | relative path, SHA-256, schema kind |
| runtimes | tool and version text |
| environment_variable_names | present names only |
| test | not-run/passed/failed/timeout/error and non-content output hash |
| warnings | partial-observation and unsupported-format notes |
| exclusions | default ignored directories and caller exclusions |

`release_status` is one of `non_git`, `dirty`, `detached`, `clean_tagged`, or
`clean_untagged`. Commit graphs retain at most 200 nodes and explicitly mark
truncation.

`snapshot_id` is a SHA-256 digest of canonical snapshot JSON with the ID field omitted.

## ComparisonReport

The comparison schema version is `1.0.0`.

- references left, right, and optional base snapshot IDs;
- records Git, file, dependency, migration, and schema findings;
- classifies conservative file- and symbol-level conflict candidates;
- records blockers and a risk level;
- provides ordered, human-executed synchronization steps;
- never contains executable automation instructions.

## Symbols

v0.1 recognizes deterministic declarations in:

- Python: functions, async functions, and classes;
- JavaScript/TypeScript: functions, classes, interfaces, types, and exported constants;
- Solidity: contracts, libraries, interfaces, structs, enums, and functions.

Each symbol stores kind, qualified display name, start line, signature hash, and a
bounded declaration-body hash. Parsing is intentionally lightweight and may miss
dynamic or unusual syntax.
