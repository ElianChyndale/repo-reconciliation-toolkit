"""Generate public and packaged JSON Schemas from Pydantic models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from repo_reconciliation_toolkit.models import ComparisonReport, RepositorySnapshot


def _schema(model: type[RepositorySnapshot] | type[ComparisonReport], schema_id: str) -> str:
    value: dict[str, Any] = model.model_json_schema(mode="validation")
    value["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    value["$id"] = schema_id
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    public = root / "schemas"
    packaged = root / "src" / "repo_reconciliation_toolkit" / "schema_data"
    values = {
        "snapshot.schema.json": _schema(
            RepositorySnapshot,
            "https://elianchyndale.github.io/repo-reconciliation-toolkit/v1/snapshot.schema.json",
        ),
        "comparison.schema.json": _schema(
            ComparisonReport,
            "https://elianchyndale.github.io/repo-reconciliation-toolkit/v1/comparison.schema.json",
        ),
    }
    if args.check:
        mismatches: list[str] = []
        for name, content in values.items():
            for directory in (public, packaged):
                path = directory / name
                if not path.is_file() or path.read_text(encoding="utf-8") != content:
                    mismatches.append(path.relative_to(root).as_posix())
        if mismatches:
            raise SystemExit("generated schema mismatch: " + ", ".join(mismatches))
        return 0
    public.mkdir(parents=True, exist_ok=True)
    packaged.mkdir(parents=True, exist_ok=True)
    for name, content in values.items():
        (public / name).write_text(content, encoding="utf-8", newline="\n")
        (packaged / name).write_text(content, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

