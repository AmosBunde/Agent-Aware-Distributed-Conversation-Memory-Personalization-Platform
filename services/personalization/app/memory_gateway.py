"""Read-side client for the memory service.

The personalization service never talks to the memories table directly —
retrieval stays owned by the memory service. If it is unreachable, callers
degrade gracefully (profile from signals only, empty memory list).
"""

from typing import Protocol

from convmem_shared.http_client import ServiceClient, ServiceUnavailable
from convmem_shared.schemas import Memory, ScoredMemory


class MemoryGateway(Protocol):
    async def recent_memories(self, user_id: str, limit: int) -> list[Memory]: ...

    async def search_context(self, user_id: str, query: str, top_k: int) -> list[ScoredMemory]: ...


class HttpMemoryGateway:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._client = ServiceClient(base_url, "memory", timeout=timeout)

    async def recent_memories(self, user_id: str, limit: int) -> list[Memory]:
        try:
            resp = await self._client.get(f"/api/v1/memories/{user_id}", params={"limit": limit})
            resp.raise_for_status()
        except ServiceUnavailable:
            return []
        return [Memory.model_validate(m) for m in resp.json()]

    async def search_context(self, user_id: str, query: str, top_k: int) -> list[ScoredMemory]:
        try:
            resp = await self._client.get(
                f"/api/v1/memories/{user_id}/context",
                params={"query": query, "top_k": top_k},
            )
            resp.raise_for_status()
        except ServiceUnavailable:
            return []
        return [ScoredMemory.model_validate(m) for m in resp.json()]
