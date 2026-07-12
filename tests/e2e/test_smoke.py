"""Black-box golden path, exercised exclusively through the gateway.

Store memories -> semantic context search -> preference signal ->
context bundle -> web console. This is the exact flow the README quickstart
promises, so if this passes, the docs are true.

Requires: make dev
"""

import pytest

pytestmark = pytest.mark.e2e


def test_gateway_reports_all_upstreams_healthy(gateway):
    body = gateway.get("/healthz").json()
    assert body["status"] == "ok", body
    assert set(body["upstreams"]) == {"memory", "session", "personalization", "embedding"}
    assert all(u["circuit"] == "closed" for u in body["upstreams"].values())


def test_golden_path(gateway, user_id):
    headers = {"X-User-ID": user_id}

    # 1. Store two memories with different topics
    for content, intent in [
        ("I prefer concise answers. I am a senior Python engineer.", "preference_setting"),
        ("Help me profile a slow asyncpg query.", "coding_help"),
    ]:
        resp = gateway.post(
            "/api/v1/memories",
            json={
                "session_id": "e2e-sess",
                "role": "user",
                "content": content,
                "metadata": {"intent": intent},
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    # 2. Semantic search finds the relevant one first, with score breakdown
    hits = gateway.get(
        f"/api/v1/memories/{user_id}/context",
        params={"query": "slow asyncpg query profiling", "top_k": 2},
    ).json()
    assert len(hits) == 2
    assert "asyncpg" in hits[0]["memory"]["content"]
    assert hits[0]["score"] >= hits[1]["score"]

    # 3. Explicit preference signal
    resp = gateway.post(
        f"/api/v1/personalization/{user_id}/signal",
        json={"key": "tone", "value": "concise"},
        headers=headers,
    )
    assert resp.status_code == 204

    # 4. Context bundle merges profile + memories
    bundle = gateway.get(
        f"/api/v1/personalization/{user_id}/context-bundle",
        params={"query": "python help"},
        headers=headers,
    ).json()
    assert bundle["profile"]["preferences"]["tone"] == "concise"
    assert bundle["profile"]["memory_count"] == 2
    assert bundle["memories"]

    # 5. Session lifecycle through the gateway
    session = gateway.post(
        "/api/v1/sessions",
        json={"user_id": user_id, "state": {"seen": True}},
        headers=headers,
    ).json()
    ended = gateway.delete(f"/api/v1/sessions/{session['session_id']}", headers=headers).json()
    assert ended["ended"] is True


def test_web_console_is_served(gateway):
    resp = gateway.get("/")
    assert resp.status_code == 200
    assert "convmem" in resp.text
