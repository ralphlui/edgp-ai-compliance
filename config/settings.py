"""
Configuration settings for the AI Compliance Agent
Production-ready configuration with validation and environment variable support
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    """Application settings with environment variable support and validation"""

    # Application
    app_env: str = Field(default="development", description="Application environment for config file selection")
    app_name: str = Field(default="AI Compliance Agent", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment: development, staging, production")

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port number")
    api_workers: int = Field(default=4, ge=1, le=32, description="Number of API workers")
    api_timeout: int = Field(default=60, ge=1, description="API request timeout in seconds")

    # Database
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/compliance_db",
        description="Database connection URL"
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    database_pool_timeout: int = Field(default=30, ge=1)
    database_pool_recycle: int = Field(default=3600, ge=300)

    # Redis Cache
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    redis_max_connections: int = Field(default=50, ge=1)

    # AI/ML Settings
    ai_agent_api_key: Optional[str] = Field(default=None, description="Primary AI Agent API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key (for backward compatibility)")
    ai_model_name: str = Field(default="gpt-3.5-turbo", description="AI model name")
    ai_max_tokens: int = Field(default=2000, ge=100, le=32000)
    ai_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    ai_timeout: int = Field(default=30, ge=5, le=120)

    # Security
    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT tokens"
    )
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    algorithm: str = Field(default="HS256", description="JWT algorithm")

    # CORS
    allowed_origins: List[str] = Field(default=["*"], description="Allowed CORS origins")
    allowed_methods: List[str] = Field(default=["*"])
    allowed_headers: List[str] = Field(default=["*"])

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")

    # Compliance Engine
    enable_ai_analysis: bool = Field(default=True)
    default_frameworks: List[str] = Field(default=["pdpa_singapore", "gdpr_eu"])
    max_assessment_time: int = Field(default=300, ge=30, le=3600)

    # Data Retention
    default_retention_days: int = Field(default=2555, ge=1)
    audit_log_retention_days: int = Field(default=2555, ge=365)

    # Notifications
    email_enabled: bool = Field(default=False)
    smtp_server: Optional[str] = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = Field(default=True)

    # Singapore-specific settings
    pdpc_notification_threshold: int = Field(default=500, ge=1)
    pdpc_notification_timeframe_hours: int = Field(default=72, ge=1)

    # Remediation Agent Settings
    remediation_agent_enabled: bool = Field(default=True)
    remediation_max_concurrent_workflows: int = Field(default=10, ge=1, le=100)
    remediation_default_timeout_hours: int = Field(default=72, ge=1)
    remediation_enable_notifications: bool = Field(default=True)
    remediation_auto_retry_failed: bool = Field(default=True)
    remediation_max_retry_attempts: int = Field(default=3, ge=1, le=10)

    # AWS SQS Settings
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key")
    aws_endpoint_url: Optional[str] = Field(default=None, description="Custom AWS endpoint (for LocalStack)")

    # SQS Queue URLs
    sqs_main_queue_url: Optional[str] = None
    sqs_dlq_url: Optional[str] = None
    sqs_high_priority_queue_url: Optional[str] = None
    sqs_human_intervention_queue_url: Optional[str] = None

    # SQS Configuration
    sqs_message_retention_period: int = Field(default=1209600, ge=60, le=1209600)
    sqs_visibility_timeout: int = Field(default=300, ge=0, le=43200)
    sqs_receive_message_wait_time: int = Field(default=20, ge=0, le=20)
    sqs_max_receive_count: int = Field(default=3, ge=1, le=1000)

    # Health Check
    health_check_interval: int = Field(default=30, ge=5, description="Health check interval in seconds")

    # Metrics
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, ge=1, le=65535, description="Prometheus metrics port")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment"""
        allowed = ["development", "staging", "production"]
        v = v.lower()
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"

    def validate_required_secrets(self) -> List[str]:
        """Validate that required secrets are set"""
        missing = []

        if self.is_production():
            if not self.openai_api_key:
                missing.append("OPENAI_API_KEY")
            if self.secret_key == "your-secret-key-change-in-production":
                missing.append("SECRET_KEY")
            if "*" in self.allowed_origins:
                missing.append("ALLOWED_ORIGINS (should not be '*' in production)")

        return missing


def create_settings() -> Settings:
    """Create settings instance with environment-specific configuration loading"""
    import os
    from pathlib import Path
    
    # First, load base .env to get APP_ENV
    base_env_file = Path(".env")
    if base_env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(base_env_file)
    
    # Get APP_ENV from environment or command line
    app_env = os.getenv("APP_ENV", "development")
    
    # Determine which env file to load based on APP_ENV
    env_file_path = f".env.{app_env}"
    env_file = Path(env_file_path)
    
    # If specific env file doesn't exist, fall back to .env
    if not env_file.exists():
        env_file = base_env_file
        if not env_file.exists():
            print(f"Warning: Neither {env_file_path} nor .env found, using defaults")
    else:
        print(f"Loading configuration from: {env_file_path}")
    
    # Create settings with the appropriate env file
    class EnvironmentSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=str(env_file) if env_file.exists() else None,
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore"
        )
    
    return EnvironmentSettings()


# Global settings instance
settings = create_settings()

# Validate settings on import
if settings.is_production():
    missing = settings.validate_required_secrets()
    if missing:
        import warnings
        warnings.warn(
            f"Production mode detected but missing required configuration: {', '.join(missing)}",
            RuntimeWarning
        )