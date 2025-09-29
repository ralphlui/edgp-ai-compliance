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

    # Remediation Agent Settings
    remediation_agent_enabled: bool = True
    remediation_max_concurrent_workflows: int = 10
    remediation_default_timeout_hours: int = 72
    remediation_enable_notifications: bool = True
    remediation_auto_retry_failed: bool = True
    remediation_max_retry_attempts: int = 3

    # AWS SQS Settings
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # SQS Queue URLs
    sqs_main_queue_url: Optional[str] = None
    sqs_dlq_url: Optional[str] = None
    sqs_high_priority_queue_url: Optional[str] = None
    sqs_human_intervention_queue_url: Optional[str] = None

    # SQS Configuration
    sqs_message_retention_period: int = 1209600  # 14 days
    sqs_visibility_timeout: int = 300  # 5 minutes
    sqs_receive_message_wait_time: int = 20  # long polling
    sqs_max_receive_count: int = 3
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()