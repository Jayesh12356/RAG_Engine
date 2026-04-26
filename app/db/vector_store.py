"""Vector store abstraction.

The Qdrant backend now supports true hybrid retrieval:
    - Collections are created with **named vectors** ``dense`` and ``sparse``.
    - Ingestion upserts both vectors per point.
    - Queries use ``query_points`` with two prefetches (dense + sparse) fused
      server-side via Reciprocal Rank Fusion (RRF). This yields meaningful
      sparse-aware retrieval rather than the dense-only approximation we had
      before.

Backwards compatibility: existing collections created without named vectors
are detected by ``ensure_collection`` and left untouched. The runtime
``hybrid_search`` falls back to dense-only when the collection is unnamed
or sparse vectors are unavailable, so a stale store keeps serving traffic
until it is migrated via ``scripts/migrate_qdrant_hybrid.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings
from app.models.query import SearchResult


class VectorStore(ABC):
    @property
    def supports_sparse(self) -> bool:  # pragma: no cover - default
        return False

    @abstractmethod
    async def ensure_collection(self, name: str, dim: int) -> None: ...

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
        sparse_vector: dict[int, float] | None = None,
    ) -> None: ...

    @abstractmethod
    async def hybrid_search(
        self,
        collection: str,
        dense_vec: list[float],
        sparse_vec: dict[str, float] | None,
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def search_by_vector(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def delete(self, collection: str, chunk_ids: list[str]) -> None: ...

    @abstractmethod
    async def upsert_payload(self, collection: str, id: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def fetch_payloads(
        self, collection: str, filter: dict[str, Any], limit: int = 10000
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete_by_filter(self, collection: str, filter: dict[str, Any]) -> None: ...


# ──────────────────────────────────────────────────────────────────────────
# Qdrant
# ──────────────────────────────────────────────────────────────────────────
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


def _to_point_id(value: str) -> str:
    """Qdrant accepts UUIDs or unsigned ints. Hash arbitrary strings into UUIDs."""
    import uuid

    try:
        uuid.UUID(value)
        return value
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, value))


class QdrantVectorStore(VectorStore):
    @property
    def supports_sparse(self) -> bool:
        return True

    def __init__(self) -> None:
        import warnings

        from qdrant_client import AsyncQdrantClient

        settings = get_settings()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY.strip() or None,
            )
        self._named_collections: dict[str, bool] = {}

    # ------------------------------------------------------------------ ensure
    async def ensure_collection(self, name: str, dim: int) -> None:
        from qdrant_client.http.models import (
            Distance,
            SparseVectorParams,
            VectorParams,
        )

        collections = await self.client.get_collections()
        existing = next((c for c in collections.collections if c.name == name), None)
        if existing is None:
            await self.client.create_collection(
                collection_name=name,
                vectors_config={
                    DENSE_VECTOR_NAME: VectorParams(size=dim, distance=Distance.COSINE),
                },
                sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
            )
            self._named_collections[name] = True
            return
        # Detect named-vector layout on existing collections.
        try:
            info = await self.client.get_collection(collection_name=name)
            params = getattr(info.config.params, "vectors", None)
            self._named_collections[name] = isinstance(params, dict) and DENSE_VECTOR_NAME in params
        except Exception:
            self._named_collections[name] = False

    async def _is_named(self, name: str) -> bool:
        if name in self._named_collections:
            return self._named_collections[name]
        try:
            info = await self.client.get_collection(collection_name=name)
            params = getattr(info.config.params, "vectors", None)
            named = isinstance(params, dict) and DENSE_VECTOR_NAME in params
        except Exception:
            named = False
        self._named_collections[name] = named
        return named

    # ------------------------------------------------------------------ upsert
    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
        sparse_vector: dict[int, float] | None = None,
    ) -> None:
        from qdrant_client.http.models import PointStruct, SparseVector

        point_id = _to_point_id(id)
        named = await self._is_named(collection)
        if named:
            vec_obj: Any = {DENSE_VECTOR_NAME: vector}
            if sparse_vector:
                indices = list(sparse_vector.keys())
                values = [float(v) for v in sparse_vector.values()]
                vec_obj[SPARSE_VECTOR_NAME] = SparseVector(indices=indices, values=values)
            await self.client.upsert(
                collection_name=collection,
                points=[PointStruct(id=point_id, vector=vec_obj, payload=payload)],
            )
        else:
            await self.client.upsert(
                collection_name=collection,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )

    @staticmethod
    def _extract_qdrant_points(result: Any) -> list[Any]:
        if result is None:
            return []
        if isinstance(result, list):
            return result
        points = getattr(result, "points", None)
        if points is not None:
            return list(points)
        return []

    @staticmethod
    def _to_search_results(points: list[Any]) -> list[SearchResult]:
        out: list[SearchResult] = []
        for res in points:
            payload = getattr(res, "payload", None) or {}
            score = getattr(res, "score", 0.0)
            out.append(
                SearchResult(
                    chunk_id=payload.get("chunk_id", ""),
                    document_id=payload.get("document_id", ""),
                    text=payload.get("text", ""),
                    score=score,
                    metadata=payload,
                )
            )
        return out

    def _build_filter(self, filter: dict[str, Any] | None) -> Any:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue

        if not filter:
            return None
        conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter.items()]
        return Filter(must=conditions)

    # ------------------------------------------------------------------ hybrid query
    async def hybrid_search(
        self,
        collection: str,
        dense_vec: list[float],
        sparse_vec: dict[str, float] | None,
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        named = await self._is_named(collection)
        if not named or not sparse_vec:
            return await self.search_by_vector(collection, dense_vec, top_k, filter)
        try:
            from qdrant_client.http.models import (
                Fusion,
                FusionQuery,
                Prefetch,
                SparseVector,
            )
        except ImportError:
            return await self.search_by_vector(collection, dense_vec, top_k, filter)

        settings = get_settings()
        qdrant_filter = self._build_filter(filter)

        try:
            indices = [int(k) for k in sparse_vec.keys()]
            values = [float(v) for v in sparse_vec.values()]
        except (TypeError, ValueError):
            return await self.search_by_vector(collection, dense_vec, top_k, filter)

        prefetch_args: list[Any] = [
            Prefetch(
                query=dense_vec,
                using=DENSE_VECTOR_NAME,
                limit=settings.HYBRID_DENSE_LIMIT,
                filter=qdrant_filter,
            ),
            Prefetch(
                query=SparseVector(indices=indices, values=values),
                using=SPARSE_VECTOR_NAME,
                limit=settings.HYBRID_SPARSE_LIMIT,
                filter=qdrant_filter,
            ),
        ]

        try:
            result = await self.client.query_points(
                collection_name=collection,
                prefetch=prefetch_args,
                query=FusionQuery(fusion=Fusion.RRF),
                limit=top_k,
                with_payload=True,
                query_filter=qdrant_filter,
            )
        except Exception:
            return await self.search_by_vector(collection, dense_vec, top_k, filter)
        return self._to_search_results(self._extract_qdrant_points(result))

    async def _query_dense_points(
        self,
        *,
        collection: str,
        vector: list[float],
        top_k: int,
        qdrant_filter: Any,
    ) -> list[Any]:
        named = await self._is_named(collection)
        query_points = getattr(self.client, "query_points", None)
        if callable(query_points):
            try:
                if named:
                    result = await query_points(
                        collection_name=collection,
                        query=vector,
                        using=DENSE_VECTOR_NAME,
                        limit=top_k,
                        query_filter=qdrant_filter,
                    )
                else:
                    result = await query_points(
                        collection_name=collection,
                        query=vector,
                        limit=top_k,
                        query_filter=qdrant_filter,
                    )
                points = self._extract_qdrant_points(result)
                if points:
                    return points
            except Exception:
                pass
        search = getattr(self.client, "search", None)
        if callable(search):
            return await search(
                collection_name=collection,
                query_vector=(DENSE_VECTOR_NAME, vector) if named else vector,
                limit=top_k,
                query_filter=qdrant_filter,
            )
        raise AttributeError("Qdrant client does not support query_points or search")

    async def search_by_vector(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        qdrant_filter = self._build_filter(filter)
        results = await self._query_dense_points(
            collection=collection,
            vector=vector,
            top_k=top_k,
            qdrant_filter=qdrant_filter,
        )
        return self._to_search_results(results)

    # ------------------------------------------------------------------ misc
    async def delete(self, collection: str, chunk_ids: list[str]) -> None:
        from qdrant_client.http.models import PointIdsList

        point_ids = [_to_point_id(cid) for cid in chunk_ids]
        if point_ids:
            await self.client.delete(
                collection_name=collection,
                points_selector=PointIdsList(points=point_ids),
            )

    async def upsert_payload(self, collection: str, id: str, payload: dict[str, Any]) -> None:
        # Empty placeholder vector keeps signatures aligned for payload-only upsert paths.
        await self.upsert(collection=collection, id=id, vector=[0.0], payload=payload)

    async def fetch_payloads(
        self, collection: str, filter: dict[str, Any], limit: int = 10000
    ) -> list[dict[str, Any]]:
        qdrant_filter = self._build_filter(filter)
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
            if isinstance(response, tuple):
                batch, next_offset = response
            else:
                batch = getattr(response, "points", [])
                next_offset = getattr(response, "next_page_offset", None)
            points.extend(batch or [])
            if not next_offset:
                break
            offset = next_offset
        return [(getattr(p, "payload", None) or {}) for p in points[:limit]]

    async def delete_by_filter(self, collection: str, filter: dict[str, Any]) -> None:
        qdrant_filter = self._build_filter(filter)
        delete_method = getattr(self.client, "delete", None)
        if not callable(delete_method):
            return
        try:
            from qdrant_client.http.models import FilterSelector

            await delete_method(
                collection_name=collection,
                points_selector=FilterSelector(filter=qdrant_filter),
            )
        except Exception:
            await delete_method(
                collection_name=collection,
                points_selector=qdrant_filter,
            )


# ──────────────────────────────────────────────────────────────────────────
# Milvus (dense-only)
# ──────────────────────────────────────────────────────────────────────────
class MilvusVectorStore(VectorStore):
    @property
    def supports_sparse(self) -> bool:
        return False

    def __init__(self) -> None:
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
            auto_id=False,
        )

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
        sparse_vector: dict[int, float] | None = None,  # ignored
    ) -> None:
        data = payload.copy()
        data["id"] = id
        data["vector"] = vector
        await self.client.insert(collection_name=collection, data=[data])

    async def hybrid_search(
        self,
        collection: str,
        dense_vec: list[float],
        sparse_vec: dict[str, float] | None,
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        return await self.search_by_vector(collection, dense_vec, top_k, filter)

    async def search_by_vector(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        filter_expr = ""
        if filter:
            filter_expr = " and ".join(f"{k} == '{v}'" for k, v in filter.items())

        results = await self.client.search(
            collection_name=collection,
            data=[vector],
            limit=top_k,
            filter=filter_expr if filter_expr else None,
            output_fields=["*"],
        )
        out: list[SearchResult] = []
        if not results:
            return out
        for hit in results[0]:
            payload = hit.get("entity", {})
            out.append(
                SearchResult(
                    chunk_id=payload.get("chunk_id", ""),
                    document_id=payload.get("document_id", ""),
                    text=payload.get("text", ""),
                    score=hit.get("distance", 0.0),
                    metadata=payload,
                )
            )
        return out

    async def delete(self, collection: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        ids_str = ", ".join([f"'{cid}'" for cid in chunk_ids])
        expr = f"id in [{ids_str}]"
        await self.client.delete(collection_name=collection, filter=expr)

    async def upsert_payload(self, collection: str, id: str, payload: dict[str, Any]) -> None:
        await self.client.delete(collection_name=collection, filter=f"id == '{id}'")
        data = payload.copy()
        data["id"] = id
        data["vector"] = [0.0]
        await self.client.insert(collection_name=collection, data=[data])

    async def fetch_payloads(
        self, collection: str, filter: dict[str, Any], limit: int = 10000
    ) -> list[dict[str, Any]]:
        filter_expr = " and ".join(f"{k} == '{v}'" for k, v in filter.items())
        rows = await self.client.query(
            collection_name=collection,
            filter=filter_expr if filter_expr else None,
            output_fields=["*"],
            limit=limit,
        )
        return rows or []

    async def delete_by_filter(self, collection: str, filter: dict[str, Any]) -> None:
        filter_expr = " and ".join(f"{k} == '{v}'" for k, v in filter.items())
        await self.client.delete(
            collection_name=collection,
            filter=filter_expr if filter_expr else None,
        )


def get_vector_store() -> VectorStore:
    settings = get_settings()
    if settings.VECTOR_DB == "milvus":
        return MilvusVectorStore()
    return QdrantVectorStore()
