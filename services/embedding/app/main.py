from convmem_shared.health import health_router
from convmem_shared.schemas import EmbedRequest, EmbedResponse
from fastapi import FastAPI

from .backends import build_backend
from .config import get_settings

settings = get_settings()
backend = build_backend(
    settings.embedding_backend,
    settings.embedding_dim,
    api_key=settings.openai_api_key,
    model=settings.openai_model,
)

app = FastAPI(title="Embedding Service", version="0.1.0")
app.include_router(health_router(settings.service_name))


@app.post("/api/v1/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    vectors = await backend.embed(req.texts)
    return EmbedResponse(vectors=vectors, dim=settings.embedding_dim, backend=backend.name)
