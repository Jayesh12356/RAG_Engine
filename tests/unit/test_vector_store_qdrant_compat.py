import pytest

from app.db.vector_store import QdrantVectorStore
from app.config import Settings


class _Point:
    def __init__(self, payload: dict, score: float):
        self.payload = payload
        self.score = score


class _QueryPointsResponse:
    def __init__(self, points):
        self.points = points


@pytest.mark.asyncio
async def test_qdrant_search_by_vector_query_points_only(monkeypatch):
    class DummyClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def query_points(self, **kwargs):
            return _QueryPointsResponse(
                points=[
                    _Point(
                        payload={
                            "chunk_id": "c1",
                            "document_id": "d1",
                            "text": "printer install steps",
                        },
                        score=0.91,
                    )
                ]
            )

    monkeypatch.setattr("qdrant_client.AsyncQdrantClient", DummyClient)
    settings = Settings(QDRANT_URL="https://qdrant.example")
    monkeypatch.setattr("app.db.vector_store.get_settings", lambda: settings)

    store = QdrantVectorStore()
    out = await store.search_by_vector("helpdesk_chunks", [0.1, 0.2, 0.3], 3)

    assert len(out) == 1
    assert out[0].chunk_id == "c1"
    assert out[0].document_id == "d1"
    assert out[0].text == "printer install steps"
    assert out[0].score == 0.91


@pytest.mark.asyncio
async def test_qdrant_search_by_vector_legacy_search_only(monkeypatch):
    class DummyClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def search(self, **kwargs):
            return [
                _Point(
                    payload={
                        "chunk_id": "c2",
                        "document_id": "d2",
                        "text": "vpn prerequisites",
                    },
                    score=0.87,
                )
            ]

    monkeypatch.setattr("qdrant_client.AsyncQdrantClient", DummyClient)
    settings = Settings(QDRANT_URL="https://qdrant.example")
    monkeypatch.setattr("app.db.vector_store.get_settings", lambda: settings)

    store = QdrantVectorStore()
    out = await store.search_by_vector("helpdesk_chunks", [0.2, 0.3, 0.4], 5)

    assert len(out) == 1
    assert out[0].chunk_id == "c2"
    assert out[0].document_id == "d2"
    assert out[0].text == "vpn prerequisites"
    assert out[0].score == 0.87
