from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from repo_reconciliation_toolkit.cli import main
from repo_reconciliation_toolkit.reporting import generate_fixture_release


def _hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def test_release_report_is_deterministic(project_root: Path, tmp_path: Path) -> None:
    output = tmp_path / "reports"
    first = generate_fixture_release(project_root, output)
    first_hashes = _hashes(output)
    second = generate_fixture_release(project_root, output)
    assert first == second
    assert first_hashes == _hashes(output)
    assert first["passed"] is True
    for name in (
        "REPO_SNAPSHOT.json",
        "DEPENDENCY_REPORT.md",
        "DIVERGENCE_REPORT.md",
        "MIGRATION_PLAN.md",
        "BACKUP_CHECKLIST.md",
    ):
        assert (output / name).is_file()


def test_machine_artifacts_parse(project_root: Path, tmp_path: Path) -> None:
    generate_fixture_release(project_root, tmp_path / "reports")
    root = project_root / "research" / "results" / "v0.1"
    assert list(root.glob("*.json"))
    assert list(root.glob("*.jsonl"))
    assert list(root.glob("*.csv"))
    for path in root.glob("*.json"):
        assert json.loads(path.read_text(encoding="utf-8"))
    for path in root.glob("*.jsonl"):
        assert [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
    for path in root.glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as stream:
            assert list(csv.DictReader(stream))


def test_cli_validate(project_root: Path) -> None:
    assert main(["validate", str(project_root / "fixtures" / "snapshots")]) == 0


def test_cli_compare(project_root: Path, tmp_path: Path) -> None:
    fixtures = project_root / "fixtures" / "snapshots"
    output = tmp_path / "compare"
    code = main(
        [
            "compare",
            str(fixtures / "left.json"),
            str(fixtures / "right.json"),
            "--base",
            str(fixtures / "base.json"),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert (output / "DIVERGENCE_REPORT.json").is_file()


def test_cli_malformed_json_returns_one(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    assert main(["validate", str(path)]) == 1

