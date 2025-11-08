"""
Configuration settings for the AI Compliance Agent
Production-ready configuration with validation and environment variable support
"""

from typing import Any, Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
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

    # EDGP Master Data Database Configuration
    edgp_db_host: str = Field(default="localhost", description="EDGP database host")
    edgp_db_port: int = Field(default=3306, ge=1, le=65535, description="EDGP database port")
    edgp_db_username: str = Field(default="root", description="EDGP database username")
    edgp_db_password: str = Field(default="password", description="EDGP database password")
    edgp_db_name: str = Field(default="edgp_masterdata", description="EDGP database name")
    edgp_db_secret_name: Optional[str] = Field(default=None, description="AWS Secrets Manager secret name for DB credentials")
    local_db_url: Optional[str] = Field(default=None, description="Local database URL override")
    
    # AWS RDS Configuration (for production/staging environments)
    aws_rds_enabled: bool = Field(default=True, env="AWS_RDS_ENABLED", description="Enable AWS RDS connection")
    aws_rds_host: Optional[str] = Field(default=None, env="AWS_RDS_HOST", description="AWS RDS endpoint")
    aws_rds_port: int = Field(default=3306, ge=1, le=65535, env="AWS_RDS_PORT", description="AWS RDS port")
    aws_rds_database: str = Field(default="masterdata", env="AWS_RDS_DATABASE", description="AWS RDS database name")
    aws_rds_secret_name: Optional[str] = Field(default=None, env="AWS_RDS_SECRET_NAME", description="AWS RDS Secrets Manager secret name")
    aws_secrets_manager_enabled: bool = Field(default=True, env="AWS_SECRETS_MANAGER_ENABLED", description="Use AWS Secrets Manager for credentials")
    aws_secret_name: Optional[str] = Field(default=None, description="AWS Secrets Manager secret name")
    aws_region: str = Field(default="ap-southeast-1", env="AWS_REGION", description="AWS region")

    # Redis Cache
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    redis_max_connections: int = Field(default=50, ge=1)

    # AI/ML Settings
    ai_agent_api_key: Optional[str] = Field(default=None, description="Primary AI Agent API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key (for backward compatibility)")
    ai_secret_name: Optional[str] = Field(default=None, description="AWS Secrets Manager secret name for AI API keys")
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
    
    # PII Protection Settings
    enable_pii_masking: bool = Field(default=True, description="Enable PII masking in logs (disable for development only)")
    
    # Debug Logging Settings
    enable_detailed_request_logging: bool = Field(default=False, description="Enable detailed request logging for debugging")

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
    aws_region: str = Field(default="us-east-1", env="AWS_REGION", description="AWS region")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID", description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY", description="AWS secret access key")
    aws_endpoint_url: Optional[str] = Field(default=None, env="AWS_ENDPOINT_URL", description="Custom AWS endpoint (for LocalStack)")

    # SQS Queue URLs
    sqs_main_queue_url: Optional[str] = Field(default=None, env="SQS_MAIN_QUEUE_URL", description="Main SQS queue URL")
    sqs_dlq_url: Optional[str] = Field(default=None, env="SQS_DLQ_URL", description="Dead letter queue URL")
    sqs_high_priority_queue_url: Optional[str] = Field(default=None, env="SQS_HIGH_PRIORITY_QUEUE_URL", description="High priority queue URL")
    sqs_human_intervention_queue_url: Optional[str] = Field(default=None, env="SQS_HUMAN_INTERVENTION_QUEUE_URL", description="Human intervention queue URL")

    # SQS Configuration
    sqs_message_retention_period: int = Field(default=1209600, ge=60, le=1209600)
    sqs_visibility_timeout: int = Field(default=300, ge=0, le=43200)
    sqs_receive_message_wait_time: int = Field(default=20, ge=0, le=20)
    sqs_max_receive_count: int = Field(default=3, ge=1, le=1000)

    # AWS OpenSearch Configuration
    opensearch_enabled: bool = Field(default=True, env="OPENSEARCH_ENABLED", description="Enable OpenSearch for compliance patterns")
    opensearch_endpoint: Optional[str] = Field(default=None, env="OPENSEARCH_ENDPOINT", description="OpenSearch endpoint URL")
    opensearch_index_name: str = Field(default="edgp-compliance-info", env="OPENSEARCH_INDEX_NAME", description="OpenSearch index name")
    opensearch_timeout: int = Field(default=30, ge=5, le=300, env="OPENSEARCH_TIMEOUT", description="OpenSearch request timeout in seconds")
    opensearch_max_retries: int = Field(default=3, ge=1, le=10, env="OPENSEARCH_MAX_RETRIES", description="OpenSearch max retries")

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
        """Validate environment - K8s uses 'prd' which maps to 'production'"""
        # Map K8s environment names to standard names
        env_mapping = {
            "prd": "production",
            "prod": "production",
            "dev": "development",
            "development": "development",
            "staging": "staging",
            "sit": "sit"
        }
        
        v_lower = v.lower()
        if v_lower in env_mapping:
            return env_mapping[v_lower]
        
        # If not in mapping, check if it's a valid environment name
        allowed = ["development", "staging", "production", "sit", "prd", "prod"]
        if v_lower not in allowed:
            raise ValueError(f"environment must be one of {allowed} (or prd/prod/dev)")
        return v_lower

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"

    def sanitized_copy(self) -> Dict[str, Any]:
        """
        Return a sanitised configuration dictionary with sensitive values redacted.

        Keys containing common secret markers (e.g. 'key', 'token', 'password')
        are masked to avoid leaking credentials in logs.
        """
        data = self.model_dump(mode="python")
        sensitive_markers = ("key", "token", "secret", "password")

        for field, value in data.items():
            if value is None:
                continue

            lower_name = field.lower()
            if any(marker in lower_name for marker in sensitive_markers):
                data[field] = "***REDACTED***"

        return data

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
    from dotenv import load_dotenv
    
    print("=" * 80)
    print("🔧 ENVIRONMENT CONFIGURATION LOADING")
    print("=" * 80)
    
    # First, load base .env to get APP_ENV (without override to set defaults)
    base_env_file = Path(".env")
    if base_env_file.exists():
        print(f"📄 Loading base configuration: .env")
        load_dotenv(base_env_file, override=False)
        print(f"   ✅ Base .env loaded")
    else:
        print(f"   ⚠️  Base .env not found")
    
    # Get APP_ENV from environment or command line
    app_env = os.getenv("APP_ENV", "development")
    print(f"🌍 APP_ENV: {app_env}")
    
    # Determine which env file to load based on APP_ENV
    # File naming: .env.development, .env.sit, .env.prd
    env_file_path = f".env.{app_env}"
    env_file = Path(env_file_path)
    print(f"📂 Looking for file: {env_file_path}")
    
    # Load environment-specific file WITHOUT override
    # This allows K8s-injected env vars (or export commands) to take precedence
    # File values only set defaults for missing variables
    if env_file.exists():
        print(f"📄 Loading environment-specific configuration: {env_file_path}")
        load_dotenv(env_file, override=False)
        print(f"   ✅ {env_file_path} loaded (sets defaults, K8s/export values take precedence)")
    elif not base_env_file.exists():
        print(f"   ⚠️  Neither {env_file_path} nor .env found, using defaults")
    else:
        print(f"   ℹ️  {env_file_path} not found, using base .env only")
    
    # Show what was loaded
    print(f"🔑 Key Configuration Values (from environment):")
    
    # AWS Region - check if it's a placeholder
    aws_region = os.getenv('AWS_REGION', 'N/A')
    if aws_region == 'AWS_REGION':
        print(f"   AWS_REGION: {aws_region} ⚠️  (PLACEHOLDER - K8s should inject real value)")
    else:
        print(f"   AWS_REGION: {aws_region}")
    
    # AWS Credentials - check if they're placeholders
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID', None)
    if aws_access_key:
        if aws_access_key == 'AWS_ACCESS_KEY_ID':
            print(f"   AWS_ACCESS_KEY_ID: {aws_access_key} ⚠️  (PLACEHOLDER - K8s should inject real value)")
        else:
            print(f"   AWS_ACCESS_KEY_ID: {aws_access_key[:10]}... ✅")
    else:
        print(f"   AWS_ACCESS_KEY_ID: N/A")
    
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', None)
    if aws_secret_key:
        if aws_secret_key == 'AWS_SECRET_ACCESS_KEY':
            print(f"   AWS_SECRET_ACCESS_KEY: {aws_secret_key} ⚠️  (PLACEHOLDER - K8s should inject real value)")
        else:
            print(f"   AWS_SECRET_ACCESS_KEY: ****** ✅")
    else:
        print(f"   AWS_SECRET_ACCESS_KEY: N/A")
    
    print(f"   ENVIRONMENT: {os.getenv('ENVIRONMENT', 'N/A')}")
    print(f"   AWS_RDS_ENABLED: {os.getenv('AWS_RDS_ENABLED', 'N/A')}")
    print(f"   AWS_RDS_SECRET_NAME: {os.getenv('AWS_RDS_SECRET_NAME', 'N/A')}")
    print(f"   OPENSEARCH_ENABLED: {os.getenv('OPENSEARCH_ENABLED', 'N/A')}")
    
    # Check if running in K8s
    if os.path.exists('/var/run/secrets/kubernetes.io'):
        print(f"   🏗️  Running in Kubernetes cluster")
    elif os.getenv('KUBERNETES_SERVICE_HOST'):
        print(f"   🏗️  Running in Kubernetes cluster")
    else:
        print(f"   💻 Running locally (not in K8s)")
        if aws_region == 'AWS_REGION' or aws_access_key == 'AWS_ACCESS_KEY_ID':
            print(f"   ⚠️  WARNING: Placeholder values detected! These will cause failures.")
            print(f"   ℹ️  For local testing, use .env.development or .env.sit instead.")
    print("=" * 80)
    
    # Create settings - Pydantic will read from os.environ which now has the correct overrides
    return Settings()


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
