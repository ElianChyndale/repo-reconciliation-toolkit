"""Privacy and read-only safety helpers."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from repo_reconciliation_toolkit.canonical import sha256_text

DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "build",
        "dist",
        "target",
        "coverage",
    }
)

SECRET_NAME_PATTERN = re.compile(
    r"(^|[._-])(env|secret|secrets|credential|credentials|token|tokens|cookie|cookies|"
    r"wallet|keystore|private[-_]?key|id_rsa|id_ed25519)([._-]|$)",
    re.IGNORECASE,
)

SAFE_ENVIRONMENT_NAMES = frozenset(
    {
        "CI",
        "GITHUB_ACTIONS",
        "GITHUB_WORKFLOW",
        "PYTHONHASHSEED",
        "SOURCE_DATE_EPOCH",
        "TZ",
    }
)


def is_secret_prone_path(relative_path: str) -> bool:
    return any(SECRET_NAME_PATTERN.search(part) for part in Path(relative_path).parts)


def redact_path(relative_path: str) -> str:
    digest = sha256_text(relative_path).removeprefix("sha256:")
    return f"<redacted:{digest[:16]}>"


def safe_display_path(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    return redact_path(normalized) if is_secret_prone_path(normalized) else normalized


def sanitize_remote_url(value: str) -> str:
    """Remove credentials and local paths while retaining useful remote identity."""

    stripped = value.strip()
    if not stripped:
        return "<empty>"
    if re.match(r"^[A-Za-z]:[\\/]", stripped) or stripped.startswith(("/", "\\", ".")):
        return "<local-path>"
    if "://" in stripped:
        parsed = urlsplit(stripped)
        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port is not None else ""
        netloc = hostname + port
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    scp_match = re.match(r"^(?:[^@]+@)?([^:]+):(.+)$", stripped)
    if scp_match:
        return f"ssh://{scp_match.group(1)}/{scp_match.group(2)}"
    return "<redacted-remote>"


def sanitize_declared_dependency(value: str) -> str:
    """Remove URL credentials, query strings, and fragments from declarations."""

    if "://" not in value:
        return value.strip()
    match = re.search(r"https?://[^\s]+", value)
    if match is None:
        return value.strip()
    sanitized = sanitize_remote_url(match.group(0))
    return value[: match.start()] + sanitized + value[match.end() :]

