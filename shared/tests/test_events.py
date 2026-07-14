import json

from convmem_shared.events import (
    KafkaEventPublisher,
    NullEventPublisher,
    RedisEventPublisher,
    build_publisher,
)


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


class FakeKafkaProducer:
    def __init__(self, healthy: bool = True):
        self.healthy = healthy
        self.sent: list[tuple[str, bytes]] = []

    async def send_and_wait(self, topic, value):
        if not self.healthy:
            raise ConnectionError("broker down")
        self.sent.append((topic, value))


async def test_kafka_publish_prefixes_topic_and_stamps_payload():
    producer = FakeKafkaProducer()
    publisher = KafkaEventPublisher("kafka:9092", producer=producer)
    ok = await publisher.publish("memory.stored", {"user_id": "u1"})
    assert ok is True
    [(topic, value)] = producer.sent
    assert topic == "convmem.events.memory.stored"
    payload = json.loads(value)
    assert payload["user_id"] == "u1" and "emitted_at" in payload


async def test_kafka_outage_is_swallowed_and_producer_reset():
    publisher = KafkaEventPublisher("kafka:9092", producer=FakeKafkaProducer(healthy=False))
    assert await publisher.publish("memory.stored", {}) is False
    assert publisher._producer is None  # rebuilt on next attempt


def test_build_publisher_selects_transport():
    assert isinstance(
        build_publisher("kafka", kafka_bootstrap_servers="k:9092"), KafkaEventPublisher
    )
    assert isinstance(build_publisher("redis", redis_url="redis://r/0"), RedisEventPublisher)
    assert isinstance(build_publisher("none"), NullEventPublisher)
    assert isinstance(build_publisher("kafka"), NullEventPublisher)  # no servers -> null
