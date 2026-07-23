from __future__ import annotations

from repo_reconciliation_toolkit.comparison import compare_snapshots
from repo_reconciliation_toolkit.validation import load_snapshot


def test_three_way_comparison_finds_expected_conflicts(project_root) -> None:
    root = project_root / "fixtures" / "snapshots"
    base = load_snapshot(root / "base.json")
    left = load_snapshot(root / "left.json")
    right = load_snapshot(root / "right.json")
    report = compare_snapshots(left, right, base)
    assert report.mode == "three_way"
    assert report.risk_level == "high"
    assert report.same_repository_identity
    assert report.summary.changed_files == 8
    assert report.summary.conflicts == 11
    assert {item.path for item in report.conflicts} >= {
        "src/model.py",
        "contracts/Vault.sol",
        "schemas/risk.schema.json",
        "migrations/002_add.sql",
        "pyproject.toml",
    }
    symbol_conflicts = {
        item.symbol for item in report.conflicts if item.kind == "symbol"
    }
    assert "function:score" in symbol_conflicts
    assert "function:settle" in symbol_conflicts


def test_one_sided_file_is_not_conflict(project_root) -> None:
    root = project_root / "fixtures" / "snapshots"
    base = load_snapshot(root / "base.json")
    left = load_snapshot(root / "left.json")
    right = load_snapshot(root / "right.json")
    report = compare_snapshots(left, right, base)
    delta = next(item for item in report.file_deltas if item.path == "src/service.ts")
    assert delta.status == "right_only_change"
    assert all(item.path != "src/service.ts" for item in report.conflicts)


def test_two_way_comparison_declares_missing_base(project_root) -> None:
    root = project_root / "fixtures" / "snapshots"
    left = load_snapshot(root / "left.json")
    right = load_snapshot(root / "right.json")
    report = compare_snapshots(left, right)
    assert report.mode == "two_way"
    assert "No shared-base snapshot was supplied." in report.blockers
    assert report.risk_level == "high"


def test_identical_clean_three_way_is_low_risk(project_root) -> None:
    base = load_snapshot(project_root / "fixtures" / "snapshots" / "base.json")
    report = compare_snapshots(base, base, base)
    assert report.risk_level == "low"
    assert report.file_deltas == []
    assert report.conflicts == []
    assert report.blockers == []


def test_sync_plan_never_claims_execution(project_root) -> None:
    root = project_root / "fixtures" / "snapshots"
    report = compare_snapshots(
        load_snapshot(root / "left.json"),
        load_snapshot(root / "right.json"),
        load_snapshot(root / "base.json"),
    )
    flattened = " ".join(
        item
        for step in report.sync_steps
        for item in [step.title, step.rationale, *step.manual_checks]
    )
    assert "manually" in flattened.lower() or "manual" in flattened.lower()
