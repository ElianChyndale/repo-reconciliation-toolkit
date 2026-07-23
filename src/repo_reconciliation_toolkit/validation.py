"""Schema-backed snapshot and comparison loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from repo_reconciliation_toolkit.canonical import object_id
from repo_reconciliation_toolkit.models import ComparisonReport, RepositorySnapshot


@dataclass(frozen=True)
class ValidationIssue:
    layer: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    record_type: str
    issues: tuple[ValidationIssue, ...]


def schema_root() -> Path:
    return Path(__file__).resolve().parent / "schema_data"


def load_schema(record_type: str) -> dict[str, Any]:
    if record_type not in {"snapshot", "comparison"}:
        raise KeyError(f"unknown record type: {record_type}")
    value = json.loads(
        (schema_root() / f"{record_type}.schema.json").read_text(encoding="utf-8")
    )
    if not isinstance(value, dict):
        raise ValueError("schema is not an object")
    schema = cast(dict[str, Any], value)
    Draft202012Validator.check_schema(schema)
    return schema


def infer_record_type(record: dict[str, Any]) -> str | None:
    if "snapshot_id" in record and "comparison_id" not in record:
        return "snapshot"
    if "comparison_id" in record and "snapshot_id" not in record:
        return "comparison"
    return None


def validate_record(
    record: dict[str, Any],
    record_type: str | None = None,
) -> ValidationResult:
    resolved = record_type or infer_record_type(record)
    if resolved is None:
        return ValidationResult(
            False,
            "unknown",
            (ValidationIssue("dispatch", "$", "cannot infer record type"),),
        )
    schema = load_schema(resolved)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_issues = tuple(
        ValidationIssue(
            "schema",
            "$." + ".".join(str(item) for item in error.absolute_path),
            error.message,
        )
        for error in sorted(
            validator.iter_errors(record),
            key=lambda item: list(item.absolute_path),
        )
    )
    if schema_issues:
        return ValidationResult(False, resolved, schema_issues)
    model = RepositorySnapshot if resolved == "snapshot" else ComparisonReport
    try:
        instance = model.model_validate(record)
    except ValidationError as exc:
        issues = tuple(
            ValidationIssue(
                "semantic",
                "$." + ".".join(str(part) for part in error["loc"]),
                str(error["msg"]),
            )
            for error in exc.errors()
        )
        return ValidationResult(False, resolved, issues)
    id_field = "snapshot_id" if resolved == "snapshot" else "comparison_id"
    expected = object_id(instance.model_dump(mode="json"), id_field)
    if record.get(id_field) != expected:
        return ValidationResult(
            False,
            resolved,
            (
                ValidationIssue(
                    "integrity",
                    f"$.{id_field}",
                    f"{id_field} does not match canonical record content",
                ),
            ),
        )
    return ValidationResult(True, resolved, ())


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"top-level JSON must be an object: {path}")
    return cast(dict[str, Any], value)


def load_snapshot(path: Path) -> RepositorySnapshot:
    value = read_json(path)
    result = validate_record(value, "snapshot")
    if not result.valid:
        details = "; ".join(f"{item.path}: {item.message}" for item in result.issues)
        raise ValueError(f"invalid snapshot {path}: {details}")
    return RepositorySnapshot.model_validate(value)
