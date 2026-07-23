"""Typed snapshot and comparison contracts."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
GitCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{40,64}$")]
SchemaVersion = Literal["1.0.0"]


def _validate_relative_or_redacted(value: str) -> str:
    if value.startswith("<redacted:") and value.endswith(">"):
        return value
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError("path must be repository-relative or redacted")
    if any(part == ".." for part in normalized.split("/")):
        raise ValueError("path cannot traverse upward")
    return normalized


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @field_serializer("*", when_used="json")
    def serialize_values(self, value: object) -> object:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        return value


class BranchState(StrictModel):
    name: str
    commit: GitCommit
    upstream: str | None
    ahead: Annotated[int, Field(ge=0)] | None
    behind: Annotated[int, Field(ge=0)] | None
    divergence_source: Literal["local_tracking_ref", "none"]


class TagState(StrictModel):
    name: str
    commit: GitCommit


class RemoteState(StrictModel):
    name: str
    fetch_url: str
    push_url: str


class CommitNode(StrictModel):
    commit: GitCommit
    parents: list[GitCommit]


class GitState(StrictModel):
    is_repository: bool
    head_commit: GitCommit | None
    branch: str | None
    detached: bool
    branches: list[BranchState]
    tags: list[TagState]
    remotes: list[RemoteState]
    commits: list[CommitNode]
    commit_graph_truncated: bool


class WorkingTreeChange(StrictModel):
    path: str
    status: Literal[
        "staged",
        "modified",
        "deleted",
        "renamed",
        "copied",
        "untracked",
        "conflicted",
        "type_changed",
    ]
    old_path: str | None

    @field_validator("path", "old_path")
    @classmethod
    def relative_paths(cls, value: str | None) -> str | None:
        return None if value is None else _validate_relative_or_redacted(value)


class SymbolFingerprint(StrictModel):
    language: Literal["python", "javascript", "typescript", "solidity"]
    kind: str
    name: str
    start_line: Annotated[int, Field(ge=1)]
    signature_hash: Digest
    body_hash: Digest


class FileRecord(StrictModel):
    path: str
    kind: Literal["file", "symlink"]
    size: Annotated[int, Field(ge=0)]
    sha256: Digest
    executable: bool
    symbols: list[SymbolFingerprint]
    link_target_hash: Digest | None

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _validate_relative_or_redacted(value)


class DependencyRecord(StrictModel):
    ecosystem: Literal["python", "node", "rust", "go", "dotnet", "unknown"]
    manifest: str
    group: str
    name: str
    declared: str
    lockfile: str | None
    lock_hash: Digest | None

    @field_validator("manifest", "lockfile")
    @classmethod
    def relative_paths(cls, value: str | None) -> str | None:
        return None if value is None else _validate_relative_or_redacted(value)


class MigrationRecord(StrictModel):
    path: str
    framework: str
    order_key: str
    sha256: Digest

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _validate_relative_or_redacted(value)


class SchemaRecord(StrictModel):
    path: str
    schema_kind: str
    sha256: Digest

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _validate_relative_or_redacted(value)


class RuntimeRecord(StrictModel):
    name: str
    version: str


class TestResult(StrictModel):
    status: Literal["not_run", "passed", "failed", "timeout", "error"]
    command: list[str]
    exit_code: int | None
    duration_ms: Annotated[int, Field(ge=0)] | None
    output_hash: Digest | None
    note: str


class RepositorySnapshot(StrictModel):
    schema_version: SchemaVersion = "1.0.0"
    snapshot_id: Digest
    captured_at: datetime
    repository_name: str
    root_fingerprint: Digest
    release_status: Literal[
        "non_git",
        "dirty",
        "detached",
        "clean_tagged",
        "clean_untagged",
    ]
    git: GitState
    working_tree: list[WorkingTreeChange]
    files: list[FileRecord]
    dependencies: list[DependencyRecord]
    migrations: list[MigrationRecord]
    schemas: list[SchemaRecord]
    runtimes: list[RuntimeRecord]
    environment_variable_names: list[str]
    test: TestResult
    warnings: list[str]
    exclusions: list[str]

    @field_validator("captured_at")
    @classmethod
    def aware_capture_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must include a UTC offset")
        return value


class FileDelta(StrictModel):
    path: str
    status: Literal[
        "left_only",
        "right_only",
        "modified",
        "left_only_change",
        "right_only_change",
        "both_same",
        "both_different",
        "deleted_both",
    ]
    base_hash: Digest | None
    left_hash: Digest | None
    right_hash: Digest | None

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _validate_relative_or_redacted(value)


class ValueDelta(StrictModel):
    key: str
    status: Literal[
        "left_only",
        "right_only",
        "modified",
        "left_only_change",
        "right_only_change",
        "both_same",
        "both_different",
        "deleted_both",
    ]
    base_value: str | None
    left_value: str | None
    right_value: str | None


class ConflictCandidate(StrictModel):
    kind: Literal["file", "symbol", "dependency", "migration", "schema"]
    path: str
    symbol: str | None
    severity: Literal["low", "medium", "high"]
    reason: str

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _validate_relative_or_redacted(value)


class SyncStep(StrictModel):
    order: Annotated[int, Field(ge=1)]
    title: str
    rationale: str
    manual_checks: list[str]


class ComparisonSummary(StrictModel):
    changed_files: Annotated[int, Field(ge=0)]
    conflicts: Annotated[int, Field(ge=0)]
    dependency_changes: Annotated[int, Field(ge=0)]
    migration_changes: Annotated[int, Field(ge=0)]
    schema_changes: Annotated[int, Field(ge=0)]


class ComparisonReport(StrictModel):
    schema_version: SchemaVersion = "1.0.0"
    comparison_id: Digest
    mode: Literal["two_way", "three_way"]
    base_snapshot_id: Digest | None
    left_snapshot_id: Digest
    right_snapshot_id: Digest
    same_repository_identity: bool
    git_relation: str
    file_deltas: list[FileDelta]
    dependency_deltas: list[ValueDelta]
    migration_deltas: list[ValueDelta]
    schema_deltas: list[ValueDelta]
    conflicts: list[ConflictCandidate]
    blockers: list[str]
    risk_level: Literal["low", "medium", "high"]
    sync_steps: list[SyncStep]
    summary: ComparisonSummary
