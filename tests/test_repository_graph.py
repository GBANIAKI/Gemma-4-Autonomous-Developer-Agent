
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


def test_resolves_relative_sibling_import(tmp_path):
    package = tmp_path / "pkg" / "sub"
    package.mkdir(parents=True)

    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "consumer.py").write_text(
        "from . import helper\n",
        encoding="utf-8",
    )
    (package / "helper.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    graph = build_dependency_graph(tmp_path)

    assert (
        "pkg/sub/consumer.py",
        "pkg/sub/helper.py",
    ) in graph.edges


def test_resolves_relative_parent_package_import(tmp_path):
    package = tmp_path / "pkg" / "sub"
    package.mkdir(parents=True)

    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "shared.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "consumer.py").write_text(
        "from .. import shared\n",
        encoding="utf-8",
    )

    graph = build_dependency_graph(tmp_path)

    assert (
        "pkg/sub/consumer.py",
        "pkg/shared.py",
    ) in graph.edges


def test_resolves_relative_import_from_package_initializer(tmp_path):
    package = tmp_path / "pkg" / "sub"
    package.mkdir(parents=True)

    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from . import helper\n",
        encoding="utf-8",
    )
    (package / "helper.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    graph = build_dependency_graph(tmp_path)

    assert (
        "pkg/sub/__init__.py",
        "pkg/sub/helper.py",
    ) in graph.edges




def test_malformed_python_file_is_recorded_without_aborting_build(tmp_path):
    create_repository(tmp_path)
    broken = tmp_path / 'pkg' / 'broken.py'
    broken.write_text('def broken(:\n    pass\n', encoding='utf-8')

    graph = build_dependency_graph(tmp_path)

    relative = 'pkg/broken.py'
    assert relative in graph.nodes
    assert graph.nodes[relative].parse_error is not None
    assert relative in graph.parse_errors
    assert graph.parse_errors[relative]


def test_parse_error_does_not_discard_valid_dependencies(tmp_path):
    create_repository(tmp_path)
    broken = tmp_path / 'pkg' / 'broken.py'
    broken.write_text('def broken(:\n    pass\n', encoding='utf-8')

    graph = build_dependency_graph(tmp_path)

    assert ('pkg/a.py', 'pkg/b.py') in graph.edges
    assert ('pkg/b.py', 'pkg/c.py') in graph.edges
    assert 'pkg/broken.py' in graph.parse_errors


def test_excludes_configured_generated_and_dependency_directories(tmp_path):
    create_repository(tmp_path)

    excluded_dirs = [
        '.venv', '__pycache__', 'node_modules', 'build', 'dist',
        '.git', '.mypy_cache', '.pytest_cache', 'site-packages', 'venv',
    ]

    for directory in excluded_dirs:
        folder = tmp_path / directory
        folder.mkdir(parents=True)
        (folder / 'hidden.py').write_text('VALUE = 1', encoding='utf-8')

    graph = build_dependency_graph(tmp_path)

    for directory in excluded_dirs:
        assert f'{directory}/hidden.py' not in graph.nodes

    assert 'pkg/a.py' in graph.nodes


def test_excludes_nested_generated_directories_without_excluding_neighbors(tmp_path):
    package = tmp_path / 'pkg'
    package.mkdir()
    (package / 'main.py').write_text('VALUE = 1', encoding='utf-8')

    cache = package / '__pycache__'
    cache.mkdir()
    (cache / 'cached.py').write_text('VALUE = 2', encoding='utf-8')

    build = package / 'build'
    build.mkdir()
    (build / 'generated.py').write_text('VALUE = 3', encoding='utf-8')

    graph = build_dependency_graph(tmp_path)

    assert 'pkg/main.py' in graph.nodes
    assert 'pkg/__pycache__/cached.py' not in graph.nodes
    assert 'pkg/build/generated.py' not in graph.nodes



def test_build_preserves_circular_dependencies(tmp_path):
    package = tmp_path / 'cycle'
    package.mkdir()

    newline = chr(10)
    (package / 'a.py').write_text('import cycle.b' + newline, encoding='utf-8')
    (package / 'b.py').write_text('import cycle.c' + newline, encoding='utf-8')
    (package / 'c.py').write_text('import cycle.a' + newline, encoding='utf-8')

    graph = build_dependency_graph(tmp_path)

    assert set(graph.edges) == {
        ('cycle/a.py', 'cycle/b.py'),
        ('cycle/b.py', 'cycle/c.py'),
        ('cycle/c.py', 'cycle/a.py'),
    }


def test_recursive_navigation_terminates_on_circular_dependencies(tmp_path):
    package = tmp_path / 'cycle'
    package.mkdir()

    newline = chr(10)
    (package / 'a.py').write_text('import cycle.b' + newline, encoding='utf-8')
    (package / 'b.py').write_text('import cycle.c' + newline, encoding='utf-8')
    (package / 'c.py').write_text('import cycle.a' + newline, encoding='utf-8')

    navigator = RepositoryNavigator(tmp_path)

    assert navigator.dependencies('cycle/a.py', recursive=True) == [
        'cycle/b.py',
        'cycle/c.py',
    ]
    assert navigator.dependents('cycle/a.py', recursive=True) == [
        'cycle/b.py',
        'cycle/c.py',
    ]
    assert navigator.dependency_path('cycle/a.py', 'cycle/a.py') == [
        'cycle/a.py',
    ]


def test_large_graph_respects_node_limit_and_reports_truncation(tmp_path):
    newline = chr(10)
    root = tmp_path / 'root.py'
    imports = [f'import module_{i}' for i in range(20)]
    root.write_text(newline.join(imports) + newline, encoding='utf-8')

    for i in range(20):
        (tmp_path / f'module_{i}.py').write_text(
            'VALUE = ' + str(i) + newline,
            encoding='utf-8',
        )

    graph = build_dependency_graph(tmp_path)
    result = graph.subgraph('root.py', max_depth=2, max_nodes=5)

    assert len(result['nodes']) == 5
    assert result['root'] == 'root.py'
    assert result['truncated'] is True


def test_depth_limit_reports_unvisited_descendants(tmp_path):
    newline = chr(10)
    (tmp_path / 'root.py').write_text('import middle' + newline, encoding='utf-8')
    (tmp_path / 'middle.py').write_text('import leaf' + newline, encoding='utf-8')
    (tmp_path / 'leaf.py').write_text('VALUE = 1' + newline, encoding='utf-8')

    graph = build_dependency_graph(tmp_path)
    result = graph.subgraph('root.py', max_depth=1)

    assert result['nodes'] == ['middle.py', 'root.py']
    assert result['truncated'] is True


def test_depth_limit_does_not_report_truncation_at_graph_boundary(tmp_path):
    newline = chr(10)
    (tmp_path / 'root.py').write_text('import middle' + newline, encoding='utf-8')
    (tmp_path / 'middle.py').write_text('VALUE = 1' + newline, encoding='utf-8')

    graph = build_dependency_graph(tmp_path)
    result = graph.subgraph('root.py', max_depth=1)

    assert result['nodes'] == ['middle.py', 'root.py']
    assert result['truncated'] is False
