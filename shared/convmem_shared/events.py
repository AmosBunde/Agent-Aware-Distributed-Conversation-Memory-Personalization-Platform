"""Event publishing over Redis Streams.

Downstream consumers (analytics, async profile rebuilds) subscribe with
XREAD/consumer groups instead of polling the APIs. Streams are named
``convmem.events.<topic>`` and capped so an absent consumer can never
exhaust Redis memory.

Publishing is strictly best-effort: an event-bus outage must never fail
the request that triggered the event. ``publish`` returns whether the
event was actually written, and callers treat it as fire-and-forget.

Redis Streams is the deliberate starter choice — Redis is already in the
stack. The ``EventPublisher`` protocol is the seam where a Kafka or
Pub/Sub implementation drops in later.
"""

import json
from typing import Any, Protocol

from .schemas import utcnow

STREAM_PREFIX = "convmem.events."
MAX_STREAM_LENGTH = 10_000  # per-topic cap, approximate trimming


class EventPublisher(Protocol):
    async def publish(self, topic: str, payload: dict[str, Any]) -> bool: ...


class RedisEventPublisher:
    def __init__(self, redis_client, max_length: int = MAX_STREAM_LENGTH):
        self._redis = redis_client
        self._max_length = max_length

    async def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        try:
            await self._redis.xadd(
                STREAM_PREFIX + topic,
                {"payload": json.dumps({**payload, "emitted_at": utcnow().isoformat()})},
                maxlen=self._max_length,
                approximate=True,
            )
            return True
        except Exception:
            return False


class NullEventPublisher:
    """Default when no event bus is configured; publishing is a no-op."""

    async def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        return False
