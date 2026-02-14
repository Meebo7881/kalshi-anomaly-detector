from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Kalshi Anomaly Detector"
    VERSION: str = "1.3.0"
    DESCRIPTION: str = "Real-time monitoring for suspicious trading patterns"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://kalshi_user:changeme@postgres:5432/kalshi_detector")
    
    # Kalshi API
    KALSHI_API_KEY_ID: str = os.getenv("KALSHI_API_KEY_ID", "")
    KALSHI_PRIVATE_KEY_PATH: str = os.getenv("KALSHI_PRIVATE_KEY_PATH", "/app/kalshi_private_key.key")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
    
    # Application Settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Monitoring Settings
    UPDATE_INTERVAL_SECONDS: int = int(os.getenv("UPDATE_INTERVAL_SECONDS", "300"))
    DETECTION_INTERVAL_SECONDS: int = int(os.getenv("DETECTION_INTERVAL_SECONDS", "300"))
    
    # NEW: Market categories to monitor
    MONITORED_CATEGORIES: List[str] = [
        "Politics",
        "Economics", 
        "Weather",
        "Entertainment",
        "Finance",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
