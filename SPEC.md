# Specification

## Purpose

Repo Reconciliation Toolkit records the observable state of local repositories and
compares immutable snapshots. It helps a user decide how to preserve and reconcile
work; it does not perform the reconciliation.

## Normative safety rules

- Repository inspection MUST use read-only Git commands.
- The tool MUST NOT run commands that update refs, the index, working files, remotes,
  configuration, submodules, or ignored data.
- The tool MUST NOT contact a remote. Ahead/behind counts use existing local remote
  tracking refs and MUST be labelled stale-capable.
- Optional tests MUST use an argument vector with `shell=False`.
- Snapshot output MUST NOT be written inside the scanned repository unless the user
  explicitly selects a path there.
- Environment-variable names MAY be recorded; values MUST NOT be recorded.
- Remote URLs MUST have credentials, query strings, and fragments removed.
- File contents MUST NOT be stored. Files are represented by metadata, SHA-256, and
  bounded symbol fingerprints.
- Known secret-prone paths MUST be redacted by default.
- Symlinks MUST be recorded as links and MUST NOT be followed.

## Snapshot scope

A snapshot contains:

- repository identity without an absolute root path;
- current commit, branch, detached state, branches, tags, remotes, and upstream
  divergence from locally available refs;
- a bounded 200-node parent graph with an explicit truncation flag and release status;
- staged, modified, deleted, renamed, conflicted, and untracked paths;
- a filtered file inventory with sizes, hashes, kinds, and symbol fingerprints;
- declared dependencies and lockfile hashes;
- migration and schema file hashes;
- runtime versions and environment-variable names;
- an optional test result;
- collection warnings and explicit exclusions.

## Comparison scope

Two-way comparison reports differences between snapshots. Three-way comparison also
accepts a base snapshot and identifies:

- files changed only on the left or right;
- files changed identically;
- files changed differently on both sides;
- symbols changed differently on both sides;
- migration-order and schema divergence;
- dependency declaration and lockfile divergence;
- dirty-worktree and missing-base blockers.

Predictions are conservative signals. A potential conflict is not a claim that Git
will produce a textual merge conflict.

## Determinism

Commands accept a caller-supplied UTC capture time for fixtures and reproducible
audits. Reports sort repositories, paths, branches, tags, dependencies, symbols, and
findings. No report contains a generation clock.
