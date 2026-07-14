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

    # Must match the vector(N) column in scripts/initdb.sql and the
    # embedding service's EMBEDDING_DIM.
    embedding_dim: int = 384

    # Event bus: "redis" (default), "kafka", or "none"
    event_bus: str = "redis"
    redis_url: str = "redis://redis:6379/0"
    kafka_bootstrap_servers: str = "kafka:9092"

    # SQL migrations applied on startup (memory service owns the schema)
    migrations_dir: str = "scripts/migrations"

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
