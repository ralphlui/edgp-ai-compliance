#!/usr/bin/env python3
"""
test_compliance_pattern_loader.py

Comprehensive test suite for Compliance Pattern Loader
Tests for 70%+ code coverage

Tests include:
1. Loader initialization
2. JSON file loading
3. PDPA pattern processing
4. GDPR pattern processing
5. Risk level determination
6. Data type extraction
7. Violation pattern extraction
8. Remediation action extraction
9. OpenSearch index creation
10. Pattern loading to OpenSearch
11. Vector search testing
12. Embedding generation
13. Error handling
"""

import pytest
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

# Set up test environment
os.environ.update({
    'AWS_ACCESS_KEY_ID': 'test_access_key',
    'AWS_SECRET_ACCESS_KEY': 'test_secret_key',
    'AWS_REGION': 'eu-west-1',  # Match actual config
    'OPENSEARCH_ENDPOINT': 'https://test-opensearch.example.com',
    'OPENAI_API_KEY': 'test_openai_key'
})

from src.compliance_agent.services.compliance_pattern_loader import InternationalCompliancePatternLoader

logger = logging.getLogger(__name__)


class TestLoaderInitialization:
    """Test loader initialization and configuration"""
    
    def test_loader_initialization_with_credentials(self):
        """Test 1: Loader initializes with valid AWS credentials"""
        
        # Mock settings object
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-compliance-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_access_key'
        mock_settings.aws_secret_access_key = 'test_secret_key'
        mock_settings.aws_region = 'eu-west-1'
        
        # Patch the import in the loader's __init__ method
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                    loader = InternationalCompliancePatternLoader()
                    
                    assert loader.aws_access_key == 'test_access_key'
                    assert loader.aws_secret_key == 'test_secret_key'
                    assert loader.aws_region == 'eu-west-1'
                    assert loader.opensearch_endpoint == 'https://test-opensearch.example.com'
                    assert loader.compliance_index == 'test-compliance-index'
                    assert loader.opensearch_enabled is True
        
        logger.info("✅ Test 1 passed: Loader initialization with credentials")
    
    def test_loader_initialization_without_api_key(self):
        """Test 2: Loader handles missing OpenAI API key"""
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value=None):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                # Should initialize but log warning about missing API key
                assert loader is not None
        
        logger.info("✅ Test 2 passed: Loader without API key")
    
    def test_loader_initialization_missing_endpoint(self):
        """Test 3: Loader initializes with warning when OpenSearch endpoint missing"""
        
        # Mock settings with OpenSearch disabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = False  # Disabled
        mock_settings.opensearch_endpoint = None  # No endpoint
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_access_key'
        mock_settings.aws_secret_access_key = 'test_secret_key'
        mock_settings.aws_region = 'eu-west-1'
        
        # Patch the import in the loader's __init__ method
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                # Should initialize but with client set to None
                loader = InternationalCompliancePatternLoader()
                
                assert loader.opensearch_enabled is False
                assert loader.client is None
        
        logger.info("✅ Test 3 passed: Missing endpoint handled gracefully")


class TestJSONFileLoading:
    """Test JSON file loading functionality"""
    
    def test_load_json_file_success(self):
        """Test 4: Load JSON file successfully"""
        
        mock_data = [
            {"id": "PDPA_001", "title": "Data Retention", "content": "Retain data for 7 years"},
            {"id": "PDPA_002", "title": "Data Access", "content": "Provide data access"}
        ]
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
                    patterns = loader.load_json_file('test.json')
                    
                    assert len(patterns) == 2
                    assert patterns[0]['id'] == 'PDPA_001'
                    assert patterns[1]['title'] == 'Data Access'
        
        logger.info("✅ Test 4 passed: Load JSON file success")
    
    def test_load_json_file_error(self):
        """Test 5: Handle JSON file loading error"""
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
                    patterns = loader.load_json_file('nonexistent.json')
                    
                    assert patterns == []
        
        logger.info("✅ Test 5 passed: JSON file error handling")


class TestEmbeddingGeneration:
    """Test vector embedding generation"""
    
    def test_generate_embedding_success(self):
        """Test 6: Generate embedding successfully"""
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.openai.embeddings.create', return_value=mock_response):
                    loader = InternationalCompliancePatternLoader()
                    
                    embedding = loader.generate_embedding("test text")
                    
                    assert embedding == [0.1, 0.2, 0.3]
        
        logger.info("✅ Test 6 passed: Generate embedding success")
    
    def test_generate_embedding_error(self):
        """Test 7: Handle embedding generation error"""
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.openai.embeddings.create', side_effect=Exception("API error")):
                    loader = InternationalCompliancePatternLoader()
                    
                    embedding = loader.generate_embedding("test text")
                    
                    assert embedding == []
        
        logger.info("✅ Test 7 passed: Embedding error handling")


class TestPDPAPatternProcessing:
    """Test PDPA pattern processing"""
    
    def test_process_pdpa_pattern_success(self):
        """Test 8: Process PDPA pattern successfully"""
        
        mock_pattern = {
            'id': 'PDPA_001',
            'title': 'Data Retention Requirements',
            'content': 'Personal data must be deleted after 7 years',
            'category': 'data_retention',
            'applies_to': ['customer_data', 'financial_data']
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                with patch.object(loader, 'generate_embedding', return_value=[0.1, 0.2, 0.3]):
                    processed = loader.process_pdpa_pattern(mock_pattern)
                    
                    assert processed is not None
                    assert processed['compliance_id'] == 'PDPA_001'
                    assert processed['framework'] == 'PDPA'
                    assert processed['title'] == 'Data Retention Requirements'
                    assert processed['country'] == 'Singapore'
                    assert processed['region'] == 'APAC'
                    assert len(processed['embedding']) == 3
        
        logger.info("✅ Test 8 passed: Process PDPA pattern")
    
    def test_process_pdpa_pattern_error(self):
        """Test 9: Handle invalid pattern gracefully"""
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                # Test with empty pattern that will cause embedding failure
                invalid_pattern = {'id': 'INVALID_001'}
                
                with patch.object(loader, 'generate_embedding', side_effect=Exception("Embedding failed")):
                    processed = loader.process_pdpa_pattern(invalid_pattern)
                    
                    assert processed is None
                    logger.info("✅ Test 9 passed: PDPA pattern error handling")


class TestGDPRPatternProcessing:
    """Test GDPR pattern processing"""
    
    def test_process_gdpr_pattern_success(self):
        """Test 10: Process GDPR pattern successfully"""
        
        mock_pattern = {
            'id': 'GDPR_001',
            'title': 'Right to Erasure',
            'content': 'Data subjects have the right to erasure of personal data',
            'category': 'data_rights',
            'applies_to': ['personal_data']
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                with patch.object(loader, 'generate_embedding', return_value=[0.4, 0.5, 0.6]):
                    processed = loader.process_gdpr_pattern(mock_pattern)
                    
                    assert processed is not None
                    assert processed['compliance_id'] == 'GDPR_001'
                    assert processed['framework'] == 'GDPR'
                    assert processed['title'] == 'Right to Erasure'
                    assert processed['country'] == 'European Union'
                    assert processed['region'] == 'EU'
                    assert len(processed['embedding']) == 3
        
        logger.info("✅ Test 10 passed: Process GDPR pattern")


class TestRiskLevelDetermination:
    """Test risk level determination logic"""
    
    def test_determine_high_risk(self):
        """Test 11: Determine high risk level"""
        
        high_risk_pattern = {
            'title': 'Data Breach Penalties',
            'content': 'Violation of this rule results in severe penalties and fines'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                risk = loader._determine_risk_level(high_risk_pattern)
                
                assert risk == "HIGH"
        
        logger.info("✅ Test 11 passed: High risk determination")
    
    def test_determine_medium_risk(self):
        """Test 12: Determine medium risk level"""
        
        medium_risk_pattern = {
            'title': 'Data Access Rights',
            'content': 'Data subjects must consent to data processing activities'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                risk = loader._determine_risk_level(medium_risk_pattern)
                
                assert risk == "MEDIUM"
        
        logger.info("✅ Test 12 passed: Medium risk determination")
    
    def test_determine_low_risk(self):
        """Test 13: Determine low risk level"""
        
        low_risk_pattern = {
            'title': 'Data Records',
            'content': 'Maintain records and documentation for audit purposes'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                risk = loader._determine_risk_level(low_risk_pattern)
                
                assert risk == "LOW"
        
        logger.info("✅ Test 13 passed: Low risk determination")


class TestDataTypeExtraction:
    """Test data type extraction"""
    
    def test_extract_data_types_multiple(self):
        """Test 14: Extract multiple data types"""
        
        pattern = {
            'content': 'This rule applies to personal data, financial information, and customer records'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                data_types = loader._extract_data_types(pattern)
                
                assert 'personal_data' in data_types
                assert 'financial_data' in data_types
                assert 'customer_data' in data_types
        
        logger.info("✅ Test 14 passed: Extract multiple data types")
    
    def test_extract_data_types_default(self):
        """Test 15: Extract data types with default"""
        
        pattern = {
            'content': 'General data protection requirements'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                data_types = loader._extract_data_types(pattern)
                
                assert data_types == ['personal_data']  # Default value
        
        logger.info("✅ Test 15 passed: Extract data types default")


class TestViolationPatternExtraction:
    """Test violation pattern extraction"""
    
    def test_extract_violation_patterns_retention(self):
        """Test 16: Extract retention violation patterns"""
        
        pattern = {
            'content': 'Data retention period must not exceed 7 years'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                violations = loader._extract_violation_patterns(pattern)
                
                assert 'retention' in violations.lower()
        
        logger.info("✅ Test 16 passed: Extract retention violations")
    
    def test_extract_violation_patterns_consent(self):
        """Test 17: Extract consent violation patterns"""
        
        pattern = {
            'content': 'Valid consent must be obtained before processing'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                violations = loader._extract_violation_patterns(pattern)
                
                assert 'consent' in violations.lower()
        
        logger.info("✅ Test 17 passed: Extract consent violations")


class TestRemediationActionExtraction:
    """Test remediation action extraction"""
    
    def test_extract_remediation_delete(self):
        """Test 18: Extract deletion remediation actions"""
        
        pattern = {
            'content': 'Data must be deleted upon request'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                actions = loader._extract_remediation_actions(pattern)
                
                assert 'delete' in actions.lower()
        
        logger.info("✅ Test 18 passed: Extract deletion remediation")
    
    def test_extract_remediation_consent(self):
        """Test 19: Extract consent remediation actions"""
        
        pattern = {
            'content': 'Obtain valid consent from data subjects'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                actions = loader._extract_remediation_actions(pattern)
                
                assert 'consent' in actions.lower()
        
        logger.info("✅ Test 19 passed: Extract consent remediation")
    
    def test_extract_remediation_retention(self):
        """Test 20: Extract retention remediation actions"""
        
        pattern = {
            'content': 'Review data retention policies annually'
        }
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
            with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch'):
                loader = InternationalCompliancePatternLoader()
                
                actions = loader._extract_remediation_actions(pattern)
                
                assert 'retention' in actions.lower()
        
        logger.info("✅ Test 20 passed: Extract retention remediation")


class TestOpenSearchIndexCreation:
    """Test OpenSearch index creation"""
    
    @pytest.mark.asyncio
    async def test_create_compliance_index_new(self):
        """Test 21: Create new compliance index"""
        
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.return_value = {'acknowledged': True}
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    result = await loader.create_compliance_index()
                    
                    assert result is True
                    mock_client.indices.create.assert_called_once()
        
        logger.info("✅ Test 21 passed: Create new index")
    
    @pytest.mark.asyncio
    async def test_create_compliance_index_exists(self):
        """Test 22: Handle existing compliance index"""
        
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    result = await loader.create_compliance_index()
                    
                    assert result is True
                    mock_client.indices.create.assert_not_called()
        
        logger.info("✅ Test 22 passed: Index already exists")
    
    @pytest.mark.asyncio
    async def test_create_compliance_index_error(self):
        """Test 23: Handle index creation error"""
        
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.side_effect = Exception("Index creation failed")
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    result = await loader.create_compliance_index()
                    
                    assert result is False
        
        logger.info("✅ Test 23 passed: Index creation error")


class TestPatternLoadingToOpenSearch:
    """Test loading patterns to OpenSearch"""
    
    @pytest.mark.asyncio
    async def test_load_patterns_success(self):
        """Test 24: Load patterns to OpenSearch successfully"""
        
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_client.index.return_value = {'result': 'created'}
        mock_client.indices.refresh.return_value = {'_shards': {'successful': 1}}
        
        mock_patterns = [
            {'id': 'PDPA_001', 'title': 'Test', 'content': 'Test content', 'category': 'test'}
        ]
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    with patch('os.path.exists', return_value=True):
                        loader = InternationalCompliancePatternLoader()
                        loader.client = mock_client
                        
                        with patch.object(loader, 'load_json_file', return_value=mock_patterns):
                            with patch.object(loader, 'process_pdpa_pattern') as mock_process:
                                with patch.object(loader, 'process_gdpr_pattern') as mock_gdpr:
                                    mock_process.return_value = {
                                        'compliance_id': 'PDPA_001',
                                        'embedding': [0.1, 0.2, 0.3]
                                    }
                                    mock_gdpr.return_value = {
                                        'compliance_id': 'GDPR_001',
                                        'embedding': [0.4, 0.5, 0.6]
                                    }
                                    
                                    result = await loader.load_patterns_to_opensearch()
                                    
                                    assert result is True
        
        logger.info("✅ Test 24 passed: Load patterns success")
    
    @pytest.mark.asyncio
    async def test_load_patterns_index_creation_fails(self):
        """Test 25: Handle index creation failure"""
        
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.side_effect = Exception("Cannot create index")
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    result = await loader.load_patterns_to_opensearch()
                    
                    assert result is False
        
        logger.info("✅ Test 25 passed: Index creation failure")


class TestVectorSearch:
    """Test vector search functionality"""
    
    @pytest.mark.asyncio
    async def test_pattern_search_success(self):
        """Test 26: Vector search successful"""
        
        mock_client = MagicMock()
        mock_client.search.return_value = {
            'hits': {
                'hits': [
                    {
                        '_score': 0.95,
                        '_source': {
                            'compliance_id': 'PDPA_001',
                            'framework': 'PDPA',
                            'title': 'Data Retention',
                            'category': 'retention',
                            'risk_level': 'HIGH'
                        }
                    }
                ]
            }
        }
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    with patch.object(loader, 'generate_embedding', return_value=[0.1, 0.2, 0.3]):
                        result = await loader.test_pattern_search("data retention")
                        
                        assert result is True
                        mock_client.search.assert_called_once()
        
        logger.info("✅ Test 26 passed: Vector search success")
    
    @pytest.mark.asyncio
    async def test_pattern_search_no_embedding(self):
        """Test 27: Vector search fails without embedding"""
        
        mock_client = MagicMock()
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    with patch.object(loader, 'generate_embedding', return_value=[]):
                        result = await loader.test_pattern_search("test query")
                        
                        assert result is False
        
        logger.info("✅ Test 27 passed: Search without embedding")
    
    @pytest.mark.asyncio
    async def test_pattern_search_error(self):
        """Test 28: Handle search error"""
        
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Search failed")
        
        # Mock settings with OpenSearch enabled
        mock_settings = MagicMock()
        mock_settings.opensearch_enabled = True
        mock_settings.opensearch_endpoint = 'https://test-opensearch.example.com'
        mock_settings.opensearch_index_name = 'test-index'
        mock_settings.opensearch_timeout = 30
        mock_settings.opensearch_max_retries = 3
        mock_settings.aws_access_key_id = 'test_key'
        mock_settings.aws_secret_access_key = 'test_secret'
        mock_settings.aws_region = 'ap-southeast-1'
        
        with patch('config.settings.settings', mock_settings):
            with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value='test_key'):
                with patch('src.compliance_agent.services.compliance_pattern_loader.OpenSearch', return_value=mock_client):
                    loader = InternationalCompliancePatternLoader()
                    loader.client = mock_client
                    
                    with patch.object(loader, 'generate_embedding', return_value=[0.1, 0.2, 0.3]):
                        result = await loader.test_pattern_search("test query")
                        
                        assert result is False
        
        logger.info("✅ Test 28 passed: Search error handling")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
