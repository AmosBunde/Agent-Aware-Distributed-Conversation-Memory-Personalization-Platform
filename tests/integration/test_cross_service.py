"""Cross-service integration: services talking to each other over the
compose network, addressed directly (not through the gateway).

Requires: make dev
"""

import httpx
import pytest

from tests.conftest import MEMORY_URL, PERSONALIZATION_URL, SESSION_URL

pytestmark = pytest.mark.integration


@pytest.fixture
def memory() -> httpx.Client:
    with httpx.Client(base_url=MEMORY_URL, timeout=30) as client:
        yield client


@pytest.fixture
def personalization() -> httpx.Client:
    with httpx.Client(base_url=PERSONALIZATION_URL, timeout=30) as client:
        yield client


@pytest.fixture
def session() -> httpx.Client:
    with httpx.Client(base_url=SESSION_URL, timeout=30) as client:
        yield client


def test_memory_service_embeds_via_embedding_service(memory, user_id):
    """Storing a memory exercises memory -> embedding service call."""
    resp = memory.post(
        "/api/v1/memories",
        json={"session_id": "it-sess", "role": "user", "content": "integration probe"},
        headers={"X-User-ID": user_id},
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == user_id


def test_personalization_reads_memories_from_memory_service(memory, personalization, user_id):
    memory.post(
        "/api/v1/memories",
        json={
            "session_id": "it-sess",
            "role": "user",
            "content": "I love typed python",
            "metadata": {"intent": "coding_help"},
        },
        headers={"X-User-ID": user_id},
    )
    profile = personalization.get(f"/api/v1/personalization/{user_id}/profile").json()
    assert profile["memory_count"] >= 1
    assert "coding_help" in profile["top_intents"]


def test_session_lifecycle(session, user_id):
    created = session.post(
        "/api/v1/sessions", json={"user_id": user_id, "state": {"topic": "it"}}
    ).json()
    sid = created["session_id"]
    assert session.patch(f"/api/v1/sessions/{sid}", json={"state": {"turns": 1}}).status_code == 200
    ended = session.delete(f"/api/v1/sessions/{sid}").json()
    assert ended["final_state"]["state"] == {"topic": "it", "turns": 1}
