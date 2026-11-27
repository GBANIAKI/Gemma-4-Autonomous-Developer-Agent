
from pathlib import Path
from types import SimpleNamespace

import pytest

import local_dev.local_tools as tools


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """Create a temporary repository and redirect the tool wrappers to it."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        "import pkg.b\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "b.py").write_text(
        "import pkg.c\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "c.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    return tmp_path


def test_get_repository_dependencies(repository, monkeypatch):
    calls = []
    navigator = SimpleNamespace(
        dependencies=lambda target, recursive=False: (
            calls.append((target, recursive)) or ["pkg/b.py"]
        )
    )
    monkeypatch.setattr(tools, "_get_repository_navigator", lambda: navigator)

    result = tools.get_repository_dependencies("pkg/a.py")

    assert result["success"] is True
    assert result["target"] == "pkg/a.py"
    assert result["dependencies"] == ["pkg/b.py"]
    assert result["count"] == 1
    assert calls == [("pkg/a.py", False)]


def test_get_repository_dependencies_recursive(repository, monkeypatch):
    navigator = SimpleNamespace(
        dependencies=lambda target, recursive=False: ["pkg/b.py", "pkg/c.py"]
    )
    monkeypatch.setattr(tools, "_get_repository_navigator", lambda: navigator)

    result = tools.get_repository_dependencies("pkg/a.py", recursive=True)

    assert result["success"] is True
    assert result["recursive"] is True
    assert result["count"] == 2


def test_get_repository_dependents(repository, monkeypatch):
    navigator = SimpleNamespace(
        dependents=lambda target, recursive=False: ["pkg/a.py"]
    )
    monkeypatch.setattr(tools, "_get_repository_navigator", lambda: navigator)

    result = tools.get_repository_dependents("pkg/b.py")

    assert result["success"] is True
    assert result["target"] == "pkg/b.py"
    assert result["dependents"] == ["pkg/a.py"]


def test_find_dependency_path(repository, monkeypatch):
    navigator = SimpleNamespace(
        dependency_path=lambda source, destination: [
            source, "pkg/b.py", destination
        ]
    )
    monkeypatch.setattr(tools, "_get_repository_navigator", lambda: navigator)

    result = tools.find_dependency_path("pkg/a.py", "pkg/c.py")

    assert result["success"] is True
    assert result["path_found"] is True
    assert result["path"] == ["pkg/a.py", "pkg/b.py", "pkg/c.py"]


def test_find_dependency_path_not_found(repository, monkeypatch):
    navigator = SimpleNamespace(
        dependency_path=lambda source, destination: None
    )
    monkeypatch.setattr(tools, "_get_repository_navigator", lambda: navigator)

    result = tools.find_dependency_path("pkg/a.py", "pkg/c.py")

    assert result["success"] is True
    assert result["path_found"] is False
    assert result["path"] is None


@pytest.mark.parametrize(
    "function,args",
    [
        (tools.get_repository_dependencies, ("missing.py",)),
        (tools.get_repository_dependents, ("missing.py",)),
        (tools.find_dependency_path, ("pkg/a.py", "missing.py")),
    ],
)
def test_dependency_wrappers_reject_missing_files(
    repository, monkeypatch, function, args
):
    monkeypatch.setattr(
        tools,
        "_get_repository_navigator",
        lambda: pytest.fail("Navigator must not be created for invalid paths"),
    )

    result = function(*args)

    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_dependency_wrapper_rejects_non_python_file(repository):
    (repository / "notes.txt").write_text("notes", encoding="utf-8")

    result = tools.get_repository_dependencies("notes.txt")

    assert result["success"] is False
    assert "Python file" in result["error"]


def test_dependency_wrapper_rejects_path_outside_repository(repository, tmp_path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("VALUE = 1", encoding="utf-8")

    result = tools.get_repository_dependencies(str(outside))

    assert result["success"] is False
    assert "outside" in result["error"].lower()


def test_dependency_wrapper_rejects_non_boolean_recursive(repository):
    result = tools.get_repository_dependencies(
        "pkg/a.py", recursive="yes"
    )

    assert result["success"] is False
    assert "boolean" in result["error"]


@pytest.mark.parametrize("query", ["", "   ", None, 42])
def test_semantic_search_rejects_invalid_query(query):
    result = tools.search_semantic_code(query)

    assert result["success"] is False
    assert "query" in result["error"]


@pytest.mark.parametrize("max_results", [0, 21, True, 1.5, "5"])
def test_semantic_search_rejects_invalid_result_limit(max_results):
    result = tools.search_semantic_code("dependency analysis", max_results)

    assert result["success"] is False
    assert "max_results" in result["error"]


def test_semantic_search_reports_missing_artifact(repository, monkeypatch):
    monkeypatch.setenv(
        "REPOSITORY_EMBEDDINGS_PATH",
        "artifacts/missing.jsonl",
    )

    result = tools.search_semantic_code("dependency analysis")

    assert result["success"] is False
    assert "artifact was not found" in result["error"]
    assert "next_step" in result


def test_semantic_search_rejects_invalid_path_filter(repository, monkeypatch):
    artifact = repository / "embeddings.jsonl"
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REPOSITORY_EMBEDDINGS_PATH", "embeddings.jsonl")

    result = tools.search_semantic_code(
        "dependency analysis",
        path_filter="missing.py",
    )

    assert result["success"] is False
    assert "path_filter" in result["error"]


def test_semantic_search_rejects_model_mismatch(repository, monkeypatch):
    artifact = repository / "embeddings.jsonl"
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REPOSITORY_EMBEDDINGS_PATH", "embeddings.jsonl")
    monkeypatch.setenv("REPOSITORY_EMBEDDING_MODEL", "configured-model")

    class FakeSearch:
        def __init__(self, path):
            self.chunks = [{"embedding_model": "different-model"}]

    import src.embeddings.semantic_search as semantic_module

    monkeypatch.setattr(semantic_module, "SemanticCodeSearch", FakeSearch)
    monkeypatch.setattr(
        tools,
        "_get_embedding_provider",
        lambda model: pytest.fail("Provider must not load on model mismatch"),
    )

    result = tools.search_semantic_code("dependency analysis")

    assert result["success"] is False
    assert "does not match" in result["error"]


def test_semantic_search_success(repository, monkeypatch):
    artifact = repository / "embeddings.jsonl"
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REPOSITORY_EMBEDDINGS_PATH", "embeddings.jsonl")
    monkeypatch.setenv("REPOSITORY_EMBEDDING_MODEL", "test-model")

    class FakeSearch:
        def __init__(self, path):
            self.chunks = [{"embedding_model": "test-model"}]

        def search(self, query_embedding, top_k, path_filter):
            assert query_embedding == [0.1, 0.2]
            assert top_k == 3
            assert path_filter == "pkg/a.py"
            return [{"path": "pkg/a.py", "score": 0.9}]

    class FakeProvider:
        def encode(self, queries):
            assert queries == ["find dependencies"]
            return [[0.1, 0.2]]

    import src.embeddings.semantic_search as semantic_module

    monkeypatch.setattr(semantic_module, "SemanticCodeSearch", FakeSearch)
    monkeypatch.setattr(
        tools, "_get_embedding_provider", lambda model: FakeProvider()
    )

    result = tools.search_semantic_code(
        "  find dependencies  ",
        max_results=3,
        path_filter="pkg/a.py",
    )

    assert result["success"] is True
    assert result["query"] == "find dependencies"
    assert result["count"] == 1
    assert result["embedding_model"] == "test-model"
