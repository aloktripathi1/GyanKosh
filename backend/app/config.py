from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/gyankosh"
    redis_url: str = "redis://localhost:6379/0"
    storage_backend: str = "local"
    local_storage_path: str = "./storage_data"
    api_key: str = "dev-local-key"
    # Comma-separated list of allowed frontend origins, e.g.
    # "https://gyankosh-frontend.onrender.com,https://app.example.com".
    # Defaults to the local Vite dev server only.
    cors_allowed_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
