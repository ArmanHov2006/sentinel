from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from sentinel.shield.pii_shield import PIIAction


class PIISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PII_", extra="ignore")
    action: PIIAction = PIIAction.REDACT


class InjectionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INJECTION_", extra="ignore")
    block_threshold: float = 0.9
    warn_threshold: float = 0.7


class RetrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RETRY_", extra="ignore")
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 40.0


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")
    host: str = "localhost"
    port: int = 6379
    socket_timeout: float = 5.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sentinel_env: str = "development"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    request_timeout_seconds: float = 60.0
    host: str = "0.0.0.0"
    port: int = 8000

    # Nested settings
    pii: PIISettings = PIISettings()
    injection: InjectionSettings = InjectionSettings()
    retry: RetrySettings = RetrySettings()
    redis: RedisSettings = RedisSettings()

    # Rate limiting (could also be nested)
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
