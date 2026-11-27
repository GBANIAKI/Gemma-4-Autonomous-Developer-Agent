
"""Extract searchable, line-aware code chunks from Python repositories."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "site-packages",
    "dist",
    "build",
    ".pytest_cache",
}


class PythonCodeChunker:
    """Extract functions, classes, and module-level code from Python files."""

    def __init__(
        self,
        repository_root: str | Path,
        max_chunk_lines: int = 120,
    ):
        self.root = Path(repository_root).resolve()

        if max_chunk_lines < 1:
            raise ValueError("max_chunk_lines must be positive.")

        self.max_chunk_lines = max_chunk_lines

    def discover_files(self) -> list[Path]:
        """Discover Python files while excluding generated directories."""
        return sorted(
            path
            for path in self.root.rglob("*.py")
            if not any(part in EXCLUDED_DIRS for part in path.relative_to(self.root).parts)
        )

    def _split_large_block(
        self,
        lines: list[str],
        start_line: int,
        path: str,
    ) -> list[dict[str, Any]]:
        """Split oversized source blocks into bounded line ranges."""
        chunks = []

        for offset in range(0, len(lines), self.max_chunk_lines):
            content_lines = lines[offset:offset + self.max_chunk_lines]

            if not any(line.strip() for line in content_lines):
                continue

            first = offset
            last = offset + len(content_lines) - 1

            chunks.append({
                "path": path,
                "start_line": start_line + first,
                "end_line": start_line + last,
                "symbol": "module_segment",
                "content": "".join(content_lines),
            })

        return chunks

    def chunk_file(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Extract top-level classes, functions, and module segments."""
        file_path = Path(file_path).resolve()

        try:
            relative_path = file_path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError("File must be inside the repository root.") from exc

        source = file_path.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)

        if not lines:
            return []

        try:
            tree = ast.parse(source, filename=relative_path)
        except SyntaxError:
            return self._split_large_block(lines, 1, relative_path)

        blocks = []

        for node in tree.body:
            if not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue

            start = node.lineno
            if node.decorator_list:
                start = min(
                    start,
                    *(decorator.lineno for decorator in node.decorator_list),
                )

            end = node.end_lineno or node.lineno

            blocks.append({
                "start": start,
                "end": end,
                "symbol": node.name,
            })

        blocks.sort(key=lambda item: item["start"])

        chunks = []
        cursor = 1

        for block in blocks:
            if cursor < block["start"]:
                chunks.extend(
                    self._split_large_block(
                        lines[cursor - 1:block["start"] - 1],
                        cursor,
                        relative_path,
                    )
                )

            block_lines = lines[block["start"] - 1:block["end"]]

            if len(block_lines) <= self.max_chunk_lines:
                chunks.append({
                    "path": relative_path,
                    "start_line": block["start"],
                    "end_line": block["end"],
                    "symbol": block["symbol"],
                    "content": "".join(block_lines),
                })
            else:
                chunks.extend(
                    self._split_large_block(
                        block_lines,
                        block["start"],
                        relative_path,
                    )
                )

            cursor = block["end"] + 1

        if cursor <= len(lines):
            chunks.extend(
                self._split_large_block(
                    lines[cursor - 1:],
                    cursor,
                    relative_path,
                )
            )

        return chunks

    def chunk_repository(self) -> list[dict[str, Any]]:
        """Extract searchable chunks from all discovered Python files."""
        chunks = []

        for file_path in self.discover_files():
            try:
                chunks.extend(self.chunk_file(file_path))
            except (OSError, UnicodeDecodeError):
                continue

        return chunks


def chunk_repository(
    repository_root: str | Path,
    max_chunk_lines: int = 120,
) -> list[dict[str, Any]]:
    """Convenience interface for repository code chunking."""
    chunker = PythonCodeChunker(
        repository_root,
        max_chunk_lines=max_chunk_lines,
    )
    return chunker.chunk_repository()
