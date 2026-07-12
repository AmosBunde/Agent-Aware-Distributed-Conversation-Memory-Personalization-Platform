"""Session storage behind a protocol.

``RedisSessionStore`` is production (native TTL expiry). ``InMemorySessionStore``
mirrors the TTL semantics with an injectable clock so unit tests can verify
expiry behaviour without sleeping or running Redis.
"""

import json
import time
from typing import Any, Protocol

from convmem_shared.schemas import Session

_KEY_PREFIX = "session:"


class SessionStore(Protocol):
    async def create(self, session: Session) -> Session: ...

    async def get(self, session_id: str, refresh_ttl: bool = True) -> Session | None: ...

    async def merge_state(self, session_id: str, state: dict[str, Any]) -> Session | None: ...

    async def end(self, session_id: str) -> Session | None: ...


class RedisSessionStore:
    def __init__(self, redis_client):
        self._redis = redis_client

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def create(self, session: Session) -> Session:
        await self._redis.set(
            _KEY_PREFIX + session.session_id,
            session.model_dump_json(),
            ex=session.ttl_seconds,
        )
        return session

    async def get(self, session_id: str, refresh_ttl: bool = True) -> Session | None:
        raw = await self._redis.get(_KEY_PREFIX + session_id)
        if raw is None:
            return None
        session = Session.model_validate_json(raw)
        if refresh_ttl:
            await self._redis.expire(_KEY_PREFIX + session_id, session.ttl_seconds)
        return session

    async def merge_state(self, session_id: str, state: dict[str, Any]) -> Session | None:
        session = await self.get(session_id, refresh_ttl=False)
        if session is None:
            return None
        session.state.update(state)
        await self._redis.set(
            _KEY_PREFIX + session_id, session.model_dump_json(), ex=session.ttl_seconds
        )
        return session

    async def end(self, session_id: str) -> Session | None:
        key = _KEY_PREFIX + session_id
        raw = await self._redis.get(key)
        if raw is None:
            return None
        await self._redis.delete(key)
        return Session.model_validate_json(raw)


class InMemorySessionStore:
    """Dict-backed store with real TTL semantics via an injectable clock."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._rows: dict[str, tuple[str, float]] = {}  # id -> (json, expires_at)

    def _live(self, session_id: str) -> str | None:
        row = self._rows.get(session_id)
        if row is None:
            return None
        raw, expires_at = row
        if self._clock() >= expires_at:
            del self._rows[session_id]
            return None
        return raw

    async def create(self, session: Session) -> Session:
        self._rows[session.session_id] = (
            session.model_dump_json(),
            self._clock() + session.ttl_seconds,
        )
        return session

    async def get(self, session_id: str, refresh_ttl: bool = True) -> Session | None:
        raw = self._live(session_id)
        if raw is None:
            return None
        session = Session.model_validate_json(raw)
        if refresh_ttl:
            self._rows[session_id] = (raw, self._clock() + session.ttl_seconds)
        return session

    async def merge_state(self, session_id: str, state: dict[str, Any]) -> Session | None:
        raw = self._live(session_id)
        if raw is None:
            return None
        session = Session.model_validate_json(raw)
        session.state.update(state)
        _, expires_at = self._rows[session_id]
        self._rows[session_id] = (session.model_dump_json(), expires_at)
        return session

    async def end(self, session_id: str) -> Session | None:
        raw = self._live(session_id)
        if raw is None:
            return None
        del self._rows[session_id]
        return Session.model_validate_json(raw)


def state_snapshot(session: Session) -> dict[str, Any]:
    """The payload flushed to long-term memory when a session ends."""
    return json.loads(session.model_dump_json())
