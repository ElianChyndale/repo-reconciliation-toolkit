"""Deterministic JSON serialization and identifiers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def object_id(value: dict[str, Any], id_field: str) -> str:
    payload = dict(value)
    payload.pop(id_field, None)
    return sha256_bytes(canonical_bytes(payload))

