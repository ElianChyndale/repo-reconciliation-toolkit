"""Filesystem, dependency, migration, and schema inspection."""

from __future__ import annotations

import json
import os
import re
import stat
import tomllib
from collections.abc import Iterator
from pathlib import Path

from repo_reconciliation_toolkit.canonical import sha256_text
from repo_reconciliation_toolkit.models import (
    DependencyRecord,
    FileRecord,
    MigrationRecord,
    SchemaRecord,
)
from repo_reconciliation_toolkit.safety import (
    DEFAULT_EXCLUDED_DIRS,
    is_secret_prone_path,
    safe_display_path,
    sanitize_declared_dependency,
)
from repo_reconciliation_toolkit.symbols import SOURCE_SUFFIXES, extract_symbols

MAX_SYMBOL_FILE_BYTES = 1_000_000


def _excluded(relative: Path, exclusions: set[str]) -> bool:
    parts = {part.lower() for part in relative.parts}
    return bool(parts & exclusions)


def iter_repository_entries(
    root: Path,
    extra_exclusions: set[str] | None = None,
) -> Iterator[tuple[Path, Path]]:
    exclusions = {item.lower() for item in DEFAULT_EXCLUDED_DIRS}
    exclusions.update(item.lower() for item in (extra_exclusions or set()))

    def walk(directory: Path) -> Iterator[tuple[Path, Path]]:
        entries = sorted(os.scandir(directory), key=lambda item: item.name.lower())
        for entry in entries:
            absolute = Path(entry.path)
            relative = absolute.relative_to(root)
            if _excluded(relative, exclusions):
                continue
            if entry.is_symlink():
                yield absolute, relative
            elif entry.is_dir(follow_symlinks=False):
                yield from walk(absolute)
            elif entry.is_file(follow_symlinks=False):
                yield absolute, relative

    yield from walk(root)


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SOURCE_SUFFIXES:
        return f"source:{SOURCE_SUFFIXES[suffix]}"
    if suffix in {".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini"}:
        return "structured-data"
    if suffix in {".md", ".txt", ".rst"}:
        return "documentation"
    if suffix in {".sql", ".graphql", ".proto", ".prisma"}:
        return "schema-or-migration"
    return "other"


def scan_files(
    root: Path,
    extra_exclusions: set[str] | None = None,
) -> tuple[list[FileRecord], list[str]]:
    records: list[FileRecord] = []
    warnings: list[str] = []
    for absolute, relative in iter_repository_entries(root, extra_exclusions):
        relative_text = relative.as_posix()
        display_path = safe_display_path(relative_text)
        try:
            metadata = absolute.lstat()
            executable = bool(metadata.st_mode & stat.S_IXUSR)
            if absolute.is_symlink():
                target = os.readlink(absolute)
                records.append(
                    FileRecord(
                        path=display_path,
                        kind="symlink",
                        size=len(target.encode("utf-8", errors="surrogatepass")),
                        sha256=sha256_text(target),
                        executable=executable,
                        symbols=[],
                        link_target_hash=sha256_text(target),
                    )
                )
                continue
            if is_secret_prone_path(relative_text):
                records.append(
                    FileRecord(
                        path=display_path,
                        kind="file",
                        size=metadata.st_size,
                        sha256=sha256_text("redacted:" + relative_text),
                        executable=executable,
                        symbols=[],
                        link_target_hash=None,
                    )
                )
                continue
            digest = _hash_file(absolute)
            symbols = []
            if (
                metadata.st_size <= MAX_SYMBOL_FILE_BYTES
                and absolute.suffix.lower() in SOURCE_SUFFIXES
            ):
                try:
                    source = absolute.read_text(encoding="utf-8")
                    symbols = extract_symbols(absolute, source)
                except UnicodeDecodeError:
                    warnings.append(f"Symbol analysis skipped for non-UTF-8 file {display_path}.")
            records.append(
                FileRecord(
                    path=display_path,
                    kind="file",
                    size=metadata.st_size,
                    sha256=digest,
                    executable=executable,
                    symbols=symbols,
                    link_target_hash=None,
                )
            )
        except OSError as exc:
            warnings.append(f"Could not inspect {display_path}: {type(exc).__name__}.")
    return sorted(records, key=lambda item: item.path), sorted(set(warnings))


def _lock_info(root: Path, names: list[str]) -> tuple[str | None, str | None]:
    for name in names:
        path = root / name
        if path.is_file():
            return name, _hash_file(path)
    return None, None


def _dependency_name(value: str) -> str:
    cleaned = value.strip()
    match = re.match(r"^([A-Za-z0-9_.-]+)", cleaned)
    return match.group(1).lower() if match else "<unparsed>"


def _python_dependencies(root: Path, warnings: list[str]) -> list[DependencyRecord]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return []
    lockfile, lock_hash = _lock_info(
        root,
        ["uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock"],
    )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        warnings.append("Could not parse pyproject.toml.")
        return []
    records: list[DependencyRecord] = []
    project = data.get("project", {})
    if isinstance(project, dict):
        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, list):
            for item in dependencies:
                if isinstance(item, str):
                    records.append(
                        DependencyRecord(
                            ecosystem="python",
                            manifest="pyproject.toml",
                            group="runtime",
                            name=_dependency_name(item),
                            declared=sanitize_declared_dependency(item),
                            lockfile=lockfile,
                            lock_hash=lock_hash,
                        )
                    )
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group, items in sorted(optional.items()):
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str):
                            records.append(
                                DependencyRecord(
                                    ecosystem="python",
                                    manifest="pyproject.toml",
                                    group=str(group),
                                    name=_dependency_name(item),
                                    declared=sanitize_declared_dependency(item),
                                    lockfile=lockfile,
                                    lock_hash=lock_hash,
                                )
                            )
    return records


def _requirements_dependencies(root: Path) -> list[DependencyRecord]:
    records: list[DependencyRecord] = []
    for path in sorted(root.glob("requirements*.txt")):
        lock_hash = _hash_file(path)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            item = line.strip()
            if not item or item.startswith(("#", "-", "--")):
                continue
            records.append(
                DependencyRecord(
                    ecosystem="python",
                    manifest=path.name,
                    group="requirements",
                    name=_dependency_name(item),
                    declared=sanitize_declared_dependency(item),
                    lockfile=path.name,
                    lock_hash=lock_hash,
                )
            )
    return records


def _node_dependencies(root: Path, warnings: list[str]) -> list[DependencyRecord]:
    path = root / "package.json"
    if not path.is_file():
        return []
    lockfile, lock_hash = _lock_info(
        root,
        ["pnpm-lock.yaml", "package-lock.json", "yarn.lock"],
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        warnings.append("Could not parse package.json.")
        return []
    records: list[DependencyRecord] = []
    for field, group in (
        ("dependencies", "runtime"),
        ("devDependencies", "dev"),
        ("peerDependencies", "peer"),
        ("optionalDependencies", "optional"),
    ):
        values = data.get(field, {})
        if isinstance(values, dict):
            for name, declared in sorted(values.items()):
                if isinstance(declared, str):
                    records.append(
                        DependencyRecord(
                            ecosystem="node",
                            manifest="package.json",
                            group=group,
                            name=str(name),
                            declared=sanitize_declared_dependency(declared),
                            lockfile=lockfile,
                            lock_hash=lock_hash,
                        )
                    )
    return records


def _rust_dependencies(root: Path, warnings: list[str]) -> list[DependencyRecord]:
    path = root / "Cargo.toml"
    if not path.is_file():
        return []
    lockfile, lock_hash = _lock_info(root, ["Cargo.lock"])
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        warnings.append("Could not parse Cargo.toml.")
        return []
    records: list[DependencyRecord] = []
    for field, group in (
        ("dependencies", "runtime"),
        ("dev-dependencies", "dev"),
        ("build-dependencies", "build"),
    ):
        values = data.get(field, {})
        if isinstance(values, dict):
            for name, declared in sorted(values.items()):
                display = (
                    declared
                    if isinstance(declared, str)
                    else json.dumps(declared, sort_keys=True, separators=(",", ":"))
                )
                records.append(
                    DependencyRecord(
                        ecosystem="rust",
                        manifest="Cargo.toml",
                        group=group,
                        name=str(name),
                        declared=sanitize_declared_dependency(display),
                        lockfile=lockfile,
                        lock_hash=lock_hash,
                    )
                )
    return records


def _go_dependencies(root: Path) -> list[DependencyRecord]:
    path = root / "go.mod"
    if not path.is_file():
        return []
    lockfile, lock_hash = _lock_info(root, ["go.sum"])
    text = path.read_text(encoding="utf-8", errors="replace")
    records: list[DependencyRecord] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "require (":
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if line.startswith("require "):
            line = line.removeprefix("require ").strip()
        elif not in_block:
            continue
        parts = line.split()
        if len(parts) >= 2:
            records.append(
                DependencyRecord(
                    ecosystem="go",
                    manifest="go.mod",
                    group="runtime",
                    name=parts[0],
                    declared=parts[1],
                    lockfile=lockfile,
                    lock_hash=lock_hash,
                )
            )
    return records


def collect_dependencies(root: Path) -> tuple[list[DependencyRecord], list[str]]:
    warnings: list[str] = []
    records = [
        *_python_dependencies(root, warnings),
        *_requirements_dependencies(root),
        *_node_dependencies(root, warnings),
        *_rust_dependencies(root, warnings),
        *_go_dependencies(root),
    ]
    unique = {
        (
            item.ecosystem,
            item.manifest,
            item.group,
            item.name,
            item.declared,
        ): item
        for item in records
    }
    return (
        sorted(
            unique.values(),
            key=lambda item: (
                item.ecosystem,
                item.manifest,
                item.group,
                item.name,
            ),
        ),
        sorted(set(warnings)),
    )


def collect_migrations(files: list[FileRecord]) -> list[MigrationRecord]:
    records: list[MigrationRecord] = []
    for file in files:
        path = file.path
        if path.startswith("<redacted:") or file.kind != "file":
            continue
        lower = "/" + path.lower()
        framework: str | None = None
        if "/alembic/versions/" in lower:
            framework = "alembic"
        elif "/prisma/migrations/" in lower:
            framework = "prisma"
        elif "/db/migrate/" in lower:
            framework = "rails"
        elif "/migrations/" in lower or lower.startswith("/migrations/"):
            framework = "generic"
        if framework is not None:
            records.append(
                MigrationRecord(
                    path=path,
                    framework=framework,
                    order_key=Path(path).name,
                    sha256=file.sha256,
                )
            )
    return sorted(records, key=lambda item: (item.framework, item.order_key, item.path))


def collect_schemas(files: list[FileRecord]) -> list[SchemaRecord]:
    records: list[SchemaRecord] = []
    for file in files:
        path = file.path
        if path.startswith("<redacted:") or file.kind != "file":
            continue
        lower = path.lower()
        kind: str | None = None
        if lower.endswith((".schema.json", ".schema.yaml", ".schema.yml")):
            kind = "json-schema"
        elif lower.endswith(".graphql"):
            kind = "graphql"
        elif lower.endswith(".proto"):
            kind = "protobuf"
        elif lower.endswith("schema.prisma"):
            kind = "prisma"
        elif "/schemas/" in "/" + lower and lower.endswith(".json"):
            kind = "json-schema"
        if kind is not None:
            records.append(SchemaRecord(path=path, schema_kind=kind, sha256=file.sha256))
    return sorted(records, key=lambda item: (item.schema_kind, item.path))
