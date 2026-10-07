from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Mobile Diagnostics API"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, validation_alias="DEBUG")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        validation_alias="CORS_ORIGINS",
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/mobile_diagnostics",
        validation_alias="DATABASE_URL",
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Security
    secret_key: str = Field(
        default="dev-secret-change-in-production",
        validation_alias="SECRET_KEY",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ADB
    adb_path: str = Field(default="adb", validation_alias="ADB_PATH")
    adb_timeout: int = 30

    # iOS (libimobiledevice)
    idevice_id_path: str = Field(default="idevice_id", validation_alias="IDEVICE_ID_PATH")
    idevice_info_path: str = Field(default="ideviceinfo", validation_alias="IDEVICE_INFO_PATH")
    idevice_backup_path: str = Field(default="idevicebackup2", validation_alias="IDEVICE_BACKUP_PATH")
    ios_timeout: int = 60

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")  # json or console


@lru_cache
def get_settings() -> Settings:
    return Settings()
