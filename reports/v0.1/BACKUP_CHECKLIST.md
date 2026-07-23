# Backup Checklist

- [ ] Confirm both snapshot IDs and capture times.
- [ ] Copy each repository to an independent destination.
- [ ] Preserve untracked, staged, modified, renamed, deleted, and conflicted paths.
- [ ] Record branches, tags, HEAD commits, and sanitized remotes.
- [ ] Verify copied files can be read and their critical hashes match.
- [ ] Preserve databases, migrations, local-only configuration, and ignored data separately.
- [ ] Keep credentials outside repository backups and reports.
- [ ] Do not delete either source copy until reconciliation tests pass.

The toolkit does not create, verify, move, or delete backups.
