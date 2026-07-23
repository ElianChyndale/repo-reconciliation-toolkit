from __future__ import annotations

import json

from repo_reconciliation_toolkit.safety import (
    is_secret_prone_path,
    safe_display_path,
    sanitize_declared_dependency,
    sanitize_remote_url,
)


def test_secret_prone_paths_are_redacted() -> None:
    assert is_secret_prone_path(".env")
    assert is_secret_prone_path("config/private-key.pem")
    value = safe_display_path("nested/credentials.json")
    assert value.startswith("<redacted:")
    assert "credentials" not in value


def test_normal_paths_are_preserved_with_forward_slashes() -> None:
    assert safe_display_path(r"src\module.py") == "src/module.py"


def test_https_remote_credentials_query_and_fragment_are_removed() -> None:
    value = sanitize_remote_url(
        "https://token:password@github.com/example/repo.git?access=secret#fragment"
    )
    assert value == "https://github.com/example/repo.git"
    assert "token" not in value
    assert "password" not in value
    assert "secret" not in value


def test_ssh_remote_user_is_removed() -> None:
    assert (
        sanitize_remote_url("git@github.com:example/repo.git")
        == "ssh://github.com/example/repo.git"
    )


def test_local_remote_is_redacted() -> None:
    assert sanitize_remote_url("C:/repos/source") == "<local-path>"
    assert sanitize_remote_url("../source") == "<local-path>"


def test_dependency_url_credentials_are_removed() -> None:
    value = sanitize_declared_dependency(
        "package @ https://user:pass@example.com/pkg.whl?token=x"
    )
    assert value == "package @ https://example.com/pkg.whl"


def test_serialized_values_do_not_contain_secret_input() -> None:
    values = {
        "path": safe_display_path("wallet/secret-key.json"),
        "remote": sanitize_remote_url("https://abc:def@example.com/repo?token=ghi"),
    }
    text = json.dumps(values)
    for secret in ("wallet", "secret-key", "abc", "def", "ghi"):
        assert secret not in text

