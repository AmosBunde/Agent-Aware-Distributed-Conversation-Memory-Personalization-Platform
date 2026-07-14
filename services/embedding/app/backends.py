"""Embedding backends behind a single protocol.

``LocalHashingBackend`` is the default: a deterministic feature-hashing
encoder that needs no model download and no API key, so the whole platform
runs (and is testable) offline. ``OpenAIBackend`` is a drop-in upgrade for
production-quality semantics.
"""

import hashlib
import math
import re
from typing import Protocol

import httpx

_TOKEN_RE = re.compile(r"[a-z0-9']+")


class EmbeddingBackend(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalHashingBackend:
    """Deterministic bag-of-words feature hashing with L2 normalisation.

    Each token is hashed twice (bucket + sign), which is the classic
    "hashing trick": cheap, stable across processes, and good enough for
    lexical similarity. Not a semantic model — swap in the OpenAI backend
    when meaning-level retrieval quality matters.
    """

    name = "local"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            # Empty/no-token input: fixed unit vector so pgvector never
            # receives a zero vector (cosine distance is undefined there).
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class OpenAIBackend:
    name = "openai"

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dim: int = 384):
        self.model = model
        self.dim = dim
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.post(
            "/embeddings",
            json={"model": self.model, "input": texts, "dimensions": self.dim},
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]


def build_backend(
    backend: str, dim: int, api_key: str = "", model: str = "", st_model: str = ""
) -> EmbeddingBackend:
    if backend == "openai":
        if not api_key:
            raise ValueError("EMBEDDING_BACKEND=openai requires OPENAI_API_KEY")
        return OpenAIBackend(api_key=api_key, model=model, dim=dim)
    if backend == "sentence-transformers":
        kwargs = {"model_name": st_model} if st_model else {}
        return SentenceTransformersBackend(dim=dim, **kwargs)
    if backend == "local":
        return LocalHashingBackend(dim=dim)
    raise ValueError(f"Unknown embedding backend: {backend!r}")


class SentenceTransformersBackend:
    """Local semantic embeddings via sentence-transformers.

    Real semantic quality with no API key — at the cost of heavy optional
    dependencies (torch), which is why they live in requirements-st.txt
    instead of the base image. Encoding runs off the event loop.
    """

    name = "sentence-transformers"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", dim: int = 384):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "EMBEDDING_BACKEND=sentence-transformers needs its optional deps: "
                "pip install -r services/embedding/requirements-st.txt"
            ) from exc
        self._model = SentenceTransformer(model_name)
        model_dim = self._model.get_sentence_embedding_dimension()
        if model_dim != dim:
            raise ValueError(
                f"model {model_name!r} produces {model_dim}-dim vectors but "
                f"EMBEDDING_DIM={dim}; the memories schema is vector({dim})"
            )
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        vectors = await asyncio.to_thread(self._model.encode, texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
