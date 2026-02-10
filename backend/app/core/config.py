from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    KALSHI_API_KEY: str
    KALSHI_API_SECRET: str
    
    # Database
    DATABASE_URL: str = "postgresql://kalshi_user:kalshi_pass@postgres:5432/kalshi_detector"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # App Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Kalshi Anomaly Detector"
    
    # Detection Thresholds
    VOLUME_THRESHOLD: float = 3.0
    PRICE_THRESHOLD: float = 2.5
    HIGH_ALERT_SCORE: float = 7.5
    MEDIUM_ALERT_SCORE: float = 5.0
    
    # Monitoring
    BASELINE_WINDOW_DAYS: int = 30
    UPDATE_INTERVAL_MINUTES: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
