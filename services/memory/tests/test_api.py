USER = {"X-User-ID": "user-123"}


async def store(client, content: str, session_id: str = "sess-1", **metadata):
    resp = await client.post(
        "/api/v1/memories",
        json={
            "session_id": session_id,
            "role": "user",
            "content": content,
            "metadata": metadata,
        },
        headers=USER,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_store_and_list(client):
    await store(client, "I prefer concise answers")
    await store(client, "I am a senior Python engineer")
    resp = await client.get("/api/v1/memories/user-123")
    assert resp.status_code == 200
    contents = [m["content"] for m in resp.json()]
    assert "I prefer concise answers" in contents
    assert len(contents) == 2


async def test_store_requires_user_header(client):
    resp = await client.post(
        "/api/v1/memories",
        json={"session_id": "s", "role": "user", "content": "hi"},
    )
    assert resp.status_code == 422


async def test_context_search_returns_most_relevant_first(client):
    await store(client, "help me debug python asyncio code")
    await store(client, "my favourite food is sushi")
    resp = await client.get(
        "/api/v1/memories/user-123/context",
        params={"query": "python asyncio debugging", "top_k": 2},
    )
    assert resp.status_code == 200
    results = resp.json()
    assert results[0]["memory"]["content"] == "help me debug python asyncio code"
    assert results[0]["score"] >= results[1]["score"]
    assert {"similarity", "recency", "score"} <= results[0].keys()


async def test_context_search_is_scoped_to_user(client):
    await store(client, "python tips")
    resp = await client.get("/api/v1/memories/other-user/context", params={"query": "python tips"})
    assert resp.json() == []


async def test_patch_merges_metadata(client):
    created = await store(client, "note", intent="preference_setting")
    resp = await client.patch(
        f"/api/v1/memories/user-123/{created['id']}",
        json={"metadata": {"pinned": True}},
    )
    assert resp.status_code == 200
    assert resp.json()["metadata"] == {"intent": "preference_setting", "pinned": True}


async def test_delete_then_404(client):
    created = await store(client, "temporary")
    assert (await client.delete(f"/api/v1/memories/user-123/{created['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/memories/user-123/{created['id']}")).status_code == 404


async def test_delete_other_users_memory_is_404(client):
    created = await store(client, "mine")
    resp = await client.delete(f"/api/v1/memories/attacker/{created['id']}")
    assert resp.status_code == 404


async def test_wipe_user_deletes_everything_scoped(client):
    await store(client, "one")
    await store(client, "two")
    resp = await client.delete("/api/v1/memories/user-123")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "user-123", "deleted": 2}
    assert (await client.get("/api/v1/memories/user-123")).json() == []
    # idempotent: a second wipe deletes nothing
    assert (await client.delete("/api/v1/memories/user-123")).json()["deleted"] == 0


async def test_dimension_mismatch_is_a_loud_502(repo):
    import httpx

    from services.memory.app.config import Settings
    from services.memory.app.main import create_app
    from services.memory.tests.conftest import FakeEmbedder

    # Service expects 384-dim vectors; the fake embedder produces 16.
    app = create_app(
        settings=Settings(_env_file=None, embedding_dim=384),
        repository=repo,
        embedder=FakeEmbedder(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/memories",
            json={"session_id": "s", "role": "user", "content": "hi"},
            headers=USER,
        )
    assert resp.status_code == 502
    assert "dimension mismatch" in resp.json()["detail"]
    assert "EMBEDDING_DIM" in resp.json()["detail"]
