"""
Unit tests for AI Secrets Manager Service
Tests the fetching of OpenAI API keys from AWS Secrets Manager
"""

import pytest
import json
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError

from src.compliance_agent.services.ai_secrets_service import (
    AISecretsManager,
    get_ai_secrets_manager,
    get_openai_api_key
)


class TestAISecretsManager:
    """Test AISecretsManager class"""

    @pytest.fixture
    def secrets_manager(self):
        """Create a secrets manager instance"""
        return AISecretsManager(region_name="us-east-1")

    @pytest.fixture
    def mock_boto3_client(self):
        """Mock boto3 Secrets Manager client"""
        mock_client = MagicMock()
        return mock_client

    def test_init_default_region(self):
        """Test initialization with default region"""
        with patch.dict('os.environ', {}, clear=True):
            manager = AISecretsManager()
            assert manager.region_name == "ap-southeast-1"

    def test_init_custom_region(self):
        """Test initialization with custom region"""
        manager = AISecretsManager(region_name="us-west-2")
        assert manager.region_name == "us-west-2"

    def test_init_from_env_variable(self):
        """Test initialization reads region from AWS_REGION env var"""
        with patch.dict('os.environ', {'AWS_REGION': 'eu-west-1'}):
            manager = AISecretsManager()
            assert manager.region_name == "eu-west-1"

    def test_get_client_creates_client(self, secrets_manager):
        """Test that _get_client creates a boto3 client"""
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client

            client = secrets_manager._get_client()

            mock_boto.assert_called_once_with(
                'secretsmanager',
                region_name='us-east-1'
            )
            assert client == mock_client

    def test_get_client_reuses_client(self, secrets_manager):
        """Test that _get_client reuses existing client"""
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client

            client1 = secrets_manager._get_client()
            client2 = secrets_manager._get_client()

            # Should only create client once
            mock_boto.assert_called_once()
            assert client1 == client2

    def test_get_secret_success(self, secrets_manager, mock_boto3_client):
        """Test successful secret retrieval"""
        secret_data = {"openai_api_key": "sk-test-key", "username": "user"}
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
            result = secrets_manager.get_secret("test/secret")

            mock_boto3_client.get_secret_value.assert_called_once_with(SecretId="test/secret")
            assert result == secret_data

    def test_get_secret_uses_cache(self, secrets_manager, mock_boto3_client):
        """Test that get_secret uses cache on second call"""
        secret_data = {"openai_api_key": "sk-test-key"}
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
            # First call
            result1 = secrets_manager.get_secret("test/secret", use_cache=True)
            # Second call
            result2 = secrets_manager.get_secret("test/secret", use_cache=True)

            # Should only call AWS once
            mock_boto3_client.get_secret_value.assert_called_once()
            assert result1 == result2 == secret_data

    def test_get_secret_bypass_cache(self, secrets_manager, mock_boto3_client):
        """Test that get_secret can bypass cache"""
        secret_data = {"openai_api_key": "sk-test-key"}
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
            # First call
            secrets_manager.get_secret("test/secret", use_cache=True)
            # Second call with cache disabled
            secrets_manager.get_secret("test/secret", use_cache=False)

            # Should call AWS twice
            assert mock_boto3_client.get_secret_value.call_count == 2

    def test_get_secret_decryption_failure(self, secrets_manager, mock_boto3_client):
        """Test handling of decryption failure"""
        mock_boto3_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'DecryptionFailureException'}},
            'GetSecretValue'
        )

        with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
            with pytest.raises(ClientError):
                secrets_manager.get_secret("test/secret")

    def test_get_secret_not_found(self, secrets_manager, mock_boto3_client):
        """Test handling of secret not found"""
        mock_boto3_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetSecretValue'
        )

        with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
            with pytest.raises(ClientError):
                secrets_manager.get_secret("test/secret")

    def test_get_secret_invalid_json(self, secrets_manager, mock_boto3_client):
        """Test handling of invalid JSON in secret"""
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': "not valid json{"
        }

        with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
            with pytest.raises(json.JSONDecodeError):
                secrets_manager.get_secret("test/secret")

    def test_get_openai_api_key_from_env_openai_key(self, secrets_manager):
        """Test get_openai_api_key returns env var OPENAI_API_KEY"""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-real-key'}):
            api_key = secrets_manager.get_openai_api_key()
            assert api_key == 'sk-real-key'

    def test_get_openai_api_key_from_env_ai_agent_key(self, secrets_manager):
        """Test get_openai_api_key returns env var AI_AGENT_API_KEY"""
        with patch.dict('os.environ', {'AI_AGENT_API_KEY': 'sk-real-key'}, clear=True):
            api_key = secrets_manager.get_openai_api_key()
            assert api_key == 'sk-real-key'

    def test_get_openai_api_key_skips_placeholder(self, secrets_manager):
        """Test get_openai_api_key skips placeholder values"""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'sit_openai_api_key_here'}, clear=True):
            with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}):
                with patch.object(secrets_manager, 'get_secret') as mock_get_secret:
                    mock_get_secret.return_value = {"openai_api_key": "sk-real-key"}

                    api_key = secrets_manager.get_openai_api_key()

                    # Should have called Secrets Manager instead of using placeholder
                    mock_get_secret.assert_called_once()
                    assert api_key == 'sk-real-key'

    def test_get_openai_api_key_from_secrets_manager(self, secrets_manager, mock_boto3_client):
        """Test get_openai_api_key retrieves from Secrets Manager"""
        secret_data = {"openai_api_key": "sk-from-secrets-manager"}
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.dict('os.environ', {'AI_SECRET_NAME': 'sit/edgp/secret'}, clear=True):
            with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
                api_key = secrets_manager.get_openai_api_key()
                assert api_key == 'sk-from-secrets-manager'

    def test_get_openai_api_key_tries_multiple_key_names(self, secrets_manager, mock_boto3_client):
        """Test get_openai_api_key tries different key names in secret"""
        # Secret has uppercase key name
        secret_data = {"OPENAI_API_KEY": "sk-uppercase-key"}
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
            with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
                api_key = secrets_manager.get_openai_api_key()
                assert api_key == 'sk-uppercase-key'

    def test_get_openai_api_key_no_secret_name(self, secrets_manager):
        """Test get_openai_api_key returns None when no AI_SECRET_NAME configured"""
        with patch.dict('os.environ', {}, clear=True):
            api_key = secrets_manager.get_openai_api_key()
            assert api_key is None

    def test_get_openai_api_key_secret_has_no_api_key(self, secrets_manager, mock_boto3_client):
        """Test get_openai_api_key returns None when secret has no API key field"""
        secret_data = {"username": "user", "password": "pass"}  # No API key
        mock_boto3_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
            with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
                api_key = secrets_manager.get_openai_api_key()
                assert api_key is None

    def test_get_openai_api_key_secrets_manager_error(self, secrets_manager, mock_boto3_client):
        """Test get_openai_api_key handles Secrets Manager errors gracefully"""
        mock_boto3_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'InternalServiceErrorException'}},
            'GetSecretValue'
        )

        with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
            with patch.object(secrets_manager, '_get_client', return_value=mock_boto3_client):
                api_key = secrets_manager.get_openai_api_key()
                assert api_key is None

    def test_is_placeholder_key_detects_placeholders(self, secrets_manager):
        """Test _is_placeholder detects placeholder values"""
        placeholders = [
            "placeholder",
            "your_key_here",
            "api_key_here",
            "openai_api_key_here",
            "sit_openai_api_key_here",
            "test-key",
            "xxx",
        ]

        for placeholder in placeholders:
            assert secrets_manager._is_placeholder(placeholder) is True

    def test_is_placeholder_key_accepts_real_keys(self, secrets_manager):
        """Test _is_placeholder accepts real API keys"""
        real_keys = [
            "sk-proj-abc123def456",
            "sk-real-key-12345",
            "actual-api-key",
        ]

        for key in real_keys:
            assert secrets_manager._is_placeholder(key) is False

    def test_clear_cache(self, secrets_manager):
        """Test clear_cache clears the cache"""
        secrets_manager._cache = {"test/secret": {"key": "value"}}
        secrets_manager.clear_cache()
        assert secrets_manager._cache == {}


class TestGlobalFunctions:
    """Test module-level convenience functions"""

    def test_get_ai_secrets_manager_singleton(self):
        """Test get_ai_secrets_manager returns singleton instance"""
        # Clear any existing singleton
        import src.compliance_agent.services.ai_secrets_service as service_module
        service_module._ai_secrets_manager = None

        manager1 = get_ai_secrets_manager()
        manager2 = get_ai_secrets_manager()

        assert manager1 is manager2

    def test_get_openai_api_key_convenience_function(self):
        """Test get_openai_api_key convenience function"""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-real-api-key-12345'}, clear=True):
            # Clear singleton cache AND internal cache INSIDE the context manager
            import src.compliance_agent.services.ai_secrets_service as service_module
            if service_module._ai_secrets_manager:
                service_module._ai_secrets_manager.clear_cache()
            service_module._ai_secrets_manager = None

            api_key = get_openai_api_key()
            assert api_key == 'sk-real-api-key-12345'

    def test_get_openai_api_key_with_custom_secret_name(self):
        """Test get_openai_api_key with custom secret name"""
        mock_manager = MagicMock()
        mock_manager.get_openai_api_key.return_value = 'sk-custom-key'

        with patch('src.compliance_agent.services.ai_secrets_service.get_ai_secrets_manager', return_value=mock_manager):
            api_key = get_openai_api_key(secret_name='custom/secret')

            mock_manager.get_openai_api_key.assert_called_once_with('custom/secret')
            assert api_key == 'sk-custom-key'


class TestIntegrationScenarios:
    """Test realistic integration scenarios"""

    def test_full_flow_env_to_secrets_manager(self):
        """Test complete flow from environment to Secrets Manager"""
        # Setup: placeholder in env, real key in Secrets Manager
        secret_data = {"openai_api_key": "sk-real-production-key"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        # Clear singleton cache
        import src.compliance_agent.services.ai_secrets_service as service_module
        if service_module._ai_secrets_manager:
            service_module._ai_secrets_manager.clear_cache()
        service_module._ai_secrets_manager = None

        with patch.dict('os.environ', {
            'OPENAI_API_KEY': 'sit_openai_api_key_here',  # Placeholder
            'AI_SECRET_NAME': 'sit/edgp/secret',
            'AWS_REGION': 'ap-southeast-1'
        }, clear=True):
            with patch('boto3.client', return_value=mock_client):
                api_key = get_openai_api_key()

                # Should fetch from Secrets Manager, not use placeholder
                assert api_key == 'sk-real-production-key'
                mock_client.get_secret_value.assert_called_once_with(SecretId='sit/edgp/secret')

    def test_local_development_uses_env_var(self):
        """Test local development with real key in env var"""
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': 'sk-local-dev-key',
        }):
            api_key = get_openai_api_key()

            # Should use env var for local dev
            assert api_key == 'sk-local-dev-key'

    def test_kubernetes_deployment_scenario(self):
        """Test Kubernetes deployment scenario with APP_ENV"""
        # Simulates: APP_ENV=sit → loads .env.sit → AI_SECRET_NAME=sit/edgp/secret
        secret_data = {
            "openai_api_key": "sk-kubernetes-key",
            "username": "edgp_user",
            "password": "edgp_pass"
        }
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.dict('os.environ', {
            'APP_ENV': 'sit',
            'AI_SECRET_NAME': 'sit/edgp/secret',
            'AWS_REGION': 'ap-southeast-1'
        }, clear=True):
            # Clear singleton cache
            import src.compliance_agent.services.ai_secrets_service as service_module
            service_module._ai_secrets_manager = None

            with patch('boto3.client', return_value=mock_client):
                api_key = get_openai_api_key()

                assert api_key == 'sk-kubernetes-key'

    def test_caching_reduces_aws_calls(self):
        """Test that caching reduces AWS Secrets Manager calls"""
        secret_data = {"openai_api_key": "sk-cached-key"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
            with patch('boto3.client', return_value=mock_client):
                # Clear singleton to start fresh
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                # First call
                api_key1 = get_openai_api_key()
                # Second call
                api_key2 = get_openai_api_key()
                # Third call
                api_key3 = get_openai_api_key()

                # Should only call AWS once due to caching
                assert mock_client.get_secret_value.call_count == 1
                assert api_key1 == api_key2 == api_key3 == 'sk-cached-key'
