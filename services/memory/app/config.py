from functools import lru_cache

from convmem_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "memory"
    port: int = 8001

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "convmem"
    postgres_user: str = "convmem"
    postgres_password: str = "convmem-dev-password"

    # Ranking weights: score = w_similarity * cosine + w_recency * exp(-age/half_life)
    rank_weight_similarity: float = 0.75
    rank_weight_recency: float = 0.25
    rank_recency_half_life_seconds: float = 7 * 24 * 3600  # one week

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
