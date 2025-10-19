"""
Integration tests for OpenAI API Key retrieval across all components
Tests the complete flow from environment to Secrets Manager to LLM usage
"""

import pytest
import json
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
from uuid import uuid4
from botocore.exceptions import ClientError

# Mock SQLAlchemy to avoid Python 3.13 compatibility issues
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()

# Import all components that use OpenAI
from src.remediation_agent.agents.decision_agent import DecisionAgent
from src.remediation_agent.state.models import (
    RemediationSignal,
    SignalType,
    UrgencyLevel
)
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation,
    DataProcessingActivity,
    RiskLevel,
    DataType
)


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def sample_compliance_violation() -> ComplianceViolation:
    """Create a sample compliance violation for testing"""
    return ComplianceViolation(
        rule_id="gdpr_art17_violation_001",
        activity_id="user_data_001",
        description="User requested data deletion but system lacks automated deletion capability",
        risk_level=RiskLevel.HIGH,
        remediation_actions=[
            "Delete user personal data from database",
            "Remove user from mailing lists",
            "Verify complete data removal",
            "Send confirmation to user"
        ]
    )


@pytest.fixture
def sample_data_processing_activity() -> DataProcessingActivity:
    """Create a sample data processing activity for testing"""
    return DataProcessingActivity(
        id="user_data_001",
        name="User Profile Management",
        purpose="Account management and personalization",
        data_types=[DataType.PERSONAL_DATA, DataType.BEHAVIORAL_DATA],
        legal_bases=["consent"],
        recipients=["internal_systems"],
        retention_period=1825,  # 5 years in days
        security_measures=["encryption", "access_controls"]
    )


@pytest.fixture
def sample_remediation_signal(sample_compliance_violation, sample_data_processing_activity) -> RemediationSignal:
    """Create a sample remediation signal for testing"""
    return RemediationSignal(
        signal_id=str(uuid4()),
        violation_id=sample_compliance_violation.rule_id,
        activity_id=sample_data_processing_activity.id,
        signal_type=SignalType.COMPLIANCE_VIOLATION,
        confidence_score=0.9,
        urgency_level=UrgencyLevel.HIGH,
        detected_violations=["gdpr_art17_violation"],
        recommended_actions=["delete_user_data"],
        context={
            "user_request_id": "user_123",
            "request_timestamp": datetime.now(timezone.utc).isoformat(),
            "affected_systems": ["user_db", "analytics_db", "email_service"]
        },
        id=str(uuid4()),
        priority=RiskLevel.HIGH,
        violation=sample_compliance_violation,
        activity=sample_data_processing_activity
    )


# ==========================================
# TESTS
# ==========================================

class TestSecretsManagerIntegration:
    """Integration tests for Secrets Manager across all components"""

    @pytest.fixture
    def mock_aws_secret(self):
        """Mock AWS Secrets Manager with realistic secret"""
        secret_data = {
            "openai_api_key": "sk-proj-abc123def456",  # Avoid "test" keyword to prevent placeholder detection
            "username": "edgp_user",
            "password": "edgp_password"
        }

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch('boto3.client', return_value=mock_client):
            yield mock_client, secret_data

    def test_decision_agent_uses_secrets_manager(self, mock_aws_secret):
        """Test that DecisionAgent fetches API key from Secrets Manager"""
        mock_client, secret_data = mock_aws_secret

        with patch.dict('os.environ', {'AI_SECRET_NAME': 'sit/edgp/secret', 'AWS_REGION': 'ap-southeast-1'}, clear=True):
            # Clear singleton, its cache, and its boto3 client
            import src.compliance_agent.services.ai_secrets_service as service_module
            if service_module._ai_secrets_manager:
                service_module._ai_secrets_manager.clear_cache()
                service_module._ai_secrets_manager._client = None  # Reset boto3 client
            service_module._ai_secrets_manager = None

            agent = DecisionAgent(model_name="gpt-4o")

            # Verify API key was fetched from Secrets Manager
            assert agent.api_key == "sk-proj-abc123def456"
            mock_client.get_secret_value.assert_called_once_with(SecretId='sit/edgp/secret')

    # Note: Removed tests for compliance_pattern_loader, data_retention_scanner, and international_ai_agent
    # due to SQLAlchemy Python 3.13 compatibility issues. These components are tested in unit tests.

    def test_placeholder_detection_triggers_secrets_manager(self):
        """Test that placeholder values in env vars trigger Secrets Manager fetch"""
        secret_data = {"openai_api_key": "sk-real-production-key"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch('boto3.client', return_value=mock_client):
            with patch.dict('os.environ', {
                'OPENAI_API_KEY': 'sit_openai_api_key_here',  # Placeholder
                'AI_SECRET_NAME': 'sit/edgp/secret'
            }, clear=True):
                # Clear singleton cache AND internal cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                if service_module._ai_secrets_manager:
                    service_module._ai_secrets_manager.clear_cache()
                service_module._ai_secrets_manager = None

                agent = DecisionAgent()

                # Should NOT use the placeholder, should fetch from Secrets Manager
                assert agent.api_key == "sk-real-production-key"
                mock_client.get_secret_value.assert_called_once()

    def test_secrets_manager_failure_handles_gracefully(self):
        """Test that components handle Secrets Manager failures gracefully"""
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetSecretValue'
        )

        with patch('boto3.client', return_value=mock_client):
            with patch.dict('os.environ', {'AI_SECRET_NAME': 'nonexistent/secret'}, clear=True):
                # Clear singleton cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                # Should not crash, should fall back to test-key
                agent = DecisionAgent()

                assert agent.api_key == "test-key"


class TestEnvironmentBasedConfiguration:
    """Test configuration loading based on APP_ENV"""

    def test_sit_environment_loads_correct_secret(self):
        """Test that SIT environment loads sit/edgp/secret"""
        secret_data = {"openai_api_key": "sk-sit-key"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch('boto3.client', return_value=mock_client):
            # Simulate .env.sit being loaded (which has AI_SECRET_NAME=sit/edgp/secret)
            with patch.dict('os.environ', {
                'APP_ENV': 'sit',
                'AI_SECRET_NAME': 'sit/edgp/secret'  # From .env.sit
            }, clear=True):
                # Clear singleton cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                agent = DecisionAgent()

                mock_client.get_secret_value.assert_called_with(SecretId='sit/edgp/secret')
                assert agent.api_key == "sk-sit-key"

    def test_production_environment_loads_correct_secret(self):
        """Test that production environment loads prod/edgp/secret"""
        secret_data = {"openai_api_key": "sk-prod-key"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch('boto3.client', return_value=mock_client):
            # Simulate .env.production being loaded (which has AI_SECRET_NAME=prod/edgp/secret)
            with patch.dict('os.environ', {
                'APP_ENV': 'production',
                'AI_SECRET_NAME': 'prod/edgp/secret'  # From .env.production
            }, clear=True):
                # Clear singleton cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                agent = DecisionAgent()

                mock_client.get_secret_value.assert_called_with(SecretId='prod/edgp/secret')
                assert agent.api_key == "sk-prod-key"

    def test_development_uses_env_var_directly(self):
        """Test that local development can use env vars directly"""
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': 'sk-local-dev-key'
        }, clear=True):
            # Clear singleton cache
            import src.compliance_agent.services.ai_secrets_service as service_module
            service_module._ai_secrets_manager = None

            agent = DecisionAgent()

            # Should use the env var directly for local dev
            assert agent.api_key == "sk-local-dev-key"


class TestLLMCallsWithSecretsManager:
    """Test that LLM calls work correctly with Secrets Manager keys"""

    @pytest.mark.asyncio
    async def test_decision_agent_llm_call_with_secrets_key(self, sample_remediation_signal):
        """Test that DecisionAgent makes LLM calls with Secrets Manager key"""
        secret_data = {"openai_api_key": "sk-test-llm-key"}
        mock_boto_client = MagicMock()
        mock_boto_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch('boto3.client', return_value=mock_boto_client):
            with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
                # Clear singleton cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                agent = DecisionAgent()

                # Mock OpenAI response
                mock_choice = MagicMock()
                mock_choice.message.content = json.dumps({
                    "remediation_type": "automatic",
                    "confidence_score": 0.9,
                    "reasoning": "Test",
                    "estimated_effort": 30,
                    "risk_if_delayed": "low"
                })
                mock_response = MagicMock()
                mock_response.choices = [mock_choice]

                with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_openai:
                    mock_client = AsyncMock()
                    mock_client.chat.completions.create.return_value = mock_response
                    mock_openai.return_value = mock_client

                    result = await agent.make_decision(sample_remediation_signal)

                    # Verify AsyncOpenAI was initialized with the Secrets Manager key
                    mock_openai.assert_called_once_with(api_key="sk-test-llm-key")
                    # Verify LLM was actually called
                    mock_client.chat.completions.create.assert_called_once()


class TestSecurityAndErrorHandling:
    """Test security aspects and error handling"""

    def test_api_key_not_logged(self):
        """Test that API keys are not logged"""
        secret_data = {"openai_api_key": "sk-secret-key-should-not-log"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        with patch('boto3.client', return_value=mock_client):
            with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
                with patch('src.compliance_agent.services.ai_secrets_service.logger') as mock_logger:
                    # Clear singleton cache
                    import src.compliance_agent.services.ai_secrets_service as service_module
                    service_module._ai_secrets_manager = None

                    agent = DecisionAgent()

                    # Check that the actual API key is not in any log calls
                    for call in mock_logger.info.call_args_list:
                        args_str = str(call)
                        assert "sk-secret-key-should-not-log" not in args_str

    def test_iam_permission_error_handled(self):
        """Test that IAM permission errors are handled gracefully"""
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException'}},
            'GetSecretValue'
        )

        with patch('boto3.client', return_value=mock_client):
            with patch.dict('os.environ', {'AI_SECRET_NAME': 'secret/denied'}, clear=True):
                # Clear singleton cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                # Should not crash
                agent = DecisionAgent()

                # Should fall back to test-key
                assert agent.api_key == "test-key"

    def test_malformed_secret_handled(self):
        """Test that malformed secrets are handled gracefully"""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': "not valid json {"
        }

        with patch('boto3.client', return_value=mock_client):
            with patch.dict('os.environ', {'AI_SECRET_NAME': 'test/secret'}, clear=True):
                # Clear singleton cache
                import src.compliance_agent.services.ai_secrets_service as service_module
                service_module._ai_secrets_manager = None

                # Should not crash
                agent = DecisionAgent()

                # Should fall back to test-key
                assert agent.api_key == "test-key"
