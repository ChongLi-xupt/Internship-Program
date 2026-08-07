"""
Vector store abstraction layer.
Supports Qdrant (production) and ChromaDB (development).
All vector operations go through this interface — never call vendor SDKs directly in business logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config import settings


class VectorStoreBase(ABC):
    """Abstract base class for vector store implementations."""

    @abstractmethod
    async def create_collection(self, collection_name: str, dimension: int) -> None:
        """Create a new collection with given embedding dimension."""
        ...

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection and all its data."""
        ...

    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> None:
        """Insert or update vectors."""
        ...

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_text: str | None = None,
        query_vector: List[float] | None = None,
        tenant_id: str = "",
        filter_tags: List[str] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search by text or vector similarity. Returns list of chunk refs."""
        ...

    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        ids: List[str] | None = None,
        filter_dict: Dict[str, Any] | None = None,
    ) -> None:
        """Delete vectors by ID or filter."""
        ...

    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get collection metadata (count, etc.)."""
        ...


class QdrantStore(VectorStoreBase):
    """Qdrant vector store implementation."""

    def __init__(self):
        from qdrant_client import AsyncQdrantClient

        self._client: AsyncQdrantClient | None = None

    def _get_client(self) -> "AsyncQdrantClient":
        if self._client is None:
            from qdrant_client import AsyncQdrantClient

            kwargs = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                kwargs["api_key"] = settings.qdrant_api_key
            self._client = AsyncQdrantClient(**kwargs)
        return self._client

    async def create_collection(self, collection_name: str, dimension: int) -> None:
        client = self._get_client()
        from qdrant_client.models import Distance, VectorParams

        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )

    async def delete_collection(self, collection_name: str) -> None:
        client = self._get_client()
        await client.delete_collection(collection_name=collection_name)

    async def upsert(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> None:
        client = self._get_client()
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(id=idx, vector=vec, payload=payload)
            for idx, (vec, payload) in enumerate(zip(vectors, payloads))
        ]
        await client.upsert(collection_name=collection_name, points=points)

    async def search(
        self,
        collection_name: str,
        query_text: str | None = None,
        query_vector: List[float] | None = None,
        tenant_id: str = "",
        filter_tags: List[str] | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        # Get query vector if text provided
        if query_vector is None and query_text:
            from app.llm.base import get_embedding_provider
            embedder = get_embedding_provider()
            query_vector = await embedder.embed_query(query_text)

        if not query_vector:
            return []

        client = self._get_client()

        # Build filter
        qdrant_filter = None
        if tenant_id or filter_tags:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            conditions = []
            if tenant_id:
                conditions.append(FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)))
            if filter_tags:
                for tag in filter_tags:
                    conditions.append(
                        FieldCondition(key="permissions", match=MatchValue(value=tag))
                    )
            qdrant_filter = Filter(must=conditions)

        results = await client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        return [
            {
                "content": hit.payload.get("content", ""),
                "document_id": hit.payload.get("document_id", ""),
                "kb_id": hit.payload.get("kb_id", ""),
                "chunk_index": hit.payload.get("chunk_index", 0),
                "score": hit.score,
                "metadata": hit.payload.get("metadata", {}),
            }
            for hit in results
        ]

    async def delete(
        self,
        collection_name: str,
        ids: List[str] | None = None,
        filter_dict: Dict[str, Any] | None = None,
    ) -> None:
        client = self._get_client()
        if ids:
            from qdrant_client.models import PointIdsList

            await client.delete(collection_name=collection_name, points_selector=PointIdsList(points=[int(i) for i in ids]))
        elif filter_dict:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter_dict.items()]
            await client.delete(
                collection_name=collection_name,
                points_selector=Filter(must=conditions),
            )

    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        client = self._get_client()
        info = await client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.points_count,
            "status": str(info.status),
        }


# Store instance cache
_store_instance: VectorStoreBase | None = None


def get_vector_store() -> VectorStoreBase:
    global _store_instance
    if _store_instance is None:
        provider = settings.vector_store.lower()
        if provider == "qdrant":
            _store_instance = QdrantStore()
        else:
            raise ValueError(f"Unsupported vector store: {provider}")
    return _store_instance
