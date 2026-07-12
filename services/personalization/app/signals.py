"""Explicit preference-signal storage (protocol + Postgres + in-memory)."""

from typing import Protocol

import asyncpg
from convmem_shared.schemas import PreferenceSignal


class SignalStore(Protocol):
    async def upsert(self, user_id: str, signal: PreferenceSignal) -> None: ...

    async def list_for_user(self, user_id: str) -> list[PreferenceSignal]: ...


class PostgresSignalStore:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresSignalStore":
        return cls(await asyncpg.create_pool(dsn, min_size=1, max_size=5))

    async def ping(self) -> bool:
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1

    async def upsert(self, user_id: str, signal: PreferenceSignal) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO preference_signals (user_id, key, value, strength, updated_at)
                VALUES ($1, $2, $3, $4, now())
                ON CONFLICT (user_id, key)
                DO UPDATE SET value = $3, strength = $4, updated_at = now()
                """,
                user_id,
                signal.key,
                signal.value,
                signal.strength,
            )

    async def list_for_user(self, user_id: str) -> list[PreferenceSignal]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value, strength FROM preference_signals
                WHERE user_id = $1 ORDER BY updated_at DESC
                """,
                user_id,
            )
        return [PreferenceSignal(**dict(r)) for r in rows]

    async def close(self) -> None:
        await self._pool.close()


class InMemorySignalStore:
    def __init__(self):
        self._rows: dict[tuple[str, str], PreferenceSignal] = {}

    async def upsert(self, user_id: str, signal: PreferenceSignal) -> None:
        self._rows[(user_id, signal.key)] = signal

    async def list_for_user(self, user_id: str) -> list[PreferenceSignal]:
        return [s for (uid, _), s in self._rows.items() if uid == user_id]
