"""Deterministic snapshot and comparison reports."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from repo_reconciliation_toolkit.comparison import compare_snapshots
from repo_reconciliation_toolkit.models import ComparisonReport, RepositorySnapshot
from repo_reconciliation_toolkit.validation import load_snapshot, validate_record


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _csv_text(rows: list[dict[str, object]], fields: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_snapshot_reports(snapshot: RepositorySnapshot, output: Path) -> None:
    _write(
        output / "REPO_SNAPSHOT.json",
        _json_text(snapshot.model_dump(mode="json")),
    )
    lines = [
        "# Dependency Report",
        "",
        f"Snapshot: `{snapshot.snapshot_id}`",
        f"Release status: `{snapshot.release_status}`",
        "",
        "| Ecosystem | Manifest | Group | Package | Declared | Lockfile |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if snapshot.dependencies:
        for item in snapshot.dependencies:
            lines.append(
                f"| {item.ecosystem} | `{item.manifest}` | {item.group} | "
                f"`{item.name}` | `{item.declared}` | `{item.lockfile or 'none'}` |"
            )
    else:
        lines.append("| none detected | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "Lock hashes and declared constraints are evidence of captured state; the tool does "
            "not install or resolve dependencies.",
            "",
        ]
    )
    _write(output / "DEPENDENCY_REPORT.md", "\n".join(lines))


def write_comparison_reports(report: ComparisonReport, output: Path) -> None:
    payload = report.model_dump(mode="json")
    _write(output / "DIVERGENCE_REPORT.json", _json_text(payload))
    lines = [
        "# Divergence Report",
        "",
        f"Comparison: `{report.comparison_id}`",
        "",
        f"- Mode: `{report.mode}`",
        f"- Risk: `{report.risk_level}`",
        f"- Repository identity established: `{str(report.same_repository_identity).lower()}`",
        f"- Git relation: {report.git_relation}",
        f"- Changed files: {report.summary.changed_files}",
        f"- Conflict candidates: {report.summary.conflicts}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in report.blockers)
    if not report.blockers:
        lines.append("- None identified by the snapshot comparison.")
    lines.extend(
        [
            "",
            "## Conflict candidates",
            "",
            "| Kind | Path | Symbol | Severity | Reason |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if report.conflicts:
        for item in report.conflicts:
            lines.append(
                f"| {item.kind} | `{item.path}` | `{item.symbol or '-'}` | "
                f"{item.severity} | {item.reason} |"
            )
    else:
        lines.append("| none | - | - | - | - |")
    lines.extend(
        [
            "",
            "Conflict candidates are conservative review signals, not predictions that Git will "
            "necessarily emit a textual conflict.",
            "",
        ]
    )
    _write(output / "DIVERGENCE_REPORT.md", "\n".join(lines))

    file_rows: list[dict[str, object]] = [
        {
            "path": item.path,
            "status": item.status,
            "base_hash": item.base_hash or "",
            "left_hash": item.left_hash or "",
            "right_hash": item.right_hash or "",
        }
        for item in report.file_deltas
    ]
    _write(
        output / "file_deltas.csv",
        _csv_text(
            file_rows,
            ["path", "status", "base_hash", "left_hash", "right_hash"],
        ),
    )
    _write(
        output / "conflicts.jsonl",
        "".join(
            json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in report.conflicts
        ),
    )
    plan_lines = [
        "# Migration Plan",
        "",
        "This plan is descriptive. No step is executed by the toolkit.",
        "",
    ]
    for step in report.sync_steps:
        plan_lines.extend(
            [
                f"## {step.order}. {step.title}",
                "",
                step.rationale,
                "",
                *[f"- {item}" for item in step.manual_checks],
                "",
            ]
        )
    _write(output / "MIGRATION_PLAN.md", "\n".join(plan_lines))

    checklist = [
        "# Backup Checklist",
        "",
        "- [ ] Confirm both snapshot IDs and capture times.",
        "- [ ] Copy each repository to an independent destination.",
        "- [ ] Preserve untracked, staged, modified, renamed, deleted, and conflicted paths.",
        "- [ ] Record branches, tags, HEAD commits, and sanitized remotes.",
        "- [ ] Verify copied files can be read and their critical hashes match.",
        (
            "- [ ] Preserve databases, migrations, local-only configuration, and ignored "
            "data separately."
        ),
        "- [ ] Keep credentials outside repository backups and reports.",
        "- [ ] Do not delete either source copy until reconciliation tests pass.",
        "",
        "The toolkit does not create, verify, move, or delete backups.",
        "",
    ]
    _write(output / "BACKUP_CHECKLIST.md", "\n".join(checklist))


def generate_fixture_release(root: Path, output: Path) -> dict[str, object]:
    fixture_root = root / "fixtures" / "snapshots"
    base = load_snapshot(fixture_root / "base.json")
    left = load_snapshot(fixture_root / "left.json")
    right = load_snapshot(fixture_root / "right.json")
    report = compare_snapshots(left, right, base)
    write_snapshot_reports(left, output)
    write_comparison_reports(report, output)

    machine = root / "research" / "results" / "v0.1"
    snapshots = [base, left, right]
    validations = [
        {
            "name": name,
            "snapshot_id": snapshot.snapshot_id,
            "valid": validate_record(snapshot.model_dump(mode="json"), "snapshot").valid,
        }
        for name, snapshot in zip(("base", "left", "right"), snapshots, strict=True)
    ]
    _write(machine / "snapshot_validation.json", _json_text(validations))
    _write(
        machine / "divergence.json",
        _json_text(report.model_dump(mode="json")),
    )
    _write(
        machine / "file_deltas.csv",
        _csv_text(
            [
                {
                    "path": item.path,
                    "status": item.status,
                    "base_hash": item.base_hash or "",
                    "left_hash": item.left_hash or "",
                    "right_hash": item.right_hash or "",
                }
                for item in report.file_deltas
            ],
            ["path", "status", "base_hash", "left_hash", "right_hash"],
        ),
    )
    _write(
        machine / "conflicts.jsonl",
        "".join(
            json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in report.conflicts
        ),
    )
    _write(
        machine / "snapshot_inventory.csv",
        _csv_text(
            [
                {
                    "snapshot": name,
                    "files": len(snapshot.files),
                    "dependencies": len(snapshot.dependencies),
                    "migrations": len(snapshot.migrations),
                    "schemas": len(snapshot.schemas),
                    "working_tree_changes": len(snapshot.working_tree),
                }
                for name, snapshot in zip(("base", "left", "right"), snapshots, strict=True)
            ],
            [
                "snapshot",
                "files",
                "dependencies",
                "migrations",
                "schemas",
                "working_tree_changes",
            ],
        ),
    )
    summary = {
        "release": "v0.1",
        "snapshots": 3,
        "file_deltas": len(report.file_deltas),
        "conflicts": len(report.conflicts),
        "passed": all(item["valid"] for item in validations),
    }
    _write(output / "summary.json", _json_text(summary))
    return summary
