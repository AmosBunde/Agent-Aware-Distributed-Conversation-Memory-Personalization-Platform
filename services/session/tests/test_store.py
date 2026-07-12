from convmem_shared.schemas import Session

from services.session.app.store import InMemorySessionStore


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_session(ttl: int = 60) -> Session:
    return Session(session_id="sess-1", user_id="u1", state={"topic": "python"}, ttl_seconds=ttl)


async def test_session_expires_after_ttl():
    clock = FakeClock()
    store = InMemorySessionStore(clock=clock)
    await store.create(make_session(ttl=60))
    clock.advance(61)
    assert await store.get("sess-1") is None


async def test_get_refreshes_ttl():
    clock = FakeClock()
    store = InMemorySessionStore(clock=clock)
    await store.create(make_session(ttl=60))

    clock.advance(50)
    assert await store.get("sess-1") is not None  # refreshes TTL to now+60
    clock.advance(50)  # 100s after create, but only 50s after refresh
    assert await store.get("sess-1") is not None


async def test_get_without_refresh_does_not_extend():
    clock = FakeClock()
    store = InMemorySessionStore(clock=clock)
    await store.create(make_session(ttl=60))

    clock.advance(50)
    assert await store.get("sess-1", refresh_ttl=False) is not None
    clock.advance(11)
    assert await store.get("sess-1") is None


async def test_merge_state_keeps_existing_keys():
    store = InMemorySessionStore(clock=FakeClock())
    await store.create(make_session())
    updated = await store.merge_state("sess-1", {"mood": "focused"})
    assert updated.state == {"topic": "python", "mood": "focused"}


async def test_end_returns_final_state_and_removes():
    store = InMemorySessionStore(clock=FakeClock())
    await store.create(make_session())
    ended = await store.end("sess-1")
    assert ended.state == {"topic": "python"}
    assert await store.get("sess-1") is None
    assert await store.end("sess-1") is None
