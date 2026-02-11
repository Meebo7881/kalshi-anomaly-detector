from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://kalshi_user:changeme@postgres:5432/kalshi_detector")
    KALSHI_API_KEY_ID: str = os.getenv("KALSHI_API_KEY_ID", "")
    KALSHI_PRIVATE_KEY_PATH: str = os.getenv("KALSHI_PRIVATE_KEY_PATH", "/app/kalshi_private_key.key")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
