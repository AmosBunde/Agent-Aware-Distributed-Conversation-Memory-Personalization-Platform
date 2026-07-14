import httpx
import pytest
from convmem_shared.schemas import Session

from services.session.app.config import Settings
from services.session.app.main import create_app
from services.session.app.store import InMemorySessionStore


class FakeFlusher:
    def __init__(self, healthy: bool = True):
        self.healthy = healthy
        self.flushed: list[Session] = []

    async def flush(self, session: Session) -> bool:
        if not self.healthy:
            return False
        self.flushed.append(session)
        return True


class RecordingPublisher:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish(self, topic: str, payload: dict) -> bool:
        self.events.append((topic, payload))
        return True


@pytest.fixture
def flusher() -> FakeFlusher:
    return FakeFlusher()


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def client(flusher, publisher) -> httpx.AsyncClient:
    app = create_app(
        settings=Settings(_env_file=None),
        store=InMemorySessionStore(),
        flusher=flusher,
        publisher=publisher,
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def create_session(client, **state) -> dict:
    resp = await client.post("/api/v1/sessions", json={"user_id": "u1", "state": state})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_returns_session_with_ttl(client):
    body = await create_session(client, topic="python")
    assert body["session_id"].startswith("sess-")
    assert body["user_id"] == "u1"
    assert body["ttl_seconds"] == 1800
    assert body["state"] == {"topic": "python"}


async def test_get_roundtrip(client):
    created = await create_session(client, topic="python")
    resp = await client.get(f"/api/v1/sessions/{created['session_id']}")
    assert resp.status_code == 200
    assert resp.json()["state"] == {"topic": "python"}


async def test_patch_merges_state(client):
    created = await create_session(client, topic="python")
    resp = await client.patch(
        f"/api/v1/sessions/{created['session_id']}",
        json={"state": {"turns": 3}},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == {"topic": "python", "turns": 3}


async def test_end_session_returns_final_state(client):
    created = await create_session(client, topic="python")
    resp = await client.delete(f"/api/v1/sessions/{created['session_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ended"] is True
    assert body["final_state"]["state"] == {"topic": "python"}
    # gone afterwards
    assert (await client.get(f"/api/v1/sessions/{created['session_id']}")).status_code == 404


async def test_end_session_flushes_state_to_memory(client, flusher):
    created = await create_session(client, topic="python")
    body = (await client.delete(f"/api/v1/sessions/{created['session_id']}")).json()
    assert body["flushed"] is True
    [flushed] = flusher.flushed
    assert flushed.user_id == "u1"
    assert flushed.state == {"topic": "python"}


async def test_empty_session_is_not_flushed(client, flusher):
    created = await create_session(client)  # no state
    body = (await client.delete(f"/api/v1/sessions/{created['session_id']}")).json()
    assert body["flushed"] is False
    assert flusher.flushed == []


async def test_memory_outage_does_not_block_session_end(client, flusher):
    flusher.healthy = False
    created = await create_session(client, topic="python")
    resp = await client.delete(f"/api/v1/sessions/{created['session_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ended"] is True
    assert body["flushed"] is False


async def test_unknown_session_is_404(client):
    assert (await client.get("/api/v1/sessions/nope")).status_code == 404
    assert (await client.delete("/api/v1/sessions/nope")).status_code == 404


async def test_end_session_publishes_event(client, publisher):
    created = await create_session(client, topic="python")
    await client.delete(f"/api/v1/sessions/{created['session_id']}")
    [(topic, payload)] = publisher.events
    assert topic == "session.ended"
    assert payload == {
        "session_id": created["session_id"],
        "user_id": "u1",
        "flushed": True,
    }
