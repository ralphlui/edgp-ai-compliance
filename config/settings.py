"""
Configuration settings for the AI Compliance Agent
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_name: str = "AI Compliance Agent"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/compliance_db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Redis Cache
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600  # 1 hour
    
    # AI/ML Settings
    openai_api_key: Optional[str] = None
    ai_model_name: str = "gpt-3.5-turbo"
    ai_max_tokens: int = 2000
    ai_temperature: float = 0.1
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"
    
    # CORS
    allowed_origins: List[str] = ["*"]
    allowed_methods: List[str] = ["*"]
    allowed_headers: List[str] = ["*"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Compliance Engine
    enable_ai_analysis: bool = True
    default_frameworks: List[str] = ["pdpa_singapore", "gdpr_eu"]
    max_assessment_time: int = 300  # 5 minutes
    
    # Data Retention
    default_retention_days: int = 2555  # 7 years
    audit_log_retention_days: int = 2555
    
    # Notifications
    email_enabled: bool = False
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    # Singapore-specific settings
    pdpc_notification_threshold: int = 500  # subjects affected
    pdpc_notification_timeframe_hours: int = 72
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()