from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "America/Santiago"
    log_level: str = "INFO"
    database_url: str = "sqlite:///data/local/faroflow.db"
    microsoft_calendar_enabled: bool = False
    microsoft_calendar_ids: str = "default"
    microsoft_graph_scopes: str = "Calendars.ReadBasic"
    microsoft_graph_timeout_seconds: float = 15.0
    integration_sync_history_retention_days: int = Field(default=90, ge=1, le=3650)
    integration_operations_enabled: bool = False
    integration_operation_key: SecretStr | None = None
    integration_max_sync_window_days: int = Field(default=31, ge=1, le=366)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_integration_operations(self) -> Self:
        if self.integration_operations_enabled:
            key = (
                self.integration_operation_key.get_secret_value()
                if self.integration_operation_key
                else ""
            )
            if len(key) < 32:
                raise ValueError(
                    "INTEGRATION_OPERATION_KEY must contain at least 32 characters "
                    "when operations are enabled"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
