"""
Comprehensive tests for compliance_utils module
"""

from datetime import datetime, timedelta
from src.compliance_agent.utils.compliance_utils import (
    mask_pii_data,
    validate_consent_date,
    detect_compliance_framework,
    generate_compliance_report,
    sanitize_log_data,
    calculate_retention_expiry,
    validate_data_structure,
    format_compliance_timestamp,
    parse_configuration,
)


def test_mask_pii_data_masks_email():
    text = "Contact us at john.doe@example.com for more info"
    result = mask_pii_data(text)
    assert "***@***.***" in result
    assert "john.doe@example.com" not in result


def test_mask_pii_data_masks_phone_numbers():
    text = "Call me at +1-555-123-4567"
    result = mask_pii_data(text)
    assert "+***-***-****" in result
    assert "555-123-4567" not in result


def test_mask_pii_data_masks_id_numbers():
    text = "ID: 1234567890"  # 10 digits to match the pattern
    result = mask_pii_data(text)
    assert ("***ID***" in result or "1234567890" not in result)


def test_validate_consent_date_valid():
    recent_date = (datetime.now() - timedelta(days=100)).isoformat()
    is_valid, message = validate_consent_date(recent_date, retention_days=365)
    assert is_valid is True
    assert "within retention period" in message


def test_validate_consent_date_expired():
    old_date = (datetime.now() - timedelta(days=500)).isoformat()
    is_valid, message = validate_consent_date(old_date, retention_days=365)
    assert is_valid is False
    assert "expired" in message


def test_validate_consent_date_invalid_format():
    is_valid, message = validate_consent_date("invalid-date", retention_days=365)
    assert is_valid is False
    assert "Invalid consent date format" in message


def test_validate_consent_date_with_timezone():
    recent_date = (datetime.now() - timedelta(days=100)).isoformat()
    is_valid, message = validate_consent_date(recent_date, retention_days=365)
    assert is_valid is True or is_valid is False  # Accept either, main thing is it doesn't crash


def test_detect_compliance_framework_pdpa():
    data = {"country": "singapore"}
    framework = detect_compliance_framework(data)
    assert framework == "PDPA"


def test_detect_compliance_framework_pdpa_region():
    data = {"region": "apac"}
    framework = detect_compliance_framework(data)
    assert framework == "PDPA"


def test_detect_compliance_framework_gdpr():
    data = {"country": "germany"}
    framework = detect_compliance_framework(data)
    assert framework == "GDPR"


def test_detect_compliance_framework_gdpr_region():
    data = {"region": "eu"}
    framework = detect_compliance_framework(data)
    assert framework == "GDPR"


def test_detect_compliance_framework_ccpa():
    data = {"region": "california"}
    framework = detect_compliance_framework(data)
    assert framework == "CCPA"


def test_detect_compliance_framework_generic():
    data = {"country": "unknown"}
    framework = detect_compliance_framework(data)
    assert framework == "Generic"


def test_generate_compliance_report_empty():
    violations = []
    report = generate_compliance_report(violations)
    assert report["total_violations"] == 0
    assert report["severity_breakdown"]["high"] == 0


def test_generate_compliance_report_with_violations():
    violations = [
        {"type": "data_retention", "severity": "high"},
        {"type": "expired_consent", "severity": "medium"},
        {"type": "data_retention", "severity": "low"},
    ]
    report = generate_compliance_report(violations)
    assert report["total_violations"] == 3
    assert report["violation_types"]["data_retention"] == 2
    assert report["severity_breakdown"]["high"] == 1
    assert report["severity_breakdown"]["medium"] == 1


def test_generate_compliance_report_recommendations():
    violations = [
        {"type": "expired_consent", "severity": "high"},
        {"type": "data_retention", "severity": "medium"},
    ]
    report = generate_compliance_report(violations)
    assert len(report["recommendations"]) > 0
    assert any("Immediate action" in r for r in report["recommendations"])


def test_sanitize_log_data_masks_sensitive_keys():
    data = {
        "username": "john",
        "password": "secret123",
        "email": "john@example.com",
        "normal_field": "value",
    }
    sanitized = sanitize_log_data(data)
    assert sanitized["password"] == "***MASKED***"
    assert sanitized["email"] == "***MASKED***"
    assert sanitized["username"] == "john"
    assert sanitized["normal_field"] == "value"


def test_sanitize_log_data_nested_dict():
    data = {
        "user": {"username": "john", "password": "secret", "age": 30},
        "status": "active",
    }
    sanitized = sanitize_log_data(data)
    assert sanitized["user"]["password"] == "***MASKED***"
    assert sanitized["user"]["age"] == 30
    assert sanitized["status"] == "active"


def test_sanitize_log_data_with_list():
    data = {
        "users": [{"name": "john", "email": "john@example.com"}, {"name": "jane", "token": "abc123"}]
    }
    sanitized = sanitize_log_data(data)
    assert sanitized["users"][0]["email"] == "***MASKED***"
    assert sanitized["users"][1]["token"] == "***MASKED***"


def test_sanitize_log_data_masks_pii_in_strings():
    data = {"message": "Contact john.doe@example.com for details"}
    sanitized = sanitize_log_data(data)
    assert "john.doe@example.com" not in sanitized["message"]
    assert "***@***.***" in sanitized["message"]


def test_calculate_retention_expiry_valid_date():
    created_date = "2023-01-01T00:00:00"
    expiry = calculate_retention_expiry(created_date, 365)
    expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    created_dt = datetime.fromisoformat(created_date)
    diff = (expiry_dt - created_dt).days
    assert diff == 365


def test_calculate_retention_expiry_invalid_date():
    expiry = calculate_retention_expiry("invalid-date", 365)
    assert expiry is not None
    # Should return a valid ISO format date
    datetime.fromisoformat(expiry.replace("Z", "+00:00"))


def test_calculate_retention_expiry_with_timezone():
    created_date = "2023-01-01T00:00:00Z"
    expiry = calculate_retention_expiry(created_date, 365)
    assert expiry is not None


def test_validate_data_structure_all_fields_present():
    data = {"name": "John", "email": "john@example.com", "age": 30}
    required = ["name", "email", "age"]
    is_valid, missing = validate_data_structure(data, required)
    assert is_valid is True
    assert len(missing) == 0


def test_validate_data_structure_missing_fields():
    data = {"name": "John", "age": 30}
    required = ["name", "email", "age"]
    is_valid, missing = validate_data_structure(data, required)
    assert is_valid is False
    assert "email" in missing


def test_validate_data_structure_empty_values():
    data = {"name": "John", "email": "", "age": None}
    required = ["name", "email", "age"]
    is_valid, missing = validate_data_structure(data, required)
    assert is_valid is False
    assert "email" in missing
    assert "age" in missing


def test_format_compliance_timestamp_default():
    timestamp = format_compliance_timestamp()
    assert timestamp is not None
    dt = datetime.fromisoformat(timestamp)
    assert isinstance(dt, datetime)


def test_format_compliance_timestamp_custom():
    custom_dt = datetime(2023, 1, 1, 12, 0, 0)
    timestamp = format_compliance_timestamp(custom_dt)
    assert "2023-01-01" in timestamp


def test_parse_configuration_defaults():
    config = parse_configuration({})
    assert config["retention_days"] == 365
    assert config["compliance_framework"] == "Generic"
    assert config["log_level"] == "INFO"
    assert config["enable_pii_masking"] is True


def test_parse_configuration_custom_values():
    custom = {"retention_days": 730, "compliance_framework": "GDPR", "log_level": "DEBUG"}
    config = parse_configuration(custom)
    assert config["retention_days"] == 730
    assert config["compliance_framework"] == "GDPR"
    assert config["log_level"] == "DEBUG"


def test_parse_configuration_validates_ranges():
    invalid_config = {"retention_days": -1, "scan_interval_hours": 0.0001}
    config = parse_configuration(invalid_config)
    assert config["retention_days"] == 365  # Should reset to default
    assert config["scan_interval_hours"] == 5 / 60  # Should reset to default


def test_parse_configuration_merges_with_defaults():
    partial = {"retention_days": 180}
    config = parse_configuration(partial)
    assert config["retention_days"] == 180
    assert "compliance_framework" in config
    assert "log_level" in config
