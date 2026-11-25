
from pathlib import Path

import pytest

from src.repository.dependency_graph import (
    DependencyGraphBuilder,
    build_dependency_graph,
)
from src.graph_intelligence.navigation import RepositoryNavigator


def create_repository(root: Path):
    """Create a small repository with a three-module dependency chain."""
    package = root / "pkg"
    package.mkdir(parents=True)

    (package / "__init__.py").write_text("", encoding="utf-8")

    (package / "a.py").write_text(
        "import pkg.b\n",
        encoding="utf-8",
    )

    (package / "b.py").write_text(
        "from pkg import c\n",
        encoding="utf-8",
    )

    (package / "c.py").write_text(
        "import os\n",
        encoding="utf-8",
    )


def test_build_detects_internal_dependencies(tmp_path):
    create_repository(tmp_path)

    graph = build_dependency_graph(tmp_path)

    assert ("pkg/a.py", "pkg/b.py") in graph.edges
    assert ("pkg/b.py", "pkg/c.py") in graph.edges

    assert graph.nodes["pkg/a.py"].imports == ["pkg/b.py"]
    assert graph.nodes["pkg/b.py"].imported_by == ["pkg/a.py"]


def test_builder_and_convenience_function_agree(tmp_path):
    create_repository(tmp_path)

    direct = DependencyGraphBuilder(tmp_path).build()
    convenience = build_dependency_graph(tmp_path)

    assert direct.edges == convenience.edges
    assert set(direct.nodes) == set(convenience.nodes)


def test_neighbors_reject_unknown_file(tmp_path):
    create_repository(tmp_path)
    graph = build_dependency_graph(tmp_path)

    with pytest.raises(ValueError, match="Unknown repository file"):
        graph.neighbors("missing.py")


def test_subgraph_respects_depth(tmp_path):
    create_repository(tmp_path)
    graph = build_dependency_graph(tmp_path)

    result = graph.subgraph("pkg/a.py", max_depth=1)

    assert result["root"] == "pkg/a.py"
    assert result["nodes"] == ["pkg/a.py", "pkg/b.py"]
    assert result["max_depth"] == 1


def test_subgraph_respects_node_limit(tmp_path):
    create_repository(tmp_path)
    graph = build_dependency_graph(tmp_path)

    result = graph.subgraph("pkg/a.py", max_depth=3, max_nodes=2)

    assert len(result["nodes"]) <= 2


def test_subgraph_rejects_invalid_limits(tmp_path):
    create_repository(tmp_path)
    graph = build_dependency_graph(tmp_path)

    with pytest.raises(ValueError):
        graph.subgraph("pkg/a.py", max_depth=6)

    with pytest.raises(ValueError):
        graph.subgraph("pkg/a.py", max_nodes=0)


def test_navigator_direct_and_recursive_dependencies(tmp_path):
    create_repository(tmp_path)
    navigator = RepositoryNavigator(tmp_path)

    assert navigator.dependencies("pkg/a.py") == ["pkg/b.py"]

    assert navigator.dependencies(
        "pkg/a.py",
        recursive=True,
    ) == ["pkg/b.py", "pkg/c.py"]


def test_navigator_direct_and_recursive_dependents(tmp_path):
    create_repository(tmp_path)
    navigator = RepositoryNavigator(tmp_path)

    assert navigator.dependents("pkg/c.py") == ["pkg/b.py"]

    assert navigator.dependents(
        "pkg/c.py",
        recursive=True,
    ) == ["pkg/a.py", "pkg/b.py"]


def test_dependency_path_finds_shortest_path(tmp_path):
    create_repository(tmp_path)
    navigator = RepositoryNavigator(tmp_path)

    result = navigator.dependency_path(
        "pkg/a.py",
        "pkg/c.py",
    )

    assert result == [
        "pkg/a.py",
        "pkg/b.py",
        "pkg/c.py",
    ]


def test_dependency_path_returns_none_when_unreachable(tmp_path):
    create_repository(tmp_path)
    navigator = RepositoryNavigator(tmp_path)

    assert navigator.dependency_path(
        "pkg/c.py",
        "pkg/a.py",
    ) is None


def test_navigator_rejects_unknown_files(tmp_path):
    create_repository(tmp_path)
    navigator = RepositoryNavigator(tmp_path)

    with pytest.raises(ValueError):
        navigator.dependencies("missing.py", recursive=True)

    with pytest.raises(ValueError):
        navigator.dependency_path("missing.py", "pkg/a.py")


def test_rank_related_files(tmp_path):
    create_repository(tmp_path)
    navigator = RepositoryNavigator(tmp_path)

    results = navigator.rank_related_files("pkg/a.py")

    paths = [item["path"] for item in results]

    assert "pkg/b.py" in paths
    assert "pkg/c.py" in paths
    assert results[0]["path"] == "pkg/b.py"


def test_graph_serialization(tmp_path):
    create_repository(tmp_path)
    graph = build_dependency_graph(tmp_path)

    result = graph.to_dict()

    assert "pkg/a.py" in result["nodes"]
    assert {"source": "pkg/a.py", "target": "pkg/b.py"} in result["edges"]
