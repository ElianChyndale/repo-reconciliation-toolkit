"""Require every generated machine artifact to parse and contain records."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _nonempty(value: Any) -> bool:
    if isinstance(value, (dict, list)):
        return bool(value)
    return value is not None


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "research" / "results" / "v0.1"
    checked = 0
    for path in sorted(root.iterdir()):
        if path.suffix == ".json":
            if not _nonempty(json.loads(path.read_text(encoding="utf-8"))):
                raise SystemExit(f"empty JSON artifact: {path}")
        elif path.suffix == ".jsonl":
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line
            ]
            if not rows:
                raise SystemExit(f"empty JSONL artifact: {path}")
        elif path.suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as stream:
                if not list(csv.DictReader(stream)):
                    raise SystemExit(f"empty CSV artifact: {path}")
        else:
            continue
        checked += 1
    if checked == 0:
        raise SystemExit("no machine artifacts found")
    print(f"parsed {checked} non-empty artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

