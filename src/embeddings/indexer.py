
"""End-to-end repository indexing pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.embeddings.artifact_exporter import (
    EmbeddingProvider,
    export_embedding_artifact,
)
from src.embeddings.code_chunker import PythonCodeChunker


class RepositoryIndexer:
    """Extract repository code and export semantic embedding artifacts."""

    def __init__(
        self,
        repository_root: str | Path,
        provider: EmbeddingProvider,
        max_chunk_lines: int = 120,
        batch_size: int = 32,
    ):
        self.repository_root = Path(repository_root).resolve()
        self.provider = provider
        self.max_chunk_lines = max_chunk_lines
        self.batch_size = batch_size

        if not self.repository_root.is_dir():
            raise NotADirectoryError(self.repository_root)

        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

    def extract_chunks(self) -> list[dict[str, Any]]:
        """Extract code chunks from the repository."""
        chunker = PythonCodeChunker(
            self.repository_root,
            max_chunk_lines=self.max_chunk_lines,
        )
        return chunker.chunk_repository()

    def build_index(
        self,
        output_path: str | Path,
    ) -> dict[str, Any]:
        """Generate embeddings and write the JSONL artifact."""
        chunks = self.extract_chunks()

        if not chunks:
            raise ValueError("No code chunks were extracted.")

        report = export_embedding_artifact(
            chunks=chunks,
            provider=self.provider,
            output_path=output_path,
            batch_size=self.batch_size,
        )

        report["repository_root"] = str(self.repository_root)
        report["source_files"] = len({
            chunk["path"] for chunk in chunks
        })

        return report


def build_repository_index(
    repository_root: str | Path,
    provider: EmbeddingProvider,
    output_path: str | Path,
    max_chunk_lines: int = 120,
    batch_size: int = 32,
) -> dict[str, Any]:
    """Convenience interface for repository indexing."""
    indexer = RepositoryIndexer(
        repository_root=repository_root,
        provider=provider,
        max_chunk_lines=max_chunk_lines,
        batch_size=batch_size,
    )

    return indexer.build_index(output_path)
