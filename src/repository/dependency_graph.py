"""AST-based Python repository dependency graph.

This module is read-only. It discovers Python modules, resolves imports,
and exposes bounded graph traversal for repository intelligence.
"""

from __future__ import annotations

import ast
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".mypy_cache", ".pytest_cache", "site-packages", "dist", "build",
}


@dataclass
class DependencyNode:
    path: str
    module: str
    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    parse_error: str | None = None


@dataclass
class DependencyGraph:
    root: str
    nodes: dict[str, DependencyNode]
    edges: list[tuple[str, str]]
    parse_errors: dict[str, str]

    def neighbors(self, path: str) -> dict:
        node = self.nodes.get(path)
        if node is None:
            raise ValueError(f"Unknown repository file: {path}")

        return {
            "target": path,
            "imports": sorted(node.imports),
            "imported_by": sorted(node.imported_by),
        }

    def subgraph(
        self,
        start: str,
        max_depth: int = 2,
        max_nodes: int = 50,
    ) -> dict:
        if start not in self.nodes:
            raise ValueError(f"Unknown repository file: {start}")
        if not 0 <= max_depth <= 5:
            raise ValueError("max_depth must be between 0 and 5")
        if not 1 <= max_nodes <= 100:
            raise ValueError("max_nodes must be between 1 and 100")

        adjacency = {}
        for source, target in self.edges:
            adjacency.setdefault(source, []).append(target)

        queue = deque([(start, 0)])
        visited = {start}
        selected_edges = []

        while queue and len(visited) < max_nodes:
            current, depth = queue.popleft()

            if depth >= max_depth:
                continue

            for target in sorted(adjacency.get(current, [])):
                selected_edges.append((current, target))

                if target not in visited and len(visited) < max_nodes:
                    visited.add(target)
                    queue.append((target, depth + 1))

        return {
            "root": start,
            "nodes": sorted(visited),
            "edges": [
                {"source": source, "target": target}
                for source, target in selected_edges
                if source in visited and target in visited
            ],
            "max_depth": max_depth,
            "truncated": bool(queue),
        }

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "nodes": {
                path: asdict(node)
                for path, node in sorted(self.nodes.items())
            },
            "edges": [
                {"source": source, "target": target}
                for source, target in sorted(set(self.edges))
            ],
            "parse_errors": self.parse_errors,
        }


class DependencyGraphBuilder:
    def __init__(self, repository_root: str | Path):
        self.root = Path(repository_root).resolve()

    def _files(self) -> list[Path]:
        return sorted(
            path for path in self.root.rglob("*.py")
            if not any(part in EXCLUDED_DIRS for part in path.parts)
        )

    def _module_name(self, path: Path) -> str:
        relative = path.relative_to(self.root).with_suffix("")
        parts = list(relative.parts)

        if parts[-1] == "__init__":
            parts.pop()

        return ".".join(parts)

    def _resolve_import(
        self,
        source_module: str,
        source_path: Path,
        node: ast.Import | ast.ImportFrom,
        modules: dict[str, str],
    ) -> set[str]:
        resolved = set()

        if isinstance(node, ast.Import):
            for alias in node.names:
                candidate = alias.name
                if candidate in modules:
                    resolved.add(modules[candidate])
            return resolved

        package = (
            source_module.split(".")
            if source_path.name == "__init__.py"
            else source_module.split(".")[:-1]
        )

        if node.level:
            remove_count = node.level - 1
            if remove_count > len(package):
                return resolved
            package = package[:len(package) - remove_count]

        base = ".".join(package + ([node.module] if node.module else []))

        if base in modules:
            resolved.add(modules[base])

        for alias in node.names:
            candidate = f"{base}.{alias.name}" if base else alias.name
            if candidate in modules:
                resolved.add(modules[candidate])

        return resolved

    def build(self) -> DependencyGraph:
        files = self._files()
        modules = {
            self._module_name(path): path.relative_to(self.root).as_posix()
            for path in files
        }

        nodes = {
            relative: DependencyNode(
                path=relative,
                module=module,
            )
            for module, relative in modules.items()
        }

        edges = []
        errors = {}

        for path in files:
            relative = path.relative_to(self.root).as_posix()
            module = self._module_name(path)

            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8"),
                    filename=relative,
                )

                for item in ast.walk(tree):
                    if isinstance(item, (ast.Import, ast.ImportFrom)):
                        targets = self._resolve_import(
                            module, path, item, modules
                        )

                        for target in targets:
                            if target != relative:
                                edges.append((relative, target))

            except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                message = str(exc)
                nodes[relative].parse_error = message
                errors[relative] = message

        edges = sorted(set(edges))

        for source, target in edges:
            nodes[source].imports.append(target)
            nodes[target].imported_by.append(source)

        return DependencyGraph(
            root=str(self.root),
            nodes=nodes,
            edges=edges,
            parse_errors=errors,
        )


def build_dependency_graph(repository_root: str | Path) -> DependencyGraph:
    """Build a read-only dependency graph for a Python repository."""
    return DependencyGraphBuilder(repository_root).build()
