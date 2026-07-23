"""Repository snapshot orchestration."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from repo_reconciliation_toolkit.canonical import object_id, sha256_bytes, sha256_text
from repo_reconciliation_toolkit.git_inspection import GitInspector
from repo_reconciliation_toolkit.models import (
    RepositorySnapshot,
    RuntimeRecord,
    TestResult,
)
from repo_reconciliation_toolkit.safety import (
    DEFAULT_EXCLUDED_DIRS,
    SAFE_ENVIRONMENT_NAMES,
)
from repo_reconciliation_toolkit.scanning import (
    collect_dependencies,
    collect_migrations,
    collect_schemas,
    scan_files,
)

EMPTY_DIGEST = "sha256:" + "0" * 64


def _runtime_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if result.returncode == 0 and output else None


def collect_runtimes(git_executable: str) -> list[RuntimeRecord]:
    values: list[RuntimeRecord] = []
    python_version = _runtime_version([sys.executable, "--version"])
    if python_version:
        values.append(RuntimeRecord(name="python", version=python_version))
    git_version = _runtime_version([git_executable, "--version"])
    if git_version:
        values.append(RuntimeRecord(name="git", version=git_version))
    node = shutil.which("node")
    if node:
        node_version = _runtime_version([node, "--version"])
        if node_version:
            values.append(RuntimeRecord(name="node", version=node_version))
    return sorted(values, key=lambda item: item.name)


def run_explicit_test(
    repository: Path,
    command: list[str],
    timeout_seconds: int,
) -> TestResult:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=repository,
            check=False,
            capture_output=True,
            shell=False,
            timeout=timeout_seconds,
        )
        duration = max(0, round((time.monotonic() - started) * 1000))
        combined = result.stdout + b"\n" + result.stderr
        return TestResult(
            status="passed" if result.returncode == 0 else "failed",
            command=command,
            exit_code=result.returncode,
            duration_ms=duration,
            output_hash=sha256_bytes(combined),
            note="Output text is intentionally not stored.",
        )
    except subprocess.TimeoutExpired as exc:
        duration = max(0, round((time.monotonic() - started) * 1000))
        output = (exc.stdout or b"") + b"\n" + (exc.stderr or b"")
        return TestResult(
            status="timeout",
            command=command,
            exit_code=None,
            duration_ms=duration,
            output_hash=sha256_bytes(output),
            note=f"Test exceeded the {timeout_seconds}-second limit.",
        )
    except OSError as exc:
        duration = max(0, round((time.monotonic() - started) * 1000))
        return TestResult(
            status="error",
            command=command,
            exit_code=None,
            duration_ms=duration,
            output_hash=None,
            note=f"Test process could not start: {type(exc).__name__}.",
        )


def create_snapshot(
    repository: Path,
    *,
    captured_at: datetime | None = None,
    git_executable: str | None = None,
    extra_exclusions: set[str] | None = None,
    test_command: list[str] | None = None,
    allow_test_execution: bool = False,
    test_timeout_seconds: int = 300,
) -> RepositorySnapshot:
    root = repository.resolve()
    if not root.is_dir():
        raise ValueError(f"repository path is not a directory: {repository}")
    capture_time = captured_at or datetime.now(UTC).replace(microsecond=0)
    if capture_time.tzinfo is None or capture_time.utcoffset() is None:
        raise ValueError("captured_at must include a UTC offset")
    inspector = GitInspector(git_executable)
    git, working_tree, git_warnings = inspector.inspect(root)
    files, file_warnings = scan_files(root, extra_exclusions)
    dependencies, dependency_warnings = collect_dependencies(root)
    migrations = collect_migrations(files)
    schemas = collect_schemas(files)
    if test_command is None:
        test = TestResult(
            status="not_run",
            command=[],
            exit_code=None,
            duration_ms=None,
            output_hash=None,
            note="No explicit test command was supplied.",
        )
    elif not allow_test_execution:
        raise ValueError("test execution requires --allow-test-execution")
    elif not test_command:
        raise ValueError("test command cannot be empty")
    else:
        test = run_explicit_test(root, test_command, test_timeout_seconds)

    if not git.is_repository:
        release_status = "non_git"
    elif working_tree:
        release_status = "dirty"
    elif git.detached:
        release_status = "detached"
    elif git.head_commit is not None and git.head_commit in {tag.commit for tag in git.tags}:
        release_status = "clean_tagged"
    else:
        release_status = "clean_untagged"

    environment_names = sorted(SAFE_ENVIRONMENT_NAMES.intersection(os.environ))
    exclusions = sorted(DEFAULT_EXCLUDED_DIRS.union(extra_exclusions or set()))
    snapshot = RepositorySnapshot(
        snapshot_id=EMPTY_DIGEST,
        captured_at=capture_time,
        repository_name=root.name,
        root_fingerprint=sha256_text(str(root)),
        release_status=release_status,  # type: ignore[arg-type]
        git=git,
        working_tree=working_tree,
        files=files,
        dependencies=dependencies,
        migrations=migrations,
        schemas=schemas,
        runtimes=collect_runtimes(inspector.executable),
        environment_variable_names=environment_names,
        test=test,
        warnings=sorted(set([*git_warnings, *file_warnings, *dependency_warnings])),
        exclusions=exclusions,
    )
    payload = snapshot.model_dump(mode="json")
    snapshot.snapshot_id = object_id(payload, "snapshot_id")
    return snapshot
