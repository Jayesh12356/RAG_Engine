import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import patch

@pytest.mark.asyncio
async def test_post_chat_new_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={"question": "how do I reset my VPN password?"},
            headers={"X-Demo-Mode": "true"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] is not None
        assert data["refused"] is False

@pytest.mark.asyncio
async def test_post_chat_continues_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/chat",
            json={"question": "how do I reset VPN?"},
            headers={"X-Demo-Mode": "true"}
        )
        session_id = first.json()["session_id"]
        
        second = await client.post(
            "/chat",
            json={"session_id": session_id, "question": "what about SSL?"},
            headers={"X-Demo-Mode": "true"}
        )
        data = second.json()
        assert data["session_id"] == session_id
        assert len(data["history"]) == 4

@pytest.mark.asyncio
async def test_get_history():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            "/chat",
            json={"question": "how do I reset VPN?"},
            headers={"X-Demo-Mode": "true"}
        )
        session_id = post_resp.json()["session_id"]
        
        resp = await client.get(
            f"/chat/{session_id}/history",
            headers={"X-Demo-Mode": "true"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

@pytest.mark.asyncio
async def test_delete_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            "/chat",
            json={"question": "how do I delete it?"},
            headers={"X-Demo-Mode": "true"}
        )
        session_id = post_resp.json()["session_id"]
        
        del_resp = await client.delete(
            f"/chat/{session_id}",
            headers={"X-Demo-Mode": "true"}
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"
        
        get_resp = await client.get(
            f"/chat/{session_id}/history",
            headers={"X-Demo-Mode": "true"}
        )
        assert get_resp.status_code == 404

@pytest.mark.asyncio
async def test_get_sessions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            "/chat",
            json={"question": "first query"},
            headers={"X-Demo-Mode": "true"}
        )
        session_id = post_resp.json()["session_id"]
        
        await client.post(
            "/chat",
            json={"session_id": session_id, "question": "second query"},
            headers={"X-Demo-Mode": "true"}
        )
        
        sessions_resp = await client.get(
            "/chat/sessions",
            headers={"X-Demo-Mode": "true"}
        )
        assert sessions_resp.status_code == 200
        data = sessions_resp.json()
        assert data["total"] >= 1
        
        session_data = next((s for s in data["sessions"] if s["session_id"] == session_id), None)
        assert session_data is not None
        assert session_data["turn_count"] >= 2


@pytest.mark.asyncio
@patch("app.api.routes.ChatPipeline")
async def test_post_chat_stream(mock_pipeline_class):
    async def stream_gen(_request):
        yield 'data: {"type":"delta","text":"Hello"}\n\n'
        yield 'data: {"type":"final","payload":{"session_id":"s1","turn_id":"t1","question":"q","answer":"Hello","confidence":0.9,"confidence_label":"high","sources":[],"service_category":"general","refused":false,"history":[]}}\n\n'

    mock_pipeline = mock_pipeline_class.return_value
    mock_pipeline.run_stream = stream_gen

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat/stream",
            json={"question": "hello"},
            headers={"X-Demo-Mode": "true"}
        )
        assert response.status_code == 200
        assert 'data: {"type":"delta","text":"Hello"}' in response.text
        assert '"type":"final"' in response.text
