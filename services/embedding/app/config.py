from functools import lru_cache

from convmem_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "embedding"
    port: int = 8003

    embedding_backend: str = "local"  # "local" | "openai"
    embedding_dim: int = 384
    openai_api_key: str = ""
    openai_model: str = "text-embedding-3-small"


@lru_cache
def get_settings() -> Settings:
    return Settings()
