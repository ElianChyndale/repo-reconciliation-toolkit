# Migration Plan

This plan is descriptive. No step is executed by the toolkit.

## 1. Confirm snapshot identity and freshness

A plan is unsafe if snapshots describe different repositories or stale refs.

- Verify repository names and sanitized remotes.
- Confirm both snapshots were captured from the intended copies.

## 2. Preserve every working state

Uncommitted and untracked work must be recoverable before integration.

- Treat dirty working trees as a release blocker.
- Create independent backups outside both repositories.
- Record dirty and untracked paths before any manual Git operation.
- Verify backup readability.

## 3. Establish the shared base and current remote state

Three-way attribution and remote divergence require a trusted base.

- Confirm the supplied base snapshot.
- Refresh remote refs manually only after backups are verified.

## 4. Reconcile schemas, migrations, and dependencies first

These changes constrain the order in which source code can be integrated.

- Resolve migration order collisions.
- Review schema compatibility and generated artifacts.
- Select dependency and lockfile changes intentionally.

## 5. Integrate source changes in small reviewed units

File and symbol candidates identify where manual review is most valuable.

- Start with one-sided changes.
- Resolve both-sided symbols with project owners.
- Do not discard a side solely because a file-level hash differs.

## 6. Run project validation

A clean merge is not evidence that behavior remains correct.

- Run targeted tests before broad suites.
- Parse generated research artifacts.
- Review failures and limitations.

## 7. Review and publish manually

Remote updates remain a deliberate human-controlled action.

- Inspect the final diff and commit graph.
- Confirm no secrets or machine-local paths were introduced.
- Update the remote only after review approval.
