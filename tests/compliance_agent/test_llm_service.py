"""
Unit tests for LLM Service
Tests for AI-powered compliance analysis and suggestions
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.compliance_agent.services.llm_service import LLMComplianceService
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation,
    ComplianceFramework,
    RiskLevel
)


class TestLLMServiceInitialization:
    """Test LLM Service initialization"""

    @pytest.mark.asyncio
    async def test_llm_service_creation(self):
        """Test creating LLM service instance"""
        service = LLMComplianceService()
        assert service is not None
        assert service.client is None
        assert service.model_name == "gpt-3.5-turbo"
        assert service.temperature == 0.1
        assert service.max_tokens == 500
        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_with_valid_api_key(self):
        """Test initialization with valid API key"""
        with patch('src.compliance_agent.services.llm_service.get_openai_api_key', return_value='test-api-key'):
            service = LLMComplianceService()
            result = await service.initialize()
            assert result is True
            assert service.is_initialized is True
            assert service.client is not None

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self):
        """Test initialization without API key"""
        with patch('src.compliance_agent.services.llm_service.get_openai_api_key', return_value=None):
            service = LLMComplianceService()
            result = await service.initialize()
            assert result is False
            assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_with_secret_name(self):
        """Test initialization with custom secret name"""
        with patch('src.compliance_agent.services.llm_service.get_openai_api_key', return_value='test-api-key') as mock_get_key:
            service = LLMComplianceService()
            result = await service.initialize(secret_name='custom/secret')
            assert result is True
            mock_get_key.assert_called_once_with('custom/secret')

    @pytest.mark.asyncio
    async def test_initialize_handles_exception(self):
        """Test initialization handles exceptions gracefully"""
        with patch('src.compliance_agent.services.llm_service.get_openai_api_key', side_effect=Exception("Connection error")):
            service = LLMComplianceService()
            result = await service.initialize()
            assert result is False
            assert service.is_initialized is False


class TestLLMComplianceSuggestions:
    """Test LLM compliance suggestion generation"""

    @pytest.fixture
    def initialized_service(self):
        """Create an initialized LLM service"""
        with patch('src.compliance_agent.services.llm_service.get_openai_api_key', return_value='test-api-key'):
            service = LLMComplianceService()
            service.client = Mock()
            service.is_initialized = True
            return service

    @pytest.fixture
    def sample_violation(self):
        """Create a sample violation"""
        return ComplianceViolation(
            id="test_violation_001",
            activity_id="activity_001",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            rule_id="pdpa_rule_001",
            risk_level=RiskLevel.HIGH,
            description="Data retention period exceeded",
            detected_at="2025-10-21T00:00:00Z"
        )

    @pytest.mark.asyncio
    async def test_generate_suggestion_when_not_initialized(self, sample_violation):
        """Test that suggestion returns None when service not initialized"""
        service = LLMComplianceService()
        service.is_initialized = False
        
        # Convert violation to dict format expected by the method
        violation_dict = {
            "rule_id": sample_violation.rule_id,
            "description": sample_violation.description,
            "risk_level": sample_violation.risk_level.value,
            "activity_id": sample_violation.activity_id
        }
        
        result = await service.generate_compliance_suggestion(violation_dict)
        # Should return fallback suggestion, not None
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_suggestion_success(self, initialized_service, sample_violation):
        """Test successful suggestion generation"""
        # Convert violation to dict format
        violation_dict = {
            "rule_id": sample_violation.rule_id,
            "description": sample_violation.description,
            "risk_level": sample_violation.risk_level.value,
            "activity_id": sample_violation.activity_id
        }
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            "description": "AI-generated description",
            "recommendation": "AI-generated recommendation",
            "legal_reference": "PDPA Article 25",
            "urgency": "HIGH",
            "compliance_impact": "Critical issue"
        })
        
        with patch.object(initialized_service.client.chat.completions, 'create', return_value=mock_response):
            result = await initialized_service.generate_compliance_suggestion(violation_dict)
            
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_suggestion_handles_api_error(self, initialized_service, sample_violation):
        """Test handling of API errors"""
        violation_dict = {
            "rule_id": sample_violation.rule_id,
            "description": sample_violation.description,
            "risk_level": sample_violation.risk_level.value
        }
        
        with patch.object(initialized_service.client.chat.completions, 'create', side_effect=Exception("API Error")):
            result = await initialized_service.generate_compliance_suggestion(violation_dict)
            # Should return fallback suggestion on error
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_suggestion_handles_invalid_json(self, initialized_service, sample_violation):
        """Test handling of invalid JSON response"""
        violation_dict = {
            "rule_id": sample_violation.rule_id,
            "description": sample_violation.description,
            "risk_level": sample_violation.risk_level.value
        }
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Invalid JSON response"
        
        with patch.object(initialized_service.client.chat.completions, 'create', return_value=mock_response):
            result = await initialized_service.generate_compliance_suggestion(violation_dict)
            # Should handle gracefully and return fallback
            assert result is not None
            assert isinstance(result, dict)


class TestLLMBatchProcessing:
    """Test batch processing capabilities"""

    @pytest.fixture
    def initialized_service(self):
        """Create an initialized LLM service"""
        with patch('src.compliance_agent.services.llm_service.get_openai_api_key', return_value='test-api-key'):
            service = LLMComplianceService()
            service.client = Mock()
            service.is_initialized = True
            return service

    @pytest.fixture
    def sample_violations(self):
        """Create multiple sample violations"""
        return [
            ComplianceViolation(
                id=f"test_violation_{i:03d}",
                activity_id=f"activity_{i:03d}",
                framework=ComplianceFramework.PDPA_SINGAPORE,
                rule_id="pdpa_rule_001",
                risk_level=RiskLevel.HIGH,
                description=f"Violation {i}",
                detected_at="2025-10-21T00:00:00Z"
            )
            for i in range(3)
        ]

    @pytest.mark.asyncio
    async def test_batch_suggestions_generation(self, initialized_service, sample_violations):
        """Test generating suggestions for multiple violations"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            "description": "Test description",
            "recommendation": "Test recommendation",
            "legal_reference": "Test reference",
            "urgency": "HIGH",
            "compliance_impact": "Test impact"
        })
        
        with patch.object(initialized_service.client.chat.completions, 'create', return_value=mock_response):
            results = []
            for violation in sample_violations:
                violation_dict = {
                    "rule_id": violation.rule_id,
                    "description": violation.description,
                    "risk_level": violation.risk_level.value
                }
                result = await initialized_service.generate_compliance_suggestion(violation_dict)
                results.append(result)
            
            assert len(results) == 3
            assert all(r is not None for r in results)


class TestLLMServiceConfiguration:
    """Test LLM service configuration"""

    def test_default_model_configuration(self):
        """Test default model settings"""
        service = LLMComplianceService()
        assert service.model_name == "gpt-3.5-turbo"
        assert service.temperature == 0.1
        assert service.max_tokens == 500

    def test_service_attributes(self):
        """Test service has required attributes"""
        service = LLMComplianceService()
        assert hasattr(service, 'client')
        assert hasattr(service, 'model_name')
        assert hasattr(service, 'temperature')
        assert hasattr(service, 'max_tokens')
        assert hasattr(service, 'is_initialized')


class TestLLMPromptGeneration:
    """Test prompt generation methods"""

    def test_create_compliance_prompt_with_full_data(self):
        """Test prompt creation with complete violation data"""
        service = LLMComplianceService()
        violation_data = {
            'customer_id': 'CUST123',
            'data_age_days': 400,
            'excess_days': 35,
            'retention_limit_days': 365,
            'is_archived': False,
            'violation_type': 'DATA_RETENTION_EXCEEDED',
            'framework': 'PDPA'
        }
        
        prompt = service._create_compliance_prompt(violation_data, 'PDPA')
        
        assert 'CUST123' in prompt
        assert '400 days' in prompt
        assert '35 days' in prompt
        assert '365 days' in prompt
        assert 'PDPA' in prompt
        assert 'description' in prompt
        assert 'recommendation' in prompt

    def test_create_compliance_prompt_with_minimal_data(self):
        """Test prompt creation with minimal data"""
        service = LLMComplianceService()
        violation_data = {}
        
        prompt = service._create_compliance_prompt(violation_data, 'GDPR')
        
        assert 'GDPR' in prompt
        assert 'Unknown' in prompt
        assert 'description' in prompt

    def test_create_compliance_prompt_with_alternate_id_fields(self):
        """Test prompt uses alternate ID fields"""
        service = LLMComplianceService()
        
        # Test with 'id' field
        violation_data = {'id': 'USER456'}
        prompt = service._create_compliance_prompt(violation_data, 'PDPA')
        assert 'USER456' in prompt
        
        # Test with 'user_id' field
        violation_data = {'user_id': 'USER789'}
        prompt = service._create_compliance_prompt(violation_data, 'GDPR')
        assert 'USER789' in prompt

    def test_create_compliance_prompt_archived_customer(self):
        """Test prompt includes archived status"""
        service = LLMComplianceService()
        violation_data = {
            'customer_id': 'CUST123',
            'is_archived': True
        }
        
        prompt = service._create_compliance_prompt(violation_data, 'PDPA')
        assert 'True' in prompt or 'archived' in prompt.lower()


class TestLLMResponseParsing:
    """Test LLM response parsing"""

    def test_parse_llm_response_valid_json(self):
        """Test parsing valid JSON response"""
        service = LLMComplianceService()
        response = json.dumps({
            'description': 'Test description',
            'recommendation': 'Test recommendation',
            'legal_reference': 'Test reference',
            'urgency_level': 'HIGH',
            'compliance_impact': 'Test impact'
        })
        
        result = service._parse_llm_response(response)
        
        assert result['description'] == 'Test description'
        assert result['recommendation'] == 'Test recommendation'
        assert result['legal_reference'] == 'Test reference'
        assert result['urgency_level'] == 'HIGH'
        assert result['compliance_impact'] == 'Test impact'

    def test_parse_llm_response_incomplete_json(self):
        """Test parsing JSON with missing fields"""
        service = LLMComplianceService()
        response = json.dumps({
            'description': 'Only description'
        })
        
        result = service._parse_llm_response(response)
        
        assert result['description'] == 'Only description'
        assert 'recommendation' in result
        assert 'legal_reference' in result
        assert 'urgency_level' in result

    def test_parse_llm_response_non_json_text(self):
        """Test parsing non-JSON text response"""
        service = LLMComplianceService()
        response = "This is a plain text response that is not JSON formatted."
        
        result = service._parse_llm_response(response)
        
        assert isinstance(result, dict)
        assert 'description' in result
        assert response in result['description']

    def test_parse_llm_response_long_text(self):
        """Test parsing long text is truncated"""
        service = LLMComplianceService()
        response = "A" * 300  # Long text
        
        result = service._parse_llm_response(response)
        
        assert '...' in result['description']
        assert len(result['description']) <= 204  # 200 + '...'

    def test_parse_llm_response_invalid_json(self):
        """Test parsing invalid JSON"""
        service = LLMComplianceService()
        response = "{'invalid': json, 'structure'}"
        
        result = service._parse_llm_response(response)
        
        assert isinstance(result, dict)
        assert 'description' in result


class TestFallbackSuggestions:
    """Test fallback suggestion generation"""

    def test_fallback_suggestion_pdpa(self):
        """Test PDPA fallback suggestion"""
        service = LLMComplianceService()
        violation_data = {
            'excess_days': 45,
            'violation_type': 'DATA_RETENTION_EXCEEDED'
        }
        
        result = service._get_fallback_suggestion(violation_data, 'PDPA')
        
        assert 'PDPA' in result['description']
        assert '45 days' in result['description']
        assert 'PDPA Section 24' in result['legal_reference']
        assert 'S$1 million' in result['compliance_impact']
        assert result['urgency_level'] == 'HIGH'

    def test_fallback_suggestion_gdpr(self):
        """Test GDPR fallback suggestion"""
        service = LLMComplianceService()
        violation_data = {
            'excess_days': 20,
            'violation_type': 'DATA_RETENTION_EXCEEDED'
        }
        
        result = service._get_fallback_suggestion(violation_data, 'GDPR')
        
        assert 'GDPR' in result['description']
        assert '20 days' in result['description']
        assert 'GDPR Article 17' in result['legal_reference']
        assert '4%' in result['compliance_impact']
        assert result['urgency_level'] == 'MEDIUM'

    def test_fallback_suggestion_other_framework(self):
        """Test fallback for other frameworks"""
        service = LLMComplianceService()
        violation_data = {'excess_days': 10}
        
        result = service._get_fallback_suggestion(violation_data, 'CCPA')
        
        assert 'Data Protection Regulations' in result['legal_reference']
        assert 'compliance risk' in result['compliance_impact']

    def test_fallback_suggestion_urgency_levels(self):
        """Test urgency level based on excess days"""
        service = LLMComplianceService()
        
        # High urgency (>30 days)
        violation_data = {'excess_days': 50}
        result = service._get_fallback_suggestion(violation_data, 'PDPA')
        assert result['urgency_level'] == 'HIGH'
        
        # Medium urgency (<=30 days)
        violation_data = {'excess_days': 20}
        result = service._get_fallback_suggestion(violation_data, 'PDPA')
        assert result['urgency_level'] == 'MEDIUM'


class TestRemediationPlanGeneration:
    """Test remediation plan generation"""

    @pytest.fixture
    def sample_violations(self):
        """Create sample violations"""
        return [
            {'customer_id': 'CUST001', 'excess_days': 30},
            {'customer_id': 'CUST002', 'excess_days': 45},
            {'customer_id': 'CUST003', 'excess_days': 60}
        ]

    @pytest.mark.asyncio
    async def test_generate_remediation_plan_not_initialized(self, sample_violations):
        """Test remediation plan when service not initialized"""
        service = LLMComplianceService()
        service.is_initialized = False
        
        result = await service.generate_remediation_plan(sample_violations, 'PDPA')
        
        assert isinstance(result, dict)
        assert 'priority_actions' in result
        assert 'short_term_plan' in result
        assert 'long_term_plan' in result
        assert 'estimated_timeline' in result
        assert 'resources_needed' in result

    @pytest.mark.asyncio
    async def test_generate_remediation_plan_with_llm_error(self, sample_violations):
        """Test remediation plan when LLM fails"""
        service = LLMComplianceService()
        service.is_initialized = True
        service.client = Mock()
        
        # Mock LLM to raise error
        with patch.object(service, '_call_openai_chat', side_effect=Exception("API Error")):
            result = await service.generate_remediation_plan(sample_violations, 'GDPR')
            
            assert isinstance(result, dict)
            assert 'priority_actions' in result

    def test_format_violations_for_prompt(self):
        """Test formatting violations for prompt"""
        service = LLMComplianceService()
        violations = [
            {'customer_id': 'CUST001', 'excess_days': 30},
            {'customer_id': 'CUST002', 'excess_days': 45},
            {'customer_id': 'CUST003', 'excess_days': 60}
        ]
        
        result = service._format_violations_for_prompt(violations)
        
        assert 'CUST001' in result
        assert 'CUST002' in result
        assert '30 days' in result
        assert '45 days' in result

    def test_format_violations_limits_to_five(self):
        """Test formatting limits violations to 5"""
        service = LLMComplianceService()
        violations = [
            {'customer_id': f'CUST{i:03d}', 'excess_days': i * 10}
            for i in range(10)
        ]
        
        result = service._format_violations_for_prompt(violations)
        
        lines = result.split('\n')
        assert len(lines) == 5

    def test_parse_remediation_response_valid_json(self):
        """Test parsing valid remediation response"""
        service = LLMComplianceService()
        response = json.dumps({
            'priority_actions': ['Action 1', 'Action 2'],
            'short_term_plan': ['Plan 1'],
            'long_term_plan': ['Strategy 1']
        })
        
        result = service._parse_remediation_response(response)
        
        assert 'priority_actions' in result
        assert len(result['priority_actions']) == 2

    def test_parse_remediation_response_invalid_json(self):
        """Test parsing invalid remediation response"""
        service = LLMComplianceService()
        response = "Invalid JSON response"
        
        result = service._parse_remediation_response(response)
        
        assert isinstance(result, dict)
        assert 'priority_actions' in result

    def test_get_basic_remediation_plan(self):
        """Test basic remediation plan fallback"""
        service = LLMComplianceService()
        violations = []
        
        result = service._get_basic_remediation_plan(violations, 'PDPA')
        
        assert isinstance(result, dict)
        assert 'priority_actions' in result
        assert 'short_term_plan' in result
        assert 'long_term_plan' in result
        assert 'estimated_timeline' in result
        assert 'resources_needed' in result
        assert 'compliance_monitoring' in result
        
        assert len(result['priority_actions']) == 3
        assert len(result['short_term_plan']) == 3
        assert len(result['long_term_plan']) == 3


import json
