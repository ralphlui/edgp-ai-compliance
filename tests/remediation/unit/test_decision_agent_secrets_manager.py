"""
Unit tests for DecisionAgent with AWS Secrets Manager integration
Tests the API key fetching from Secrets Manager
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import json

from src.remediation_agent.agents.decision_agent import DecisionAgent
from src.remediation_agent.state.models import RemediationType, RemediationDecision
from src.compliance_agent.models.compliance_models import RiskLevel


class TestDecisionAgentSecretsManager:
    """Test DecisionAgent initialization with Secrets Manager"""

    @pytest.fixture
    def mock_secrets_service(self):
        """Mock the ai_secrets_service"""
        with patch('src.remediation_agent.agents.decision_agent.DecisionAgent._get_api_key_from_secrets_manager') as mock:
            yield mock

    def test_init_fetches_api_key_from_secrets_manager(self, mock_secrets_service):
        """Test that __init__ fetches API key from Secrets Manager"""
        mock_secrets_service.return_value = "sk-real-key-from-secrets"

        agent = DecisionAgent(model_name="gpt-4", temperature=0.1)

        mock_secrets_service.assert_called_once()
        assert agent.api_key == "sk-real-key-from-secrets"

    def test_init_uses_test_key_when_secrets_manager_fails(self, mock_secrets_service):
        """Test that __init__ falls back to test-key when Secrets Manager fails"""
        mock_secrets_service.return_value = None

        agent = DecisionAgent()

        assert agent.api_key == "test-key"

    def test_init_logs_warning_when_no_api_key(self, mock_secrets_service):
        """Test that __init__ logs warning when no API key found"""
        mock_secrets_service.return_value = None

        with patch('src.remediation_agent.agents.decision_agent.logger') as mock_logger:
            agent = DecisionAgent()

            mock_logger.warning.assert_called_once()
            assert "No OpenAI API key found" in str(mock_logger.warning.call_args)

    def test_init_uses_custom_model_name(self, mock_secrets_service):
        """Test that __init__ accepts custom model name"""
        mock_secrets_service.return_value = "sk-test-key"

        agent = DecisionAgent(model_name="gpt-4o", temperature=0.5)

        assert agent.model_name == "gpt-4o"
        assert agent.temperature == 0.5

    def test_init_uses_settings_when_available(self, mock_secrets_service):
        """Test that __init__ uses settings when available"""
        mock_secrets_service.return_value = "sk-test-key"
        mock_settings = MagicMock()
        mock_settings.ai_model_name = "gpt-4o-mini"
        mock_settings.ai_temperature = 0.2

        with patch('src.remediation_agent.agents.decision_agent.settings', mock_settings):
            with patch('src.remediation_agent.agents.decision_agent.SETTINGS_AVAILABLE', True):
                agent = DecisionAgent()

                assert agent.model_name == "gpt-4o-mini"
                assert agent.temperature == 0.2

    @pytest.mark.asyncio
    async def test_analyze_with_llm_uses_api_key_from_secrets(self, mock_secrets_service, sample_remediation_signal):
        """Test that _analyze_with_llm uses the API key from Secrets Manager"""
        mock_secrets_service.return_value = "sk-secrets-manager-key"

        agent = DecisionAgent()

        # Mock OpenAI client
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

        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await agent._analyze_with_llm(sample_remediation_signal)

            # Verify AsyncOpenAI was called with the correct API key
            mock_client_class.assert_called_once_with(api_key="sk-secrets-manager-key")

    def test_get_api_key_from_secrets_manager_success(self):
        """Test _get_api_key_from_secrets_manager returns key successfully"""
        mock_get_key = MagicMock(return_value="sk-fetched-key")

        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', mock_get_key):
            result = DecisionAgent._get_api_key_from_secrets_manager()

            mock_get_key.assert_called_once()
            assert result == "sk-fetched-key"

    def test_get_api_key_from_secrets_manager_returns_none(self):
        """Test _get_api_key_from_secrets_manager returns None when no key found"""
        mock_get_key = MagicMock(return_value=None)

        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', mock_get_key):
            with patch('src.remediation_agent.agents.decision_agent.logger') as mock_logger:
                result = DecisionAgent._get_api_key_from_secrets_manager()

                assert result is None
                mock_logger.warning.assert_called_once()

    def test_get_api_key_from_secrets_manager_handles_exception(self):
        """Test _get_api_key_from_secrets_manager handles exceptions gracefully"""
        mock_get_key = MagicMock(side_effect=Exception("AWS connection error"))

        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', mock_get_key):
            with patch('src.remediation_agent.agents.decision_agent.logger') as mock_logger:
                result = DecisionAgent._get_api_key_from_secrets_manager()

                assert result is None
                mock_logger.warning.assert_called_once()
                assert "AWS connection error" in str(mock_logger.warning.call_args)


class TestDecisionAgentWithSecretsManagerIntegration:
    """Integration tests for DecisionAgent with Secrets Manager"""

    @pytest.mark.asyncio
    async def test_full_flow_with_secrets_manager(self, sample_remediation_signal):
        """Test complete flow from Secrets Manager to LLM call"""
        # Mock Secrets Manager
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key') as mock_get_key:
            mock_get_key.return_value = "sk-production-key"

            # Create agent (should fetch key from Secrets Manager)
            agent = DecisionAgent(model_name="gpt-4", temperature=0.1)

            # Mock OpenAI response
            mock_choice = MagicMock()
            mock_choice.message.content = json.dumps({
                "remediation_type": "human_in_loop",
                "confidence_score": 0.85,
                "reasoning": "Requires human oversight",
                "estimated_effort": 60,
                "risk_if_delayed": "high",
                "prerequisites": ["approval_required"],
                "recommended_actions": ["review", "approve"]
            })
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.chat.completions.create.return_value = mock_response
                mock_client_class.return_value = mock_client

                # Make decision
                result = await agent.make_decision(sample_remediation_signal)

                # Verify the entire flow
                mock_get_key.assert_called_once()
                mock_client_class.assert_called_once_with(api_key="sk-production-key")
                assert isinstance(result, RemediationDecision)
                assert result.remediation_type == RemediationType.HUMAN_IN_LOOP

    @pytest.mark.asyncio
    async def test_fallback_to_rule_based_when_no_api_key(self, sample_remediation_signal):
        """Test that agent falls back to rule-based logic when no API key"""
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key') as mock_get_key:
            mock_get_key.return_value = None  # No API key available

            agent = DecisionAgent()

            # Agent will still try LLM but should fail and fall back to rule-based logic
            with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client_class:
                # Make the mock fail to simulate LLM call failure
                mock_client = AsyncMock()
                mock_client.chat.completions.create.side_effect = Exception("No valid API key")
                mock_client_class.return_value = mock_client

                result = await agent.make_decision(sample_remediation_signal)

                # Should have tried to instantiate OpenAI client
                mock_client_class.assert_called_once_with(api_key="test-key")

                # Should still return a valid decision (from rule-based fallback)
                assert isinstance(result, RemediationDecision)
                assert result.remediation_type in [
                    RemediationType.AUTOMATIC,
                    RemediationType.HUMAN_IN_LOOP,
                    RemediationType.MANUAL_ONLY
                ]

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_rules(self, sample_remediation_signal):
        """Test that LLM failure triggers fallback to rule-based logic"""
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key') as mock_get_key:
            mock_get_key.return_value = "sk-test-key"

            agent = DecisionAgent()

            # Mock OpenAI to raise an error
            with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.chat.completions.create.side_effect = Exception("API error")
                mock_client_class.return_value = mock_client

                # Should fall back to rule-based logic
                result = await agent.make_decision(sample_remediation_signal)

                assert isinstance(result, RemediationDecision)
                # Rule-based logic should still work
                assert result.violation_id == sample_remediation_signal.violation.rule_id


class TestDecisionAgentRuleBasedLogic:
    """Test rule-based decision logic (used when LLM unavailable)"""

    @pytest.fixture
    def agent_without_llm(self):
        """Create agent without LLM (simulates no API key)"""
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key') as mock_get_key:
            mock_get_key.return_value = None
            agent = DecisionAgent()
            return agent

    def test_critical_risk_triggers_manual_only(self, agent_without_llm, sample_remediation_signal):
        """Test that CRITICAL risk level triggers MANUAL_ONLY"""
        sample_remediation_signal.violation.risk_level = RiskLevel.CRITICAL

        factors = agent_without_llm._build_decision_factors(sample_remediation_signal)
        decision_payload = agent_without_llm._determine_rule_based_decision(
            sample_remediation_signal, factors
        )

        assert decision_payload["decision_type"] == RemediationType.MANUAL_ONLY.value

    def test_policy_action_triggers_manual_only(self, agent_without_llm, sample_remediation_signal):
        """Test that policy-related actions trigger MANUAL_ONLY"""
        sample_remediation_signal.violation.remediation_actions = [
            "Update privacy policy",
            "Review terms of service"
        ]

        factors = agent_without_llm._build_decision_factors(sample_remediation_signal)
        decision_payload = agent_without_llm._determine_rule_based_decision(
            sample_remediation_signal, factors
        )

        assert decision_payload["decision_type"] == RemediationType.MANUAL_ONLY.value

    def test_deletion_action_triggers_human_in_loop(self, agent_without_llm, sample_remediation_signal):
        """Test that deletion actions trigger HUMAN_IN_LOOP"""
        sample_remediation_signal.violation.remediation_actions = ["Delete user data"]
        sample_remediation_signal.violation.risk_level = RiskLevel.MEDIUM

        factors = agent_without_llm._build_decision_factors(sample_remediation_signal)
        decision_payload = agent_without_llm._determine_rule_based_decision(
            sample_remediation_signal, factors
        )

        assert decision_payload["decision_type"] == RemediationType.HUMAN_IN_LOOP.value

    def test_low_risk_simple_action_triggers_automatic(self, agent_without_llm, sample_remediation_signal):
        """Test that low-risk simple actions trigger AUTOMATIC"""
        sample_remediation_signal.violation.remediation_actions = ["Update user preference"]
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW

        factors = agent_without_llm._build_decision_factors(sample_remediation_signal)
        decision_payload = agent_without_llm._determine_rule_based_decision(
            sample_remediation_signal, factors
        )

        assert decision_payload["decision_type"] == RemediationType.AUTOMATIC.value

    def test_complexity_score_calculation(self, agent_without_llm):
        """Test _assess_complexity calculates score correctly"""
        actions = [
            "Update database",
            "Send notification",
            "Delete old records"
        ]

        complexity = agent_without_llm._assess_complexity(actions)

        assert "complexity_score" in complexity
        assert complexity["complexity_score"] > 1.0  # More than base score
        assert "automation_patterns" in complexity
        assert complexity["automation_patterns"] >= 0

    def test_cross_system_impact_assessment(self, agent_without_llm, sample_remediation_signal):
        """Test _estimate_cross_system_impact assessment"""
        # High impact scenario
        sample_remediation_signal.activity.cross_border_transfers = True
        sample_remediation_signal.activity.automated_decision_making = True
        sample_remediation_signal.activity.recipients = ["system1", "system2", "system3"]
        sample_remediation_signal.violation.remediation_actions = ["action1", "action2", "action3", "action4"]

        impact = agent_without_llm._estimate_cross_system_impact(sample_remediation_signal)

        assert impact == "high"

    def test_prerequisites_for_manual_only(self, agent_without_llm, sample_remediation_signal):
        """Test that MANUAL_ONLY gets correct prerequisites"""
        prereqs = agent_without_llm._determine_prerequisites(
            sample_remediation_signal,
            RemediationType.MANUAL_ONLY
        )

        assert "Legal review required" in prereqs
        assert "Compliance officer approval" in prereqs
        assert "Impact assessment" in prereqs

    def test_prerequisites_for_cross_border_transfer(self, agent_without_llm, sample_remediation_signal):
        """Test that cross-border transfers add prerequisites"""
        sample_remediation_signal.activity.cross_border_transfers = True

        prereqs = agent_without_llm._determine_prerequisites(
            sample_remediation_signal,
            RemediationType.HUMAN_IN_LOOP
        )

        assert "Cross-border transfer compliance check" in prereqs
