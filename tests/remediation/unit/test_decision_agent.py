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
        with patch('src.remediation_agent.agents.decision_agent.ChatOpenAI') as mock_llm:
            mock_llm.return_value = AsyncMock()
            agent = DecisionAgent(model_name="gpt-4", temperature=0.1)
            agent.llm = AsyncMock()
            return agent
    
    @pytest.mark.asyncio
    async def test_analyze_violation_automatic_remediation(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation that should be automatically remediated"""
        # Mock LLM response for automatic remediation
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "remediation_type": "automatic",
            "confidence_score": 0.95,
            "reasoning": "Low-risk standard operation can be automated",
            "estimated_effort": "low",
            "automation_potential": 0.95,
            "risk_assessment": {
                "data_risk": "low",
                "system_risk": "low",
                "compliance_risk": "low"
            },
            "required_approvals": [],
            "human_tasks": []
        })
        
        decision_agent.llm.ainvoke.return_value = mock_response
        
        # Modify signal for low-risk scenario
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        sample_remediation_signal.violation.remediation_actions = ["Update user preference"]
        
        result = await decision_agent.analyze_violation(sample_remediation_signal)
        
        assert isinstance(result, RemediationDecision)
        assert result.remediation_type == RemediationType.AUTOMATIC
        assert result.confidence_score == 0.95
        assert result.automation_potential == 0.95
        assert len(result.required_approvals) == 0
        assert len(result.human_tasks) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_violation_human_in_loop(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation requiring human-in-the-loop"""
        # Mock LLM response for human-in-loop
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "remediation_type": "human_in_loop",
            "confidence_score": 0.85,
            "reasoning": "High-risk data deletion requires human oversight",
            "estimated_effort": "medium",
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
        
        decision_agent.llm.ainvoke.return_value = mock_response
        
        result = await decision_agent.analyze_violation(sample_remediation_signal)
        
        assert isinstance(result, RemediationDecision)
        assert result.remediation_type == RemediationType.HUMAN_IN_LOOP
        assert result.confidence_score == 0.85
        assert result.automation_potential == 0.7
        assert "data_protection_officer" in result.required_approvals
        assert len(result.human_tasks) == 3
    
    @pytest.mark.asyncio
    async def test_analyze_violation_manual_only(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation requiring manual-only remediation"""
        # Mock LLM response for manual-only
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "remediation_type": "manual_only",
            "confidence_score": 0.9,
            "reasoning": "Complex legal review required, cannot be automated",
            "estimated_effort": "high",
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
        
        decision_agent.llm.ainvoke.return_value = mock_response
        
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
        assert result.automation_potential == 0.1
        assert len(result.required_approvals) == 3
        assert len(result.human_tasks) == 4
    
    @pytest.mark.asyncio
    async def test_analyze_violation_with_fallback_parsing(self, decision_agent, sample_remediation_signal):
        """Test analyzing violation with non-JSON LLM response (fallback parsing)"""
        # Mock LLM response that's not valid JSON
        mock_response = MagicMock()
        mock_response.content = (
            "Based on the analysis, this violation requires human_in_loop remediation. "
            "The confidence score is 0.8 and the reasoning is that data deletion requires oversight. "
            "The automation potential is medium at 0.6."
        )
        
        decision_agent.llm.ainvoke.return_value = mock_response
        
        result = await decision_agent.analyze_violation(sample_remediation_signal)
        
        assert isinstance(result, RemediationDecision)
        # Fallback should default to human_in_loop for safety
        assert result.remediation_type == RemediationType.HUMAN_IN_LOOP
        assert result.confidence_score == 0.7  # Default fallback confidence
        assert "LLM analysis" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_analyze_violation_llm_error_handling(self, decision_agent, sample_remediation_signal):
        """Test error handling when LLM call fails"""
        # Mock LLM to raise an exception
        decision_agent.llm.ainvoke.side_effect = Exception("LLM API error")
        
        result = await decision_agent.analyze_violation(sample_remediation_signal)
        
        assert isinstance(result, RemediationDecision)
        # Should fallback to safe defaults on error
        assert result.remediation_type == RemediationType.HUMAN_IN_LOOP
        assert result.confidence_score == 0.7
        assert "Error occurred during analysis" in result.reasoning
    
    def test_analyze_complexity_high_risk(self, decision_agent, sample_remediation_signal):
        """Test complexity analysis for high-risk violations"""
        sample_remediation_signal.violation.risk_level = RiskLevel.HIGH
        sample_remediation_signal.violation.remediation_actions = [
            "Delete user data from multiple systems",
            "Update third-party integrations",
            "Notify data processors"
        ]
        
        complexity = decision_agent._analyze_complexity(sample_remediation_signal)
        
        assert complexity["risk_level"] == "high"
        assert complexity["action_count"] == 3
        assert complexity["estimated_complexity"] == "high"
        assert "multiple systems" in complexity["complexity_factors"]
    
    def test_analyze_complexity_low_risk(self, decision_agent, sample_remediation_signal):
        """Test complexity analysis for low-risk violations"""
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        sample_remediation_signal.violation.remediation_actions = ["Update user preference"]
        
        complexity = decision_agent._analyze_complexity(sample_remediation_signal)
        
        assert complexity["risk_level"] == "low"
        assert complexity["action_count"] == 1
        assert complexity["estimated_complexity"] == "low"
    
    def test_estimate_cross_system_impact_high(self, decision_agent, sample_remediation_signal):
        """Test cross-system impact estimation for high impact"""
        sample_remediation_signal.context = {
            "affected_systems": ["user_db", "analytics_db", "email_service", "crm_system"]
        }
        
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
        text = "This violation requires human_in_loop approach with confidence of 0.8"
        
        result = decision_agent._fallback_parse(text)
        
        assert result["remediation_type"] == "human_in_loop"
        assert result["confidence_score"] == 0.8