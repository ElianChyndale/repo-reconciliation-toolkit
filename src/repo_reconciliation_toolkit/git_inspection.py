"""Strictly read-only Git inspection."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from repo_reconciliation_toolkit.models import (
    BranchState,
    CommitNode,
    GitState,
    RemoteState,
    TagState,
    WorkingTreeChange,
)
from repo_reconciliation_toolkit.safety import safe_display_path, sanitize_remote_url

ALLOWED_GIT_COMMANDS = frozenset(
    {
        "diff",
        "for-each-ref",
        "ls-files",
        "remote",
        "rev-list",
        "rev-parse",
        "show",
        "status",
        "symbolic-ref",
    }
)


class GitInspectionError(RuntimeError):
    pass


class GitInspector:
    def __init__(self, executable: str | None = None) -> None:
        resolved = executable or shutil.which("git")
        if resolved is None:
            raise GitInspectionError("git executable was not found")
        self.executable = resolved

    def run(
        self,
        repository: Path,
        arguments: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not arguments or arguments[0] not in ALLOWED_GIT_COMMANDS:
            command = arguments[0] if arguments else "<empty>"
            raise GitInspectionError(f"forbidden Git command: {command}")
        result = subprocess.run(
            [self.executable, "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        if check and result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
            raise GitInspectionError(f"git {arguments[0]} failed: {message}")
        return result

    def is_repository(self, repository: Path) -> bool:
        result = self.run(
            repository,
            ["rev-parse", "--is-inside-work-tree"],
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def inspect(self, repository: Path) -> tuple[GitState, list[WorkingTreeChange], list[str]]:
        if not self.is_repository(repository):
            return (
                GitState(
                    is_repository=False,
                    head_commit=None,
                    branch=None,
                    detached=False,
                    branches=[],
                    tags=[],
                    remotes=[],
                    commits=[],
                    commit_graph_truncated=False,
                ),
                [],
                ["Directory is not a Git working tree."],
            )
        warnings: list[str] = []
        head_result = self.run(repository, ["rev-parse", "HEAD"], check=False)
        head_commit = head_result.stdout.strip() if head_result.returncode == 0 else None
        branch_result = self.run(
            repository,
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        detached = head_commit is not None and branch is None
        branches = self._branches(repository, warnings)
        tags = self._tags(repository)
        remotes = self._remotes(repository)
        commits, commit_graph_truncated = self._commit_graph(repository)
        if commit_graph_truncated:
            warnings.append("Commit graph was truncated to 200 nodes.")
        working_tree = self._working_tree(repository)
        state = GitState(
            is_repository=True,
            head_commit=head_commit,
            branch=branch,
            detached=detached,
            branches=branches,
            tags=tags,
            remotes=remotes,
            commits=commits,
            commit_graph_truncated=commit_graph_truncated,
        )
        return state, working_tree, warnings

    def _branches(self, repository: Path, warnings: list[str]) -> list[BranchState]:
        result = self.run(
            repository,
            [
                "for-each-ref",
                "--format=%(refname:short)%00%(objectname)%00%(upstream:short)",
                "refs/heads",
            ],
        )
        branches: list[BranchState] = []
        for line in result.stdout.splitlines():
            parts = line.split("\x00")
            if len(parts) != 3:
                continue
            name, commit, upstream = parts
            ahead: int | None = None
            behind: int | None = None
            source: str = "none"
            if upstream:
                count = self.run(
                    repository,
                    ["rev-list", "--left-right", "--count", f"{name}...{upstream}"],
                    check=False,
                )
                if count.returncode == 0:
                    values = count.stdout.strip().split()
                    if len(values) == 2 and all(value.isdigit() for value in values):
                        ahead, behind = int(values[0]), int(values[1])
                        source = "local_tracking_ref"
                else:
                    warnings.append(
                        f"Could not calculate local-ref divergence for branch {name}."
                    )
            branches.append(
                BranchState(
                    name=name,
                    commit=commit,
                    upstream=upstream or None,
                    ahead=ahead,
                    behind=behind,
                    divergence_source=source,  # type: ignore[arg-type]
                )
            )
        return sorted(branches, key=lambda item: item.name)

    def _tags(self, repository: Path) -> list[TagState]:
        result = self.run(
            repository,
            [
                "for-each-ref",
                "--format=%(refname:short)%00%(objectname)%00%(*objectname)",
                "refs/tags",
            ],
        )
        tags: list[TagState] = []
        for line in result.stdout.splitlines():
            parts = line.split("\x00")
            if len(parts) != 3:
                continue
            name, object_name, peeled = parts
            commit = peeled or object_name
            if re.fullmatch(r"[0-9a-f]{40,64}", commit):
                tags.append(TagState(name=name, commit=commit))
        return sorted(tags, key=lambda item: item.name)

    def _commit_graph(self, repository: Path) -> tuple[list[CommitNode], bool]:
        result = self.run(
            repository,
            [
                "rev-list",
                "--all",
                "--parents",
                "--topo-order",
                "--max-count=201",
            ],
        )
        nodes: list[CommitNode] = []
        for line in result.stdout.splitlines():
            values = line.split()
            if not values:
                continue
            commit, *parents = values
            if re.fullmatch(r"[0-9a-f]{40,64}", commit) and all(
                re.fullmatch(r"[0-9a-f]{40,64}", parent) for parent in parents
            ):
                nodes.append(CommitNode(commit=commit, parents=parents))
        truncated = len(nodes) > 200
        return nodes[:200], truncated

    def _remotes(self, repository: Path) -> list[RemoteState]:
        result = self.run(repository, ["remote", "-v"])
        values: dict[str, dict[str, str]] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^(\S+)\s+(.+)\s+\((fetch|push)\)$", line)
            if match is None:
                continue
            name, url, mode = match.groups()
            values.setdefault(name, {})[mode] = sanitize_remote_url(url)
        return [
            RemoteState(
                name=name,
                fetch_url=modes.get("fetch", "<missing>"),
                push_url=modes.get("push", "<missing>"),
            )
            for name, modes in sorted(values.items())
        ]

    def _working_tree(self, repository: Path) -> list[WorkingTreeChange]:
        changes: list[WorkingTreeChange] = []
        changes.extend(self._diff_changes(repository, cached=True))
        changes.extend(self._diff_changes(repository, cached=False))
        untracked = self.run(
            repository,
            ["ls-files", "--others", "--exclude-standard", "-z"],
        )
        for path in (item for item in untracked.stdout.split("\x00") if item):
            changes.append(
                WorkingTreeChange(
                    path=safe_display_path(path),
                    status="untracked",
                    old_path=None,
                )
            )
        conflicts = set(
            item
            for item in self.run(
                repository,
                ["diff", "--name-only", "--diff-filter=U", "-z"],
            ).stdout.split("\x00")
            if item
        )
        if conflicts:
            changes = [change for change in changes if change.path not in conflicts]
            changes.extend(
                WorkingTreeChange(
                    path=safe_display_path(path),
                    status="conflicted",
                    old_path=None,
                )
                for path in conflicts
            )
        unique = {
            (change.path, change.status, change.old_path): change for change in changes
        }
        return sorted(
            unique.values(),
            key=lambda item: (item.path, item.status, item.old_path or ""),
        )

    def _diff_changes(
        self,
        repository: Path,
        *,
        cached: bool,
    ) -> list[WorkingTreeChange]:
        arguments = ["diff"]
        if cached:
            arguments.append("--cached")
        arguments.extend(["--name-status", "-z"])
        fields = [
            item for item in self.run(repository, arguments).stdout.split("\x00") if item
        ]
        changes: list[WorkingTreeChange] = []
        index = 0
        while index < len(fields):
            status_code = fields[index]
            index += 1
            if index >= len(fields):
                break
            old_path: str | None = None
            path = fields[index]
            index += 1
            code = status_code[:1]
            if code in {"R", "C"} and index < len(fields):
                old_path = path
                path = fields[index]
                index += 1
            status = {
                "A": "staged" if cached else "modified",
                "M": "staged" if cached else "modified",
                "D": "deleted",
                "R": "renamed",
                "C": "copied",
                "T": "type_changed",
                "U": "conflicted",
            }.get(code, "modified")
            changes.append(
                WorkingTreeChange(
                    path=safe_display_path(path),
                    status=status,  # type: ignore[arg-type]
                    old_path=None if old_path is None else safe_display_path(old_path),
                )
            )
        return changes
