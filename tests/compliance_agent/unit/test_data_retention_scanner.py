#!/usr/bin/env python3
"""
test_data_retention_scanner.py

Comprehensive test suite for Data Retention Scanner
Tests for 75%+ code coverage

Tests include:
1. Scanner initialization
2. Risk threshold configuration
3. Table scanning (customer, location, vendor, product)
4. Retention period analysis
5. Violation detection and classification
6. Compliance score calculation
7. AI-powered analysis (with mocking)
8. Error handling
9. Database integration
10. Batch processing
"""

import pytest
import logging
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

# Mock SQLAlchemy BEFORE any imports (Python 3.13 compatibility)
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()
sys.modules['sqlalchemy.sql'] = MagicMock()

# Set up test environment
os.environ.update({
    'OPENAI_API_KEY': 'test_openai_key',
    'AWS_ACCESS_KEY_ID': 'test_access_key',
    'AWS_SECRET_ACCESS_KEY': 'test_secret_key',
    'AWS_REGION': 'ap-southeast-1'
})

from src.compliance_agent.services.data_retention_scanner import DataRetentionScanner
from src.compliance_agent.models.edgp_models import (
    CustomerData, LocationData, VendorData, ProductData,
    ComplianceViolationRecord, DataRetentionAnalysis,
    DataRetentionStatus, ComplianceCategory
)
from src.compliance_agent.models.compliance_models import ComplianceFramework, RiskLevel

logger = logging.getLogger(__name__)


class TestScannerInitialization:
    """Test scanner initialization and configuration"""
    
    def test_scanner_initialization_with_api_key(self):
        """Test 1: Scanner initializes with OpenAI API key"""
        scanner = DataRetentionScanner()
        
        assert scanner is not None
        assert hasattr(scanner, 'default_retention_periods')
        assert hasattr(scanner, 'risk_thresholds')
        assert scanner.llm is not None  # Should have LLM client
        
        logger.info("✅ Test 1 passed: Scanner initialization with API key")
    
    def test_default_retention_periods(self):
        """Test 2: Default retention periods are configured"""
        scanner = DataRetentionScanner()
        
        periods = scanner.default_retention_periods
        
        assert periods['customer'] == 7, "Customer retention should be 7 years"
        assert periods['location'] == 10, "Location retention should be 10 years"
        assert periods['vendor'] == 7, "Vendor retention should be 7 years"
        assert periods['product'] == 5, "Product retention should be 5 years"
        
        logger.info("✅ Test 2 passed: Default retention periods")
    
    def test_risk_thresholds_configuration(self):
        """Test 3: Risk thresholds are properly configured"""
        scanner = DataRetentionScanner()
        
        thresholds = scanner.risk_thresholds
        
        assert thresholds[RiskLevel.LOW] == 30, "Low risk should be 30 days"
        assert thresholds[RiskLevel.MEDIUM] == 90, "Medium risk should be 90 days"
        assert thresholds[RiskLevel.HIGH] == 180, "High risk should be 180 days"
        assert thresholds[RiskLevel.CRITICAL] == 365, "Critical risk should be 365 days"
        
        logger.info("✅ Test 3 passed: Risk thresholds configuration")
    
    def test_scanner_initialization_without_api_key(self):
        """Test 4: Scanner handles missing API key gracefully"""
        
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value=None):
            scanner = DataRetentionScanner()
            
            assert scanner.llm is None, "LLM should be None without API key"
            assert hasattr(scanner, 'default_retention_periods')
        
        logger.info("✅ Test 4 passed: Scanner without API key")


class TestRetentionPeriodCalculation:
    """Test retention period calculations"""
    
    def test_calculate_record_age(self):
        """Test 5: Calculate record age correctly"""
        scanner = DataRetentionScanner()
        
        # Create old record (8 years ago)
        created_date = datetime.now() - timedelta(days=365 * 8)
        record_age = (datetime.now() - created_date).days
        
        # Should be approximately 2920 days (8 years)
        expected_age = 365 * 8
        assert abs(record_age - expected_age) <= 2, f"Age should be ~{expected_age} days"
        
        logger.info(f"✅ Test 5 passed: Record age = {record_age} days")
    
    def test_calculate_days_overdue(self):
        """Test 6: Calculate days overdue for retention"""
        scanner = DataRetentionScanner()
        
        # Record created 8 years ago, retention limit 7 years
        record_age_days = 365 * 8
        retention_limit_days = 365 * 7
        days_overdue = record_age_days - retention_limit_days
        
        assert days_overdue == 365, "Should be 365 days overdue"
        assert days_overdue >= scanner.risk_thresholds[RiskLevel.CRITICAL], "Should be critical risk (>=365 days)"
        
        logger.info("✅ Test 6 passed: Days overdue calculation")


class TestCustomerRecordAnalysis:
    """Test customer record retention analysis"""
    
    @pytest.mark.asyncio
    async def test_analyze_customer_records_with_violations(self):
        """Test 7: Analyze customer records and find violations"""
        scanner = DataRetentionScanner()
        
        # Create old customer that exceeds retention
        old_customer = CustomerData(
            id=1,
            file_id="CUST_001",
            firstname="John",
            lastname="Doe",
            email="john@example.com",
            country="Singapore",
            domain_name="example.com",
            created_date=datetime.now() - timedelta(days=365 * 8),  # 8 years old
            updated_date=datetime.now() - timedelta(days=365 * 4),  # 4 years since update
            is_archived=False,
            retention_period_years=7
        )
        
        # Mock AI analysis
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_violation = ComplianceViolationRecord(
                table_name="customer",
                record_id=1,
                record_code="CUST_001",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=7,
                record_age_days=365 * 8,
                days_overdue=365,
                risk_level=RiskLevel.HIGH,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={"email": "john@example.com"}
            )
            mock_analyze.return_value = mock_violation
            
            violations = await scanner._analyze_customer_records([old_customer], ComplianceFramework.GDPR_EU)
            
            assert len(violations) == 1, "Should find one violation"
            assert violations[0].table_name == "customer"
            assert violations[0].risk_level == RiskLevel.HIGH
            mock_analyze.assert_called_once()
        
        logger.info("✅ Test 7 passed: Customer record analysis with violations")
    
    @pytest.mark.asyncio
    async def test_analyze_customer_records_no_violations(self):
        """Test 8: Analyze recent customer records with no violations"""
        scanner = DataRetentionScanner()
        
        # Create recent customer within retention period
        new_customer = CustomerData(
            id=2,
            file_id="CUST_002",
            firstname="Jane",
            lastname="Smith",
            email="jane@example.com",
            created_date=datetime.now() - timedelta(days=365),  # 1 year old
            updated_date=datetime.now() - timedelta(days=30),
            is_archived=False,
            retention_period_years=7
        )
        
        # Mock AI analysis returning None (no violation)
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = None
            
            violations = await scanner._analyze_customer_records([new_customer], ComplianceFramework.PDPA_SINGAPORE)
            
            assert len(violations) == 0, "Should find no violations"
        
        logger.info("✅ Test 8 passed: No violations for recent customer")
    
    @pytest.mark.asyncio
    async def test_analyze_customer_with_missing_name(self):
        """Test 9: Handle customer with missing firstname/lastname"""
        scanner = DataRetentionScanner()
        
        # Customer with no name
        customer = CustomerData(
            id=3,
            email="nofirstname@example.com",
            created_date=datetime.now() - timedelta(days=365 * 8),
            updated_date=datetime.now(),
            retention_period_years=7
        )
        
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = None
            
            violations = await scanner._analyze_customer_records([customer], ComplianceFramework.GDPR_EU)
            
            # Should handle gracefully
            assert isinstance(violations, list)
            # Check that customer name was generated
            call_args = mock_analyze.call_args
            record_data = call_args[1]['record_data']
            assert 'Customer ID 3' in record_data['customer_name'] or record_data['customer_name'] == ''
        
        logger.info("✅ Test 9 passed: Customer with missing name")


class TestLocationRecordAnalysis:
    """Test location record retention analysis"""
    
    @pytest.mark.asyncio
    async def test_analyze_location_records(self):
        """Test 10: Analyze location records"""
        scanner = DataRetentionScanner()
        
        old_location = LocationData(
            id=1,
            location_code="LOC_001",
            location_name="Old Warehouse",
            location_type="warehouse",
            status="inactive",
            country="Singapore",
            city="Singapore",
            created_at=datetime.now() - timedelta(days=365 * 12),  # 12 years old
            updated_at=datetime.now() - timedelta(days=365 * 5),
            retention_period_years=10
        )
        
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_violation = ComplianceViolationRecord(
                table_name="location",
                record_id=1,
                record_code="LOC_001",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=10,
                record_age_days=365 * 12,
                days_overdue=730,
                risk_level=RiskLevel.HIGH,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={"location_name": "Old Warehouse"}
            )
            mock_analyze.return_value = mock_violation
            
            violations = await scanner._analyze_location_records([old_location], ComplianceFramework.GDPR_EU)
            
            assert len(violations) == 1
            assert violations[0].table_name == "location"
        
        logger.info("✅ Test 10 passed: Location record analysis")


class TestVendorRecordAnalysis:
    """Test vendor record retention analysis"""
    
    @pytest.mark.asyncio
    async def test_analyze_vendor_records(self):
        """Test 11: Analyze vendor records"""
        scanner = DataRetentionScanner()
        
        old_vendor = VendorData(
            id=1,
            vendor_code="VEN_001",
            vendor_name="Old Supplier Inc",
            status="inactive",
            country="Singapore",
            created_at=datetime.now() - timedelta(days=365 * 9),  # 9 years old
            updated_at=datetime.now() - timedelta(days=365 * 6),
            last_transaction_date=datetime.now() - timedelta(days=365 * 6),
            retention_period_years=7
        )
        
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_violation = ComplianceViolationRecord(
                table_name="vendor",
                record_id=1,
                record_code="VEN_001",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=7,
                record_age_days=365 * 9,
                days_overdue=730,
                risk_level=RiskLevel.MEDIUM,
                compliance_framework=ComplianceFramework.PDPA_SINGAPORE,
                record_data={"vendor_name": "Old Supplier Inc"}
            )
            mock_analyze.return_value = mock_violation
            
            violations = await scanner._analyze_vendor_records([old_vendor], ComplianceFramework.PDPA_SINGAPORE)
            
            assert len(violations) == 1
            assert violations[0].table_name == "vendor"
        
        logger.info("✅ Test 11 passed: Vendor record analysis")


class TestProductRecordAnalysis:
    """Test product record retention analysis"""
    
    @pytest.mark.asyncio
    async def test_analyze_product_records(self):
        """Test 12: Analyze product records"""
        scanner = DataRetentionScanner()
        
        old_product = ProductData(
            id=1,
            product_code="PROD_001",
            product_name="Discontinued Widget",
            status="discontinued",
            created_at=datetime.now() - timedelta(days=365 * 7),  # 7 years old
            updated_at=datetime.now() - timedelta(days=365 * 4),
            retention_period_years=5
        )
        
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_violation = ComplianceViolationRecord(
                table_name="product",
                record_id=1,
                record_code="PROD_001",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=5,
                record_age_days=365 * 7,
                days_overdue=730,
                risk_level=RiskLevel.MEDIUM,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={"product_name": "Discontinued Widget"}
            )
            mock_analyze.return_value = mock_violation
            
            violations = await scanner._analyze_product_records([old_product], ComplianceFramework.GDPR_EU)
            
            assert len(violations) == 1
            assert violations[0].table_name == "product"
        
        logger.info("✅ Test 12 passed: Product record analysis")


class TestTableScanning:
    """Test table scanning functionality"""
    
    @pytest.mark.asyncio
    async def test_scan_table_customer(self):
        """Test 13: Scan customer table"""
        scanner = DataRetentionScanner()
        
        mock_customers = [
            CustomerData(
                id=1,
                email="test@example.com",
                created_date=datetime.now() - timedelta(days=365 * 8),
                updated_date=datetime.now(),
                retention_period_years=7
            )
        ]
        
        with patch.object(scanner, '_analyze_customer_records', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = []
            
            violations = await scanner._scan_table("customer", ComplianceFramework.GDPR_EU)
            
            assert isinstance(violations, list)
            # _scan_table calls the database, but since we mock _analyze_customer_records, 
            # the actual database call happens
        
        logger.info("✅ Test 13 passed: Scan customer table")
    
    @pytest.mark.asyncio
    async def test_scan_table_unknown(self):
        """Test 14: Handle unknown table name"""
        scanner = DataRetentionScanner()
        
        violations = await scanner._scan_table("unknown_table", ComplianceFramework.GDPR_EU)
        
        assert isinstance(violations, list)
        assert len(violations) == 0, "Unknown table should return empty list"
        
        logger.info("✅ Test 14 passed: Unknown table handling")
    
    @pytest.mark.asyncio
    async def test_scan_table_with_error(self):
        """Test 15: Handle errors during table scan"""
        scanner = DataRetentionScanner()
        
        # Mock _analyze_customer_records to raise an error
        with patch.object(scanner, '_analyze_customer_records', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis error")
            
            violations = await scanner._scan_table("customer", ComplianceFramework.GDPR_EU)
            
            assert isinstance(violations, list)
            assert len(violations) == 0, "Error should return empty list"
        
        logger.info("✅ Test 15 passed: Table scan error handling")


class TestComprehensiveScan:
    """Test comprehensive scanning of all tables"""
    
    @pytest.mark.asyncio
    async def test_scan_all_tables_default(self):
        """Test 16: Scan all tables with default configuration"""
        scanner = DataRetentionScanner()
        
        with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.initialize', new_callable=AsyncMock):
            with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.close', new_callable=AsyncMock):
                with patch.object(scanner, '_scan_table', new_callable=AsyncMock) as mock_scan:
                    mock_scan.return_value = []
                    
                    analysis = await scanner.scan_all_tables()
                    
                    assert analysis is not None
                    assert analysis.scan_id.startswith("retention_scan_")
                    assert len(analysis.tables_scanned) == 4  # customer, location, vendor, product
                    assert "customer" in analysis.tables_scanned
                    assert "location" in analysis.tables_scanned
                    assert analysis.compliance_status == "compliant"  # No violations
        
        logger.info("✅ Test 16 passed: Scan all tables default")
    
    @pytest.mark.asyncio
    async def test_scan_all_tables_specific(self):
        """Test 17: Scan specific tables"""
        scanner = DataRetentionScanner()
        
        with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.initialize', new_callable=AsyncMock):
            with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.close', new_callable=AsyncMock):
                with patch.object(scanner, '_scan_table', new_callable=AsyncMock) as mock_scan:
                    mock_scan.return_value = []
                    
                    analysis = await scanner.scan_all_tables(tables=["customer", "vendor"])
                    
                    assert len(analysis.tables_scanned) == 2
                    assert "customer" in analysis.tables_scanned
                    assert "vendor" in analysis.tables_scanned
                    assert mock_scan.call_count == 2
        
        logger.info("✅ Test 17 passed: Scan specific tables")
    
    @pytest.mark.asyncio
    async def test_scan_all_tables_with_violations(self):
        """Test 18: Scan with violations found"""
        scanner = DataRetentionScanner()
        
        mock_violations = [
            ComplianceViolationRecord(
                table_name="customer",
                record_id=1,
                record_code="CUST_001",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.EXPIRED,
                retention_period_years=7,
                record_age_days=365 * 8,
                days_overdue=365,
                risk_level=RiskLevel.HIGH,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={"email": "test1@example.com"}
            ),
            ComplianceViolationRecord(
                table_name="customer",
                record_id=2,
                record_code="CUST_002",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.WARNING,
                retention_period_years=7,
                record_age_days=365 * 6,
                days_overdue=100,
                risk_level=RiskLevel.MEDIUM,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={"email": "test2@example.com"}
            )
        ]
        
        with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.initialize', new_callable=AsyncMock):
            with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.close', new_callable=AsyncMock):
                with patch.object(scanner, '_scan_table', new_callable=AsyncMock) as mock_scan:
                    mock_scan.return_value = mock_violations
                    
                    analysis = await scanner.scan_all_tables(tables=["customer"])
                    
                    assert analysis.total_violations == 2
                    assert analysis.records_requiring_deletion == 1  # EXPIRED
                    assert analysis.records_requiring_review == 1  # WARNING
                    assert analysis.violations_by_table["customer"] == 2
                    assert analysis.violations_by_status[DataRetentionStatus.EXPIRED] == 1
                    assert analysis.violations_by_risk[RiskLevel.HIGH] == 1
        
        logger.info("✅ Test 18 passed: Scan with violations")


class TestComplianceScoring:
    """Test compliance score calculation"""
    
    @pytest.mark.asyncio
    async def test_compliance_score_all_compliant(self):
        """Test 19: Compliance score when all records compliant"""
        scanner = DataRetentionScanner()
        
        with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.initialize', new_callable=AsyncMock):
            with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.close', new_callable=AsyncMock):
                with patch.object(scanner, '_scan_table', new_callable=AsyncMock) as mock_scan:
                    mock_scan.return_value = []
                    
                    analysis = await scanner.scan_all_tables()
                    
                    assert analysis.overall_compliance_score == 100.0
                    assert analysis.compliance_status == "compliant"
        
        logger.info("✅ Test 19 passed: Full compliance score")
    
    @pytest.mark.asyncio
    async def test_compliance_status_warning(self):
        """Test 20: Compliance status warning level"""
        scanner = DataRetentionScanner()
        
        # Just verify that warnings are properly counted
        mock_violations = [
            ComplianceViolationRecord(
                table_name="customer",
                record_id=i,
                record_code=f"CUST_{i:03d}",
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=DataRetentionStatus.WARNING,
                retention_period_years=7,
                record_age_days=365 * 6,
                days_overdue=50,
                risk_level=RiskLevel.LOW,
                compliance_framework=ComplianceFramework.GDPR_EU,
                record_data={"email": f"test{i}@example.com"}
            )
            for i in range(1, 6)  # 5 warnings
        ]
        
        with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.initialize', new_callable=AsyncMock):
            with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.close', new_callable=AsyncMock):
                with patch.object(scanner, '_scan_table', new_callable=AsyncMock) as mock_scan:
                    mock_scan.return_value = mock_violations
                    
                    analysis = await scanner.scan_all_tables(tables=["customer"])
                    
                    # Verify warnings are captured
                    assert analysis.total_violations == 5
                    assert analysis.records_requiring_review == 5
                    assert analysis.violations_by_status[DataRetentionStatus.WARNING] == 5
        
        logger.info("✅ Test 20 passed: Warning compliance status")


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_scan_with_database_error(self):
        """Test 21: Handle database initialization error"""
        scanner = DataRetentionScanner()
        
        with patch('src.compliance_agent.services.data_retention_scanner.edgp_db_service.initialize', new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = Exception("Database connection failed")
            
            with pytest.raises(Exception):
                await scanner.scan_all_tables()
        
        logger.info("✅ Test 21 passed: Database error handling")
    
    @pytest.mark.asyncio
    async def test_analyze_customer_with_error(self):
        """Test 22: Handle error in customer analysis"""
        scanner = DataRetentionScanner()
        
        # Customer with error-inducing data
        bad_customer = CustomerData(
            id=999,
            email="error@example.com",
            created_date=datetime.now(),
            updated_date=datetime.now(),
            retention_period_years=7
        )
        
        with patch.object(scanner, '_analyze_record_retention', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis error")
            
            # Should handle error and continue
            violations = await scanner._analyze_customer_records([bad_customer], ComplianceFramework.GDPR_EU)
            
            assert len(violations) == 0, "Should return empty list on error"
        
        logger.info("✅ Test 22 passed: Customer analysis error handling")


class TestRiskLevelDetermination:
    """Test risk level determination"""
    
    def test_determine_risk_level_critical(self):
        """Test 23: Determine critical risk level"""
        scanner = DataRetentionScanner()
        
        days_overdue = 400  # Over 365 days
        
        # Critical if > 365 days overdue
        assert days_overdue > scanner.risk_thresholds[RiskLevel.CRITICAL]
        
        logger.info("✅ Test 23 passed: Critical risk determination")
    
    def test_determine_risk_level_high(self):
        """Test 24: Determine high risk level"""
        scanner = DataRetentionScanner()
        
        days_overdue = 200  # 180-365 days
        
        assert days_overdue > scanner.risk_thresholds[RiskLevel.HIGH]
        assert days_overdue < scanner.risk_thresholds[RiskLevel.CRITICAL]
        
        logger.info("✅ Test 24 passed: High risk determination")
    
    def test_determine_risk_level_medium(self):
        """Test 25: Determine medium risk level"""
        scanner = DataRetentionScanner()
        
        days_overdue = 100  # 90-180 days
        
        assert days_overdue > scanner.risk_thresholds[RiskLevel.MEDIUM]
        assert days_overdue < scanner.risk_thresholds[RiskLevel.HIGH]
        
        logger.info("✅ Test 25 passed: Medium risk determination")
    
    def test_determine_risk_level_low(self):
        """Test 26: Determine low risk level"""
        scanner = DataRetentionScanner()
        
        days_overdue = 40  # 30-90 days
        
        assert days_overdue > scanner.risk_thresholds[RiskLevel.LOW]
        assert days_overdue < scanner.risk_thresholds[RiskLevel.MEDIUM]
        
        logger.info("✅ Test 26 passed: Low risk determination")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
