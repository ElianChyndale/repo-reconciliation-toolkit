"""Generate deterministic base/left/right repository snapshots."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from repo_reconciliation_toolkit.canonical import object_id, sha256_text
from repo_reconciliation_toolkit.models import (
    BranchState,
    CommitNode,
    DependencyRecord,
    FileRecord,
    GitState,
    MigrationRecord,
    RemoteState,
    RepositorySnapshot,
    RuntimeRecord,
    SchemaRecord,
    SymbolFingerprint,
    TestResult,
    WorkingTreeChange,
)
from repo_reconciliation_toolkit.snapshot import EMPTY_DIGEST


def _symbol(language: str, kind: str, name: str, body: str, line: int = 1) -> SymbolFingerprint:
    return SymbolFingerprint(
        language=language,  # type: ignore[arg-type]
        kind=kind,
        name=name,
        start_line=line,
        signature_hash=sha256_text(f"{kind}:{name}"),
        body_hash=sha256_text(body),
    )


def _file(path: str, content: str, symbols: list[SymbolFingerprint] | None = None) -> FileRecord:
    return FileRecord(
        path=path,
        kind="file",
        size=len(content.encode("utf-8")),
        sha256=sha256_text(content),
        executable=False,
        symbols=symbols or [],
        link_target_hash=None,
    )


def _snapshot(
    *,
    head: str,
    files: list[FileRecord],
    dependencies: list[DependencyRecord],
    migrations: list[MigrationRecord],
    schemas: list[SchemaRecord],
    working_tree: list[WorkingTreeChange] | None = None,
    parent: str | None = None,
) -> RepositorySnapshot:
    snapshot = RepositorySnapshot(
        snapshot_id=EMPTY_DIGEST,
        captured_at=datetime.fromisoformat("2026-07-24T00:00:00+00:00"),
        repository_name="fixture-repo",
        root_fingerprint=sha256_text("fixture-repository-identity"),
        git=GitState(
            is_repository=True,
            head_commit=head,
            branch="main",
            detached=False,
            branches=[
                BranchState(
                    name="main",
                    commit=head,
                    upstream="origin/main",
                    ahead=1,
                    behind=1,
                    divergence_source="local_tracking_ref",
                )
            ],
            tags=[],
            remotes=[
                RemoteState(
                    name="origin",
                    fetch_url="https://github.com/example/fixture-repo.git",
                    push_url="https://github.com/example/fixture-repo.git",
                )
            ],
            commits=[
                CommitNode(commit=head, parents=[] if parent is None else [parent]),
                *(
                    []
                    if parent is None
                    else [CommitNode(commit=parent, parents=[])]
                ),
            ],
            commit_graph_truncated=False,
        ),
        working_tree=working_tree or [],
        release_status="dirty" if working_tree else "clean_untagged",
        files=sorted(files, key=lambda item: item.path),
        dependencies=dependencies,
        migrations=migrations,
        schemas=schemas,
        runtimes=[
            RuntimeRecord(name="git", version="git version fixture"),
            RuntimeRecord(name="python", version="Python 3.11.0"),
        ],
        environment_variable_names=["CI", "PYTHONHASHSEED"],
        test=TestResult(
            status="passed",
            command=["python", "-m", "pytest"],
            exit_code=0,
            duration_ms=100,
            output_hash=sha256_text("fixture-test-output"),
            note="Synthetic fixture test result.",
        ),
        warnings=[
            "Ahead/behind counts use existing local tracking refs and may be stale."
        ],
        exclusions=[".git", ".venv", "node_modules"],
    )
    snapshot.snapshot_id = object_id(snapshot.model_dump(mode="json"), "snapshot_id")
    return snapshot


def _dependency(declared: str, lock: str) -> DependencyRecord:
    return DependencyRecord(
        ecosystem="python",
        manifest="pyproject.toml",
        group="runtime",
        name="pydantic",
        declared=declared,
        lockfile="uv.lock",
        lock_hash=sha256_text(lock),
    )


def build() -> tuple[RepositorySnapshot, RepositorySnapshot, RepositorySnapshot]:
    model_base = _file(
        "src/model.py",
        "base-model",
        [_symbol("python", "function", "score", "return 0.5")],
    )
    service_base = _file(
        "src/service.ts",
        "base-service",
        [_symbol("typescript", "function", "rank", "return values")],
    )
    vault_base = _file(
        "contracts/Vault.sol",
        "base-vault",
        [_symbol("solidity", "function", "settle", "state = Settled")],
    )
    schema_base = _file("schemas/risk.schema.json", "schema-v1")
    migration_base = _file("migrations/001_init.sql", "create table")
    pyproject = _file("pyproject.toml", "pydantic>=2.8")
    lockfile = _file("uv.lock", "lock-base")
    base_files = [
        model_base,
        service_base,
        vault_base,
        schema_base,
        migration_base,
        pyproject,
        lockfile,
    ]
    base = _snapshot(
        head="a" * 40,
        files=base_files,
        dependencies=[_dependency(">=2.8", "lock-base")],
        migrations=[
            MigrationRecord(
                path=migration_base.path,
                framework="generic",
                order_key="001_init.sql",
                sha256=migration_base.sha256,
            )
        ],
        schemas=[
            SchemaRecord(
                path=schema_base.path,
                schema_kind="json-schema",
                sha256=schema_base.sha256,
            )
        ],
    )

    left_model = _file(
        "src/model.py",
        "left-model",
        [_symbol("python", "function", "score", "return calibrated")],
    )
    left_vault = _file(
        "contracts/Vault.sol",
        "left-vault",
        [_symbol("solidity", "function", "settle", "require paid; settle")],
    )
    left_schema = _file("schemas/risk.schema.json", "schema-left")
    left_migration = _file("migrations/002_add.sql", "left migration")
    left_pyproject = _file("pyproject.toml", "pydantic>=2.9")
    left_files = [
        left_model,
        service_base,
        left_vault,
        left_schema,
        migration_base,
        left_migration,
        left_pyproject,
        _file("uv.lock", "lock-left"),
    ]
    left = _snapshot(
        head="b" * 40,
        files=left_files,
        dependencies=[_dependency(">=2.9", "lock-left")],
        migrations=[
            *base.migrations,
            MigrationRecord(
                path=left_migration.path,
                framework="generic",
                order_key="002_add.sql",
                sha256=left_migration.sha256,
            ),
        ],
        schemas=[
            SchemaRecord(
                path=left_schema.path,
                schema_kind="json-schema",
                sha256=left_schema.sha256,
            )
        ],
        working_tree=[
            WorkingTreeChange(
                path="notes.txt",
                status="untracked",
                old_path=None,
            )
        ],
        parent="a" * 40,
    )

    right_model = _file(
        "src/model.py",
        "right-model",
        [_symbol("python", "function", "score", "return clipped")],
    )
    right_service = _file(
        "src/service.ts",
        "right-service",
        [_symbol("typescript", "function", "rank", "return reranked")],
    )
    right_vault = _file(
        "contracts/Vault.sol",
        "right-vault",
        [_symbol("solidity", "function", "settle", "verify nonce; settle")],
    )
    right_schema = _file("schemas/risk.schema.json", "schema-right")
    right_migration = _file("migrations/002_add.sql", "right migration")
    right_pyproject = _file("pyproject.toml", "pydantic>=2.10")
    right_files = [
        right_model,
        right_service,
        right_vault,
        right_schema,
        migration_base,
        right_migration,
        right_pyproject,
        _file("uv.lock", "lock-right"),
        _file("docs/right-only.md", "right"),
    ]
    right = _snapshot(
        head="c" * 40,
        files=right_files,
        dependencies=[_dependency(">=2.10", "lock-right")],
        migrations=[
            *base.migrations,
            MigrationRecord(
                path=right_migration.path,
                framework="generic",
                order_key="002_add.sql",
                sha256=right_migration.sha256,
            ),
        ],
        schemas=[
            SchemaRecord(
                path=right_schema.path,
                schema_kind="json-schema",
                sha256=right_schema.sha256,
            )
        ],
        parent="a" * 40,
    )
    return base, left, right


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "fixtures" / "snapshots"
    if not args.check:
        output.mkdir(parents=True, exist_ok=True)
    mismatches: list[str] = []
    for name, snapshot in zip(("base", "left", "right"), build(), strict=True):
        path = output / f"{name}.json"
        content = (
            json.dumps(
                snapshot.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                mismatches.append(path.relative_to(root).as_posix())
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    if mismatches:
        raise SystemExit("fixture mismatch: " + ", ".join(mismatches))


if __name__ == "__main__":
    main()
