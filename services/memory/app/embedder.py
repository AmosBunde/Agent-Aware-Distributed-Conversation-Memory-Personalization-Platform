"""Client for the embedding service (protocol + HTTP implementation)."""

from typing import Protocol

from convmem_shared.http_client import ServiceClient


class Embedder(Protocol):
    async def embed_one(self, text: str) -> list[float]: ...


class HttpEmbedder:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._client = ServiceClient(base_url, "embedding", timeout=timeout)

    async def embed_one(self, text: str) -> list[float]:
        resp = await self._client.post("/api/v1/embed", json={"texts": [text]})
        resp.raise_for_status()
        return resp.json()["vectors"][0]
