"""Offline command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from repo_reconciliation_toolkit.comparison import compare_snapshots
from repo_reconciliation_toolkit.reporting import (
    generate_fixture_release,
    write_comparison_reports,
    write_snapshot_reports,
)
from repo_reconciliation_toolkit.snapshot import create_snapshot
from repo_reconciliation_toolkit.validation import (
    load_snapshot,
    read_json,
    validate_record,
)


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def repository_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[2]]
    for candidate in candidates:
        if (candidate / "fixtures" / "snapshots").is_dir():
            return candidate
    raise RuntimeError("run this release command from a toolkit source checkout")


def command_snapshot(args: argparse.Namespace) -> int:
    repository = Path(args.repository)
    output = Path(args.output)
    exclusions = set(args.exclude)
    try:
        relative_output = output.resolve().relative_to(repository.resolve())
        if relative_output.parts:
            exclusions.add(relative_output.parts[0])
    except ValueError:
        pass
    captured_at = None
    if args.captured_at:
        captured_at = datetime.fromisoformat(args.captured_at.replace("Z", "+00:00"))
    test_command = args.test_command if args.test_command else None
    snapshot = create_snapshot(
        repository,
        captured_at=captured_at,
        git_executable=args.git_executable,
        extra_exclusions=exclusions,
        test_command=test_command,
        allow_test_execution=args.allow_test_execution,
        test_timeout_seconds=args.test_timeout,
    )
    write_snapshot_reports(snapshot, output)
    print(
        _json(
            {
                "snapshot_id": snapshot.snapshot_id,
                "files": len(snapshot.files),
                "working_tree_changes": len(snapshot.working_tree),
                "output": output.as_posix(),
            }
        )
    )
    return 0


def command_compare(args: argparse.Namespace) -> int:
    left = load_snapshot(Path(args.left))
    right = load_snapshot(Path(args.right))
    base = None if args.base is None else load_snapshot(Path(args.base))
    report = compare_snapshots(left, right, base)
    output = Path(args.output)
    write_comparison_reports(report, output)
    print(
        _json(
            {
                "comparison_id": report.comparison_id,
                "risk_level": report.risk_level,
                "conflicts": len(report.conflicts),
                "output": output.as_posix(),
            }
        )
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    files = [path] if path.is_file() else sorted(path.rglob("*.json"))
    if not files:
        raise ValueError(f"no JSON files found: {path}")
    rows: list[dict[str, object]] = []
    passed = True
    for file in files:
        try:
            value = read_json(file)
            result = validate_record(value, args.record_type)
            valid = result.valid
            issues = [item.__dict__ for item in result.issues]
        except ValueError as exc:
            valid = False
            issues = [{"layer": "input", "path": "$", "message": str(exc)}]
        rows.append({"path": file.as_posix(), "valid": valid, "issues": issues})
        passed = passed and valid
    print(_json({"valid": passed, "count": len(rows), "results": rows}))
    return 0 if passed else 1


def command_report(args: argparse.Namespace) -> int:
    root = repository_root()
    summary = generate_fixture_release(root, Path(args.output))
    print(_json(summary))
    return 0 if bool(summary["passed"]) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-reconcile",
        description="Read-only repository snapshots and reconciliation plans.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("repository")
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.add_argument("--captured-at")
    snapshot_parser.add_argument("--git-executable")
    snapshot_parser.add_argument("--exclude", action="append", default=[])
    snapshot_parser.add_argument("--test-timeout", type=int, default=300)
    snapshot_parser.add_argument("--allow-test-execution", action="store_true")
    snapshot_parser.add_argument("--test-command", nargs=argparse.REMAINDER)
    snapshot_parser.set_defaults(handler=command_snapshot)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("left")
    compare_parser.add_argument("right")
    compare_parser.add_argument("--base")
    compare_parser.add_argument("--output", required=True)
    compare_parser.set_defaults(handler=command_compare)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.add_argument(
        "--type",
        dest="record_type",
        choices=["snapshot", "comparison"],
    )
    validate_parser.set_defaults(handler=command_validate)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--output", default="reports/v0.1")
    report_parser.set_defaults(handler=command_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (KeyError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

