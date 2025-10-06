"""
Integration tests for the API endpoints
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from src.compliance_agent.api.main import app
from src.compliance_agent.models.compliance_models import (
    ComplianceFramework,
    DataType,
    RiskLevel,
    ComplianceStatus,
    DataProcessingActivity,
    ComplianceAssessment,
    PrivacyImpactAssessment
)


class TestComplianceAPI:
    """Test compliance API endpoints"""
    
    @pytest.fixture
    def client(self, mock_compliance_engine):
        """Create test client with mocked dependencies"""
        from src.compliance_agent.api.routers.compliance_router import get_compliance_engine
        
        # Override the dependency
        app.dependency_overrides[get_compliance_engine] = lambda: mock_compliance_engine
        
        yield TestClient(app)
        
        # Clean up
        app.dependency_overrides.clear()
    
    @pytest.fixture
    def sample_activity_data(self):
        """Sample activity data for testing"""
        return {
            "id": "test_activity_001",
            "name": "Customer Registration",
            "purpose": "Collect customer information for account creation",
            "data_types": ["personal_data", "financial_data"],
            "legal_bases": ["consent", "contract"],
            "retention_period": 2555,
            "recipients": ["internal_team", "payment_processor"],
            "cross_border_transfers": False,
            "automated_decision_making": False
        }
    
    @pytest.fixture
    def mock_compliance_engine(self):
        """Mock compliance engine for testing"""
        engine = Mock()
        engine.assess_compliance = AsyncMock()
        engine.conduct_privacy_impact_assessment = AsyncMock()
        return engine
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["message"] == "AI Compliance Agent API"
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert data["status"] == "healthy"
    
    def test_get_supported_frameworks(self, client):
        """Test get supported frameworks endpoint"""
        response = client.get("/api/v1/compliance/frameworks")
        assert response.status_code == 200
        data = response.json()
        assert "frameworks" in data
        assert len(data["frameworks"]) > 0
        
        # Check that PDPA Singapore is included
        framework_codes = [f["code"] for f in data["frameworks"]]
        assert "pdpa_singapore" in framework_codes
        assert "gdpr_eu" in framework_codes
    
    def test_get_supported_data_types(self, client):
        """Test get supported data types endpoint"""
        response = client.get("/api/v1/compliance/data-types")
        assert response.status_code == 200
        data = response.json()
        assert "data_types" in data
        assert len(data["data_types"]) > 0
        
        # Check that personal data is included
        data_type_codes = [dt["code"] for dt in data["data_types"]]
        assert "personal_data" in data_type_codes
        assert "sensitive_data" in data_type_codes
    
    def test_get_risk_levels(self, client):
        """Test get risk levels endpoint"""
        response = client.get("/api/v1/compliance/risk-levels")
        assert response.status_code == 200
        data = response.json()
        assert "risk_levels" in data
        assert len(data["risk_levels"]) == 4
        
        # Check all risk levels are present
        risk_level_codes = [rl["code"] for rl in data["risk_levels"]]
        assert "low" in risk_level_codes
        assert "medium" in risk_level_codes
        assert "high" in risk_level_codes
        assert "critical" in risk_level_codes
    
    def test_check_compliance(self, client, sample_activity_data, mock_compliance_engine):
        """Test compliance check endpoint"""
        
        mock_assessment = ComplianceAssessment(
            id="test_assessment",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            activity=DataProcessingActivity(**sample_activity_data),
            status=ComplianceStatus.COMPLIANT,
            score=95.0,
            assessor="test_engine",
            violations=[],
            recommendations=["Continue good practices"]
        )
        mock_compliance_engine.assess_compliance.return_value = [mock_assessment]
        
        # Make request
        request_data = {
            "activity": sample_activity_data,
            "frameworks": ["pdpa_singapore"],
            "include_ai_analysis": True
        }
        
        response = client.post("/api/v1/compliance/check", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "assessments" in data
        assert "overall_status" in data
        assert "summary" in data
        assert len(data["assessments"]) == 1
        assert data["overall_status"] == "compliant"


class TestPrivacyAPI:
    """Test privacy API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        yield TestClient(app)
        # Clean up any overrides
        app.dependency_overrides.clear()
    
    def test_get_data_subject_rights(self, client):
        """Test get data subject rights endpoint"""
        response = client.get("/api/v1/privacy/data-subject-rights")
        assert response.status_code == 200
        data = response.json()
        assert "rights" in data
        assert len(data["rights"]) > 0
        
        # Check that basic rights are included
        right_names = [r["name"] for r in data["rights"]]
        assert "Right of Access" in right_names
        assert "Right to Erasure" in right_names
    
    def test_get_privacy_principles(self, client):
        """Test get privacy principles endpoint"""
        response = client.get("/api/v1/privacy/privacy-principles")
        assert response.status_code == 200
        data = response.json()
        assert "principles" in data
        assert len(data["principles"]) > 0
        
        # Check that fundamental principles are included
        principle_names = [p["name"] for p in data["principles"]]
        assert "Purpose Limitation" in principle_names
        assert "Data Minimisation" in principle_names
    
    def test_record_consent(self, client):
        """Test record consent endpoint"""
        consent_data = {
            "subject_id": "subject_001",
            "purpose": "Marketing communications",
            "data_types": ["personal_data"],
            "consent_given": True,
            "consent_method": "web_form",
            "legal_basis": "consent"
        }
        
        response = client.post("/api/v1/privacy/consent", json=consent_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "consent_id" in data
        assert "successfully" in data["message"].lower()
    
    def test_get_consent_records(self, client):
        """Test get consent records endpoint"""
        response = client.get("/api/v1/privacy/consent/subject_001")
        assert response.status_code == 200
        data = response.json()
        assert "subject_id" in data
        assert "consent_records" in data
        assert data["subject_id"] == "subject_001"
    
    def test_withdraw_consent(self, client):
        """Test withdraw consent endpoint"""
        response = client.delete("/api/v1/privacy/consent/consent_001")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "consent_id" in data
        assert "withdrawn" in data["message"].lower()
    
    def test_conduct_pia(self, client):
        """Test conduct PIA endpoint"""
        from src.compliance_agent.api.routers.privacy_router import get_compliance_engine
        
        # Setup mock
        mock_engine = Mock()
        
        sample_activity = DataProcessingActivity(
            id="pia_activity",
            name="Test Activity",
            purpose="Testing",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            recipients=[]
        )
        
        mock_pia = PrivacyImpactAssessment(
            id="test_pia",
            project_name="Test Project",
            description="Test PIA",
            data_types=[DataType.PERSONAL_DATA],
            processing_activities=[sample_activity],
            risk_assessment={"test": 25.0},
            mitigation_measures=["Test measure"],
            overall_risk=RiskLevel.MEDIUM,
            requires_consultation=False
        )
        mock_engine.conduct_privacy_impact_assessment = AsyncMock(return_value=mock_pia)
        
        # Override dependency
        app.dependency_overrides[get_compliance_engine] = lambda: mock_engine
        
        # Make request
        request_data = {
            "project_name": "Test Project",
            "description": "Test project description",
            "processing_activities": [{
                "id": "pia_activity",
                "name": "Test Activity",
                "purpose": "Testing",
                "data_types": ["personal_data"],
                "legal_bases": ["consent"],
                "recipients": []
            }]
        }
        
        response = client.post("/api/v1/privacy/pia", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "assessment" in data


class TestGovernanceAPI:
    """Test governance API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_get_governance_metrics(self, client):
        """Test get governance metrics endpoint"""
        response = client.get("/api/v1/governance/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "recommendations" in data
        assert isinstance(data["metrics"], dict)
        assert isinstance(data["recommendations"], list)
    
    def test_get_singapore_frameworks(self, client):
        """Test get Singapore frameworks endpoint"""
        response = client.get("/api/v1/governance/frameworks/singapore")
        assert response.status_code == 200
        data = response.json()
        assert "frameworks" in data
        assert len(data["frameworks"]) > 0
        
        # Check that PDPA is included
        framework_names = [f["name"] for f in data["frameworks"]]
        pdpa_found = any("PDPA" in name for name in framework_names)
        assert pdpa_found
    
    def test_get_best_practices(self, client):
        """Test get best practices endpoint"""
        response = client.get("/api/v1/governance/best-practices")
        assert response.status_code == 200
        data = response.json()
        assert "best_practices" in data
        assert len(data["best_practices"]) > 0
        
        # Check that key categories are included
        categories = [bp["category"] for bp in data["best_practices"]]
        assert "Data Classification" in categories
        assert "Access Control" in categories
    
    def test_report_data_breach(self, client):
        """Test report data breach endpoint"""
        breach_data = {
            "severity": "high",
            "affected_subjects_count": 1500,
            "data_types_affected": ["personal_data", "financial_data"],
            "breach_date": "2024-01-01T10:00:00Z",
            "discovered_date": "2024-01-01T14:00:00Z",
            "description": "Unauthorized access to customer database",
            "cause": "SQL injection attack",
            "impact_assessment": "High impact due to financial data exposure",
            "containment_measures": ["Patched vulnerability", "Reset passwords"]
        }
        
        response = client.post("/api/v1/governance/breach/report", json=breach_data)
        assert response.status_code == 200
        data = response.json()
        assert "incident" in data
        assert "notification_requirements" in data
        assert "next_steps" in data
        assert isinstance(data["next_steps"], list)
    
    def test_get_breach_incident(self, client):
        """Test get breach incident endpoint"""
        response = client.get("/api/v1/governance/breach/incident_001")
        assert response.status_code == 200
        data = response.json()
        assert "incident_id" in data
        assert data["incident_id"] == "incident_001"


class TestAPIErrorHandling:
    """Test API error handling"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_invalid_compliance_check_request(self, client):
        """Test invalid compliance check request"""
        invalid_request = {
            "activity": {},  # Missing required fields
            "frameworks": ["invalid_framework"]
        }
        
        response = client.post("/api/v1/compliance/check", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    def test_invalid_pia_request(self, client):
        """Test invalid PIA request"""
        invalid_request = {
            "project_name": "",  # Empty project name
            "processing_activities": []  # Empty activities
        }
        
        response = client.post("/api/v1/privacy/pia", json=invalid_request)
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__])