from __future__ import annotations

from pathlib import Path

from repo_reconciliation_toolkit.symbols import extract_symbols


def test_python_nested_symbols() -> None:
    source = """
class Model:
    def score(self, value: float) -> float:
        return value

async def load() -> None:
    return None
""".strip()
    symbols = extract_symbols(Path("model.py"), source)
    assert [(item.kind, item.name) for item in symbols] == [
        ("class", "Model"),
        ("function", "Model.score"),
        ("async_function", "load"),
    ]


def test_typescript_symbols() -> None:
    source = """
export interface Result { value: number }
export function rank(values: number[]) { return values; }
export const VERSION = "1";
""".strip()
    symbols = extract_symbols(Path("service.ts"), source)
    assert [(item.kind, item.name) for item in symbols] == [
        ("interface", "Result"),
        ("function", "rank"),
        ("const", "VERSION"),
    ]


def test_solidity_symbols() -> None:
    source = """
contract Vault {
    struct Position { uint256 amount; }
    function settle() external { }
}
""".strip()
    symbols = extract_symbols(Path("Vault.sol"), source)
    assert [(item.kind, item.name) for item in symbols] == [
        ("contract", "Vault"),
        ("struct", "Position"),
        ("function", "settle"),
    ]


def test_invalid_python_has_no_symbols() -> None:
    assert extract_symbols(Path("broken.py"), "def broken(:") == []

