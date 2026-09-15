from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jonathan_ai_pm.integrations.security import validate_microsoft_graph_permissions


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "America/Santiago"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/local/jonathan_ai_pm.db"
    microsoft_calendar_enabled: bool = False
    microsoft_calendar_ids: str = "default"
    microsoft_graph_scopes: str = "Calendars.ReadBasic"
    microsoft_graph_timeout_seconds: float = 15.0
    integration_sync_history_retention_days: int = Field(default=90, ge=1, le=3650)
    integration_resolved_review_retention_days: int = Field(default=30, ge=1, le=3650)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_integration_permissions(self) -> Self:
        validate_microsoft_graph_permissions(
            self.microsoft_graph_scopes,
            require_calendar_read=self.microsoft_calendar_enabled,
        )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
