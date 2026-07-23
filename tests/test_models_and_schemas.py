from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from repo_reconciliation_toolkit.canonical import object_id
from repo_reconciliation_toolkit.models import FileRecord, RepositorySnapshot
from repo_reconciliation_toolkit.validation import load_schema, read_json, validate_record


@pytest.mark.parametrize("record_type", ["snapshot", "comparison"])
def test_generated_schema_is_draft_2020_12(record_type: str) -> None:
    schema = load_schema(record_type)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_public_and_packaged_schemas_match(project_root: Path) -> None:
    for name in ("snapshot.schema.json", "comparison.schema.json"):
        public = project_root / "schemas" / name
        packaged = (
            project_root
            / "src"
            / "repo_reconciliation_toolkit"
            / "schema_data"
            / name
        )
        assert public.read_bytes() == packaged.read_bytes()


@pytest.mark.parametrize("name", ["base", "left", "right"])
def test_fixture_snapshots_validate(project_root: Path, name: str) -> None:
    value = read_json(project_root / "fixtures" / "snapshots" / f"{name}.json")
    result = validate_record(value, "snapshot")
    assert result.valid, result.issues
    model = RepositorySnapshot.model_validate(value)
    assert object_id(model.model_dump(mode="json"), "snapshot_id") == model.snapshot_id


def test_unknown_field_is_rejected(project_root: Path) -> None:
    value = read_json(project_root / "fixtures" / "snapshots" / "base.json")
    value["unexpected"] = True
    result = validate_record(value, "snapshot")
    assert not result.valid
    assert result.issues[0].layer == "schema"


def test_snapshot_id_detects_tampering(project_root: Path) -> None:
    value = read_json(project_root / "fixtures" / "snapshots" / "base.json")
    value["repository_name"] = "tampered"
    result = validate_record(value, "snapshot")
    assert not result.valid
    assert result.issues[0].layer == "integrity"


def test_naive_capture_time_is_rejected(project_root: Path) -> None:
    value = read_json(project_root / "fixtures" / "snapshots" / "base.json")
    value["captured_at"] = "2026-07-24T00:00:00"
    result = validate_record(value, "snapshot")
    assert not result.valid


def test_absolute_file_path_is_rejected() -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        FileRecord(
            path="C:/private/repo/file.py",
            kind="file",
            size=1,
            sha256="sha256:" + "0" * 64,
            executable=False,
            symbols=[],
            link_target_hash=None,
        )


def test_comparison_schema_rejects_bad_risk(project_root: Path) -> None:
    from repo_reconciliation_toolkit.comparison import compare_snapshots
    from repo_reconciliation_toolkit.validation import load_snapshot

    base = load_snapshot(project_root / "fixtures" / "snapshots" / "base.json")
    left = load_snapshot(project_root / "fixtures" / "snapshots" / "left.json")
    right = load_snapshot(project_root / "fixtures" / "snapshots" / "right.json")
    report = compare_snapshots(left, right, base)
    value = report.model_dump(mode="json")
    value["risk_level"] = "critical"
    result = validate_record(value, "comparison")
    assert not result.valid
    assert result.issues[0].layer == "schema"


def test_malformed_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read JSON"):
        read_json(path)
