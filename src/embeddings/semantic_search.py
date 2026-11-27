
"""Read-only semantic retrieval over precomputed repository embeddings."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class SemanticCodeSearch:
    """Retrieve code chunks by cosine similarity."""

    def __init__(self, artifact_path: str | Path):
        self.artifact_path = Path(artifact_path)
        self.chunks = self._load_artifact()
        self._validate_chunks()

    def _load_artifact(self) -> list[dict[str, Any]]:
        if not self.artifact_path.exists():
            raise FileNotFoundError(
                f"Embedding artifact not found: {self.artifact_path}"
            )

        if self.artifact_path.suffix.lower() == ".json":
            data = json.loads(self.artifact_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("chunks", [])
            if not isinstance(data, list):
                raise ValueError("JSON artifact must contain a list of chunks.")
            return data

        if self.artifact_path.suffix.lower() == ".jsonl":
            chunks = []
            with self.artifact_path.open(encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    if line.strip():
                        try:
                            chunks.append(json.loads(line))
                        except json.JSONDecodeError as exc:
                            raise ValueError(
                                f"Invalid JSON on line {line_number}"
                            ) from exc
            return chunks

        raise ValueError("Supported artifact formats: .json and .jsonl")

    def _validate_chunks(self) -> None:
        if not self.chunks:
            raise ValueError("Embedding artifact contains no code chunks.")

        expected_dimension = None

        for index, chunk in enumerate(self.chunks):
            for field in ("path", "start_line", "end_line", "embedding"):
                if field not in chunk:
                    raise ValueError(
                        f"Chunk {index} is missing required field: {field}"
                    )

            embedding = chunk["embedding"]

            if not isinstance(embedding, list) or not embedding:
                raise ValueError(f"Chunk {index} has an invalid embedding.")

            if any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in embedding
            ):
                raise ValueError(f"Chunk {index} has invalid vector values.")

            if expected_dimension is None:
                expected_dimension = len(embedding)
            elif len(embedding) != expected_dimension:
                raise ValueError("Embedding dimensions are inconsistent.")

            if not isinstance(chunk["path"], str):
                raise ValueError(f"Chunk {index} has an invalid path.")

            if (
                not isinstance(chunk["start_line"], int)
                or not isinstance(chunk["end_line"], int)
                or chunk["start_line"] < 1
                or chunk["end_line"] < chunk["start_line"]
            ):
                raise ValueError(f"Chunk {index} has invalid line numbers.")

    @staticmethod
    def cosine_similarity(
        vector_a: list[float],
        vector_b: list[float],
    ) -> float:
        if len(vector_a) != len(vector_b):
            raise ValueError("Query and stored embeddings have different dimensions.")

        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a))
        norm_b = math.sqrt(sum(b * b for b in vector_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        path_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the most semantically similar code chunks."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            for value in query_embedding
        ):
            raise ValueError("Query embedding contains invalid values.")

        expected_dimension = len(self.chunks[0]["embedding"])
        if len(query_embedding) != expected_dimension:
            raise ValueError(
                f"Expected query dimension {expected_dimension}, "
                f"received {len(query_embedding)}."
            )

        results = []

        for chunk in self.chunks:
            if path_filter and path_filter not in chunk["path"]:
                continue

            score = self.cosine_similarity(
                query_embedding,
                chunk["embedding"],
            )

            results.append({
                "path": chunk["path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "score": round(score, 6),
                "content": chunk.get("content", ""),
            })

        return sorted(
            results,
            key=lambda item: (-item["score"], item["path"], item["start_line"]),
        )[:top_k]


def search_repository_code(
    artifact_path: str | Path,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Convenience interface for semantic repository search."""
    searcher = SemanticCodeSearch(artifact_path)
    return searcher.search(query_embedding, top_k=top_k)
