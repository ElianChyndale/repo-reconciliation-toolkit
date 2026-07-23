from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def git_executable() -> str:
    resolved = shutil.which("git")
    if resolved is None:
        bundled = Path(
            "C:/Users/Administrator/.cache/codex-runtimes/"
            "codex-primary-runtime/dependencies/native/git/cmd/git.exe"
        )
        if bundled.is_file():
            resolved = str(bundled)
    if resolved is None:
        pytest.skip("Git executable is required for repository fixture tests")
    return resolved

