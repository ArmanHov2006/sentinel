"""Text embedding service using SentenceTransformers."""

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    @property
    def embedding_dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        emb = self._model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return emb

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        emb = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return emb

    def similarity(self, text_a: str, text_b: str) -> float:
        emb_a = self.embed(text_a)
        emb_b = self.embed(text_b)
        return float(np.dot(emb_a, emb_b))
