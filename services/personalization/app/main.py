from contextlib import asynccontextmanager

from convmem_shared.health import health_router
from convmem_shared.schemas import ContextBundle, PreferenceSignal, UserProfile
from fastapi import FastAPI, Query

from .config import Settings, get_settings
from .memory_gateway import HttpMemoryGateway, MemoryGateway
from .profile import build_profile
from .signals import SignalStore


def create_app(
    settings: Settings | None = None,
    signal_store: SignalStore | None = None,
    memory_gateway: MemoryGateway | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    state: dict = {"signals": signal_store, "memories": memory_gateway}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if state["signals"] is None:
            from .signals import PostgresSignalStore

            state["signals"] = await PostgresSignalStore.connect(settings.postgres_dsn)
        if state["memories"] is None:
            state["memories"] = HttpMemoryGateway(
                settings.memory_service_url, settings.http_timeout_seconds
            )
        yield
        close = getattr(state["signals"], "close", None)
        if close:
            await close()

    app = FastAPI(title="Personalization Service", version="0.1.0", lifespan=lifespan)

    async def signals_ping() -> bool:
        ping = getattr(state["signals"], "ping", None)
        return await ping() if ping else True

    app.include_router(health_router(settings.service_name, checks={"postgres": signals_ping}))

    async def _profile(user_id: str) -> UserProfile:
        memories = await state["memories"].recent_memories(user_id, settings.profile_history_window)
        signals = await state["signals"].list_for_user(user_id)
        return build_profile(user_id, memories, signals, settings.profile_top_intents)

    @app.get("/api/v1/personalization/{user_id}/profile", response_model=UserProfile)
    async def get_profile(user_id: str) -> UserProfile:
        return await _profile(user_id)

    @app.post("/api/v1/personalization/{user_id}/signal", status_code=204)
    async def ingest_signal(user_id: str, signal: PreferenceSignal) -> None:
        await state["signals"].upsert(user_id, signal)

    @app.delete("/api/v1/personalization/{user_id}/signals")
    async def clear_signals(user_id: str) -> dict:
        """Right to be forgotten: drop all explicit preference signals."""
        deleted = await state["signals"].clear(user_id)
        return {"user_id": user_id, "deleted": deleted}

    @app.get("/api/v1/personalization/{user_id}/context-bundle", response_model=ContextBundle)
    async def context_bundle(
        user_id: str,
        query: str = Query(min_length=1),
        top_k: int = Query(5, ge=1, le=50),
    ) -> ContextBundle:
        profile = await _profile(user_id)
        memories = await state["memories"].search_context(user_id, query, top_k)
        return ContextBundle(user_id=user_id, profile=profile, memories=memories)

    return app


app = create_app()
