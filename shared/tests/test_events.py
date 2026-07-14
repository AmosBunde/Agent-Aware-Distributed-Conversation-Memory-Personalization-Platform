import json

from convmem_shared.events import NullEventPublisher, RedisEventPublisher


class FakeRedis:
    def __init__(self, healthy: bool = True):
        self.healthy = healthy
        self.streams: dict[str, list[dict]] = {}

    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        if not self.healthy:
            raise ConnectionError("redis down")
        self.streams.setdefault(stream, []).append(fields)


async def test_publish_writes_prefixed_stream_with_timestamp():
    redis = FakeRedis()
    publisher = RedisEventPublisher(redis)
    ok = await publisher.publish("memory.stored", {"user_id": "u1"})
    assert ok is True
    [entry] = redis.streams["convmem.events.memory.stored"]
    payload = json.loads(entry["payload"])
    assert payload["user_id"] == "u1"
    assert "emitted_at" in payload


async def test_publish_swallows_bus_outage():
    publisher = RedisEventPublisher(FakeRedis(healthy=False))
    assert await publisher.publish("memory.stored", {"user_id": "u1"}) is False


async def test_null_publisher_is_noop():
    assert await NullEventPublisher().publish("anything", {}) is False
