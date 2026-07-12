"""Environment-driven settings shared by every service.

Each service subclasses :class:`BaseServiceSettings` and adds its own fields.
All values come from environment variables (or a local ``.env`` file), so the
same image runs unchanged in compose, Kubernetes, or a bare VM.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "service"
    host: str = "0.0.0.0"
    port: int = 8000

    # Upstream service URLs (compose DNS names by default; override per env)
    memory_service_url: str = "http://memory:8001"
    personalization_service_url: str = "http://personalization:8002"
    embedding_service_url: str = "http://embedding:8003"
    session_service_url: str = "http://session:8004"

    # Shared client behaviour
    http_timeout_seconds: float = 10.0
    http_retries: int = 2
