"""
Tests for Compliance Remediation Integration Service
File: tests/unit/test_remediation_integration_service.py
Target: src/compliance_agent/services/remediation_integration_service.py
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
import httpx

from src.compliance_agent.services.remediation_integration_service import (
    ComplianceRemediationService,
    RemediationRequest
)


@pytest.fixture
def remediation_service():
    """Fixture for ComplianceRemediationService instance"""
    return ComplianceRemediationService()


@pytest.fixture
def sample_remediation_data():
    """Fixture for sample remediation data"""
    return {
        "id": "test_record_001",
        "action": "delete",
        "message": "Customer requested data deletion under GDPR Article 17",
        "field_name": "customer_profile",
        "domain_name": "customer",
        "framework": "gdpr_eu",
        "urgency": "high",
        "user_id": "customer_123"
    }


class TestRemediationRequest:
    """Test RemediationRequest Pydantic model"""
    
    def test_remediation_request_creation(self):
        """Test creating RemediationRequest with all fields"""
        request = RemediationRequest(
            id="test_001",
            action="delete",
            message="Test message",
            field_name="test_field",
            domain_name="test_domain",
            framework="gdpr_eu",
            urgency="high",
            user_id="user_001"
        )
        
        assert request.id == "test_001"
        assert request.action == "delete"
        assert request.message == "Test message"
        assert request.field_name == "test_field"
        assert request.domain_name == "test_domain"
        assert request.framework == "gdpr_eu"
        assert request.urgency == "high"
        assert request.user_id == "user_001"
        assert request.metadata == {}
    
    def test_remediation_request_with_metadata(self):
        """Test RemediationRequest with metadata"""
        request = RemediationRequest(
            id="test_001",
            action="anonymize",
            message="Test",
            field_name="field",
            domain_name="domain",
            framework="pdpa_singapore",
            urgency="medium",
            user_id="user_001",
            metadata={"key": "value", "count": 5}
        )
        
        assert request.metadata == {"key": "value", "count": 5}
    
    def test_remediation_request_different_actions(self):
        """Test RemediationRequest with different actions"""
        actions = ["delete", "anonymize", "archive", "export"]
        
        for action in actions:
            request = RemediationRequest(
                id="test_001",
                action=action,
                message="Test",
                field_name="field",
                domain_name="domain",
                framework="gdpr_eu",
                urgency="low",
                user_id="user_001"
            )
            assert request.action == action


class TestServiceInitialization:
    """Test ComplianceRemediationService initialization"""
    
    def test_init_default_endpoint(self):
        """Test initialization with default endpoint"""
        service = ComplianceRemediationService()
        
        assert service.remediation_endpoint == os.getenv('REMEDIATION_ENDPOINT', 'http://localhost:8001')
        assert service.timeout == 30
    
    def test_init_framework_mapping(self):
        """Test framework mapping configuration"""
        service = ComplianceRemediationService()
        
        assert "gdpr_eu" in service.framework_mapping
        assert "pdpa_singapore" in service.framework_mapping
        assert "ccpa_california" in service.framework_mapping
        assert "pipeda_canada" in service.framework_mapping
    
    def test_init_risk_to_urgency_mapping(self):
        """Test risk to urgency level mapping"""
        service = ComplianceRemediationService()
        
        assert service.risk_to_urgency["LOW"] == "low"
        assert service.risk_to_urgency["MEDIUM"] == "medium"
        assert service.risk_to_urgency["HIGH"] == "high"
        assert service.risk_to_urgency["CRITICAL"] == "critical"
    
    def test_init_with_custom_endpoint(self):
        """Test initialization with custom endpoint from environment"""
        with patch.dict(os.environ, {'REMEDIATION_ENDPOINT': 'http://custom:9000'}):
            service = ComplianceRemediationService()
            assert service.remediation_endpoint == 'http://custom:9000'


class TestTriggerRemediation:
    """Test trigger_remediation method"""
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_success_200(self, remediation_service, sample_remediation_data):
        """Test successful remediation trigger with 200 response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Success"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_success_202(self, remediation_service, sample_remediation_data):
        """Test successful remediation trigger with 202 accepted response"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = "Accepted"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_failure_400(self, remediation_service, sample_remediation_data):
        """Test remediation trigger failure with 400 response"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_failure_500(self, remediation_service, sample_remediation_data):
        """Test remediation trigger failure with 500 response"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_timeout(self, remediation_service, sample_remediation_data):
        """Test remediation trigger timeout"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_connect_error(self, remediation_service, sample_remediation_data):
        """Test remediation trigger connection error"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_generic_exception(self, remediation_service, sample_remediation_data):
        """Test remediation trigger with generic exception"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Unexpected error")
            )
            
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_with_minimal_data(self, remediation_service):
        """Test remediation trigger with minimal data using defaults"""
        minimal_data = {"user_id": "test_user"}
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await remediation_service.trigger_remediation(minimal_data)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_payload_structure(self, remediation_service, sample_remediation_data):
        """Test that payload is correctly structured"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        captured_payload = None
        
        async def capture_post(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get('json')
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = capture_post
            
            await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert captured_payload is not None
            assert captured_payload["id"] == "test_record_001"
            assert captured_payload["action"] == "delete"
            assert captured_payload["framework"] == "gdpr_eu"
            assert captured_payload["urgency"] == "high"
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_different_frameworks(self, remediation_service):
        """Test remediation with different frameworks"""
        frameworks = ["gdpr_eu", "pdpa_singapore", "ccpa_california", "pipeda_canada"]
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        for framework in frameworks:
            data = {
                "id": "test_001",
                "action": "delete",
                "message": "Test",
                "field_name": "field",
                "domain_name": "domain",
                "framework": framework,
                "urgency": "high",
                "user_id": "user_001"
            }
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                
                result = await remediation_service.trigger_remediation(data)
                
                assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_different_urgency_levels(self, remediation_service):
        """Test remediation with different urgency levels"""
        urgency_levels = ["low", "medium", "high", "critical"]
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        for urgency in urgency_levels:
            data = {
                "id": "test_001",
                "action": "delete",
                "message": "Test",
                "field_name": "field",
                "domain_name": "domain",
                "framework": "gdpr_eu",
                "urgency": urgency,
                "user_id": "user_001"
            }
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                
                result = await remediation_service.trigger_remediation(data)
                
                assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_calls_correct_endpoint(self, remediation_service, sample_remediation_data):
        """Test that remediation calls the correct endpoint"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        captured_url = None
        
        async def capture_post(url, *args, **kwargs):
            nonlocal captured_url
            captured_url = url
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = capture_post
            
            await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert captured_url == "http://localhost:8000/api/v1/remediation/trigger"
    
    @pytest.mark.asyncio
    async def test_trigger_remediation_uses_timeout(self, remediation_service, sample_remediation_data):
        """Test that remediation uses configured timeout"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        captured_timeout = None
        
        async def capture_post(*args, **kwargs):
            nonlocal captured_timeout
            captured_timeout = kwargs.get('timeout')
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = capture_post
            
            await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert captured_timeout == remediation_service.timeout


class TestDetailedLogging:
    """Test detailed logging functionality"""
    
    @pytest.mark.asyncio
    async def test_detailed_logging_executes_successfully(self, remediation_service, sample_remediation_data):
        """Test that detailed logging path executes successfully"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            # Test that the detailed logging block executes without errors
            result = await remediation_service.trigger_remediation(sample_remediation_data)
            
            assert result is True


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_remediation_flow(self):
        """Test complete remediation flow"""
        service = ComplianceRemediationService()
        
        remediation_data = {
            "id": "integration_test_001",
            "action": "delete",
            "message": "Integration test data deletion",
            "field_name": "test_field",
            "domain_name": "test_domain",
            "framework": "gdpr_eu",
            "urgency": "high",
            "user_id": "test_user_001"
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await service.trigger_remediation(remediation_data)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_multiple_remediation_requests(self, remediation_service):
        """Test handling multiple remediation requests"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        requests = [
            {"id": "req1", "action": "delete", "user_id": "user1", "framework": "gdpr_eu", "urgency": "high", "field_name": "f1", "domain_name": "d1", "message": "m1"},
            {"id": "req2", "action": "anonymize", "user_id": "user2", "framework": "pdpa_singapore", "urgency": "medium", "field_name": "f2", "domain_name": "d2", "message": "m2"},
            {"id": "req3", "action": "archive", "user_id": "user3", "framework": "ccpa_california", "urgency": "low", "field_name": "f3", "domain_name": "d3", "message": "m3"}
        ]
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            for request_data in requests:
                result = await remediation_service.trigger_remediation(request_data)
                assert result is True
