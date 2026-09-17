from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "America/Santiago"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/local/faroflow.db"
    microsoft_calendar_enabled: bool = False
    microsoft_calendar_ids: str = "default"
    microsoft_graph_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
