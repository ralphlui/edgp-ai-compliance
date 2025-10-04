"""
Unit tests for remediation validator
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
from datetime import datetime, timezone

from src.remediation_agent.tools.remediation_validator import RemediationValidator
from src.remediation_agent.state.models import (
    RemediationSignal, 
    WorkflowStep, 
    RemediationWorkflow,
    WorkflowStatus
)
from src.compliance_agent.models.compliance_models import RiskLevel


class TestRemediationValidator:
    """Test RemediationValidator class"""
    
    @pytest.fixture
    def remediation_validator(self):
        """Create a remediation validator instance for testing"""
        return RemediationValidator()
    
    @pytest.mark.asyncio
    async def test_validate_remediation_step_success(self, remediation_validator, sample_workflow_steps):
        """Test successful validation of a remediation step"""
        step = sample_workflow_steps[0]
        step.action = "Update user email preference to opt-out"
        
        with patch.object(remediation_validator, '_check_database_state') as mock_db_check, \
             patch.object(remediation_validator, '_verify_system_availability') as mock_sys_check:
            
            mock_db_check.return_value = {"valid": True, "user_exists": True}
            mock_sys_check.return_value = {"available": True, "response_time": 50}
            
            result = await remediation_validator.validate_remediation_step(step)
            
            assert result["valid"] is True
            assert result["validation_score"] >= 0.8
            assert len(result["errors"]) == 0
            assert "validation_details" in result
    
    @pytest.mark.asyncio
    async def test_validate_remediation_step_database_error(self, remediation_validator, sample_workflow_steps):
        """Test validation with database connectivity issues"""
        step = sample_workflow_steps[0]
        
        with patch.object(remediation_validator, '_check_database_state') as mock_db_check:
            mock_db_check.return_value = {"valid": False, "error": "Database connection timeout"}
            
            result = await remediation_validator.validate_remediation_step(step)
            
            assert result["valid"] is False
            assert "Database connection timeout" in str(result["errors"])
            assert result["validation_score"] < 0.5
    
    @pytest.mark.asyncio
    async def test_validate_remediation_step_system_unavailable(self, remediation_validator, sample_workflow_steps):
        """Test validation with system unavailability"""
        step = sample_workflow_steps[0]
        
        with patch.object(remediation_validator, '_verify_system_availability') as mock_sys_check:
            mock_sys_check.return_value = {"available": False, "error": "Service temporarily unavailable"}
            
            result = await remediation_validator.validate_remediation_step(step)
            
            assert result["valid"] is False
            assert "Service temporarily unavailable" in str(result["errors"])
    
    @pytest.mark.asyncio
    async def test_validate_complete_workflow(self, remediation_validator, sample_remediation_workflow):
        """Test validation of complete workflow"""
        with patch.object(remediation_validator, 'validate_remediation_step') as mock_validate_step:
            mock_validate_step.return_value = {
                "valid": True,
                "validation_score": 0.9,
                "errors": [],
                "validation_details": {"checks_passed": 5}
            }
            
            result = await remediation_validator.validate_complete_workflow(sample_remediation_workflow)
            
            assert result["valid"] is True
            assert result["overall_score"] >= 0.8
            assert result["steps_validated"] == len(sample_remediation_workflow.steps)
            assert len(result["failed_steps"]) == 0
    
    @pytest.mark.asyncio
    async def test_validate_complete_workflow_with_failures(self, remediation_validator, sample_remediation_workflow):
        """Test validation of workflow with some step failures"""
        def mock_validate_step_side_effect(step):
            if "delete" in step.action.lower():
                return {
                    "valid": False,
                    "validation_score": 0.2,
                    "errors": ["Data integrity check failed"],
                    "validation_details": {"checks_passed": 1}
                }
            else:
                return {
                    "valid": True,
                    "validation_score": 0.9,
                    "errors": [],
                    "validation_details": {"checks_passed": 5}
                }
        
        with patch.object(remediation_validator, 'validate_remediation_step') as mock_validate_step:
            mock_validate_step.side_effect = mock_validate_step_side_effect
            
            result = await remediation_validator.validate_complete_workflow(sample_remediation_workflow)
            
            assert result["valid"] is False
            assert len(result["failed_steps"]) > 0
            assert result["overall_score"] < 0.8
    
    @pytest.mark.asyncio
    async def test_validate_data_integrity(self, remediation_validator, sample_workflow_steps):
        """Test data integrity validation"""
        step = sample_workflow_steps[0]
        step.action = "Delete user personal data from users table"
        
        with patch.object(remediation_validator, '_check_data_relationships') as mock_relationships, \
             patch.object(remediation_validator, '_verify_backup_exists') as mock_backup:
            
            mock_relationships.return_value = {"valid": True, "orphaned_records": 0}
            mock_backup.return_value = {"exists": True, "backup_id": "backup-123"}
            
            result = await remediation_validator.validate_data_integrity(step)
            
            assert result["valid"] is True
            assert result["backup_verified"] is True
            assert result["relationship_check_passed"] is True
    
    @pytest.mark.asyncio
    async def test_validate_data_integrity_no_backup(self, remediation_validator, sample_workflow_steps):
        """Test data integrity validation when backup is missing"""
        step = sample_workflow_steps[0]
        step.action = "Delete user personal data from users table"
        
        with patch.object(remediation_validator, '_verify_backup_exists') as mock_backup:
            mock_backup.return_value = {"exists": False, "error": "No recent backup found"}
            
            result = await remediation_validator.validate_data_integrity(step)
            
            assert result["valid"] is False
            assert result["backup_verified"] is False
            assert "No recent backup found" in str(result["errors"])
    
    @pytest.mark.asyncio
    async def test_validate_compliance_requirements(self, remediation_validator, sample_remediation_signal):
        """Test compliance requirements validation"""
        with patch.object(remediation_validator, '_check_gdpr_compliance') as mock_gdpr, \
             patch.object(remediation_validator, '_check_retention_policies') as mock_retention:
            
            mock_gdpr.return_value = {"compliant": True, "requirements_met": ["right_to_erasure", "data_minimization"]}
            mock_retention.return_value = {"compliant": True, "retention_period_valid": True}
            
            result = await remediation_validator.validate_compliance_requirements(sample_remediation_signal)
            
            assert result["compliant"] is True
            assert len(result["requirements_met"]) >= 2
            assert result["retention_policy_compliant"] is True
    
    @pytest.mark.asyncio
    async def test_validate_compliance_requirements_gdpr_violation(self, remediation_validator, sample_remediation_signal):
        """Test compliance validation with GDPR violations"""
        with patch.object(remediation_validator, '_check_gdpr_compliance') as mock_gdpr:
            mock_gdpr.return_value = {
                "compliant": False, 
                "violations": ["Insufficient legal basis for processing"]
            }
            
            result = await remediation_validator.validate_compliance_requirements(sample_remediation_signal)
            
            assert result["compliant"] is False
            assert len(result["violations"]) > 0
    
    @pytest.mark.asyncio
    async def test_validate_system_state(self, remediation_validator):
        """Test system state validation"""
        affected_systems = ["user_database", "email_service", "analytics_db"]
        
        with patch.object(remediation_validator, '_check_system_health') as mock_health, \
             patch.object(remediation_validator, '_verify_system_capacity') as mock_capacity:
            
            mock_health.return_value = {"healthy": True, "uptime": "99.9%"}
            mock_capacity.return_value = {"sufficient": True, "cpu_usage": 45, "memory_usage": 60}
            
            result = await remediation_validator.validate_system_state(affected_systems)
            
            assert result["valid"] is True
            assert result["all_systems_healthy"] is True
            assert result["capacity_sufficient"] is True
    
    @pytest.mark.asyncio
    async def test_validate_system_state_capacity_issues(self, remediation_validator):
        """Test system state validation with capacity issues"""
        affected_systems = ["user_database"]
        
        with patch.object(remediation_validator, '_verify_system_capacity') as mock_capacity:
            mock_capacity.return_value = {
                "sufficient": False, 
                "cpu_usage": 95, 
                "memory_usage": 90,
                "warning": "High resource utilization"
            }
            
            result = await remediation_validator.validate_system_state(affected_systems)
            
            assert result["valid"] is False
            assert result["capacity_sufficient"] is False
            assert "High resource utilization" in str(result["warnings"])
    
    def test_check_database_state_user_exists(self, remediation_validator):
        """Test database state check for existing user"""
        user_id = "user-123"
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (1,)  # User exists
            
            result = remediation_validator._check_database_state(user_id)
            
            assert result["valid"] is True
            assert result["user_exists"] is True
    
    def test_check_database_state_user_not_exists(self, remediation_validator):
        """Test database state check for non-existing user"""
        user_id = "nonexistent-user"
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None  # User doesn't exist
            
            result = remediation_validator._check_database_state(user_id)
            
            assert result["valid"] is False
            assert result["user_exists"] is False
    
    def test_check_database_state_connection_error(self, remediation_validator):
        """Test database state check with connection error"""
        user_id = "user-123"
        
        with patch('psycopg2.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection refused")
            
            result = remediation_validator._check_database_state(user_id)
            
            assert result["valid"] is False
            assert "Connection refused" in result["error"]
    
    @pytest.mark.asyncio
    async def test_verify_system_availability_healthy(self, remediation_validator):
        """Test system availability check for healthy system"""
        system_name = "user_service"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"status": "healthy", "version": "1.0.0"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await remediation_validator._verify_system_availability(system_name)
            
            assert result["available"] is True
            assert result["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_verify_system_availability_unhealthy(self, remediation_validator):
        """Test system availability check for unhealthy system"""
        system_name = "user_service"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 503
            mock_response.json.return_value = {"status": "unhealthy", "error": "Database connection lost"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await remediation_validator._verify_system_availability(system_name)
            
            assert result["available"] is False
            assert "Database connection lost" in result["error"]
    
    def test_check_data_relationships_valid(self, remediation_validator):
        """Test data relationship check with valid relationships"""
        user_id = "user-123"
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (0,)  # No orphaned records
            
            result = remediation_validator._check_data_relationships(user_id)
            
            assert result["valid"] is True
            assert result["orphaned_records"] == 0
    
    def test_check_data_relationships_orphaned_records(self, remediation_validator):
        """Test data relationship check with orphaned records"""
        user_id = "user-123"
        
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (5,)  # 5 orphaned records
            
            result = remediation_validator._check_data_relationships(user_id)
            
            assert result["valid"] is False
            assert result["orphaned_records"] == 5
    
    def test_verify_backup_exists_recent_backup(self, remediation_validator):
        """Test backup verification with recent backup"""
        table_name = "users"
        
        with patch('os.path.exists') as mock_exists, \
             patch('os.path.getmtime') as mock_getmtime:
            
            mock_exists.return_value = True
            mock_getmtime.return_value = datetime.now().timestamp() - 3600  # 1 hour ago
            
            result = remediation_validator._verify_backup_exists(table_name)
            
            assert result["exists"] is True
            assert "backup_id" in result
    
    def test_verify_backup_exists_no_backup(self, remediation_validator):
        """Test backup verification with no backup"""
        table_name = "users"
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            result = remediation_validator._verify_backup_exists(table_name)
            
            assert result["exists"] is False
            assert "No backup found" in result["error"]
    
    def test_verify_backup_exists_old_backup(self, remediation_validator):
        """Test backup verification with old backup"""
        table_name = "users"
        
        with patch('os.path.exists') as mock_exists, \
             patch('os.path.getmtime') as mock_getmtime:
            
            mock_exists.return_value = True
            mock_getmtime.return_value = datetime.now().timestamp() - 86400 * 8  # 8 days ago
            
            result = remediation_validator._verify_backup_exists(table_name)
            
            assert result["exists"] is True
            assert result["backup_age_days"] > 7
            assert "warning" in result
    
    def test_check_gdpr_compliance_compliant(self, remediation_validator, sample_remediation_signal):
        """Test GDPR compliance check for compliant remediation"""
        sample_remediation_signal.violation.violation_type = "data_subject_request"
        sample_remediation_signal.violation.data_subject_id = "user-123"
        
        result = remediation_validator._check_gdpr_compliance(sample_remediation_signal)
        
        assert result["compliant"] is True
        assert "right_to_erasure" in result["requirements_met"]
    
    def test_check_gdpr_compliance_non_compliant(self, remediation_validator, sample_remediation_signal):
        """Test GDPR compliance check for non-compliant remediation"""
        sample_remediation_signal.violation.violation_type = "data_processing_without_consent"
        sample_remediation_signal.context = {"legal_basis": None}
        
        result = remediation_validator._check_gdpr_compliance(sample_remediation_signal)
        
        assert result["compliant"] is False
        assert len(result["violations"]) > 0
    
    def test_check_retention_policies_compliant(self, remediation_validator, sample_remediation_signal):
        """Test retention policy check for compliant data"""
        sample_remediation_signal.context = {
            "data_retention_period": 365,  # 1 year
            "data_age_days": 400  # Older than retention period
        }
        
        result = remediation_validator._check_retention_policies(sample_remediation_signal)
        
        assert result["compliant"] is True
        assert result["retention_period_valid"] is True
        assert result["data_eligible_for_deletion"] is True
    
    def test_check_retention_policies_non_compliant(self, remediation_validator, sample_remediation_signal):
        """Test retention policy check for non-compliant data"""
        sample_remediation_signal.context = {
            "data_retention_period": 365,  # 1 year
            "data_age_days": 200  # Younger than retention period
        }
        
        result = remediation_validator._check_retention_policies(sample_remediation_signal)
        
        assert result["compliant"] is False
        assert result["data_eligible_for_deletion"] is False
    
    def test_calculate_validation_score_high_score(self, remediation_validator):
        """Test validation score calculation for high-confidence validation"""
        checks = {
            "database_check": {"valid": True, "confidence": 0.9},
            "system_availability": {"available": True, "confidence": 0.95},
            "data_integrity": {"valid": True, "confidence": 0.85},
            "compliance_check": {"compliant": True, "confidence": 0.9}
        }
        
        score = remediation_validator._calculate_validation_score(checks)
        
        assert score >= 0.85
    
    def test_calculate_validation_score_low_score(self, remediation_validator):
        """Test validation score calculation for low-confidence validation"""
        checks = {
            "database_check": {"valid": False, "confidence": 0.3},
            "system_availability": {"available": True, "confidence": 0.7},
            "data_integrity": {"valid": False, "confidence": 0.4}
        }
        
        score = remediation_validator._calculate_validation_score(checks)
        
        assert score <= 0.5
    
    @pytest.mark.asyncio
    async def test_validate_step_prerequisites(self, remediation_validator, sample_workflow_steps):
        """Test validation of step prerequisites"""
        step = sample_workflow_steps[0]
        step.action = "Delete user personal data"
        step.prerequisites = ["backup_completed", "user_consent_verified"]
        
        with patch.object(remediation_validator, '_verify_prerequisite') as mock_verify:
            mock_verify.return_value = {"met": True, "details": "Prerequisite satisfied"}
            
            result = await remediation_validator.validate_step_prerequisites(step)
            
            assert result["valid"] is True
            assert result["prerequisites_met"] == len(step.prerequisites)
            assert mock_verify.call_count == len(step.prerequisites)
    
    @pytest.mark.asyncio
    async def test_validate_step_prerequisites_unmet(self, remediation_validator, sample_workflow_steps):
        """Test validation with unmet prerequisites"""
        step = sample_workflow_steps[0]
        step.prerequisites = ["backup_completed", "legal_approval"]
        
        def mock_verify_side_effect(prerequisite):
            if prerequisite == "legal_approval":
                return {"met": False, "error": "Legal approval pending"}
            return {"met": True, "details": "Prerequisite satisfied"}
        
        with patch.object(remediation_validator, '_verify_prerequisite') as mock_verify:
            mock_verify.side_effect = mock_verify_side_effect
            
            result = await remediation_validator.validate_step_prerequisites(step)
            
            assert result["valid"] is False
            assert len(result["unmet_prerequisites"]) == 1
            assert "legal_approval" in result["unmet_prerequisites"]