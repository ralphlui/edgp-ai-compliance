"""
AI API Key Management Service using AWS Secrets Manager
Provides secure retrieval of AI/OpenAI API keys from AWS Secrets Manager
"""

import logging
import json
import os
from typing import Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AISecretsManager:
    """Service for retrieving AI API credentials from AWS Secrets Manager"""

    def __init__(self, region_name: Optional[str] = None):
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-southeast-1")
        self._client = None
        self._cache = {}  # Simple in-memory cache for API keys

    def _get_client(self):
        """Get or create Secrets Manager client"""
        if not self._client:
            self._client = boto3.client(
                'secretsmanager',
                region_name=self.region_name
            )
        return self._client

    def get_secret(self, secret_name: str, use_cache: bool = True) -> dict:
        """
        Retrieve AI API credentials from AWS Secrets Manager

        Args:
            secret_name: Name of the secret in AWS Secrets Manager
            use_cache: Whether to use cached value if available

        Returns:
            Dictionary containing API credentials

        Raises:
            ClientError: If secret cannot be retrieved
        """
        # Check cache first
        if use_cache and secret_name in self._cache:
            logger.debug(f"Using cached secret for: {secret_name}")
            return self._cache[secret_name]

        try:
            client = self._get_client()

            logger.info(f"Retrieving AI API secret: {secret_name}")
            response = client.get_secret_value(SecretId=secret_name)

            # Parse the secret value
            secret_string = response['SecretString']
            secret_dict = json.loads(secret_string)

            # Cache the result
            self._cache[secret_name] = secret_dict

            logger.info("Successfully retrieved AI API credentials from Secrets Manager")
            return secret_dict

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'DecryptionFailureException':
                logger.error("Secrets Manager can't decrypt the protected secret text using the provided KMS key")
            elif error_code == 'InternalServiceErrorException':
                logger.error("An error occurred on the server side")
            elif error_code == 'InvalidParameterException':
                logger.error("You provided an invalid value for a parameter")
            elif error_code == 'InvalidRequestException':
                logger.error("You provided a parameter value that is not valid for the current state of the resource")
            elif error_code == 'ResourceNotFoundException':
                logger.error(f"The requested secret {secret_name} was not found")
            else:
                logger.error(f"Unknown error retrieving secret: {error_code}")

            raise e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret JSON: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret: {str(e)}")
            raise e

    def get_openai_api_key(self, secret_name: Optional[str] = None) -> Optional[str]:
        """
        Retrieve OpenAI API key from AWS Secrets Manager or environment variables

        Args:
            secret_name: Name of the secret in AWS Secrets Manager
                        If not provided, will try to get from environment variable AI_SECRET_NAME

        Returns:
            OpenAI API key string, or None if not found
        """
        # First, try environment variables (for local development)
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key and not self._is_placeholder(env_key):
            logger.info("Using OPENAI_API_KEY from environment variable")
            return env_key

        # Check for AI_AGENT_API_KEY as fallback
        env_key = os.getenv("AI_AGENT_API_KEY")
        if env_key and not self._is_placeholder(env_key):
            logger.info("Using AI_AGENT_API_KEY from environment variable")
            return env_key

        # Try to get from Secrets Manager
        secret_name = secret_name or os.getenv("AI_SECRET_NAME") or os.getenv("AWS_SECRET_NAME")
        if not secret_name:
            logger.warning("No AI_SECRET_NAME or AWS_SECRET_NAME configured, cannot fetch from Secrets Manager")
            return None

        try:
            secret_dict = self.get_secret(secret_name)

            # Try common key names in the secret
            for key_name in ["ai_agent_api_key", "AI_AGENT_API_KEY", "openai_api_key", "OPENAI_API_KEY", "api_key", "API_KEY"]:
                if key_name in secret_dict:
                    api_key = secret_dict[key_name]
                    if api_key and not self._is_placeholder(api_key):
                        logger.info(f"Successfully retrieved OpenAI API key from Secrets Manager using key: {key_name}")
                        return api_key

            logger.warning(f"Secret {secret_name} found but no valid OpenAI API key in expected fields")
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve OpenAI API key from Secrets Manager: {str(e)}")
            return None

    def get_langchain_api_key(self, secret_name: Optional[str] = None) -> Optional[str]:
        """
        Retrieve LangChain (LangSmith) API key from AWS Secrets Manager or environment variables

        Args:
            secret_name: Name of the secret in AWS Secrets Manager
                        If not provided, will try to get from environment variable AI_SECRET_NAME

        Returns:
            LangChain API key string, or None if not found
        """
        # First, try environment variables (for local development)
        env_key = os.getenv("LANGCHAIN_API_KEY")
        if env_key and not self._is_placeholder(env_key):
            logger.info("Using LANGCHAIN_API_KEY from environment variable")
            return env_key

        # Try to get from Secrets Manager
        secret_name = secret_name or os.getenv("AI_SECRET_NAME") or os.getenv("AWS_SECRET_NAME")
        if not secret_name:
            logger.warning("No AI_SECRET_NAME or AWS_SECRET_NAME configured, cannot fetch LangChain API key from Secrets Manager")
            return None

        try:
            secret_dict = self.get_secret(secret_name)

            # Try common key names in the secret
            for key_name in ["langchain_api_key", "LANGCHAIN_API_KEY", "langsmith_api_key", "LANGSMITH_API_KEY"]:
                if key_name in secret_dict:
                    api_key = secret_dict[key_name]
                    if api_key and not self._is_placeholder(api_key):
                        logger.info(f"Successfully retrieved LangChain API key from Secrets Manager using key: {key_name}")
                        return api_key

            logger.warning(f"Secret {secret_name} found but no valid LangChain API key in expected fields")
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve LangChain API key from Secrets Manager: {str(e)}")
            return None

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        """Check if the value is a placeholder and not a real API key"""
        placeholder_patterns = [
            "placeholder",
            "your_key_here", 
            "api_key_here",
            "openai_api_key_here",
            "ai_agent_api_key_here",
            "sit_openai",
            "sit_ai_agent",
            "test-key",
            "xxx",
            "will_use_secrets_manager",  # Our new placeholder pattern
        ]

        value_lower = value.lower()
        return any(pattern in value_lower for pattern in placeholder_patterns)

    def clear_cache(self):
        """Clear the cached secrets"""
        self._cache.clear()
        logger.info("Cleared AI secrets cache")


# Global instance for convenience
_ai_secrets_manager = None


def get_ai_secrets_manager() -> AISecretsManager:
    """Get or create global AISecretsManager instance"""
    global _ai_secrets_manager
    if _ai_secrets_manager is None:
        _ai_secrets_manager = AISecretsManager()
    return _ai_secrets_manager


def get_openai_api_key(secret_name: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to get OpenAI API key

    Args:
        secret_name: Optional secret name in AWS Secrets Manager

    Returns:
        OpenAI API key or None
    """
    manager = get_ai_secrets_manager()
    return manager.get_openai_api_key(secret_name)


def get_langchain_api_key(secret_name: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to get LangChain API key

    Args:
        secret_name: Optional secret name in AWS Secrets Manager

    Returns:
        LangChain API key or None
    """
    manager = get_ai_secrets_manager()
    return manager.get_langchain_api_key(secret_name)
