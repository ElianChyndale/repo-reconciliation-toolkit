"""Bounded symbol fingerprints for conservative conflict prediction."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from repo_reconciliation_toolkit.canonical import sha256_text
from repo_reconciliation_toolkit.models import SymbolFingerprint

SOURCE_SUFFIXES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".sol": "solidity",
}


def _normalized(value: str) -> str:
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())


def _fingerprint(
    language: str,
    kind: str,
    name: str,
    line: int,
    signature: str,
    body: str,
) -> SymbolFingerprint:
    return SymbolFingerprint(
        language=language,  # type: ignore[arg-type]
        kind=kind,
        name=name,
        start_line=line,
        signature_hash=sha256_text(_normalized(signature)),
        body_hash=sha256_text(body.replace("\r\n", "\n").replace("\r", "\n")),
    )


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.stack: list[str] = []
        self.symbols: list[SymbolFingerprint] = []

    def _add(self, node: ast.AST, kind: str, name: str) -> None:
        display_name = ".".join([*self.stack, name])
        segment = ast.get_source_segment(self.source, node) or ""
        first_line = segment.splitlines()[0] if segment else display_name
        line = int(getattr(node, "lineno", 1))
        self.symbols.append(
            _fingerprint("python", kind, display_name, line, first_line, segment)
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node, "class", node.name)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node, "function", node.name)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add(node, "async_function", node.name)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def _python_symbols(source: str) -> list[SymbolFingerprint]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _PythonVisitor(source)
    visitor.visit(tree)
    return sorted(visitor.symbols, key=lambda item: (item.start_line, item.kind, item.name))


JS_TS_PATTERN = re.compile(
    r"(?m)^[ \t]*(?:export\s+(?:default\s+)?)?"
    r"(?:(async)\s+)?"
    r"(function|class|interface|type|const)\s+([A-Za-z_$][\w$]*)"
)
SOLIDITY_PATTERN = re.compile(
    r"(?m)^[ \t]*(?:abstract\s+)?"
    r"(contract|library|interface|struct|enum|function)\s+([A-Za-z_$][\w$]*)"
)


def _bounded_block(source: str, start: int) -> str:
    brace = source.find("{", start)
    line_end = source.find("\n", start)
    ends_with_semicolon = (
        line_end >= 0
        and brace > line_end
        and source[start:line_end].rstrip().endswith(";")
    )
    if brace < 0 or ends_with_semicolon:
        end = len(source) if line_end < 0 else line_end
        return source[start:end]
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(brace, len(source)):
        character = source[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'", "`"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return source[start:]


def _regex_symbols(source: str, language: str) -> list[SymbolFingerprint]:
    pattern = SOLIDITY_PATTERN if language == "solidity" else JS_TS_PATTERN
    symbols: list[SymbolFingerprint] = []
    for match in pattern.finditer(source):
        if language == "solidity":
            kind = match.group(1)
            name = match.group(2)
        else:
            kind = ("async_" if match.group(1) else "") + match.group(2)
            name = match.group(3)
        assert kind is not None and name is not None
        line = source.count("\n", 0, match.start()) + 1
        body = _bounded_block(source, match.start())
        signature = body.splitlines()[0] if body else match.group(0)
        symbols.append(_fingerprint(language, kind, name, line, signature, body))
    return sorted(symbols, key=lambda item: (item.start_line, item.kind, item.name))


def extract_symbols(path: Path, source: str) -> list[SymbolFingerprint]:
    language = SOURCE_SUFFIXES.get(path.suffix.lower())
    if language is None:
        return []
    if language == "python":
        return _python_symbols(source)
    return _regex_symbols(source, language)
