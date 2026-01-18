from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra environment variables
    )
    
    sentinel_env: str = "development"
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    request_timeout_seconds: float = 60.0
    host: str = "0.0.0.0"
    port: int = 8000

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()