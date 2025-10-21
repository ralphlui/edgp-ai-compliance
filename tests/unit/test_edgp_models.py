"""
Tests for EDGP Master Data Models
File: tests/unit/test_edgp_models.py
Target: src/compliance_agent/models/edgp_models.py (Pydantic models only)

Mock SQLAlchemy to avoid Python 3.13 compatibility issues
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from unittest.mock import MagicMock
import sys

# Mock SQLAlchemy modules BEFORE importing edgp_models
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()
sys.modules['sqlalchemy.sql'] = MagicMock()

from src.compliance_agent.models.edgp_models import (
    DataRetentionStatus,
    ComplianceCategory,
    CustomerData,
    LocationData,
    VendorData,
    ProductData,
    ComplianceViolationRecord,
    DataRetentionAnalysis
)
from src.compliance_agent.models.compliance_models import (
    ComplianceFramework,
    RiskLevel
)


class TestDataRetentionStatus:
    """Test DataRetentionStatus enum"""
    
    def test_data_retention_status_values(self):
        """Test all enum values are accessible"""
        assert DataRetentionStatus.COMPLIANT == "compliant"
        assert DataRetentionStatus.WARNING == "warning"
        assert DataRetentionStatus.EXPIRED == "expired"
        assert DataRetentionStatus.VIOLATION == "violation"
    
    def test_data_retention_status_membership(self):
        """Test enum membership checks"""
        assert "compliant" in [e.value for e in DataRetentionStatus]
        assert "warning" in [e.value for e in DataRetentionStatus]
        assert "expired" in [e.value for e in DataRetentionStatus]
        assert "violation" in [e.value for e in DataRetentionStatus]


class TestComplianceCategory:
    """Test ComplianceCategory enum"""
    
    def test_compliance_category_values(self):
        """Test all category values"""
        assert ComplianceCategory.DATA_RETENTION == "data_retention"
        assert ComplianceCategory.DATA_QUALITY == "data_quality"
        assert ComplianceCategory.ACCESS_CONTROL == "access_control"
        assert ComplianceCategory.PRIVACY == "privacy"
        assert ComplianceCategory.SECURITY == "security"
    
    def test_compliance_category_membership(self):
        """Test category membership"""
        categories = [e.value for e in ComplianceCategory]
        assert "data_retention" in categories
        assert "privacy" in categories


class TestCustomerData:
    """Test CustomerData Pydantic model"""
    
    def test_customer_data_creation(self):
        """Test creating a valid customer data instance"""
        now = datetime.utcnow()
        customer = CustomerData(
            id=1,
            file_id="FILE123",
            organization_id="ORG456",
            created_date=now,
            updated_date=now,
            is_archived=False,
            domain_name="example.com",
            workflow_tracker_id="WF789",
            firstname="John",
            lastname="Doe",
            age="30",
            gender="M",
            email="john.doe@example.com",
            phone="555-1234",
            country="USA",
            address="123 Main St"
        )
        
        assert customer.id == 1
        assert customer.firstname == "John"
        assert customer.lastname == "Doe"
        assert customer.email == "john.doe@example.com"
        assert customer.table_name == "customer"
        assert customer.retention_period_years == 7
    
    def test_customer_data_optional_fields(self):
        """Test customer with optional fields"""
        now = datetime.utcnow()
        customer = CustomerData(
            id=2,
            created_date=now,
            updated_date=now,
            is_archived=False
        )
        
        assert customer.id == 2
        assert customer.firstname is None
        assert customer.email is None
        assert customer.retention_period_years == 7
    
    def test_customer_data_retention_defaults(self):
        """Test customer data retention default values"""
        now = datetime.utcnow()
        customer = CustomerData(
            id=3,
            created_date=now,
            updated_date=now,
            is_archived=False
        )
        
        assert customer.table_name == "customer"
        assert customer.record_type == "customer_data"
        assert customer.data_retention_category == "customer_data"
        assert customer.retention_period_years == 7


class TestLocationData:
    """Test LocationData Pydantic model"""
    
    def test_location_data_creation(self):
        """Test creating a valid location data instance"""
        now = datetime.utcnow()
        location = LocationData(
            id=1,
            location_code="LOC001",
            location_name="Main Office",
            location_type="Office",
            address="456 Business Rd",
            city="New York",
            state="NY",
            country="USA",
            postal_code="10001",
            coordinates="40.7128,-74.0060",
            status="active",
            created_at=now,
            updated_at=now
        )
        
        assert location.id == 1
        assert location.location_code == "LOC001"
        assert location.location_name == "Main Office"
        assert location.city == "New York"
        assert location.retention_period_years == 10
        assert location.data_retention_category == "location_data"
    
    def test_location_data_optional_fields(self):
        """Test location with minimal required fields"""
        now = datetime.utcnow()
        location = LocationData(
            id=2,
            location_code="LOC002",
            location_name="Branch Office",
            created_at=now,
            updated_at=now
        )
        
        assert location.id == 2
        assert location.location_name == "Branch Office"
        assert location.city is None
        assert location.last_compliance_check is None
    
    def test_location_data_compliance_check(self):
        """Test location with compliance check timestamp"""
        now = datetime.utcnow()
        check_time = now - timedelta(days=30)
        location = LocationData(
            id=3,
            location_code="LOC003",
            location_name="Warehouse",
            created_at=now,
            updated_at=now,
            last_compliance_check=check_time
        )
        
        assert location.last_compliance_check == check_time


class TestVendorData:
    """Test VendorData Pydantic model"""
    
    def test_vendor_data_creation(self):
        """Test creating a valid vendor data instance"""
        now = datetime.utcnow()
        reg_date = now - timedelta(days=365)
        last_transaction = now - timedelta(days=30)
        contract_start = reg_date
        contract_end = now + timedelta(days=365)
        
        vendor = VendorData(
            id=1,
            vendor_code="VEN001",
            vendor_name="ABC Supplies",
            vendor_type="Supplier",
            contact_person="Jane Smith",
            email="jane@abcsupplies.com",
            phone="555-5678",
            address="789 Vendor St",
            country="USA",
            registration_date=reg_date,
            last_transaction_date=last_transaction,
            contract_start_date=contract_start,
            contract_end_date=contract_end,
            status="active",
            created_at=now,
            updated_at=now
        )
        
        assert vendor.id == 1
        assert vendor.vendor_code == "VEN001"
        assert vendor.vendor_name == "ABC Supplies"
        assert vendor.contact_person == "Jane Smith"
        assert vendor.retention_period_years == 7
        assert vendor.data_retention_category == "vendor_data"
    
    def test_vendor_data_minimal_fields(self):
        """Test vendor with minimal required fields"""
        now = datetime.utcnow()
        vendor = VendorData(
            id=2,
            vendor_code="VEN002",
            vendor_name="XYZ Corp",
            created_at=now,
            updated_at=now
        )
        
        assert vendor.id == 2
        assert vendor.vendor_name == "XYZ Corp"
        assert vendor.status == "active"
        assert vendor.last_compliance_check is None


class TestProductData:
    """Test ProductData Pydantic model"""
    
    def test_product_data_creation(self):
        """Test creating a valid product data instance"""
        now = datetime.utcnow()
        product = ProductData(
            id=1,
            product_code="PROD001",
            product_name="Widget A",
            category="Electronics",
            subcategory="Components",
            description="High-quality widget",
            unit_of_measure="piece",
            status="active",
            created_at=now,
            updated_at=now
        )
        
        assert product.id == 1
        assert product.product_code == "PROD001"
        assert product.product_name == "Widget A"
        assert product.category == "Electronics"
        assert product.retention_period_years == 5
        assert product.data_retention_category == "product_data"
    
    def test_product_data_minimal_fields(self):
        """Test product with minimal required fields"""
        now = datetime.utcnow()
        product = ProductData(
            id=2,
            product_code="PROD002",
            product_name="Widget B",
            created_at=now,
            updated_at=now
        )
        
        assert product.id == 2
        assert product.product_name == "Widget B"
        assert product.status == "active"


class TestComplianceViolationRecord:
    """Test ComplianceViolationRecord model"""
    
    def test_violation_record_creation(self):
        """Test creating a compliance violation record"""
        violation = ComplianceViolationRecord(
            table_name="customer",
            record_id=123,
            record_code="CUST123",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.EXPIRED,
            retention_period_years=7,
            record_age_days=2920,  # ~8 years
            days_overdue=365,
            risk_level=RiskLevel.HIGH,
            compliance_framework=ComplianceFramework.GDPR_EU,
            record_data={"customer_name": "John Doe", "email": "john@example.com"}
        )
        
        assert violation.table_name == "customer"
        assert violation.record_id == 123
        assert violation.violation_type == ComplianceCategory.DATA_RETENTION
        assert violation.retention_status == DataRetentionStatus.EXPIRED
        assert violation.days_overdue == 365
        assert violation.risk_level == RiskLevel.HIGH
        assert violation.remediation_required is True
    
    def test_violation_record_with_actions(self):
        """Test violation with remediation actions"""
        violation = ComplianceViolationRecord(
            table_name="vendor",
            record_id=456,
            record_code="VEN456",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.VIOLATION,
            retention_period_years=7,
            record_age_days=3650,
            days_overdue=730,
            risk_level=RiskLevel.CRITICAL,
            compliance_framework=ComplianceFramework.CCPA_CALIFORNIA,
            record_data={"vendor_name": "Old Supplier"},
            remediation_actions=["Archive record", "Notify data protection officer", "Delete PII"]
        )
        
        assert len(violation.remediation_actions) == 3
        assert "Archive record" in violation.remediation_actions
        assert violation.risk_level == RiskLevel.CRITICAL
    
    def test_violation_record_validation_error(self):
        """Test that invalid days_overdue raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            ComplianceViolationRecord(
                table_name="customer",
                record_id=789,
                record_code="CUST789",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=7,
                record_age_days=2920,
                days_overdue=-10,  # Invalid: negative overdue
                risk_level=RiskLevel.HIGH,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={}
            )
        
        assert "days overdue must be positive" in str(exc_info.value).lower()


class TestDataRetentionAnalysis:
    """Test DataRetentionAnalysis model"""
    
    def test_analysis_creation(self):
        """Test creating a data retention analysis"""
        analysis = DataRetentionAnalysis(
            scan_id="SCAN001",
            tables_scanned=["customer", "vendor", "product"],
            total_records_scanned=1000,
            total_violations=50,
            overall_compliance_score=85.5,
            compliance_status="Good"
        )
        
        assert analysis.scan_id == "SCAN001"
        assert len(analysis.tables_scanned) == 3
        assert analysis.total_records_scanned == 1000
        assert analysis.total_violations == 50
        assert analysis.overall_compliance_score == 85.5
    
    def test_analysis_with_violations(self):
        """Test analysis with violation details"""
        violation1 = ComplianceViolationRecord(
            table_name="customer",
            record_id=1,
            record_code="CUST001",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.EXPIRED,
            retention_period_years=7,
            record_age_days=2920,
            days_overdue=365,
            risk_level=RiskLevel.HIGH,
            compliance_framework=ComplianceFramework.GDPR_EU,
            record_data={}
        )
        
        violation2 = ComplianceViolationRecord(
            table_name="vendor",
            record_id=2,
            record_code="VEN002",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.VIOLATION,
            retention_period_years=7,
            record_age_days=3650,
            days_overdue=730,
            risk_level=RiskLevel.CRITICAL,
            compliance_framework=ComplianceFramework.CCPA_CALIFORNIA,
            record_data={}
        )
        
        analysis = DataRetentionAnalysis(
            scan_id="SCAN002",
            tables_scanned=["customer", "vendor"],
            total_records_scanned=500,
            total_violations=2,
            violations=[violation1, violation2],
            records_requiring_deletion=2,
            overall_compliance_score=95.0,
            compliance_status="Excellent"
        )
        
        assert len(analysis.violations) == 2
        assert analysis.records_requiring_deletion == 2
        assert analysis.violations[0].risk_level == RiskLevel.HIGH
        assert analysis.violations[1].risk_level == RiskLevel.CRITICAL
    
    def test_analysis_calculate_compliance_score(self):
        """Test compliance score calculation"""
        # Create high-risk violations
        violations = []
        for i in range(10):
            violation = ComplianceViolationRecord(
                table_name="customer",
                record_id=i,
                record_code=f"CUST{i:03d}",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=7,
                record_age_days=3000,
                days_overdue=365,
                risk_level=RiskLevel.CRITICAL if i < 5 else RiskLevel.HIGH,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={}
            )
            violations.append(violation)
        
        analysis = DataRetentionAnalysis(
            scan_id="SCAN003",
            tables_scanned=["customer"],
            total_records_scanned=1000,
            total_violations=10,
            violations=violations,
            overall_compliance_score=0.0,  # Will be calculated
            compliance_status="Needs Improvement"
        )
        
        # Calculate score
        score = analysis.calculate_compliance_score()
        
        assert isinstance(score, float)
        assert 0 <= score <= 100
        # With 10 violations (5 critical, 5 high) out of 1000 records, score should be high
        assert score > 80
    
    def test_analysis_empty_scan(self):
        """Test analysis with no violations"""
        analysis = DataRetentionAnalysis(
            scan_id="SCAN004",
            tables_scanned=["customer"],
            total_records_scanned=1000,
            total_violations=0,
            overall_compliance_score=100.0,
            compliance_status="Perfect"
        )
        
        assert analysis.total_violations == 0
        assert len(analysis.violations) == 0
        assert analysis.calculate_compliance_score() == 100.0
    
    def test_analysis_violations_by_status(self):
        """Test violation tracking by status"""
        analysis = DataRetentionAnalysis(
            scan_id="SCAN005",
            tables_scanned=["customer", "vendor"],
            total_records_scanned=500,
            total_violations=15,
            violations_by_status={
                DataRetentionStatus.EXPIRED: 10,
                DataRetentionStatus.VIOLATION: 5
            },
            violations_by_table={
                "customer": 8,
                "vendor": 7
            },
            violations_by_risk={
                RiskLevel.CRITICAL: 3,
                RiskLevel.HIGH: 7,
                RiskLevel.MEDIUM: 5
            },
            overall_compliance_score=88.0,
            compliance_status="Good"
        )
        
        assert analysis.violations_by_status[DataRetentionStatus.EXPIRED] == 10
        assert analysis.violations_by_table["customer"] == 8
        assert analysis.violations_by_risk[RiskLevel.CRITICAL] == 3


class TestModelIntegration:
    """Test integration between models"""
    
    def test_customer_to_violation_flow(self):
        """Test creating a violation from customer data"""
        now = datetime.utcnow()
        customer = CustomerData(
            id=100,
            file_id="FILE100",
            firstname="Jane",
            lastname="Doe",
            email="jane@example.com",
            created_date=now - timedelta(days=3000),
            updated_date=now,
            is_archived=False
        )
        
        # Create violation based on customer
        violation = ComplianceViolationRecord(
            table_name=customer.table_name,
            record_id=customer.id,
            record_code=f"{customer.firstname}_{customer.lastname}",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.EXPIRED,
            retention_period_years=customer.retention_period_years,
            record_age_days=3000,
            days_overdue=435,  # ~3000 - (7*365)
            risk_level=RiskLevel.HIGH,
            compliance_framework=ComplianceFramework.GDPR_EU,
            record_data={"email": customer.email}
        )
        
        assert violation.table_name == "customer"
        assert violation.record_id == customer.id
        assert violation.retention_period_years == 7
    
    def test_multiple_table_analysis(self):
        """Test analysis across multiple data types"""
        # Create sample violations
        customer_violation = ComplianceViolationRecord(
            table_name="customer",
            record_id=1,
            record_code="CUST001",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.EXPIRED,
            retention_period_years=7,
            record_age_days=3000,
            days_overdue=435,
            risk_level=RiskLevel.HIGH,
            compliance_framework=ComplianceFramework.GDPR_EU,
            record_data={}
        )
        
        vendor_violation = ComplianceViolationRecord(
            table_name="vendor",
            record_id=2,
            record_code="VEN002",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.VIOLATION,
            retention_period_years=7,
            record_age_days=4000,
            days_overdue=1445,
            risk_level=RiskLevel.CRITICAL,
            compliance_framework=ComplianceFramework.GDPR_EU,
            record_data={}
        )
        
        product_violation = ComplianceViolationRecord(
            table_name="product",
            record_id=3,
            record_code="PROD003",
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=DataRetentionStatus.EXPIRED,
            retention_period_years=5,
            record_age_days=2000,
            days_overdue=175,
            risk_level=RiskLevel.MEDIUM,
            compliance_framework=ComplianceFramework.ISO_27001,
            record_data={}
        )
        
        # Create comprehensive analysis
        analysis = DataRetentionAnalysis(
            scan_id="SCAN_MULTI",
            tables_scanned=["customer", "vendor", "product"],
            total_records_scanned=3000,
            total_violations=3,
            violations=[customer_violation, vendor_violation, product_violation],
            violations_by_table={"customer": 1, "vendor": 1, "product": 1},
            violations_by_risk={RiskLevel.CRITICAL: 1, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 1},
            records_requiring_deletion=3,
            overall_compliance_score=92.0,
            compliance_status="Good"
        )
        
        assert len(analysis.violations) == 3
        assert len(analysis.tables_scanned) == 3
        assert analysis.violations_by_table["customer"] == 1
        assert analysis.violations_by_risk[RiskLevel.CRITICAL] == 1
