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


class KafkaEventPublisher:
    """Kafka transport for the same topics (``convmem.events.<topic>``).

    The producer is created lazily on first publish and reset on failure so
    a broker restart heals without a service restart. Same best-effort
    contract as the Redis implementation.
    """

    def __init__(self, bootstrap_servers: str, producer=None, request_timeout_ms: int = 5000):
        self._bootstrap = bootstrap_servers
        self._producer = producer
        self._request_timeout_ms = request_timeout_ms

    async def _ensure_producer(self):
        if self._producer is None:
            from aiokafka import AIOKafkaProducer

            producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap,
                request_timeout_ms=self._request_timeout_ms,
            )
            await producer.start()
            self._producer = producer
        return self._producer

    async def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        try:
            producer = await self._ensure_producer()
            message = json.dumps({**payload, "emitted_at": utcnow().isoformat()})
            await producer.send_and_wait(STREAM_PREFIX + topic, message.encode())
            return True
        except Exception:
            self._producer = None  # rebuild the connection on the next attempt
            return False


def build_publisher(
    event_bus: str,
    redis_url: str = "",
    kafka_bootstrap_servers: str = "",
) -> EventPublisher:
    """Select the transport from configuration (EVENT_BUS env)."""
    if event_bus == "kafka" and kafka_bootstrap_servers:
        return KafkaEventPublisher(kafka_bootstrap_servers)
    if event_bus == "redis" and redis_url:
        import redis.asyncio as redis

        return RedisEventPublisher(redis.from_url(redis_url))
    return NullEventPublisher()
