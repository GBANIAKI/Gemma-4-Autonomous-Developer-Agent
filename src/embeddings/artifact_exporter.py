
"""Generate and export semantic embeddings for repository code chunks."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Protocol, Sequence


class EmbeddingProvider(Protocol):
    """Interface implemented by embedding model providers."""

    model_name: str

    def encode(self, texts: Sequence[str]) -> Sequence[Any]:
        """Convert text inputs into embedding vectors."""
        ...


class SentenceTransformerProvider:
    """Embedding provider backed by Sentence Transformers.

    Importing sentence-transformers is deferred until initialization,
    so the exporter can be imported without that dependency installed.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str | None = None,
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "Install sentence-transformers to use this provider: "
                "pip install sentence-transformers"
            ) from exc

        self.model_name = model_name
        self.model = SentenceTransformer(
            model_name,
            device=device,
        )

    def encode(self, texts: Sequence[str]) -> Sequence[Any]:
        return self.model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )


def _embedding_text(chunk: dict[str, Any]) -> str:
    """Construct the text presented to the embedding model."""
    path = chunk["path"]
    symbol = chunk.get("symbol", "")
    content = chunk.get("content", "")

    return (
        f"Repository file: {path}\n"
        f"Symbol: {symbol}\n"
        f"Code:\n{content}"
    )


def _validate_vector(vector: Any, index: int) -> list[float]:
    """Convert and validate a provider output vector."""
    try:
        values = [float(value) for value in vector]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Embedding at index {index} is not a valid numeric vector."
        ) from exc

    if not values:
        raise ValueError(f"Embedding at index {index} is empty.")

    if any(not math.isfinite(value) for value in values):
        raise ValueError(
            f"Embedding at index {index} contains non-finite values."
        )

    return values


def export_embedding_artifact(
    chunks: Sequence[dict[str, Any]],
    provider: EmbeddingProvider,
    output_path: str | Path,
    batch_size: int = 32,
) -> dict[str, Any]:
    """Embed code chunks and export a SemanticCodeSearch-compatible JSONL file.

    The provider is deliberately injected. Embeddings can therefore be
    generated in Kaggle, Colab, or another environment without changing
    the artifact format or semantic retrieval implementation.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    if not chunks:
        raise ValueError("No code chunks were provided.")

    required_fields = ("path", "start_line", "end_line", "content")

    for index, chunk in enumerate(chunks):
        missing = [
            field for field in required_fields
            if field not in chunk
        ]
        if missing:
            raise ValueError(
                f"Chunk {index} is missing fields: {missing}"
            )

        if not isinstance(chunk["content"], str) or not chunk["content"].strip():
            raise ValueError(f"Chunk {index} has empty code content.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    texts = [_embedding_text(chunk) for chunk in chunks]
    temporary_path = destination.with_name(destination.name + ".tmp")

    vector_dimension = None
    exported_count = 0

    try:
        with temporary_path.open("w", encoding="utf-8") as output:
            for start in range(0, len(chunks), batch_size):
                batch_chunks = chunks[start:start + batch_size]
                batch_texts = texts[start:start + batch_size]

                vectors = provider.encode(batch_texts)

                if len(vectors) != len(batch_chunks):
                    raise ValueError(
                        "Embedding provider returned an incorrect "
                        "number of vectors."
                    )

                for chunk, raw_vector in zip(batch_chunks, vectors):
                    vector = _validate_vector(
                        raw_vector,
                        exported_count,
                    )

                    if vector_dimension is None:
                        vector_dimension = len(vector)
                    elif len(vector) != vector_dimension:
                        raise ValueError(
                            "Embedding provider returned inconsistent "
                            "vector dimensions."
                        )

                    record = {
                        "path": chunk["path"],
                        "start_line": chunk["start_line"],
                        "end_line": chunk["end_line"],
                        "symbol": chunk.get("symbol", ""),
                        "content": chunk["content"],
                        "embedding": vector,
                        "embedding_model": provider.model_name,
                    }

                    output.write(
                        json.dumps(record, ensure_ascii=False) + "\n"
                    )
                    exported_count += 1

        os.replace(temporary_path, destination)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "output_path": str(destination),
        "chunks_exported": exported_count,
        "embedding_dimension": vector_dimension,
        "embedding_model": provider.model_name,
        "format": "jsonl",
    }
