"""In-memory FAISS vector store for similarity search."""

import faiss
import numpy as np

from sentinel.core.config import get_settings


class VectorStore:
    def __init__(self, dimension: int):
        self._dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._metadata: dict[int, dict] = {}
        self._next_position = 0

    def add(self, embedding: np.ndarray, metadata: dict) -> int:
        x = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        position_id = self._next_position
        self._next_position += 1
        self._index.add(x)
        self._metadata[position_id] = metadata
        return position_id

    def search(
        self, embedding: np.ndarray, threshold: float | None = None
    ) -> tuple[dict, float] | None:
        if threshold is None:
            threshold = get_settings().semantic_cache_threshold
        if self._index.ntotal == 0:
            return None
        x = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        scores, indices = self._index.search(x, 1)
        best_idx = int(indices[0][0])
        best_score = float(scores[0][0])
        if best_idx == -1 or best_score < threshold:
            return None
        if best_idx not in self._metadata:
            return None
        return (self._metadata[best_idx], best_score)

    def remove(self, position_id: int) -> bool:
        if position_id not in self._metadata:
            return False
        del self._metadata[position_id]
        return True

    @property
    def size(self) -> int:
        return len(self._metadata)

    @property
    def dimension(self) -> int:
        return self._dimension
