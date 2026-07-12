from functools import lru_cache

from convmem_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "personalization"
    port: int = 8002

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "convmem"
    postgres_user: str = "convmem"
    postgres_password: str = "convmem-dev-password"

    profile_history_window: int = 200  # memories considered when building a profile
    profile_top_intents: int = 5

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
