"""Text embedding service using SentenceTransformers.

Heavy imports (numpy, sentence_transformers) are deferred to avoid crashing
the application at import time if the packages are unavailable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    @property
    def embedding_dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        import numpy as np

        emb = self._model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(emb)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        import numpy as np

        emb = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(emb)

    def similarity(self, text_a: str, text_b: str) -> float:
        import numpy as np

        emb_a = self.embed(text_a)
        emb_b = self.embed(text_b)
        return float(np.dot(emb_a, emb_b))
