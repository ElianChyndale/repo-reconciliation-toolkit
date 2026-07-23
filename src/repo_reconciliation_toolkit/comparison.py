"""Two-way and three-way snapshot comparison."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypeVar

from repo_reconciliation_toolkit.canonical import object_id
from repo_reconciliation_toolkit.models import (
    ComparisonReport,
    ComparisonSummary,
    ConflictCandidate,
    DependencyRecord,
    FileDelta,
    FileRecord,
    MigrationRecord,
    RepositorySnapshot,
    SchemaRecord,
    SyncStep,
    ValueDelta,
)
from repo_reconciliation_toolkit.snapshot import EMPTY_DIGEST

T = TypeVar("T")


def _file_hash(value: FileRecord | None) -> str | None:
    return None if value is None else value.sha256


def _delta_status(
    base: str | None,
    left: str | None,
    right: str | None,
    *,
    has_base: bool,
) -> str | None:
    if not has_base:
        if left is None and right is not None:
            return "right_only"
        if right is None and left is not None:
            return "left_only"
        if left != right:
            return "modified"
        return None
    if left == right:
        if left == base:
            return None
        return "deleted_both" if left is None else "both_same"
    if left == base:
        return "right_only_change"
    if right == base:
        return "left_only_change"
    if base is None:
        if left is None:
            return "right_only_change"
        if right is None:
            return "left_only_change"
    return "both_different"


def _files(
    left: RepositorySnapshot,
    right: RepositorySnapshot,
    base: RepositorySnapshot | None,
) -> list[FileDelta]:
    left_map = {item.path: item for item in left.files}
    right_map = {item.path: item for item in right.files}
    base_map = {} if base is None else {item.path: item for item in base.files}
    paths = sorted(set(left_map) | set(right_map) | set(base_map))
    deltas: list[FileDelta] = []
    for path in paths:
        base_hash = _file_hash(base_map.get(path))
        left_hash = _file_hash(left_map.get(path))
        right_hash = _file_hash(right_map.get(path))
        status = _delta_status(
            base_hash,
            left_hash,
            right_hash,
            has_base=base is not None,
        )
        if status is not None:
            deltas.append(
                FileDelta(
                    path=path,
                    status=status,  # type: ignore[arg-type]
                    base_hash=base_hash,
                    left_hash=left_hash,
                    right_hash=right_hash,
                )
            )
    return deltas


def _dependency_key(item: DependencyRecord) -> str:
    return "|".join((item.ecosystem, item.manifest, item.group, item.name))


def _dependency_value(item: DependencyRecord) -> str:
    return "|".join(
        (
            item.declared,
            item.lockfile or "",
            item.lock_hash or "",
        )
    )


def _migration_key(item: MigrationRecord) -> str:
    return item.path


def _migration_value(item: MigrationRecord) -> str:
    return "|".join((item.framework, item.order_key, item.sha256))


def _schema_key(item: SchemaRecord) -> str:
    return item.path


def _schema_value(item: SchemaRecord) -> str:
    return "|".join((item.schema_kind, item.sha256))


def _value_deltas(
    left_values: list[T],
    right_values: list[T],
    base_values: list[T] | None,
    key: Callable[[T], str],
    value: Callable[[T], str],
) -> list[ValueDelta]:
    left_map = {key(item): value(item) for item in left_values}
    right_map = {key(item): value(item) for item in right_values}
    base_map = {} if base_values is None else {key(item): value(item) for item in base_values}
    keys = sorted(set(left_map) | set(right_map) | set(base_map))
    results: list[ValueDelta] = []
    for item_key in keys:
        base_value = base_map.get(item_key)
        left_value = left_map.get(item_key)
        right_value = right_map.get(item_key)
        status = _delta_status(
            base_value,
            left_value,
            right_value,
            has_base=base_values is not None,
        )
        if status is not None:
            results.append(
                ValueDelta(
                    key=item_key,
                    status=status,  # type: ignore[arg-type]
                    base_value=base_value,
                    left_value=left_value,
                    right_value=right_value,
                )
            )
    return results


def _symbol_conflicts(
    path: str,
    left_file: FileRecord | None,
    right_file: FileRecord | None,
    base_file: FileRecord | None,
) -> list[ConflictCandidate]:
    if left_file is None or right_file is None:
        return []
    left_symbols = {(item.kind, item.name): item for item in left_file.symbols}
    right_symbols = {(item.kind, item.name): item for item in right_file.symbols}
    base_symbols = (
        {} if base_file is None else {(item.kind, item.name): item for item in base_file.symbols}
    )
    conflicts: list[ConflictCandidate] = []
    for symbol_key in sorted(set(left_symbols) & set(right_symbols)):
        left_symbol = left_symbols[symbol_key]
        right_symbol = right_symbols[symbol_key]
        base_symbol = base_symbols.get(symbol_key)
        left_changed = base_symbol is None or left_symbol.body_hash != base_symbol.body_hash
        right_changed = base_symbol is None or right_symbol.body_hash != base_symbol.body_hash
        if left_changed and right_changed and left_symbol.body_hash != right_symbol.body_hash:
            conflicts.append(
                ConflictCandidate(
                    kind="symbol",
                    path=path,
                    symbol=f"{symbol_key[0]}:{symbol_key[1]}",
                    severity="high",
                    reason="The same symbol changed differently from the shared base.",
                )
            )
    return conflicts


def _same_repository_identity(
    left: RepositorySnapshot,
    right: RepositorySnapshot,
) -> bool:
    if left.repository_name != right.repository_name:
        return False
    left_urls = {
        remote.fetch_url
        for remote in left.git.remotes
        if remote.fetch_url not in {"<local-path>", "<missing>", "<empty>"}
    }
    right_urls = {
        remote.fetch_url
        for remote in right.git.remotes
        if remote.fetch_url not in {"<local-path>", "<missing>", "<empty>"}
    }
    if left_urls and right_urls:
        return bool(left_urls & right_urls)
    return left.root_fingerprint == right.root_fingerprint


def _git_relation(left: RepositorySnapshot, right: RepositorySnapshot) -> str:
    if left.git.head_commit is None or right.git.head_commit is None:
        return "At least one snapshot has no Git HEAD."
    if left.git.head_commit == right.git.head_commit:
        return "Both snapshots point to the same HEAD commit."
    left_known = {branch.commit for branch in left.git.branches}
    right_known = {branch.commit for branch in right.git.branches}
    if left.git.head_commit in right_known:
        return "The left HEAD is present in the right snapshot's local branch refs."
    if right.git.head_commit in left_known:
        return "The right HEAD is present in the left snapshot's local branch refs."
    left_commits = {node.commit for node in left.git.commits}
    right_commits = {node.commit for node in right.git.commits}
    if left.git.head_commit in right_commits:
        return "The left HEAD is an ancestor or retained commit in the right commit graph."
    if right.git.head_commit in left_commits:
        return "The right HEAD is an ancestor or retained commit in the left commit graph."
    common = left_commits & right_commits
    if common:
        return (
            "Commit graphs share history, but neither HEAD is present in the other "
            "snapshot's bounded graph."
        )
    return "HEAD commits differ; ancestry is not established by snapshot metadata."


def _sync_steps(has_base: bool, dirty: bool) -> list[SyncStep]:
    steps = [
        SyncStep(
            order=1,
            title="Confirm snapshot identity and freshness",
            rationale=(
                "A plan is unsafe if snapshots describe different repositories or stale refs."
            ),
            manual_checks=[
                "Verify repository names and sanitized remotes.",
                "Confirm both snapshots were captured from the intended copies.",
            ],
        ),
        SyncStep(
            order=2,
            title="Preserve every working state",
            rationale="Uncommitted and untracked work must be recoverable before integration.",
            manual_checks=[
                "Create independent backups outside both repositories.",
                "Record dirty and untracked paths before any manual Git operation.",
                "Verify backup readability.",
            ],
        ),
        SyncStep(
            order=3,
            title="Establish the shared base and current remote state",
            rationale="Three-way attribution and remote divergence require a trusted base.",
            manual_checks=[
                (
                    "Confirm the supplied base snapshot."
                    if has_base
                    else "Locate and capture a shared-base snapshot before choosing winners."
                ),
                "Refresh remote refs manually only after backups are verified.",
            ],
        ),
        SyncStep(
            order=4,
            title="Reconcile schemas, migrations, and dependencies first",
            rationale="These changes constrain the order in which source code can be integrated.",
            manual_checks=[
                "Resolve migration order collisions.",
                "Review schema compatibility and generated artifacts.",
                "Select dependency and lockfile changes intentionally.",
            ],
        ),
        SyncStep(
            order=5,
            title="Integrate source changes in small reviewed units",
            rationale="File and symbol candidates identify where manual review is most valuable.",
            manual_checks=[
                "Start with one-sided changes.",
                "Resolve both-sided symbols with project owners.",
                "Do not discard a side solely because a file-level hash differs.",
            ],
        ),
        SyncStep(
            order=6,
            title="Run project validation",
            rationale="A clean merge is not evidence that behavior remains correct.",
            manual_checks=[
                "Run targeted tests before broad suites.",
                "Parse generated research artifacts.",
                "Review failures and limitations.",
            ],
        ),
        SyncStep(
            order=7,
            title="Review and publish manually",
            rationale="Remote updates remain a deliberate human-controlled action.",
            manual_checks=[
                "Inspect the final diff and commit graph.",
                "Confirm no secrets or machine-local paths were introduced.",
                "Update the remote only after review approval.",
            ],
        ),
    ]
    if dirty:
        steps[1].manual_checks.insert(0, "Treat dirty working trees as a release blocker.")
    return steps


def compare_snapshots(
    left: RepositorySnapshot,
    right: RepositorySnapshot,
    base: RepositorySnapshot | None = None,
) -> ComparisonReport:
    file_deltas = _files(left, right, base)
    dependency_deltas = _value_deltas(
        left.dependencies,
        right.dependencies,
        None if base is None else base.dependencies,
        _dependency_key,
        _dependency_value,
    )
    migration_deltas = _value_deltas(
        left.migrations,
        right.migrations,
        None if base is None else base.migrations,
        _migration_key,
        _migration_value,
    )
    schema_deltas = _value_deltas(
        left.schemas,
        right.schemas,
        None if base is None else base.schemas,
        _schema_key,
        _schema_value,
    )
    conflicts: list[ConflictCandidate] = []
    left_files = {item.path: item for item in left.files}
    right_files = {item.path: item for item in right.files}
    base_files = {} if base is None else {item.path: item for item in base.files}
    for file_delta in file_deltas:
        if file_delta.status == "both_different":
            conflicts.append(
                ConflictCandidate(
                    kind="file",
                    path=file_delta.path,
                    symbol=None,
                    severity="high",
                    reason="Both snapshots changed the file differently from the shared base.",
                )
            )
            conflicts.extend(
                _symbol_conflicts(
                    file_delta.path,
                    left_files.get(file_delta.path),
                    right_files.get(file_delta.path),
                    base_files.get(file_delta.path),
                )
            )
    for dependency_delta in dependency_deltas:
        if dependency_delta.status == "both_different":
            conflicts.append(
                ConflictCandidate(
                    kind="dependency",
                    path=dependency_delta.key.split("|")[1],
                    symbol=dependency_delta.key.split("|")[-1],
                    severity="medium",
                    reason="Both snapshots changed the dependency or lock state differently.",
                )
            )
    for migration_delta in migration_deltas:
        if migration_delta.status == "both_different":
            conflicts.append(
                ConflictCandidate(
                    kind="migration",
                    path=migration_delta.key,
                    symbol=None,
                    severity="high",
                    reason="Both snapshots changed the same migration differently.",
                )
            )
    for schema_delta in schema_deltas:
        if schema_delta.status == "both_different":
            conflicts.append(
                ConflictCandidate(
                    kind="schema",
                    path=schema_delta.key,
                    symbol=None,
                    severity="high",
                    reason="Both snapshots changed the same schema differently.",
                )
            )
    conflicts = sorted(
        conflicts,
        key=lambda item: (item.path, item.kind, item.symbol or "", item.reason),
    )
    same_identity = _same_repository_identity(left, right)
    blockers: list[str] = []
    dirty = bool(left.working_tree or right.working_tree)
    if not same_identity:
        blockers.append("Repository identity is not established.")
    if dirty:
        blockers.append("At least one snapshot has uncommitted or untracked work.")
    if base is None:
        blockers.append("No shared-base snapshot was supplied.")
    if conflicts:
        blockers.append("Potential both-sided conflicts require manual review.")
    if any(item.severity == "high" for item in conflicts) or (dirty and base is None):
        risk_level: Literal["low", "medium", "high"] = "high"
    elif conflicts or file_deltas or dependency_deltas or migration_deltas or schema_deltas:
        risk_level = "medium"
    else:
        risk_level = "low"
    summary = ComparisonSummary(
        changed_files=len(file_deltas),
        conflicts=len(conflicts),
        dependency_changes=len(dependency_deltas),
        migration_changes=len(migration_deltas),
        schema_changes=len(schema_deltas),
    )
    report = ComparisonReport(
        comparison_id=EMPTY_DIGEST,
        mode="three_way" if base is not None else "two_way",
        base_snapshot_id=None if base is None else base.snapshot_id,
        left_snapshot_id=left.snapshot_id,
        right_snapshot_id=right.snapshot_id,
        same_repository_identity=same_identity,
        git_relation=_git_relation(left, right),
        file_deltas=file_deltas,
        dependency_deltas=dependency_deltas,
        migration_deltas=migration_deltas,
        schema_deltas=schema_deltas,
        conflicts=conflicts,
        blockers=blockers,
        risk_level=risk_level,
        sync_steps=_sync_steps(base is not None, dirty),
        summary=summary,
    )
    report.comparison_id = object_id(report.model_dump(mode="json"), "comparison_id")
    return report
