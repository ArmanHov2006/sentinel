"""Semantic cache using vector similarity for near-duplicate queries."""

from datetime import datetime

from sentinel.services.embedding import EmbeddingService
from sentinel.services.vector_store import VectorStore


class SemanticCacheService:
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.dimension = embedding_service.embedding_dimension
        self.vector_store = VectorStore(self.dimension)

    def lookup(self, query: str) -> str | None:
        embedding = self.embedding_service.embed(query)
        result = self.vector_store.search(embedding)
        if result is None:
            return None
        return result[0]["response"]

    def store(self, query: str, response: str, model: str) -> None:
        embedding = self.embedding_service.embed(query)
        metadata = {
            "response": response,
            "model": model,
            "created_at": datetime.now(),
        }
        self.vector_store.add(embedding, metadata)
