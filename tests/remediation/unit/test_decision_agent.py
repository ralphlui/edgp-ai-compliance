"""
Unit tests for decision agent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.remediation_agent.agents.decision_agent import DecisionAgent
from src.remediation_agent.state.models import RemediationType, RemediationDecision
from src.compliance_agent.models.compliance_models import RiskLevel


class TestDecisionAgent:
    """Test DecisionAgent class"""
    
    @pytest.fixture
    def decision_agent(self, mock_environment_variables):
        """Create a decision agent instance for testing"""
        agent = DecisionAgent(model_name="gpt-4", temperature=0.1)
        return agent
    
    @pytest.mark.asyncio
    async def test_analyze_violation_automatic_remediation(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation that should be automatically remediated"""
        # Mock OpenAI client response
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "remediation_type": "automatic",
            "confidence_score": 0.95,
            "reasoning": "Low-risk standard operation can be automated",
            "estimated_effort": 30,
            "risk_if_delayed": "low",
            "automation_potential": 0.95,
            "risk_assessment": {
                "data_risk": "low",
                "system_risk": "low",
                "compliance_risk": "low"
            },
            "required_approvals": [],
            "human_tasks": []
        })
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            # Modify signal for low-risk scenario
            sample_remediation_signal.violation.risk_level = RiskLevel.LOW
            sample_remediation_signal.violation.remediation_actions = ["Update user preference"]
            
            result = await decision_agent.analyze_violation(sample_remediation_signal)
            
            assert isinstance(result, RemediationDecision)
            assert result.remediation_type == RemediationType.AUTOMATIC
            assert result.confidence_score == 0.95
            assert result.estimated_effort == 30
    
    @pytest.mark.asyncio
    async def test_analyze_violation_human_in_loop(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation requiring human-in-the-loop"""
        # Mock OpenAI client response
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "remediation_type": "human_in_loop",
            "confidence_score": 0.85,
            "reasoning": "High-risk data deletion requires human oversight",
            "estimated_effort": 120,
            "risk_if_delayed": "high",
            "automation_potential": 0.7,
            "risk_assessment": {
                "data_risk": "high",
                "system_risk": "medium",
                "compliance_risk": "low"
            },
            "required_approvals": ["data_protection_officer"],
            "human_tasks": [
                "Review deletion scope",
                "Approve data removal",
                "Verify compliance"
            ]
        })
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            result = await decision_agent.analyze_violation(sample_remediation_signal)
            
            assert isinstance(result, RemediationDecision)
            assert result.remediation_type == RemediationType.HUMAN_IN_LOOP
            assert result.confidence_score == 0.85
            assert result.estimated_effort == 120
    
    @pytest.mark.asyncio
    async def test_analyze_violation_manual_only(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation requiring manual-only remediation"""
        # Mock OpenAI client response
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "remediation_type": "manual_only",
            "confidence_score": 0.9,
            "reasoning": "Complex legal review required, cannot be automated",
            "estimated_effort": 240,
            "risk_if_delayed": "critical",
            "automation_potential": 0.1,
            "risk_assessment": {
                "data_risk": "critical",
                "system_risk": "high",
                "compliance_risk": "high"
            },
            "required_approvals": ["legal_team", "data_protection_officer", "ciso"],
            "human_tasks": [
                "Legal compliance review",
                "Risk assessment",
                "Manual data remediation",
                "Compliance documentation"
            ]
        })
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            # Modify signal for high-risk scenario
            sample_remediation_signal.violation.risk_level = RiskLevel.CRITICAL
            sample_remediation_signal.violation.remediation_actions = [
                "Complex cross-system data migration",
                "Legal compliance review",
                "Manual data verification"
            ]
            
            result = await decision_agent.analyze_violation(sample_remediation_signal)
            
            assert isinstance(result, RemediationDecision)
            assert result.remediation_type == RemediationType.MANUAL_ONLY
            assert result.confidence_score == 0.9
            assert result.estimated_effort == 240
    
    @pytest.mark.asyncio
    async def test_analyze_violation_normalises_nested_plan(self, decision_agent, sample_remediation_signal):
        """LLM payload nested under remediation_plan is normalised to expected schema"""
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "remediation_plan": {
                "risk_level": "high",
                "remediation_actions": [
                    {"action": "notify_customers"},
                    {"action": "delete_records"}
                ],
                "summary": "High risk scenario requiring careful handling.",
                "prerequisites": "legal_review"
            }
        })
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            sample_remediation_signal.violation.risk_level = RiskLevel.HIGH
            
            result = await decision_agent.analyze_violation(sample_remediation_signal)
        
        assert isinstance(result, RemediationDecision)
        assert result.remediation_type == RemediationType.MANUAL_ONLY
        assert 0.5 < result.confidence_score < 0.7
        assert result.estimated_effort >= 40  # derived from actions length
        assert result.prerequisites == ["legal_review"]
        assert result.recommended_actions == ["notify_customers", "delete_records"]
    
    @pytest.mark.asyncio
    async def test_analyze_violation_includes_schema_prompt(self, decision_agent, sample_remediation_signal):
        """Ensure LLM prompt includes schema instructions"""
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "remediation_type": "automatic",
            "confidence_score": 0.8,
            "reasoning": "Standard workflow",
            "estimated_effort": 25,
            "risk_if_delayed": "low"
        })
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            await decision_agent.analyze_violation(sample_remediation_signal)
            assert mock_instance.chat.completions.create.called
            call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
            messages = call_kwargs["messages"]
        
        assert messages[0]["content"] == decision_agent._system_message
        assert "Incident data:" in messages[1]["content"]
    
    @pytest.mark.asyncio
    async def test_analyze_violation_with_fallback_parsing(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation with non-JSON LLM response (fallback parsing)"""
        # Mock OpenAI client response that's not valid JSON
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Based on the analysis, this violation requires human_in_loop remediation. "
            "The confidence score is 0.8 and the reasoning is that data deletion requires oversight. "
            "The automation potential is medium at 0.6."
        )
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            result = await decision_agent.analyze_violation(sample_remediation_signal)
            
            assert isinstance(result, RemediationDecision)
            # Fallback should default to human_in_loop for safety
            assert result.remediation_type == RemediationType.HUMAN_IN_LOOP
            # When fallback parsing fails validation, it uses rule-based decision
            assert 0.0 < result.confidence_score <= 1.0
            assert "requires human verification" in result.reasoning.lower() or "human" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_violation_llm_error_handling(self, decision_agent, sample_remediation_signal):
        """Test error handling when LLM call fails"""
        # Mock OpenAI client to raise an exception
        with patch('src.remediation_agent.agents.decision_agent.openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.side_effect = Exception("LLM API error")
            mock_client.return_value = mock_instance
            
            result = await decision_agent.analyze_violation(sample_remediation_signal)
            
            assert isinstance(result, RemediationDecision)
            # Should fallback to safe defaults on error
            assert result.remediation_type == RemediationType.HUMAN_IN_LOOP
            assert 0.0 < result.confidence_score <= 1.0
            # Verify it's using rule-based fallback
            assert result.reasoning is not None and len(result.reasoning) > 0
    
    def test_analyze_complexity_high_risk(self, decision_agent, sample_remediation_signal):
        """Test complexity analysis for high-risk violations"""
        sample_remediation_signal.violation.risk_level = RiskLevel.HIGH
        sample_remediation_signal.violation.remediation_actions = [
            "Delete user data from multiple systems",
            "Update third-party integrations",
            "Notify data processors"
        ]
        
        complexity = decision_agent._assess_complexity(sample_remediation_signal.violation.remediation_actions)
        
        assert complexity["complexity_score"] > 1.0
        assert complexity["high_risk_actions"] >= 1  # "Delete" is high-risk keyword
        assert complexity["automation_patterns"] >= 1  # "Update" and "Notify" are automation keywords
    
    def test_analyze_complexity_low_risk(self, decision_agent, sample_remediation_signal):
        """Test complexity analysis for low-risk violations"""
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        sample_remediation_signal.violation.remediation_actions = ["Update user preference"]
        
        complexity = decision_agent._assess_complexity(sample_remediation_signal.violation.remediation_actions)
        
        assert complexity["complexity_score"] >= 1.0
        assert complexity["automation_patterns"] >= 1  # "Update" is an automation keyword
    
    def test_estimate_cross_system_impact_high(self, decision_agent, sample_remediation_signal):
        """Test cross-system impact estimation for high impact"""
        # Set up conditions that trigger high impact: 3+ factors
        sample_remediation_signal.activity.cross_border_transfers = True
        sample_remediation_signal.activity.automated_decision_making = True
        sample_remediation_signal.activity.recipients = ["recipient1", "recipient2", "recipient3", "recipient4"]
        sample_remediation_signal.violation.remediation_actions = ["action1", "action2", "action3", "action4"]
        
        impact = decision_agent._estimate_cross_system_impact(sample_remediation_signal)
        
        assert impact == "high"
    
    def test_parse_llm_response_valid_json(self, decision_agent):
        """Test parsing valid JSON response from LLM"""
        json_response = {
            "remediation_type": "automatic",
            "confidence_score": 0.9,
            "reasoning": "Test reasoning"
        }
        
        result = decision_agent._parse_llm_response(json.dumps(json_response))
        
        assert result["remediation_type"] == "automatic"
        assert result["confidence_score"] == 0.9
        assert result["reasoning"] == "Test reasoning"
    
    def test_fallback_parse_human_in_loop(self, decision_agent):
        """Test fallback parsing identifies human_in_loop"""
        text = "This violation requires human_in_loop approach"
        
        result = decision_agent._fallback_parse(text)
        
        assert result["remediation_type"] == "human_in_loop"
        assert result["confidence_score"] == 0.5  # Default for fallback without 'high' keyword
        assert result["estimated_effort"] == 60
        assert "__fallback__" in result
