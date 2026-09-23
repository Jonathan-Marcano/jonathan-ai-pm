from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "America/Santiago"
    log_level: str = "INFO"
    database_url: str = Field(
        default="sqlite:///data/local/cuentafaro.db",
        validation_alias="CUENTAFARO_DATABASE_URL",
    )
    base_currency: str = "CLP"
    whatsapp_enabled: bool = False
    llm_provider: str = ""
    llm_api_key: str = ""
    messaging_provider: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
