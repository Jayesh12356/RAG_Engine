from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from app.models.query import SearchResult
from app.config import get_settings

class VectorStore(ABC):
    @property
    def supports_sparse(self) -> bool:
        return False

    @abstractmethod
    async def ensure_collection(self, name: str, dim: int) -> None:
        pass

    @abstractmethod
    async def upsert(self, collection: str, id: str, vector: list[float], payload: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def hybrid_search(self, collection: str, dense_vec: list[float], sparse_vec: Optional[Dict[str, float]], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        pass

    @abstractmethod
    async def search_by_vector(self, collection: str, vector: list[float], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        pass

    @abstractmethod
    async def delete(self, collection: str, chunk_ids: List[str]) -> None:
        pass

class QdrantVectorStore(VectorStore):
    @property
    def supports_sparse(self) -> bool:
        return False

    def __init__(self):
        from qdrant_client import AsyncQdrantClient
        import warnings
        settings = get_settings()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY.strip() or None
            )

    async def ensure_collection(self, name: str, dim: int) -> None:
        from qdrant_client.http.models import VectorParams, Distance
        collections = await self.client.get_collections()
        exists = any(c.name == name for c in collections.collections)
        if not exists:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )

    async def upsert(self, collection: str, id: str, vector: list[float], payload: Dict[str, Any]) -> None:
        from qdrant_client.http.models import PointStruct
        # Qdrant requires string id to be UUID format OR integer.
        import uuid
        try:
            uuid.UUID(id)
            point_id = id
        except ValueError:
            # Dummy hash for Qdrant compatibility if not UUID
            point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, id))
        
        await self.client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)]
        )

    async def hybrid_search(self, collection: str, dense_vec: list[float], sparse_vec: Optional[Dict[str, float]], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        return await self.search_by_vector(collection, dense_vec, top_k, filter)

    async def search_by_vector(self, collection: str, vector: list[float], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        qdrant_filter = None
        if filter:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter.items()
            ]
            qdrant_filter = Filter(must=conditions)
            
        results = await self.client.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
            query_filter=qdrant_filter
        )
        out = []
        for res in results:
            payload = res.payload or {}
            out.append(SearchResult(
                chunk_id=payload.get("chunk_id", ""),
                document_id=payload.get("document_id", ""),
                text=payload.get("text", ""),
                score=res.score,
                metadata=payload
            ))
        return out

    async def delete(self, collection: str, chunk_ids: List[str]) -> None:
        import uuid
        from qdrant_client.http.models import PointIdsList
        
        point_ids = []
        for cid in chunk_ids:
            try:
                uuid.UUID(cid)
                point_ids.append(cid)
            except ValueError:
                point_ids.append(str(uuid.uuid5(uuid.NAMESPACE_OID, cid)))
                
        if point_ids:
            await self.client.delete(collection_name=collection, points_selector=PointIdsList(points=point_ids))


class MilvusVectorStore(VectorStore):
    @property
    def supports_sparse(self) -> bool:
        return False

    def __init__(self):
        from pymilvus import AsyncMilvusClient
        settings = get_settings()
        self.client = AsyncMilvusClient(uri=settings.MILVUS_URI)

    async def ensure_collection(self, name: str, dim: int) -> None:
        if await self.client.has_collection(collection_name=name):
            return
        await self.client.create_collection(
            collection_name=name,
            dimension=dim,
            id_type="string",
            max_length=65535,
            auto_id=False
        )

    async def upsert(self, collection: str, id: str, vector: list[float], payload: Dict[str, Any]) -> None:
        data = payload.copy()
        data["id"] = id
        data["vector"] = vector
        await self.client.insert(collection_name=collection, data=[data])

    async def hybrid_search(self, collection: str, dense_vec: list[float], sparse_vec: Optional[Dict[str, float]], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        return await self.search_by_vector(collection, dense_vec, top_k, filter)

    async def search_by_vector(self, collection: str, vector: list[float], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        filter_expr = ""
        if filter:
            filter_expr = " and ".join(f"{k} == '{v}'" for k, v in filter.items())
            
        results = await self.client.search(
            collection_name=collection,
            data=[vector],
            limit=top_k,
            filter=filter_expr if filter_expr else None,
            output_fields=["*"]
        )
        out = []
        if not results: return out
        for hit in results[0]:
            payload = hit.get("entity", {})
            out.append(SearchResult(
                chunk_id=payload.get("chunk_id", ""),
                document_id=payload.get("document_id", ""),
                text=payload.get("text", ""),
                score=hit.get("distance", 0.0),
                metadata=payload
            ))
        return out

    async def delete(self, collection: str, chunk_ids: List[str]) -> None:
        if not chunk_ids:
            return
            
        ids_str = ", ".join([f"'{cid}'" for cid in chunk_ids])
        expr = f"id in [{ids_str}]"
        await self.client.delete(collection_name=collection, filter=expr)


def get_vector_store() -> VectorStore:
    settings = get_settings()
    if settings.VECTOR_DB == "milvus":
        return MilvusVectorStore()
    return QdrantVectorStore()
