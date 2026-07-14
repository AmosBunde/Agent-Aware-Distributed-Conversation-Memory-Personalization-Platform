"""asyncpg-backed repository using pgvector cosine search.

All SQL is parameterized; vectors travel as text literals cast to ``vector``
server-side (asyncpg has no native codec for the pgvector type without an
extension hook, and the cast is equivalent).
"""

import json
from typing import Any
from uuid import UUID

import asyncpg
from convmem_shared.schemas import Memory


def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


def _row_to_memory(row: asyncpg.Record) -> Memory:
    return Memory(
        id=row["id"],
        user_id=row["user_id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        metadata=json.loads(row["metadata"]),
        created_at=row["created_at"],
    )


class PostgresMemoryRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresMemoryRepository":
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
        return cls(pool)

    async def ping(self) -> bool:
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1

    async def add(self, memory: Memory, embedding: list[float]) -> Memory:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (id, user_id, session_id, role, content, metadata,
                                      embedding, created_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::vector, $8)
                """,
                memory.id,
                memory.user_id,
                memory.session_id,
                memory.role,
                memory.content,
                json.dumps(memory.metadata),
                _vec_literal(embedding),
                memory.created_at,
            )
        return memory

    async def get(self, user_id: str, memory_id: UUID) -> Memory | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memories WHERE id = $1 AND user_id = $2",
                memory_id,
                user_id,
            )
        return _row_to_memory(row) if row else None

    async def list_by_user(self, user_id: str, limit: int, offset: int) -> list[Memory]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM memories WHERE user_id = $1
                ORDER BY created_at DESC LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
        return [_row_to_memory(r) for r in rows]

    async def search(
        self, user_id: str, query_vector: list[float], top_k: int
    ) -> list[tuple[Memory, float]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *, 1 - (embedding <=> $2::vector) AS similarity
                FROM memories
                WHERE user_id = $1
                ORDER BY embedding <=> $2::vector
                LIMIT $3
                """,
                user_id,
                _vec_literal(query_vector),
                top_k,
            )
        return [(_row_to_memory(r), float(r["similarity"])) for r in rows]

    async def update_metadata(
        self, user_id: str, memory_id: UUID, metadata: dict[str, Any]
    ) -> Memory | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE memories SET metadata = metadata || $3::jsonb
                WHERE id = $1 AND user_id = $2
                RETURNING *
                """,
                memory_id,
                user_id,
                json.dumps(metadata),
            )
        return _row_to_memory(row) if row else None

    async def delete(self, user_id: str, memory_id: UUID) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memories WHERE id = $1 AND user_id = $2",
                memory_id,
                user_id,
            )
        return result.endswith("1")

    async def delete_all(self, user_id: str) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM memories WHERE user_id = $1", user_id)
        return int(result.split()[-1])

    async def close(self) -> None:
        await self._pool.close()
