from functools import lru_cache

from convmem_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "gateway"
    port: int = 8000

    # Opt-in shared API key: when set, every /api/v1/* request must send it
    # in the X-API-Key header. Empty (the default) leaves the gateway open
    # for local development.
    gateway_api_key: str = ""

    rate_limit_rps: float = 20.0
    rate_limit_burst: int = 40

    circuit_failure_threshold: int = 5
    circuit_reset_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
