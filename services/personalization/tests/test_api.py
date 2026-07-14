async def test_profile_aggregates_history(client):
    resp = await client.get("/api/v1/personalization/u1/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["top_intents"][0] == "coding_help"
    assert body["memory_count"] == 3


async def test_signal_persists_and_appears_in_profile(client):
    resp = await client.post(
        "/api/v1/personalization/u1/signal",
        json={"key": "tone", "value": "concise", "strength": 1.0},
    )
    assert resp.status_code == 204
    profile = (await client.get("/api/v1/personalization/u1/profile")).json()
    assert profile["preferences"] == {"tone": "concise"}


async def test_signal_upsert_overwrites_same_key(client):
    await client.post(
        "/api/v1/personalization/u1/signal",
        json={"key": "tone", "value": "concise"},
    )
    await client.post(
        "/api/v1/personalization/u1/signal",
        json={"key": "tone", "value": "detailed"},
    )
    profile = (await client.get("/api/v1/personalization/u1/profile")).json()
    assert profile["preferences"] == {"tone": "detailed"}


async def test_context_bundle_combines_profile_and_memories(client):
    await client.post(
        "/api/v1/personalization/u1/signal",
        json={"key": "tone", "value": "concise"},
    )
    resp = await client.get(
        "/api/v1/personalization/u1/context-bundle",
        params={"query": "python help", "top_k": 2},
    )
    assert resp.status_code == 200
    bundle = resp.json()
    assert bundle["profile"]["preferences"] == {"tone": "concise"}
    assert len(bundle["memories"]) == 2
    assert bundle["memories"][0]["score"] > 0


async def test_degrades_gracefully_when_memory_service_down(client, gateway):
    gateway.down = True
    await client.post(
        "/api/v1/personalization/u1/signal",
        json={"key": "tone", "value": "concise"},
    )
    resp = await client.get(
        "/api/v1/personalization/u1/context-bundle", params={"query": "anything"}
    )
    assert resp.status_code == 200
    bundle = resp.json()
    # Signals still served; memory-derived fields are empty, not errors.
    assert bundle["profile"]["preferences"] == {"tone": "concise"}
    assert bundle["profile"]["memory_count"] == 0
    assert bundle["memories"] == []


async def test_profile_scoped_to_user(client):
    resp = await client.get("/api/v1/personalization/stranger/profile")
    assert resp.json()["memory_count"] == 0


async def test_clear_signals_wipes_only_that_user(client):
    await client.post("/api/v1/personalization/u1/signal", json={"key": "tone", "value": "concise"})
    await client.post(
        "/api/v1/personalization/u2/signal", json={"key": "tone", "value": "detailed"}
    )
    resp = await client.delete("/api/v1/personalization/u1/signals")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "u1", "deleted": 1}
    assert (await client.get("/api/v1/personalization/u1/profile")).json()["preferences"] == {}
    assert (await client.get("/api/v1/personalization/u2/profile")).json()["preferences"] == {
        "tone": "detailed"
    }
