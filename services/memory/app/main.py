from contextlib import asynccontextmanager
from uuid import UUID

from convmem_shared.health import health_router
from convmem_shared.schemas import Memory, MemoryCreate, MemoryUpdate, ScoredMemory
from fastapi import FastAPI, Header, HTTPException, Query

from .config import Settings, get_settings
from .embedder import Embedder, HttpEmbedder
from .ranking import rank
from .repository import MemoryRepository


def create_app(
    settings: Settings | None = None,
    repository: MemoryRepository | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    """App factory.

    Production runs with no arguments (Postgres + HTTP embedder wired in at
    startup); tests inject an in-memory repository and a fake embedder.
    """
    settings = settings or get_settings()
    state: dict = {"repo": repository, "embedder": embedder}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if state["repo"] is None:
            from .postgres import PostgresMemoryRepository

            state["repo"] = await PostgresMemoryRepository.connect(settings.postgres_dsn)
        if state["embedder"] is None:
            state["embedder"] = HttpEmbedder(
                settings.embedding_service_url, settings.http_timeout_seconds
            )
        yield
        close = getattr(state["repo"], "close", None)
        if close:
            await close()

    app = FastAPI(title="Memory Service", version="0.1.0", lifespan=lifespan)

    async def repo_ping() -> bool:
        ping = getattr(state["repo"], "ping", None)
        return await ping() if ping else True

    app.include_router(health_router(settings.service_name, checks={"postgres": repo_ping}))

    async def embed_checked(text: str) -> list[float]:
        """Embed and fail loudly on a dimension mismatch.

        The schema is vector(EMBEDDING_DIM); a misconfigured embedding
        service would otherwise surface as an opaque SQL error.
        """
        vector = await state["embedder"].embed_one(text)
        if len(vector) != settings.embedding_dim:
            raise HTTPException(
                502,
                f"embedding dimension mismatch: memory service expects "
                f"{settings.embedding_dim}, embedding service returned {len(vector)}; "
                f"check EMBEDDING_DIM on both services",
            )
        return vector

    @app.post("/api/v1/memories", response_model=Memory, status_code=201)
    async def store_memory(payload: MemoryCreate, x_user_id: str = Header(...)) -> Memory:
        memory = Memory(user_id=x_user_id, **payload.model_dump())
        embedding = await embed_checked(memory.content)
        return await state["repo"].add(memory, embedding)

    @app.get("/api/v1/memories/{user_id}", response_model=list[Memory])
    async def list_memories(
        user_id: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> list[Memory]:
        return await state["repo"].list_by_user(user_id, limit, offset)

    @app.get("/api/v1/memories/{user_id}/context", response_model=list[ScoredMemory])
    async def context_search(
        user_id: str,
        query: str = Query(min_length=1),
        top_k: int = Query(5, ge=1, le=50),
    ) -> list[ScoredMemory]:
        query_vector = await embed_checked(query)
        hits = await state["repo"].search(user_id, query_vector, top_k)
        return rank(
            hits,
            settings.rank_weight_similarity,
            settings.rank_weight_recency,
            settings.rank_recency_half_life_seconds,
        )

    @app.patch("/api/v1/memories/{user_id}/{memory_id}", response_model=Memory)
    async def patch_memory(user_id: str, memory_id: UUID, payload: MemoryUpdate) -> Memory:
        updated = await state["repo"].update_metadata(user_id, memory_id, payload.metadata)
        if updated is None:
            raise HTTPException(404, "memory not found")
        return updated

    @app.delete("/api/v1/memories/{user_id}/{memory_id}", status_code=204)
    async def delete_memory(user_id: str, memory_id: UUID) -> None:
        if not await state["repo"].delete(user_id, memory_id):
            raise HTTPException(404, "memory not found")

    @app.delete("/api/v1/memories/{user_id}")
    async def delete_all_memories(user_id: str) -> dict:
        """Right to be forgotten: remove every memory for this user."""
        deleted = await state["repo"].delete_all(user_id)
        return {"user_id": user_id, "deleted": deleted}

    return app


app = create_app()
