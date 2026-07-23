# Limitations

- Snapshots are observations, not backups. A hash cannot recover a file.
- Ahead/behind counts use local tracking refs and may be stale because the tool never
  fetches.
- Snapshot metadata cannot establish arbitrary commit ancestry.
- Lightweight symbol extraction is not a full parser for JavaScript, TypeScript, or
  Solidity and may miss dynamic or unusual declarations.
- A conflict candidate is not proof that Git will produce a merge conflict.
- File hashes cannot decide which side is semantically correct.
- Root fingerprints differ across physical paths and are not portable repository IDs;
  sanitized common remotes are preferred for identity.
- Dependency parsing covers common root manifests and does not fully resolve
  workspaces, transitive graphs, platform markers, or private registries.
- Migration and schema discovery uses documented path and suffix conventions.
- Default redaction cannot recognize every organization-specific secret filename.
- Optional tests are arbitrary external programs and may mutate a repository.
- Fixture reports are synthetic and are not findings about real codebases.

