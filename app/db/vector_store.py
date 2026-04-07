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

    @abstractmethod
    async def upsert_payload(self, collection: str, id: str, payload: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def fetch_payloads(self, collection: str, filter: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def delete_by_filter(self, collection: str, filter: Dict[str, Any]) -> None:
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

    @staticmethod
    def _extract_qdrant_points(result: Any) -> list[Any]:
        """Normalize Qdrant response shapes across client versions."""
        if result is None:
            return []
        if isinstance(result, list):
            return result
        points = getattr(result, "points", None)
        if points is not None:
            return list(points)
        return []

    async def _query_dense_points(
        self,
        *,
        collection: str,
        vector: list[float],
        top_k: int,
        qdrant_filter: Any,
    ) -> list[Any]:
        """
        Query Qdrant across client API versions.
        Newer clients expose query_points, while older clients expose search.
        """
        query_points = getattr(self.client, "query_points", None)
        if callable(query_points):
            result = await query_points(
                collection_name=collection,
                query=vector,
                limit=top_k,
                query_filter=qdrant_filter,
            )
            points = self._extract_qdrant_points(result)
            if points:
                return points
        search = getattr(self.client, "search", None)
        if callable(search):
            return await search(
                collection_name=collection,
                query_vector=vector,
                limit=top_k,
                query_filter=qdrant_filter,
            )
        raise AttributeError("Qdrant client does not support query_points or search")

    async def search_by_vector(self, collection: str, vector: list[float], top_k: int, filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        qdrant_filter = None
        if filter:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await self._query_dense_points(
            collection=collection,
            vector=vector,
            top_k=top_k,
            qdrant_filter=qdrant_filter,
        )
        out = []
        for res in results:
            payload = getattr(res, "payload", None) or {}
            score = getattr(res, "score", 0.0)
            out.append(SearchResult(
                chunk_id=payload.get("chunk_id", ""),
                document_id=payload.get("document_id", ""),
                text=payload.get("text", ""),
                score=score,
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

    async def upsert_payload(self, collection: str, id: str, payload: Dict[str, Any]) -> None:
        await self.upsert(collection=collection, id=id, vector=[0.0], payload=payload)

    async def fetch_payloads(self, collection: str, filter: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter.items()]
        qdrant_filter = Filter(must=conditions)

        scroll_method = getattr(self.client, "scroll", None)
        if not callable(scroll_method):
            return []

        points: list[Any] = []
        offset = None
        while len(points) < limit:
            response = await scroll_method(
                collection_name=collection,
                scroll_filter=qdrant_filter,
                limit=min(256, max(limit - len(points), 1)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            batch, next_offset = (response if isinstance(response, tuple) else (getattr(response, "points", []), getattr(response, "next_page_offset", None)))
            points.extend(batch or [])
            if not next_offset:
                break
            offset = next_offset
        return [(getattr(p, "payload", None) or {}) for p in points[:limit]]

    async def delete_by_filter(self, collection: str, filter: Dict[str, Any]) -> None:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter.items()]
        qdrant_filter = Filter(must=conditions)
        delete_method = getattr(self.client, "delete", None)
        if not callable(delete_method):
            return
        try:
            from qdrant_client.http.models import FilterSelector
            await delete_method(collection_name=collection, points_selector=FilterSelector(filter=qdrant_filter))
        except Exception:
            await delete_method(collection_name=collection, points_selector=qdrant_filter)


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

    async def upsert_payload(self, collection: str, id: str, payload: Dict[str, Any]) -> None:
        # Ensure idempotency by deleting old id before insert.
        await self.client.delete(collection_name=collection, filter=f"id == '{id}'")
        data = payload.copy()
        data["id"] = id
        data["vector"] = [0.0]
        await self.client.insert(collection_name=collection, data=[data])

    async def fetch_payloads(self, collection: str, filter: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        filter_expr = " and ".join(f"{k} == '{v}'" for k, v in filter.items())
        rows = await self.client.query(
            collection_name=collection,
            filter=filter_expr if filter_expr else None,
            output_fields=["*"],
            limit=limit,
        )
        return rows or []

    async def delete_by_filter(self, collection: str, filter: Dict[str, Any]) -> None:
        filter_expr = " and ".join(f"{k} == '{v}'" for k, v in filter.items())
        await self.client.delete(collection_name=collection, filter=filter_expr if filter_expr else None)


def get_vector_store() -> VectorStore:
    settings = get_settings()
    if settings.VECTOR_DB == "milvus":
        return MilvusVectorStore()
    return QdrantVectorStore()
