import json
import pytest

from src.embeddings.artifact_exporter import export_embedding_artifact
from src.embeddings.code_chunker import PythonCodeChunker
from src.embeddings.semantic_search import SemanticCodeSearch


class FakeProvider:
    model_name = "test-model"

    def encode(self, texts):
        return [[float(len(text)), 1.0, 0.5] for text in texts]


def sample_chunks():
    return [
        {
            "path": "pkg/a.py",
            "start_line": 1,
            "end_line": 2,
            "symbol": "calculate",
            "content": "def calculate(): return 1",
        },
        {
            "path": "pkg/b.py",
            "start_line": 1,
            "end_line": 2,
            "symbol": "process",
            "content": "def process(): return 2",
        },
    ]


def test_chunker_discovers_files_under_ancestor_named_build(tmp_path):
    root = tmp_path / "build" / "repository"
    root.mkdir(parents=True)
    (root / "main.py").write_text("VALUE = 1\n", encoding="utf-8")

    files = PythonCodeChunker(root).discover_files()

    assert [path.name for path in files] == ["main.py"]


def test_chunker_excludes_nested_generated_directories(tmp_path):
    (tmp_path / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    generated = tmp_path / "build"
    generated.mkdir()
    (generated / "generated.py").write_text("VALUE = 2\n", encoding="utf-8")

    files = PythonCodeChunker(tmp_path).discover_files()

    assert [path.name for path in files] == ["main.py"]


def test_chunk_file_rejects_outside_repository_path(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="inside the repository"):
        PythonCodeChunker(root).chunk_file(outside)


def test_chunk_file_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        PythonCodeChunker(tmp_path).chunk_file(tmp_path / "missing.py")


def test_exporter_creates_search_compatible_jsonl(tmp_path):
    output = tmp_path / "embeddings.jsonl"

    report = export_embedding_artifact(
        sample_chunks(),
        FakeProvider(),
        output,
        batch_size=1,
    )

    records = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]

    assert report["chunks_exported"] == 2
    assert report["embedding_dimension"] == 3
    assert len(records) == 2
    assert records[0]["embedding_model"] == "test-model"


def test_failed_export_preserves_existing_artifact(tmp_path):
    output = tmp_path / "embeddings.jsonl"
    output.write_text("existing data\n", encoding="utf-8")

    class FailingProvider:
        model_name = "failing"

        def encode(self, texts):
            raise RuntimeError("provider failed")

    with pytest.raises(RuntimeError, match="provider failed"):
        export_embedding_artifact(
            sample_chunks(),
            FailingProvider(),
            output,
        )

    assert output.read_text(encoding="utf-8") == "existing data\n"
    assert not output.with_name(output.name + ".tmp").exists()


def test_semantic_search_ranks_and_filters_results(tmp_path):
    output = tmp_path / "embeddings.jsonl"
    export_embedding_artifact(sample_chunks(), FakeProvider(), output)

    search = SemanticCodeSearch(output)
    results = search.search([1.0, 0.0, 0.0], path_filter="pkg/a.py")

    assert len(results) == 1
    assert results[0]["path"] == "pkg/a.py"


def test_semantic_search_rejects_wrong_query_dimension(tmp_path):
    output = tmp_path / "embeddings.jsonl"
    export_embedding_artifact(sample_chunks(), FakeProvider(), output)

    search = SemanticCodeSearch(output)

    with pytest.raises(ValueError, match="dimension"):
        search.search([1.0, 0.0])


def test_semantic_search_rejects_empty_artifact(tmp_path):
    output = tmp_path / "empty.jsonl"
    output.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="no code chunks"):
        SemanticCodeSearch(output)
