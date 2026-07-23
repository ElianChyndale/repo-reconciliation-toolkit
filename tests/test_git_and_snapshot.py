from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from repo_reconciliation_toolkit.git_inspection import GitInspectionError, GitInspector
from repo_reconciliation_toolkit.snapshot import create_snapshot


def _git(executable: str, repository: Path, *arguments: str) -> None:
    result = subprocess.run(
        [executable, "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def git_repository(tmp_path: Path, git_executable: str) -> Path:
    repository = tmp_path / "sample"
    repository.mkdir()
    _git(git_executable, repository, "init", "-b", "main")
    _git(git_executable, repository, "config", "user.name", "Fixture")
    _git(git_executable, repository, "config", "user.email", "fixture@example.invalid")
    (repository / "src").mkdir()
    (repository / "src" / "model.py").write_text(
        "def score(value: float) -> float:\n    return value\n",
        encoding="utf-8",
    )
    (repository / "pyproject.toml").write_text(
        '[project]\nname="sample"\ndependencies=["pydantic>=2"]\n',
        encoding="utf-8",
    )
    (repository / "uv.lock").write_text("fixture-lock", encoding="utf-8")
    (repository / "migrations").mkdir()
    (repository / "migrations" / "001_init.sql").write_text(
        "create table fixture;",
        encoding="utf-8",
    )
    (repository / "schemas").mkdir()
    (repository / "schemas" / "record.schema.json").write_text(
        '{"type":"object"}',
        encoding="utf-8",
    )
    _git(git_executable, repository, "add", ".")
    _git(git_executable, repository, "commit", "-m", "initial")
    _git(git_executable, repository, "tag", "v0.1.0")
    _git(
        git_executable,
        repository,
        "remote",
        "add",
        "origin",
        "https://user:password@example.com/sample.git?token=secret",
    )
    (repository / "src" / "model.py").write_text(
        "def score(value: float) -> float:\n    return value * 2\n",
        encoding="utf-8",
    )
    (repository / "notes.txt").write_text("untracked", encoding="utf-8")
    (repository / ".env").write_text("SECRET=do-not-capture", encoding="utf-8")
    return repository


def test_git_allowlist_rejects_mutation(git_executable: str, tmp_path: Path) -> None:
    inspector = GitInspector(git_executable)
    with pytest.raises(GitInspectionError, match="forbidden"):
        inspector.run(tmp_path, ["reset", "--hard"])
    with pytest.raises(GitInspectionError, match="forbidden"):
        inspector.run(tmp_path, ["fetch", "origin"])


def test_snapshot_captures_read_only_state(
    git_repository: Path,
    git_executable: str,
) -> None:
    snapshot = create_snapshot(
        git_repository,
        captured_at=datetime.fromisoformat("2026-07-24T00:00:00+00:00"),
        git_executable=git_executable,
    )
    assert snapshot.git.is_repository
    assert snapshot.git.branch == "main"
    assert snapshot.git.head_commit is not None
    assert [item.name for item in snapshot.git.tags] == ["v0.1.0"]
    assert snapshot.git.commits
    assert snapshot.git.commits[0].commit == snapshot.git.head_commit
    assert snapshot.git.commit_graph_truncated is False
    assert snapshot.release_status == "dirty"
    statuses = {(item.path, item.status) for item in snapshot.working_tree}
    assert ("src/model.py", "modified") in statuses
    assert ("notes.txt", "untracked") in statuses
    assert any(item.path.startswith("<redacted:") for item in snapshot.files)
    text = json.dumps(snapshot.model_dump(mode="json"))
    assert "do-not-capture" not in text
    assert "user:password" not in text
    assert "?token=secret" not in text
    assert str(git_repository.resolve()) not in text
    assert snapshot.dependencies[0].name == "pydantic"
    assert snapshot.migrations[0].path == "migrations/001_init.sql"
    assert snapshot.schemas[0].path == "schemas/record.schema.json"
    assert snapshot.test.status == "not_run"


def test_snapshot_id_is_deterministic_with_fixed_time(
    git_repository: Path,
    git_executable: str,
) -> None:
    captured = datetime.fromisoformat("2026-07-24T00:00:00+00:00")
    first = create_snapshot(
        git_repository,
        captured_at=captured,
        git_executable=git_executable,
    )
    second = create_snapshot(
        git_repository,
        captured_at=captured,
        git_executable=git_executable,
    )
    assert first.snapshot_id == second.snapshot_id


def test_staged_and_renamed_paths_are_captured(
    git_repository: Path,
    git_executable: str,
) -> None:
    _git(git_executable, git_repository, "add", "notes.txt")
    _git(git_executable, git_repository, "mv", "uv.lock", "renamed.lock")
    snapshot = create_snapshot(git_repository, git_executable=git_executable)
    assert any(
        item.path == "notes.txt" and item.status == "staged"
        for item in snapshot.working_tree
    )
    rename = next(
        item for item in snapshot.working_tree if item.status == "renamed"
    )
    assert rename.old_path == "uv.lock"
    assert rename.path == "renamed.lock"


def test_test_execution_requires_explicit_permission(
    git_repository: Path,
    git_executable: str,
) -> None:
    with pytest.raises(ValueError, match="allow-test-execution"):
        create_snapshot(
            git_repository,
            git_executable=git_executable,
            test_command=[sys.executable, "-c", "print('ok')"],
        )


def test_explicit_test_records_only_hash(
    git_repository: Path,
    git_executable: str,
) -> None:
    snapshot = create_snapshot(
        git_repository,
        captured_at=datetime.fromisoformat("2026-07-24T00:00:00+00:00"),
        git_executable=git_executable,
        test_command=[sys.executable, "-c", "print('sensitive-' + 'output')"],
        allow_test_execution=True,
    )
    assert snapshot.test.status == "passed"
    assert snapshot.test.output_hash is not None
    assert "sensitive-output" not in json.dumps(snapshot.model_dump(mode="json"))


def test_symlink_is_not_followed(
    tmp_path: Path,
    git_executable: str,
) -> None:
    repository = tmp_path / "links"
    repository.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside-secret", encoding="utf-8")
    link = repository / "link.txt"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    snapshot = create_snapshot(repository, git_executable=git_executable)
    record = next(item for item in snapshot.files if item.path == "link.txt")
    assert record.kind == "symlink"
    assert record.link_target_hash is not None
    assert "outside-secret" not in json.dumps(snapshot.model_dump(mode="json"))
