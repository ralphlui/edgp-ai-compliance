"""
Standalone compliance utilities for testing without external dependencies.
"""
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple


def mask_pii_data(text: str) -> str:
    """
    Mask PII data in text for compliance logging.
    
    Args:
        text: Input text that may contain PII
        
    Returns:
        Text with PII data masked
    """
    # Email masking
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    text = re.sub(email_pattern, '***@***.***', text)
    
    # Phone number masking
    phone_pattern = r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
    text = re.sub(phone_pattern, '+***-***-****', text)
    
    # ID number masking (simple pattern)
    id_pattern = r'\b\d{6,12}\b'
    text = re.sub(id_pattern, '***ID***', text)
    
    return text


def validate_consent_date(consent_date: str, retention_days: int = 365) -> Tuple[bool, str]:
    """
    Validate if consent date is within retention period.
    
    Args:
        consent_date: ISO format date string
        retention_days: Number of days for retention
        
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        consent_dt = datetime.fromisoformat(consent_date.replace('Z', '+00:00'))
        current_dt = datetime.now()
        retention_period = timedelta(days=retention_days)
        
        is_valid = (current_dt - consent_dt) <= retention_period
        
        if is_valid:
            return True, "Consent is within retention period"
        else:
            days_expired = (current_dt - consent_dt).days - retention_days
            return False, f"Consent expired {days_expired} days ago"
            
    except (ValueError, TypeError) as e:
        return False, f"Invalid consent date format: {e}"


def detect_compliance_framework(data: Dict[str, Any]) -> str:
    """
    Detect appropriate compliance framework based on data attributes.
    
    Args:
        data: Dictionary containing data attributes
        
    Returns:
        Compliance framework name
    """
    country = data.get('country', '').lower()
    region = data.get('region', '').lower()
    
    # PDPA detection (Singapore and similar)
    if country in ['singapore', 'sg'] or region in ['apac', 'asia-pacific']:
        return 'PDPA'
    
    # GDPR detection (EU countries)
    eu_countries = ['germany', 'france', 'italy', 'spain', 'netherlands', 'belgium']
    if country in eu_countries or region in ['eu', 'europe']:
        return 'GDPR'
    
    # CCPA detection (California)
    if region in ['california', 'ca'] or country == 'usa':
        return 'CCPA'
    
    return 'Generic'


def generate_compliance_report(violations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a compliance report from violations data.
    
    Args:
        violations: List of violation dictionaries
        
    Returns:
        Compliance report dictionary
    """
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_violations': len(violations),
        'violation_types': {},
        'severity_breakdown': {'high': 0, 'medium': 0, 'low': 0},
        'recommendations': []
    }
    
    for violation in violations:
        # Count violation types
        violation_type = violation.get('type', 'unknown')
        report['violation_types'][violation_type] = report['violation_types'].get(violation_type, 0) + 1
        
        # Count severity levels
        severity = violation.get('severity', 'medium')
        if severity in report['severity_breakdown']:
            report['severity_breakdown'][severity] += 1
    
    # Generate recommendations
    if report['severity_breakdown']['high'] > 0:
        report['recommendations'].append('Immediate action required for high-severity violations')
    
    if report['violation_types'].get('expired_consent', 0) > 0:
        report['recommendations'].append('Review and update consent management processes')
    
    if report['violation_types'].get('data_retention', 0) > 0:
        report['recommendations'].append('Implement automated data retention policies')
    
    return report


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize data for logging by removing or masking sensitive information.
    
    Args:
        data: Dictionary containing data to be logged
        
    Returns:
        Sanitized data dictionary
    """
    sanitized = {}
    
    sensitive_keys = ['password', 'token', 'secret', 'key', 'email', 'phone']
    
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = '***MASKED***'
        elif isinstance(value, str):
            sanitized[key] = mask_pii_data(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_log_data(item) if isinstance(item, dict) else item for item in value]
        else:
            sanitized[key] = value
    
    return sanitized


def calculate_retention_expiry(created_date: str, retention_period_days: int) -> str:
    """
    Calculate when data should expire based on retention policy.
    
    Args:
        created_date: ISO format date string when data was created
        retention_period_days: Number of days to retain data
        
    Returns:
        ISO format date string for expiry date
    """
    try:
        created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
        expiry_dt = created_dt + timedelta(days=retention_period_days)
        return expiry_dt.isoformat()
    except (ValueError, TypeError):
        # If date parsing fails, return a default expiry
        default_expiry = datetime.now() + timedelta(days=retention_period_days)
        return default_expiry.isoformat()


def validate_data_structure(data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that data structure contains required fields for compliance.
    
    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, list_of_missing_fields)
    """
    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields


def format_compliance_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Format timestamp for compliance logging.
    
    Args:
        dt: Datetime object, defaults to current time
        
    Returns:
        ISO formatted timestamp string
    """
    if dt is None:
        dt = datetime.now()
    
    return dt.isoformat()


def parse_configuration(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate configuration for compliance agent.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        Validated configuration dictionary
    """
    default_config = {
        'retention_days': 365,
        'compliance_framework': 'Generic',
        'log_level': 'INFO',
        'enable_pii_masking': True,
        'scan_interval_hours': 5/60  # Every 5 minutes
    }
    
    # Merge with defaults
    config = {**default_config, **config_dict}
    
    # Validate ranges
    if config['retention_days'] < 1:
        config['retention_days'] = 365
    
    if config['scan_interval_hours'] < 1/60:  # Minimum 1 minute
        config['scan_interval_hours'] = 5/60  # Default to 5 minutes
    
    return config