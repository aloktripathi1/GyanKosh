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


@lru_cache
def get_settings() -> Settings:
    return Settings()
