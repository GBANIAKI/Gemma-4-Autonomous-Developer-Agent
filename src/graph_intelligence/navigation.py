
"""Repository graph navigation and dependency analysis."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from src.repository.dependency_graph import (
    DependencyGraph,
    build_dependency_graph,
)


class RepositoryNavigator:
    """Read-only navigation over a repository dependency graph."""

    def __init__(self, repository_root: str | Path):
        self.repository_root = Path(repository_root).resolve()
        self.graph: DependencyGraph = build_dependency_graph(
            self.repository_root
        )

    def neighbors(self, target: str) -> dict:
        """Return direct dependencies and reverse dependencies."""
        return self.graph.neighbors(target)

    def dependencies(self, target: str, recursive: bool = False) -> list[str]:
        """Return files imported by target."""
        if not recursive:
            return self.graph.neighbors(target)["imports"]

        return self._traverse(target, direction="imports")

    def dependents(self, target: str, recursive: bool = False) -> list[str]:
        """Return files that import target."""
        if not recursive:
            return self.graph.neighbors(target)["imported_by"]

        return self._traverse(target, direction="imported_by")

    def _traverse(self, start: str, direction: str) -> list[str]:
        if start not in self.graph.nodes:
            raise ValueError(f"Unknown repository file: {start}")

        queue = deque([start])
        visited = {start}

        while queue:
            current = queue.popleft()
            node = self.graph.nodes[current]

            adjacent = getattr(node, direction)

            for target in sorted(adjacent):
                if target not in visited:
                    visited.add(target)
                    queue.append(target)

        visited.remove(start)
        return sorted(visited)

    def dependency_path(
        self,
        source: str,
        destination: str,
    ) -> list[str] | None:
        """Find the shortest directed import path between two files."""
        if source not in self.graph.nodes:
            raise ValueError(f"Unknown source: {source}")

        if destination not in self.graph.nodes:
            raise ValueError(f"Unknown destination: {destination}")

        queue = deque([(source, [source])])
        visited = {source}

        adjacency = {}

        for origin, target in self.graph.edges:
            adjacency.setdefault(origin, []).append(target)

        while queue:
            current, path = queue.popleft()

            if current == destination:
                return path

            for neighbor in sorted(adjacency.get(current, [])):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def explore(
        self,
        target: str,
        max_depth: int = 2,
        max_nodes: int = 50,
    ) -> dict:
        """Return a bounded dependency subgraph."""
        return self.graph.subgraph(
            target,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )

    def rank_related_files(
        self,
        target: str,
        candidates: list[str] | None = None,
    ) -> list[dict]:
        """Rank files using structural dependency relationships.

        This is a structural ranking, not semantic relevance ranking.
        """
        if target not in self.graph.nodes:
            raise ValueError(f"Unknown target: {target}")

        allowed = (
            set(candidates)
            if candidates is not None
            else set(self.graph.nodes)
        )

        if target not in allowed:
            allowed.add(target)

        upstream = set(self.dependents(target, recursive=True))
        downstream = set(self.dependencies(target, recursive=True))

        direct = set(
            self.graph.nodes[target].imports
            + self.graph.nodes[target].imported_by
        )

        results = []

        for path in allowed:
            if path not in self.graph.nodes or path == target:
                continue

            score = 0.0
            reasons = []

            if path in direct:
                score += 1.0
                reasons.append("direct_dependency")

            if path in downstream:
                score += 0.5
                reasons.append("transitive_dependency")

            if path in upstream:
                score += 0.5
                reasons.append("transitive_dependent")

            if score:
                results.append({
                    "path": path,
                    "score": score,
                    "reasons": reasons,
                })

        return sorted(
            results,
            key=lambda item: (-item["score"], item["path"]),
        )


def navigate_repository(
    repository_root: str | Path,
    target: str,
    max_depth: int = 2,
    max_nodes: int = 50,
) -> dict:
    """Convenience interface for repository graph exploration."""
    navigator = RepositoryNavigator(repository_root)

    return {
        "neighbors": navigator.neighbors(target),
        "subgraph": navigator.explore(
            target,
            max_depth=max_depth,
            max_nodes=max_nodes,
        ),
        "related_files": navigator.rank_related_files(target),
    }
