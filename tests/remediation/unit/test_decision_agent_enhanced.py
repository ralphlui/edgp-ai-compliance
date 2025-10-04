"""
Enhanced unit tests for decision agent with high coverage
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.remediation_agent.agents.decision_agent import DecisionAgent
from src.remediation_agent.state.models import RemediationSignal, RemediationDecision, RemediationType
from src.compliance_agent.models.compliance_models import ComplianceViolation, RiskLevel, DataProcessingActivity, ComplianceFramework, DataType


class TestDecisionAgentEnhanced:
    """Enhanced tests for DecisionAgent with high coverage"""
    
    @pytest.fixture
    def decision_agent(self):
        """Create a decision agent instance"""
        return DecisionAgent()
    
    @pytest.fixture
    def sample_violation(self):
        """Create a sample compliance violation"""
        return ComplianceViolation(
            id="violation-123",
            violation_type="unauthorized_data_processing",
            description="Processing personal data without consent",
            risk_level=RiskLevel.HIGH,
            framework=ComplianceFramework.GDPR_EU,
            data_subject_id="user-456",
            affected_data_types=[DataType.PERSONAL_DATA],
            remediation_actions=["Stop data processing", "Delete personal data", "Send notification"],
            evidence={"log_entry": "Unauthorized access detected"},
            detection_timestamp="2024-01-15T10:30:00Z"
        )
    
    @pytest.fixture
    def sample_activity(self):
        """Create a sample data processing activity"""
        return DataProcessingActivity(
            id="activity-123",
            name="User Analytics",
            description="Analyzing user behavior patterns",
            purpose="analytics",
            data_controller="Analytics Team",
            data_processor="Data Science Dept",
            data_types=[DataType.PERSONAL_DATA, DataType.BEHAVIORAL_DATA],
            legal_basis="legitimate_interest",
            retention_period_days=365,
            data_subjects=["users", "customers"],
            third_party_sharing=False,
            cross_border_transfer=False,
            automated_decision_making=True
        )
    
    @pytest.fixture
    def sample_signal(self, sample_violation, sample_activity):
        """Create a sample remediation signal"""
        return RemediationSignal(
            violation=sample_violation,
            activity=sample_activity,
            framework="GDPR",
            context={"user_consent": False, "data_age_days": 400}
        )
    
    @pytest.mark.asyncio
    async def test_make_decision_automatic_low_risk(self, decision_agent, sample_signal):
        """Test automatic decision for low risk violations"""
        # Modify signal for low risk scenario
        sample_signal.violation.risk_level = RiskLevel.LOW
        sample_signal.violation.remediation_actions = ["Update user preference setting"]
        
        with patch.object(decision_agent, '_analyze_with_llm') as mock_llm:
            mock_llm.return_value = {
                "decision_type": "automatic",
                "confidence_score": 0.95,
                "reasoning": "Simple preference update, low risk operation",
                "estimated_effort": 5,
                "risk_if_delayed": "low"
            }
            
            decision = await decision_agent.make_decision(sample_signal)
            
            assert isinstance(decision, RemediationDecision)
            assert decision.remediation_type == RemediationType.AUTOMATIC
            assert decision.confidence_score == 0.95
            assert "Simple preference update" in decision.reasoning
            assert decision.risk_if_delayed == RiskLevel.LOW
            mock_llm.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_decision_human_in_loop_medium_risk(self, decision_agent, sample_signal):
        """Test human-in-loop decision for medium risk violations"""
        sample_signal.violation.risk_level = RiskLevel.MEDIUM
        sample_signal.violation.remediation_actions = ["Delete user personal data", "Send deletion confirmation"]
        
        with patch.object(decision_agent, '_analyze_with_llm') as mock_llm:
            mock_llm.return_value = {
                "decision_type": "human_in_loop",
                "confidence_score": 0.75,
                "reasoning": "Data deletion requires human oversight for compliance",
                "estimated_effort": 30,
                "risk_if_delayed": "medium"
            }
            
            decision = await decision_agent.make_decision(sample_signal)
            
            assert decision.remediation_type == RemediationType.HUMAN_IN_LOOP
            assert decision.confidence_score == 0.75
            assert "human oversight" in decision.reasoning
            assert decision.estimated_effort == 30
    
    @pytest.mark.asyncio
    async def test_make_decision_manual_only_high_risk(self, decision_agent, sample_signal):
        """Test manual-only decision for high risk violations"""
        sample_signal.violation.risk_level = RiskLevel.CRITICAL
        sample_signal.violation.remediation_actions = [
            "Conduct legal review",
            "Update privacy policy",
            "Implement new consent mechanism"
        ]
        
        with patch.object(decision_agent, '_analyze_with_llm') as mock_llm:
            mock_llm.return_value = {
                "decision_type": "manual_only",
                "confidence_score": 0.60,
                "reasoning": "Critical legal changes require manual review and implementation",
                "estimated_effort": 480,
                "risk_if_delayed": "critical"
            }
            
            decision = await decision_agent.make_decision(sample_signal)
            
            assert decision.remediation_type == RemediationType.MANUAL_ONLY
            assert decision.confidence_score == 0.60
            assert "manual review" in decision.reasoning
            assert decision.estimated_effort == 480
            assert decision.risk_if_delayed == RiskLevel.CRITICAL
    
    @pytest.mark.asyncio
    async def test_make_decision_with_llm_error(self, decision_agent, sample_signal):
        """Test decision making when LLM fails"""
        with patch.object(decision_agent, '_analyze_with_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM service unavailable")
            
            decision = await decision_agent.make_decision(sample_signal)
            
            # Should fall back to rule-based decision
            assert isinstance(decision, RemediationDecision)
            assert decision.remediation_type in [RemediationType.AUTOMATIC, RemediationType.HUMAN_IN_LOOP, RemediationType.MANUAL_ONLY]
            assert 0.0 <= decision.confidence_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_analyze_with_llm_success(self, decision_agent, sample_signal):
        """Test successful LLM analysis"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = json.dumps({
                "decision_type": "automatic",
                "confidence_score": 0.9,
                "reasoning": "Simple data update operation",
                "estimated_effort": 15,
                "risk_if_delayed": "low"
            })
            
            mock_client.chat.completions.create.return_value = mock_response
            
            result = await decision_agent._analyze_with_llm(sample_signal)
            
            assert result["decision_type"] == "automatic"
            assert result["confidence_score"] == 0.9
            assert result["reasoning"] == "Simple data update operation"
            assert result["estimated_effort"] == 15
            assert result["risk_if_delayed"] == "low"
    
    @pytest.mark.asyncio
    async def test_analyze_with_llm_json_parse_error(self, decision_agent, sample_signal):
        """Test LLM analysis with JSON parsing error"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Invalid JSON response"
            
            mock_client.chat.completions.create.return_value = mock_response
            
            with pytest.raises(Exception):
                await decision_agent._analyze_with_llm(sample_signal)
    
    def test_determine_rule_based_decision_low_risk(self, decision_agent, sample_signal):
        """Test rule-based decision for low risk scenarios"""
        sample_signal.violation.risk_level = RiskLevel.LOW
        sample_signal.violation.remediation_actions = ["Update preference"]
        
        result = decision_agent._determine_rule_based_decision(sample_signal)
        
        assert result["decision_type"] == "automatic"
        assert result["confidence_score"] >= 0.7
        assert "low risk" in result["reasoning"].lower()
    
    def test_determine_rule_based_decision_high_risk(self, decision_agent, sample_signal):
        """Test rule-based decision for high risk scenarios"""
        sample_signal.violation.risk_level = RiskLevel.CRITICAL
        sample_signal.violation.remediation_actions = [
            "Delete all user data",
            "Update legal agreements",
            "Notify regulatory authorities"
        ]
        
        result = decision_agent._determine_rule_based_decision(sample_signal)
        
        assert result["decision_type"] == "manual_only"
        assert result["confidence_score"] <= 0.7
        assert "critical" in result["reasoning"].lower() or "manual" in result["reasoning"].lower()
    
    def test_determine_rule_based_decision_medium_risk(self, decision_agent, sample_signal):
        """Test rule-based decision for medium risk scenarios"""
        sample_signal.violation.risk_level = RiskLevel.MEDIUM
        sample_signal.violation.remediation_actions = ["Delete personal data", "Send notification"]
        
        result = decision_agent._determine_rule_based_decision(sample_signal)
        
        assert result["decision_type"] in ["human_in_loop", "manual_only"]
        assert 0.5 <= result["confidence_score"] <= 0.8
    
    def test_assess_complexity_simple_actions(self, decision_agent):
        """Test complexity assessment for simple actions"""
        actions = ["Update user preference", "Send email notification"]
        
        complexity = decision_agent._assess_complexity(actions)
        
        assert complexity <= 0.3
    
    def test_assess_complexity_moderate_actions(self, decision_agent):
        """Test complexity assessment for moderate actions"""
        actions = [
            "Delete user personal data",
            "Update privacy settings",
            "Send deletion confirmation",
            "Log remediation action"
        ]
        
        complexity = decision_agent._assess_complexity(actions)
        
        assert 0.3 < complexity <= 0.7
    
    def test_assess_complexity_complex_actions(self, decision_agent):
        """Test complexity assessment for complex actions"""
        actions = [
            "Conduct comprehensive legal review",
            "Update data processing agreements with third parties",
            "Implement new consent management system",
            "Migrate data to compliant storage",
            "Notify regulatory authorities",
            "Update privacy policy across multiple jurisdictions"
        ]
        
        complexity = decision_agent._assess_complexity(actions)
        
        assert complexity > 0.7
    
    def test_assess_cross_system_impact_single_system(self, decision_agent, sample_signal):
        """Test cross-system impact assessment for single system"""
        sample_signal.context = {"affected_systems": ["user_preferences"]}
        
        impact = decision_agent._assess_cross_system_impact(sample_signal)
        
        assert impact <= 0.3
    
    def test_assess_cross_system_impact_multiple_systems(self, decision_agent, sample_signal):
        """Test cross-system impact assessment for multiple systems"""
        sample_signal.context = {
            "affected_systems": ["user_database", "analytics_db", "email_service", "audit_logs"]
        }
        
        impact = decision_agent._assess_cross_system_impact(sample_signal)
        
        assert impact > 0.5
    
    def test_assess_cross_system_impact_no_context(self, decision_agent, sample_signal):
        """Test cross-system impact assessment without context"""
        sample_signal.context = {}
        
        impact = decision_agent._assess_cross_system_impact(sample_signal)
        
        assert 0.0 <= impact <= 1.0  # Should provide reasonable default
    
    def test_map_risk_level_to_string(self, decision_agent):
        """Test risk level mapping to strings"""
        assert decision_agent._map_risk_level_to_string(RiskLevel.LOW) == "low"
        assert decision_agent._map_risk_level_to_string(RiskLevel.MEDIUM) == "medium"
        assert decision_agent._map_risk_level_to_string(RiskLevel.HIGH) == "high"
        assert decision_agent._map_risk_level_to_string(RiskLevel.CRITICAL) == "critical"
    
    def test_map_string_to_risk_level(self, decision_agent):
        """Test string mapping to risk levels"""
        assert decision_agent._map_string_to_risk_level("low") == RiskLevel.LOW
        assert decision_agent._map_string_to_risk_level("medium") == RiskLevel.MEDIUM
        assert decision_agent._map_string_to_risk_level("high") == RiskLevel.HIGH
        assert decision_agent._map_string_to_risk_level("critical") == RiskLevel.CRITICAL
        
        # Test default fallback
        assert decision_agent._map_string_to_risk_level("unknown") == RiskLevel.MEDIUM
    
    def test_calculate_confidence_score_high_confidence(self, decision_agent):
        """Test confidence score calculation for highly confident decisions"""
        factors = {
            "complexity": 0.2,  # Low complexity
            "cross_system_impact": 0.1,  # Low impact
            "risk_level": RiskLevel.LOW,  # Low risk
            "action_count": 1  # Single action
        }
        
        confidence = decision_agent._calculate_confidence_score(factors)
        
        assert confidence >= 0.8
    
    def test_calculate_confidence_score_low_confidence(self, decision_agent):
        """Test confidence score calculation for low confidence decisions"""
        factors = {
            "complexity": 0.9,  # High complexity
            "cross_system_impact": 0.8,  # High impact
            "risk_level": RiskLevel.CRITICAL,  # Critical risk
            "action_count": 10  # Many actions
        }
        
        confidence = decision_agent._calculate_confidence_score(factors)
        
        assert confidence <= 0.5
    
    def test_estimate_effort_simple_actions(self, decision_agent):
        """Test effort estimation for simple actions"""
        actions = ["Update user preference"]
        complexity = 0.2
        
        effort = decision_agent._estimate_effort(actions, complexity)
        
        assert effort <= 15  # Should be quick
    
    def test_estimate_effort_complex_actions(self, decision_agent):
        """Test effort estimation for complex actions"""
        actions = [
            "Conduct legal review",
            "Update data processing agreements",
            "Implement new consent system",
            "Migrate data storage",
            "Update privacy policies"
        ]
        complexity = 0.9
        
        effort = decision_agent._estimate_effort(actions, complexity)
        
        assert effort >= 120  # Should take hours
    
    def test_create_llm_prompt(self, decision_agent, sample_signal):
        """Test LLM prompt creation"""
        prompt = decision_agent._create_llm_prompt(sample_signal)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be substantial
        assert "compliance violation" in prompt.lower()
        assert "remediation" in prompt.lower()
        assert sample_signal.violation.violation_type in prompt
        assert str(sample_signal.violation.risk_level.value) in prompt
    
    def test_validate_llm_response_valid(self, decision_agent):
        """Test validation of valid LLM response"""
        response = {
            "decision_type": "automatic",
            "confidence_score": 0.9,
            "reasoning": "Simple operation",
            "estimated_effort": 15,
            "risk_if_delayed": "low"
        }
        
        is_valid = decision_agent._validate_llm_response(response)
        
        assert is_valid is True
    
    def test_validate_llm_response_invalid_decision_type(self, decision_agent):
        """Test validation of LLM response with invalid decision type"""
        response = {
            "decision_type": "invalid_type",  # Invalid
            "confidence_score": 0.9,
            "reasoning": "Simple operation",
            "estimated_effort": 15,
            "risk_if_delayed": "low"
        }
        
        is_valid = decision_agent._validate_llm_response(response)
        
        assert is_valid is False
    
    def test_validate_llm_response_invalid_confidence(self, decision_agent):
        """Test validation of LLM response with invalid confidence score"""
        response = {
            "decision_type": "automatic",
            "confidence_score": 1.5,  # Invalid: > 1
            "reasoning": "Simple operation",
            "estimated_effort": 15,
            "risk_if_delayed": "low"
        }
        
        is_valid = decision_agent._validate_llm_response(response)
        
        assert is_valid is False
    
    def test_validate_llm_response_missing_fields(self, decision_agent):
        """Test validation of LLM response with missing required fields"""
        response = {
            "decision_type": "automatic",
            "confidence_score": 0.9,
            # Missing reasoning, estimated_effort, risk_if_delayed
        }
        
        is_valid = decision_agent._validate_llm_response(response)
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_decision_consistency(self, decision_agent, sample_signal):
        """Test that decisions are consistent for the same input"""
        with patch.object(decision_agent, '_analyze_with_llm') as mock_llm:
            mock_llm.return_value = {
                "decision_type": "automatic",
                "confidence_score": 0.85,
                "reasoning": "Consistent decision test",
                "estimated_effort": 20,
                "risk_if_delayed": "low"
            }
            
            # Make multiple decisions with same input
            decisions = []
            for _ in range(3):
                decision = await decision_agent.make_decision(sample_signal)
                decisions.append(decision)
            
            # All decisions should be identical
            for decision in decisions[1:]:
                assert decision.remediation_type == decisions[0].remediation_type
                assert decision.confidence_score == decisions[0].confidence_score
                assert decision.reasoning == decisions[0].reasoning
                assert decision.estimated_effort == decisions[0].estimated_effort
    
    def test_get_decision_rationale_automatic(self, decision_agent):
        """Test decision rationale for automatic decisions"""
        factors = {
            "complexity": 0.2,
            "cross_system_impact": 0.1,
            "risk_level": RiskLevel.LOW,
            "action_count": 1
        }
        
        rationale = decision_agent._get_decision_rationale("automatic", factors)
        
        assert isinstance(rationale, str)
        assert len(rationale) > 20
        assert "automatic" in rationale.lower()
        assert "low" in rationale.lower()
    
    def test_get_decision_rationale_manual_only(self, decision_agent):
        """Test decision rationale for manual-only decisions"""
        factors = {
            "complexity": 0.9,
            "cross_system_impact": 0.8,
            "risk_level": RiskLevel.CRITICAL,
            "action_count": 8
        }
        
        rationale = decision_agent._get_decision_rationale("manual_only", factors)
        
        assert isinstance(rationale, str)
        assert len(rationale) > 20
        assert "manual" in rationale.lower()
        assert ("critical" in rationale.lower() or "complex" in rationale.lower())


class TestDecisionAgentEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def decision_agent(self):
        return DecisionAgent()
    
    @pytest.mark.asyncio
    async def test_make_decision_empty_actions(self, decision_agent, sample_signal):
        """Test decision making with empty remediation actions"""
        sample_signal.violation.remediation_actions = []
        
        decision = await decision_agent.make_decision(sample_signal)
        
        # Should still provide a decision, likely manual_only due to uncertainty
        assert isinstance(decision, RemediationDecision)
        assert decision.remediation_type == RemediationType.MANUAL_ONLY
        assert decision.confidence_score <= 0.5
    
    @pytest.mark.asyncio
    async def test_make_decision_none_actions(self, decision_agent, sample_signal):
        """Test decision making with None remediation actions"""
        sample_signal.violation.remediation_actions = None
        
        decision = await decision_agent.make_decision(sample_signal)
        
        assert isinstance(decision, RemediationDecision)
        assert decision.remediation_type == RemediationType.MANUAL_ONLY
    
    def test_assess_complexity_empty_actions(self, decision_agent):
        """Test complexity assessment with empty actions"""
        complexity = decision_agent._assess_complexity([])
        
        assert complexity == 0.0
    
    def test_assess_complexity_none_actions(self, decision_agent):
        """Test complexity assessment with None actions"""
        complexity = decision_agent._assess_complexity(None)
        
        assert complexity == 1.0  # Maximum complexity for None
    
    def test_estimate_effort_empty_actions(self, decision_agent):
        """Test effort estimation with empty actions"""
        effort = decision_agent._estimate_effort([], 0.0)
        
        assert effort > 0  # Should still provide minimum effort
    
    def test_calculate_confidence_score_edge_values(self, decision_agent):
        """Test confidence score calculation with edge values"""
        factors = {
            "complexity": 1.0,  # Maximum
            "cross_system_impact": 1.0,  # Maximum
            "risk_level": RiskLevel.CRITICAL,
            "action_count": 0  # Edge case
        }
        
        confidence = decision_agent._calculate_confidence_score(factors)
        
        assert 0.0 <= confidence <= 1.0