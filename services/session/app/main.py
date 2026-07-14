from uuid import uuid4

from convmem_shared.events import EventPublisher, RedisEventPublisher
from convmem_shared.health import health_router
from convmem_shared.schemas import Session, SessionCreate, SessionUpdate
from fastapi import FastAPI, HTTPException

from .config import Settings, get_settings
from .flush import HttpMemoryFlusher, MemoryFlusher
from .store import SessionStore, state_snapshot


def create_app(
    settings: Settings | None = None,
    store: SessionStore | None = None,
    flusher: MemoryFlusher | None = None,
    publisher: EventPublisher | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    state: dict = {"store": store, "flusher": flusher, "publisher": publisher}

    async def get_store() -> SessionStore:
        if state["store"] is None:
            import redis.asyncio as redis

            from .store import RedisSessionStore

            state["store"] = RedisSessionStore(
                redis.from_url(settings.redis_url, decode_responses=True)
            )
        return state["store"]

    def get_flusher() -> MemoryFlusher:
        if state["flusher"] is None:
            state["flusher"] = HttpMemoryFlusher(
                settings.memory_service_url, settings.http_timeout_seconds
            )
        return state["flusher"]

    def get_publisher() -> EventPublisher:
        if state["publisher"] is None:
            import redis.asyncio as redis

            state["publisher"] = RedisEventPublisher(redis.from_url(settings.redis_url))
        return state["publisher"]

    app = FastAPI(title="Session Service", version="0.1.0")

    async def redis_ping() -> bool:
        store = await get_store()
        ping = getattr(store, "ping", None)
        return await ping() if ping else True

    app.include_router(health_router(settings.service_name, checks={"redis": redis_ping}))

    @app.post("/api/v1/sessions", response_model=Session, status_code=201)
    async def create_session(payload: SessionCreate) -> Session:
        session = Session(
            session_id=f"sess-{uuid4().hex[:12]}",
            user_id=payload.user_id,
            state=payload.state,
            ttl_seconds=settings.session_ttl_seconds,
        )
        return await (await get_store()).create(session)

    @app.get("/api/v1/sessions/{session_id}", response_model=Session)
    async def get_session(session_id: str) -> Session:
        session = await (await get_store()).get(session_id)
        if session is None:
            raise HTTPException(404, "session not found or expired")
        return session

    @app.patch("/api/v1/sessions/{session_id}", response_model=Session)
    async def update_session(session_id: str, payload: SessionUpdate) -> Session:
        session = await (await get_store()).merge_state(session_id, payload.state)
        if session is None:
            raise HTTPException(404, "session not found or expired")
        return session

    @app.delete("/api/v1/sessions/{session_id}")
    async def end_session(session_id: str) -> dict:
        session = await (await get_store()).end(session_id)
        if session is None:
            raise HTTPException(404, "session not found or expired")
        # Best-effort long-term flush: a memory-service outage must not
        # prevent the session from ending; the caller sees the outcome.
        flushed = bool(session.state) and await get_flusher().flush(session)
        await get_publisher().publish(
            "session.ended",
            {"session_id": session.session_id, "user_id": session.user_id, "flushed": flushed},
        )
        return {"ended": True, "flushed": flushed, "final_state": state_snapshot(session)}

    return app


app = create_app()
