"""
Unit tests for validation agent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from src.remediation_agent.agents.validation_agent import ValidationAgent
from src.remediation_agent.state.models import RemediationSignal
from src.compliance_agent.models.compliance_models import RiskLevel


class TestValidationAgent:
    """Test ValidationAgent class"""
    
    @pytest.fixture
    def validation_agent(self):
        """Create a validation agent instance for testing"""
        return ValidationAgent()
    
    @pytest.mark.asyncio
    async def test_assess_feasibility_high_feasibility(self, validation_agent, sample_remediation_signal):
        """Test feasibility assessment for highly feasible remediation"""
        # Modify signal for high feasibility scenario
        sample_remediation_signal.violation.remediation_actions = [
            "Update user email preference",
            "Set marketing opt-out flag"
        ]
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        
        result = await validation_agent.assess_feasibility(sample_remediation_signal)
        
        assert result["feasible"] is True
        assert result["overall_feasibility_score"] >= 0.8
        assert result["automation_recommendation"] == "automatic"
        assert len(result["blockers"]) == 0
        assert len(result["prerequisites"]) >= 0
    
    @pytest.mark.asyncio
    async def test_assess_feasibility_medium_feasibility(self, validation_agent, sample_remediation_signal):
        """Test feasibility assessment for medium feasibility remediation"""
        # Modify signal for medium feasibility scenario
        sample_remediation_signal.violation.remediation_actions = [
            "Delete user data from database",
            "Remove user from mailing lists",
            "Verify complete data removal"
        ]
        sample_remediation_signal.violation.risk_level = RiskLevel.MEDIUM
        
        result = await validation_agent.assess_feasibility(sample_remediation_signal)
        
        assert result["feasible"] is True
        assert 0.5 <= result["overall_feasibility_score"] < 0.8
        assert result["automation_recommendation"] == "human_in_loop"
        assert len(result["prerequisites"]) > 0
    
    @pytest.mark.asyncio
    async def test_assess_feasibility_low_feasibility(self, validation_agent, sample_remediation_signal):
        """Test feasibility assessment for low feasibility remediation"""
        # Modify signal for low feasibility scenario
        sample_remediation_signal.violation.remediation_actions = [
            "Conduct legal review of data processing agreements",
            "Renegotiate third-party contracts",
            "Implement complex cross-system data migration"
        ]
        sample_remediation_signal.violation.risk_level = RiskLevel.CRITICAL
        
        result = await validation_agent.assess_feasibility(sample_remediation_signal)
        
        assert result["overall_feasibility_score"] < 0.5
        assert result["automation_recommendation"] == "manual_only"
        assert len(result["blockers"]) > 0
        assert len(result["prerequisites"]) > 0
    
    @pytest.mark.asyncio
    async def test_assess_feasibility_no_actions(self, validation_agent, sample_remediation_signal):
        """Test feasibility assessment when no remediation actions are provided"""
        # Remove remediation actions
        sample_remediation_signal.violation.remediation_actions = []
        
        result = await validation_agent.assess_feasibility(sample_remediation_signal)
        
        assert result["feasible"] is False
        assert result["overall_feasibility_score"] == 0.0
        assert "No remediation actions provided" in result["blockers"]
    
    def test_analyze_remediation_actions_automatable(self, validation_agent):
        """Test analysis of automatable remediation actions"""
        actions = [
            "Update user preference setting",
            "Set email opt-out flag",
            "Remove user from automated campaigns"
        ]
        
        result = validation_agent._analyze_remediation_actions(actions)
        
        assert result["total_actions"] == 3
        assert result["high_feasibility_count"] >= 2
        assert result["average_feasibility"] >= 0.7
        assert result["automation_patterns_found"] > 0
    
    def test_analyze_remediation_actions_complex(self, validation_agent):
        """Test analysis of complex remediation actions"""
        actions = [
            "Conduct comprehensive legal review",
            "Renegotiate data processing agreements",
            "Implement cross-system data migration with rollback"
        ]
        
        result = validation_agent._analyze_remediation_actions(actions)
        
        assert result["total_actions"] == 3
        assert result["high_feasibility_count"] == 0
        assert result["average_feasibility"] < 0.5
        assert len(result["actions"]) == 3
        
        # Check that complex actions are correctly classified
        for action_detail in result["actions"]:
            assert action_detail["feasibility"] < 0.7
            assert action_detail["classification"] in ["manual", "complex"]
    
    def test_classify_action_type_data_modification(self, validation_agent):
        """Test classification of data modification actions"""
        action = "Delete user personal data from database"
        
        classification = validation_agent._classify_action_type(action)
        
        assert classification == "data_modification"
    
    def test_classify_action_type_system_configuration(self, validation_agent):
        """Test classification of system configuration actions"""
        action = "Update privacy settings configuration"
        
        classification = validation_agent._classify_action_type(action)
        
        assert classification == "system_configuration"
    
    def test_classify_action_type_notification(self, validation_agent):
        """Test classification of notification actions"""
        action = "Send data deletion confirmation email to user"
        
        classification = validation_agent._classify_action_type(action)
        
        assert classification == "notification"
    
    def test_classify_action_type_manual_review(self, validation_agent):
        """Test classification of manual review actions"""
        action = "Conduct legal compliance review"
        
        classification = validation_agent._classify_action_type(action)
        
        assert classification == "manual_review"
    
    def test_classify_action_type_default(self, validation_agent):
        """Test classification of unrecognized actions"""
        action = "Some completely unknown action type"
        
        classification = validation_agent._classify_action_type(action)
        
        assert classification == "other"
    
    def test_identify_blockers_high_risk_data_operations(self, validation_agent, sample_remediation_signal):
        """Test identification of blockers for high-risk data operations"""
        sample_remediation_signal.violation.risk_level = RiskLevel.CRITICAL
        sample_remediation_signal.violation.remediation_actions = [
            "Permanently delete all user data across systems"
        ]
        sample_remediation_signal.context = {
            "affected_systems": ["production_db", "analytics_db", "backup_systems"]
        }
        
        blockers = validation_agent._identify_blockers(sample_remediation_signal)
        
        assert len(blockers) > 0
        assert any("critical risk" in blocker.lower() for blocker in blockers)
        assert any("multiple systems" in blocker.lower() for blocker in blockers)
    
    def test_identify_blockers_complex_actions(self, validation_agent, sample_remediation_signal):
        """Test identification of blockers for complex actions"""
        sample_remediation_signal.violation.remediation_actions = [
            "Renegotiate data processing agreements with third parties",
            "Implement complex data migration across multiple systems"
        ]
        
        blockers = validation_agent._identify_blockers(sample_remediation_signal)
        
        assert len(blockers) > 0
        assert any("complex" in blocker.lower() or "manual" in blocker.lower() for blocker in blockers)
    
    def test_identify_blockers_no_blockers(self, validation_agent, sample_remediation_signal):
        """Test identification when no blockers exist"""
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        sample_remediation_signal.violation.remediation_actions = [
            "Update user preference setting"
        ]
        sample_remediation_signal.context = {
            "affected_systems": ["user_preferences"]
        }
        
        blockers = validation_agent._identify_blockers(sample_remediation_signal)
        
        assert len(blockers) == 0
    
    def test_identify_prerequisites_data_operations(self, validation_agent, sample_remediation_signal):
        """Test identification of prerequisites for data operations"""
        sample_remediation_signal.violation.remediation_actions = [
            "Delete user personal data",
            "Verify data deletion"
        ]
        
        prerequisites = validation_agent._identify_prerequisites(sample_remediation_signal)
        
        assert len(prerequisites) > 0
        expected_prereqs = ["backup", "verification", "approval"]
        assert any(any(expected in prereq.lower() for expected in expected_prereqs) 
                  for prereq in prerequisites)
    
    def test_identify_prerequisites_notification_actions(self, validation_agent, sample_remediation_signal):
        """Test identification of prerequisites for notification actions"""
        sample_remediation_signal.violation.remediation_actions = [
            "Send data processing notification to user",
            "Update privacy policy"
        ]
        
        prerequisites = validation_agent._identify_prerequisites(sample_remediation_signal)
        
        assert len(prerequisites) > 0
        assert any("template" in prereq.lower() or "content" in prereq.lower() 
                  for prereq in prerequisites)
    
    def test_identify_prerequisites_minimal_actions(self, validation_agent, sample_remediation_signal):
        """Test identification of prerequisites for minimal actions"""
        sample_remediation_signal.violation.remediation_actions = [
            "Update user preference"
        ]
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        
        prerequisites = validation_agent._identify_prerequisites(sample_remediation_signal)
        
        # Should have minimal prerequisites for simple actions
        assert len(prerequisites) <= 2
    
    def test_determine_automation_recommendation_high_feasibility(self, validation_agent):
        """Test automation recommendation for high feasibility score"""
        recommendation = validation_agent._determine_automation_recommendation(0.9, RiskLevel.LOW, [])
        
        assert recommendation == "automatic"
    
    def test_determine_automation_recommendation_medium_feasibility(self, validation_agent):
        """Test automation recommendation for medium feasibility score"""
        recommendation = validation_agent._determine_automation_recommendation(0.6, RiskLevel.MEDIUM, [])
        
        assert recommendation == "human_in_loop"
    
    def test_determine_automation_recommendation_low_feasibility(self, validation_agent):
        """Test automation recommendation for low feasibility score"""
        recommendation = validation_agent._determine_automation_recommendation(0.3, RiskLevel.HIGH, ["Complex operation"])
        
        assert recommendation == "manual_only"
    
    def test_determine_automation_recommendation_with_blockers(self, validation_agent):
        """Test automation recommendation when blockers exist"""
        recommendation = validation_agent._determine_automation_recommendation(
            0.8, RiskLevel.LOW, ["Critical system dependency"]
        )
        
        assert recommendation == "manual_only"
    
    def test_determine_automation_recommendation_critical_risk(self, validation_agent):
        """Test automation recommendation for critical risk level"""
        recommendation = validation_agent._determine_automation_recommendation(0.8, RiskLevel.CRITICAL, [])
        
        assert recommendation in ["human_in_loop", "manual_only"]
    
    def test_calculate_action_feasibility_simple_data_update(self, validation_agent):
        """Test feasibility calculation for simple data update"""
        action = "Update user email address"
        
        feasibility = validation_agent._calculate_action_feasibility(action)
        
        assert feasibility >= 0.8
    
    def test_calculate_action_feasibility_complex_operation(self, validation_agent):
        """Test feasibility calculation for complex operation"""
        action = "Conduct comprehensive legal review of data processing agreements"
        
        feasibility = validation_agent._calculate_action_feasibility(action)
        
        assert feasibility <= 0.3
    
    def test_calculate_action_feasibility_data_deletion(self, validation_agent):
        """Test feasibility calculation for data deletion"""
        action = "Delete user personal data from database"
        
        feasibility = validation_agent._calculate_action_feasibility(action)
        
        assert 0.4 <= feasibility <= 0.7  # Medium feasibility
    
    def test_match_automation_patterns_database_operations(self, validation_agent):
        """Test pattern matching for database operations"""
        action = "Delete user record from users table"
        
        patterns = validation_agent._match_automation_patterns(action)
        
        assert len(patterns) > 0
        assert any(pattern["pattern"] == "database_operation" for pattern in patterns)
        assert any(pattern["confidence"] > 0.7 for pattern in patterns)
    
    def test_match_automation_patterns_api_calls(self, validation_agent):
        """Test pattern matching for API calls"""
        action = "Send API request to update user preferences"
        
        patterns = validation_agent._match_automation_patterns(action)
        
        assert len(patterns) > 0
        assert any(pattern["pattern"] == "api_call" for pattern in patterns)
    
    def test_match_automation_patterns_no_patterns(self, validation_agent):
        """Test pattern matching when no patterns match"""
        action = "Conduct philosophical discussion about data rights"
        
        patterns = validation_agent._match_automation_patterns(action)
        
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_feasibility_assessment_consistency(self, validation_agent, sample_remediation_signal):
        """Test that feasibility assessment is consistent across multiple calls"""
        # Run assessment multiple times
        results = []
        for _ in range(3):
            result = await validation_agent.assess_feasibility(sample_remediation_signal)
            results.append(result)
        
        # Check consistency
        feasibility_scores = [r["overall_feasibility_score"] for r in results]
        recommendations = [r["automation_recommendation"] for r in results]
        
        # Scores should be identical (deterministic)
        assert all(score == feasibility_scores[0] for score in feasibility_scores)
        assert all(rec == recommendations[0] for rec in recommendations)
    
    def test_feasibility_scoring_edge_cases(self, validation_agent):
        """Test feasibility scoring for edge cases"""
        # Empty action
        feasibility_empty = validation_agent._calculate_action_feasibility("")
        assert feasibility_empty == 0.0
        
        # Very long action description
        long_action = "This is a very long action description that goes on and on " * 10
        feasibility_long = validation_agent._calculate_action_feasibility(long_action)
        assert 0.0 <= feasibility_long <= 1.0
        
        # Action with special characters
        special_action = "Update user@domain.com preferences with $pecial ch@racters!"
        feasibility_special = validation_agent._calculate_action_feasibility(special_action)
        assert 0.0 <= feasibility_special <= 1.0