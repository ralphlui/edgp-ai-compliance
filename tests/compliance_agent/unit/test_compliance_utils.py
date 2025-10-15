"""
Focused coverage test for compliance utilities.
"""
import pytest
import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Set up environment variables before any imports
os.environ.update({
    'MYSQL_HOST': 'localhost',
    'MYSQL_PORT': '3306',
    'MYSQL_USER': 'test_user',
    'MYSQL_PASSWORD': 'test_password',
    'MYSQL_DATABASE': 'test_edgp_compliance',
    'OPENAI_API_KEY': 'test_openai_key',
    'AWS_ACCESS_KEY_ID': 'test_access_key',
    'AWS_SECRET_ACCESS_KEY': 'test_secret_key',
    'AWS_REGION': 'ap-southeast-1',
    'COMPLIANCE_ENVIRONMENT': 'test',
    'LOG_LEVEL': 'INFO'
})


class TestComplianceUtils:
    """Test compliance utility functions."""
    
    def test_mask_pii_data(self):
        """Test PII data masking functionality."""
        from src.compliance_agent.utils.compliance_utils import mask_pii_data
        
        # Test email masking
        text_with_email = "Contact user@example.com for details"
        masked = mask_pii_data(text_with_email)
        assert "***@***.***" in masked
        assert "user@example.com" not in masked
        
        # Test phone masking
        text_with_phone = "Call +65-1234-5678 for support"
        masked = mask_pii_data(text_with_phone)
        assert "+***-***-****" in masked
        assert "+65-1234-5678" not in masked
        
        # Test ID masking
        text_with_id = "User ID is 1234567890ABC"  # Different pattern to avoid phone regex
        masked = mask_pii_data(text_with_id)
        assert "***ID***" in masked or "1234567890ABC" not in masked
    
    def test_validate_consent_date(self):
        """Test consent date validation."""
        from src.compliance_agent.utils.compliance_utils import validate_consent_date
        
        # Test valid consent (recent)
        recent_date = (datetime.now() - timedelta(days=30)).isoformat()
        is_valid, message = validate_consent_date(recent_date, retention_days=365)
        assert is_valid is True
        assert "within retention period" in message
        
        # Test expired consent
        old_date = (datetime.now() - timedelta(days=400)).isoformat()
        is_valid, message = validate_consent_date(old_date, retention_days=365)
        assert is_valid is False
        assert "expired" in message
        
        # Test invalid date format
        is_valid, message = validate_consent_date("invalid-date")
        assert is_valid is False
        assert "Invalid consent date format" in message
    
    def test_detect_compliance_framework(self):
        """Test compliance framework detection."""
        from src.compliance_agent.utils.compliance_utils import detect_compliance_framework
        
        # Test PDPA detection
        singapore_data = {'country': 'singapore', 'region': 'apac'}
        framework = detect_compliance_framework(singapore_data)
        assert framework == 'PDPA'
        
        # Test GDPR detection
        eu_data = {'country': 'germany', 'region': 'europe'}
        framework = detect_compliance_framework(eu_data)
        assert framework == 'GDPR'
        
        # Test CCPA detection
        us_data = {'country': 'usa', 'region': 'california'}
        framework = detect_compliance_framework(us_data)
        assert framework == 'CCPA'
        
        # Test generic fallback
        other_data = {'country': 'other', 'region': 'other'}
        framework = detect_compliance_framework(other_data)
        assert framework == 'Generic'
    
    def test_generate_compliance_report(self):
        """Test compliance report generation."""
        from src.compliance_agent.utils.compliance_utils import generate_compliance_report
        
        test_violations = [
            {'type': 'expired_consent', 'severity': 'high'},
            {'type': 'data_retention', 'severity': 'medium'},
            {'type': 'expired_consent', 'severity': 'low'},
            {'type': 'missing_rights', 'severity': 'high'}
        ]
        
        report = generate_compliance_report(test_violations)
        
        assert report['total_violations'] == 4
        assert report['violation_types']['expired_consent'] == 2
        assert report['violation_types']['data_retention'] == 1
        assert report['severity_breakdown']['high'] == 2
        assert report['severity_breakdown']['medium'] == 1
        assert report['severity_breakdown']['low'] == 1
        assert len(report['recommendations']) > 0
    
    def test_sanitize_log_data(self):
        """Test log data sanitization."""
        from src.compliance_agent.utils.compliance_utils import sanitize_log_data
        
        sensitive_data = {
            'username': 'testuser',
            'password': 'secret123',
            'email': 'user@example.com',
            'normal_field': 'public data',
            'nested': {
                'token': 'abc123',
                'public': 'visible'
            }
        }
        
        sanitized = sanitize_log_data(sensitive_data)
        
        assert sanitized['username'] == 'testuser'
        assert sanitized['password'] == '***MASKED***'
        assert sanitized['email'] == '***MASKED***'  # Email field is masked by key name
        assert sanitized['normal_field'] == 'public data'
        assert sanitized['nested']['token'] == '***MASKED***'
        assert sanitized['nested']['public'] == 'visible'
    
    def test_calculate_retention_expiry(self):
        """Test retention expiry calculation."""
        from src.compliance_agent.utils.compliance_utils import calculate_retention_expiry
        
        # Test valid date
        created_date = '2024-01-01T00:00:00'
        expiry = calculate_retention_expiry(created_date, 365)
        
        # Should be approximately one year later
        created_dt = datetime.fromisoformat(created_date)
        expiry_dt = datetime.fromisoformat(expiry)
        diff = expiry_dt - created_dt
        assert diff.days == 365
        
        # Test invalid date (should not crash)
        expiry = calculate_retention_expiry('invalid-date', 365)
        assert isinstance(expiry, str)
        assert 'T' in expiry  # Should be ISO format
    
    def test_validate_data_structure(self):
        """Test data structure validation."""
        from src.compliance_agent.utils.compliance_utils import validate_data_structure
        
        # Test valid data
        valid_data = {
            'user_id': '12345',
            'consent_date': '2024-01-01',
            'data_type': 'personal'
        }
        required_fields = ['user_id', 'consent_date', 'data_type']
        
        is_valid, missing = validate_data_structure(valid_data, required_fields)
        assert is_valid is True
        assert len(missing) == 0
        
        # Test missing fields
        incomplete_data = {
            'user_id': '12345'
        }
        
        is_valid, missing = validate_data_structure(incomplete_data, required_fields)
        assert is_valid is False
        assert 'consent_date' in missing
        assert 'data_type' in missing
    
    def test_format_compliance_timestamp(self):
        """Test compliance timestamp formatting."""
        from src.compliance_agent.utils.compliance_utils import format_compliance_timestamp
        
        # Test with current time
        timestamp = format_compliance_timestamp()
        assert isinstance(timestamp, str)
        assert 'T' in timestamp  # ISO format
        
        # Test with specific datetime
        specific_dt = datetime(2024, 1, 1, 12, 0, 0)
        timestamp = format_compliance_timestamp(specific_dt)
        assert timestamp.startswith('2024-01-01T12:00:00')
    
    def test_parse_configuration(self):
        """Test configuration parsing."""
        from src.compliance_agent.utils.compliance_utils import parse_configuration
        
        # Test with partial config
        input_config = {
            'retention_days': 730,
            'compliance_framework': 'PDPA'
        }
        
        parsed = parse_configuration(input_config)
        
        assert parsed['retention_days'] == 730
        assert parsed['compliance_framework'] == 'PDPA'
        assert parsed['log_level'] == 'INFO'  # Default value
        assert parsed['enable_pii_masking'] is True  # Default value
        
        # Test with invalid values
        invalid_config = {
            'retention_days': -10,
            'scan_interval_hours': 0
        }
        
        parsed = parse_configuration(invalid_config)
        
        assert parsed['retention_days'] == 365  # Reset to default
        assert parsed['scan_interval_hours'] == 5/60  # Reset to 5-minute default (0.0833... hours)


class TestLoggerUtils:
    """Test logger utility functions."""
    
    def test_logger_import_and_functionality(self):
        """Test logger import and basic functionality."""
        from src.compliance_agent.utils.logger import get_logger
        
        logger = get_logger(__name__)
        assert logger is not None
        
        # Test basic logging (should not raise exceptions)
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        
        # Test with structured data
        logger.info("Test with data", user_id="12345", action="test")


class TestAsyncComplianceOperations:
    """Test async compliance operations."""
    
    @pytest.mark.asyncio
    async def test_async_compliance_workflow(self):
        """Test async compliance workflow simulation."""
        async def simulate_compliance_check(data):
            # Simulate async processing
            await asyncio.sleep(0.001)
            
            from src.compliance_agent.utils.compliance_utils import (
                detect_compliance_framework,
                validate_consent_date,
                mask_pii_data
            )
            
            # Use actual utility functions
            framework = detect_compliance_framework(data)
            consent_valid, _ = validate_consent_date(data.get('consent_date', '2024-01-01'))
            masked_data = mask_pii_data(str(data))
            
            return {
                'framework': framework,
                'consent_valid': consent_valid,
                'processed_data': masked_data
            }
        
        test_data = {
            'country': 'singapore',
            'consent_date': (datetime.now() - timedelta(days=30)).isoformat(),
            'email': 'test@example.com'
        }
        
        result = await simulate_compliance_check(test_data)
        
        assert result['framework'] == 'PDPA'
        assert result['consent_valid'] is True
        assert '***@***.***' in result['processed_data']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])