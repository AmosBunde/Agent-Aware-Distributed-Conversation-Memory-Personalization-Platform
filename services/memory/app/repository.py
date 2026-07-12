"""Memory storage behind a protocol.

``PostgresMemoryRepository`` (see ``postgres.py``) is the production
implementation; ``InMemoryMemoryRepository`` backs unit tests and keeps the
API layer testable without infrastructure.
"""

from typing import Any, Protocol
from uuid import UUID

from convmem_shared.schemas import Memory


class MemoryRepository(Protocol):
    async def add(self, memory: Memory, embedding: list[float]) -> Memory: ...

    async def get(self, user_id: str, memory_id: UUID) -> Memory | None: ...

    async def list_by_user(self, user_id: str, limit: int, offset: int) -> list[Memory]: ...

    async def search(
        self, user_id: str, query_vector: list[float], top_k: int
    ) -> list[tuple[Memory, float]]: ...

    async def update_metadata(
        self, user_id: str, memory_id: UUID, metadata: dict[str, Any]
    ) -> Memory | None: ...

    async def delete(self, user_id: str, memory_id: UUID) -> bool: ...


class InMemoryMemoryRepository:
    """Dict-backed repository with real cosine search, for tests."""

    def __init__(self):
        self._rows: dict[UUID, tuple[Memory, list[float]]] = {}

    async def add(self, memory: Memory, embedding: list[float]) -> Memory:
        self._rows[memory.id] = (memory, embedding)
        return memory

    async def get(self, user_id: str, memory_id: UUID) -> Memory | None:
        row = self._rows.get(memory_id)
        if row and row[0].user_id == user_id:
            return row[0]
        return None

    async def list_by_user(self, user_id: str, limit: int, offset: int) -> list[Memory]:
        rows = sorted(
            (m for m, _ in self._rows.values() if m.user_id == user_id),
            key=lambda m: m.created_at,
            reverse=True,
        )
        return rows[offset : offset + limit]

    async def search(
        self, user_id: str, query_vector: list[float], top_k: int
    ) -> list[tuple[Memory, float]]:
        hits = [
            (m, sum(a * b for a, b in zip(vec, query_vector, strict=True)))
            for m, vec in self._rows.values()
            if m.user_id == user_id
        ]
        hits.sort(key=lambda pair: pair[1], reverse=True)
        return hits[:top_k]

    async def update_metadata(
        self, user_id: str, memory_id: UUID, metadata: dict[str, Any]
    ) -> Memory | None:
        row = self._rows.get(memory_id)
        if not row or row[0].user_id != user_id:
            return None
        memory, vec = row
        updated = memory.model_copy(update={"metadata": {**memory.metadata, **metadata}})
        self._rows[memory_id] = (updated, vec)
        return updated

    async def delete(self, user_id: str, memory_id: UUID) -> bool:
        row = self._rows.get(memory_id)
        if not row or row[0].user_id != user_id:
            return False
        del self._rows[memory_id]
        return True
