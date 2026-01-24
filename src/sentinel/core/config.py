from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore"
    )    
    host: str = "localhost"
    port: int = 6379
    socket_timeout: float = 5.0

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    sentinel_env: str = "development"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    request_timeout_seconds: float = 60.0
    host: str = "0.0.0.0"
    port: int = 8000
    redis: RedisSettings = RedisSettings()

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()