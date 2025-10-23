"""
Tests for compliance_utils without SQLAlchemy dependencies
"""

import pytest
from datetime import datetime, timedelta


def test_mask_pii_data_email():
    """Test email masking"""
    from src.compliance_agent.utils.compliance_utils import mask_pii_data

    text = "Email: john.doe@example.com"
    result = mask_pii_data(text)
    assert "***@***.***" in result
    assert "john.doe@example.com" not in result


def test_mask_pii_data_phone():
    """Test phone masking"""
    from src.compliance_agent.utils.compliance_utils import mask_pii_data

    text = "Phone: +1-555-1234"
    result = mask_pii_data(text)
    assert "+***-***-****" in result


def test_mask_pii_data_id():
    """Test ID masking"""
    from src.compliance_agent.utils.compliance_utils import mask_pii_data

    text = "ID: 1234567890"  # 10 digits
    result = mask_pii_data(text)
    assert ("***ID***" in result or "1234567890" not in result)


def test_validate_consent_date_valid():
    """Test valid consent date"""
    from src.compliance_agent.utils.compliance_utils import validate_consent_date

    recent = (datetime.now() - timedelta(days=100)).isoformat()
    valid, msg = validate_consent_date(recent, 365)
    assert valid is True


def test_validate_consent_date_expired():
    """Test expired consent"""
    from src.compliance_agent.utils.compliance_utils import validate_consent_date

    old = (datetime.now() - timedelta(days=500)).isoformat()
    valid, msg = validate_consent_date(old, 365)
    assert valid is False
    assert "expired" in msg


def test_detect_framework_pdpa():
    """Test PDPA detection"""
    from src.compliance_agent.utils.compliance_utils import detect_compliance_framework

    result = detect_compliance_framework({"country": "singapore"})
    assert result == "PDPA"


def test_detect_framework_gdpr():
    """Test GDPR detection"""
    from src.compliance_agent.utils.compliance_utils import detect_compliance_framework

    result = detect_compliance_framework({"country": "germany"})
    assert result == "GDPR"


def test_detect_framework_ccpa():
    """Test CCPA detection"""
    from src.compliance_agent.utils.compliance_utils import detect_compliance_framework

    result = detect_compliance_framework({"region": "california"})
    assert result == "CCPA"


def test_generate_report():
    """Test compliance report generation"""
    from src.compliance_agent.utils.compliance_utils import generate_compliance_report

    violations = [
        {"type": "data_retention", "severity": "high"},
        {"type": "expired_consent", "severity": "medium"},
    ]
    report = generate_compliance_report(violations)
    assert report["total_violations"] == 2
    assert len(report["recommendations"]) > 0


def test_sanitize_log_data():
    """Test log data sanitization"""
    from src.compliance_agent.utils.compliance_utils import sanitize_log_data

    data = {"password": "secret", "email": "test@test.com", "name": "John"}
    result = sanitize_log_data(data)
    assert result["password"] == "***MASKED***"
    assert result["email"] == "***MASKED***"
    assert result["name"] == "John"


def test_sanitize_nested():
    """Test nested sanitization"""
    from src.compliance_agent.utils.compliance_utils import sanitize_log_data

    data = {"user": {"password": "secret", "name": "John"}}
    result = sanitize_log_data(data)
    assert result["user"]["password"] == "***MASKED***"
    assert result["user"]["name"] == "John"


def test_calculate_retention_expiry():
    """Test retention expiry calculation"""
    from src.compliance_agent.utils.compliance_utils import calculate_retention_expiry

    created = "2023-01-01T00:00:00"
    expiry = calculate_retention_expiry(created, 365)
    assert "2024" in expiry


def test_validate_data_structure():
    """Test data structure validation"""
    from src.compliance_agent.utils.compliance_utils import validate_data_structure

    data = {"name": "John", "email": "john@test.com"}
    valid, missing = validate_data_structure(data, ["name", "email"])
    assert valid is True
    assert len(missing) == 0


def test_validate_data_missing_fields():
    """Test missing fields detection"""
    from src.compliance_agent.utils.compliance_utils import validate_data_structure

    data = {"name": "John"}
    valid, missing = validate_data_structure(data, ["name", "email"])
    assert valid is False
    assert "email" in missing


def test_format_timestamp():
    """Test timestamp formatting"""
    from src.compliance_agent.utils.compliance_utils import format_compliance_timestamp

    result = format_compliance_timestamp()
    assert result is not None
    assert "T" in result


def test_parse_configuration():
    """Test configuration parsing"""
    from src.compliance_agent.utils.compliance_utils import parse_configuration

    config = parse_configuration({"retention_days": 730})
    assert config["retention_days"] == 730
    assert "compliance_framework" in config


def test_parse_config_validates():
    """Test configuration validation"""
    from src.compliance_agent.utils.compliance_utils import parse_configuration

    config = parse_configuration({"retention_days": -10})
    assert config["retention_days"] == 365  # Should default


def test_multiple_pii_masks():
    """Test multiple PII items in one text"""
    from src.compliance_agent.utils.compliance_utils import mask_pii_data

    text = "Contact john@test.com or call +1-555-1234, ID: 987654321"
    result = mask_pii_data(text)
    assert "john@test.com" not in result
    assert "555-1234" not in result
    assert "987654321" not in result


def test_sanitize_list_data():
    """Test sanitizing list of dicts"""
    from src.compliance_agent.utils.compliance_utils import sanitize_log_data

    data = {"users": [{"email": "a@test.com"}, {"token": "secret"}]}
    result = sanitize_log_data(data)
    assert result["users"][0]["email"] == "***MASKED***"
    assert result["users"][1]["token"] == "***MASKED***"


def test_report_with_different_types():
    """Test report with various violation types"""
    from src.compliance_agent.utils.compliance_utils import generate_compliance_report

    violations = [
        {"type": "data_retention", "severity": "high"},
        {"type": "data_retention", "severity": "low"},
        {"type": "expired_consent", "severity": "medium"},
        {"type": "access_control", "severity": "high"},
    ]
    report = generate_compliance_report(violations)
    assert report["violation_types"]["data_retention"] == 2
    assert report["severity_breakdown"]["high"] == 2
    assert report["severity_breakdown"]["medium"] == 1
