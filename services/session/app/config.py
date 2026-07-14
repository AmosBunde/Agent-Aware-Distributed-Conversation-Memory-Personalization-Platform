from functools import lru_cache

from convmem_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "session"
    port: int = 8004

    redis_url: str = "redis://redis:6379/0"
    session_ttl_seconds: int = 1800

    # Event bus: "redis" (default), "kafka", or "none"
    event_bus: str = "redis"
    kafka_bootstrap_servers: str = "kafka:9092"


@lru_cache
def get_settings() -> Settings:
    return Settings()
