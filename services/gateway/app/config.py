from functools import lru_cache

from convmem_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "gateway"
    port: int = 8000

    rate_limit_rps: float = 20.0
    rate_limit_burst: int = 40

    circuit_failure_threshold: int = 5
    circuit_reset_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
