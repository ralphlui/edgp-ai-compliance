"""
EDGP Master Data Models for Compliance Scanning

These models represent the tables in the edgp_masterdata schema
and include compliance-related metadata for data retention analysis.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from .compliance_models import ComplianceFramework, RiskLevel

Base = declarative_base()


class DataRetentionStatus(str, Enum):
    """Data retention compliance status"""
    COMPLIANT = "compliant"
    WARNING = "warning"          # Approaching retention limit
    EXPIRED = "expired"           # Past retention period
    VIOLATION = "violation"       # Significant violation


class ComplianceCategory(str, Enum):
    """Categories of compliance checks"""
    DATA_RETENTION = "data_retention"
    DATA_QUALITY = "data_quality"
    ACCESS_CONTROL = "access_control"
    PRIVACY = "privacy"
    SECURITY = "security"


# SQLAlchemy ORM Models for EDGP Master Data
class Customer(Base):
    """Customer table from edgp_masterdata schema - matches actual schema"""
    __tablename__ = "customer"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(50))
    organization_id = Column(String(50))
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)
    domain_name = Column(String(255))
    workflow_tracker_id = Column(String(255))
    firstname = Column(String(100))
    lastname = Column(String(100))
    age = Column(String(100))  # Note: stored as string in your schema
    gender = Column(String(100))
    email = Column(String(50))
    phone = Column(String(50))
    country = Column(String(50))
    address = Column(String(100))


class Location(Base):
    """Location table from edgp_masterdata schema"""
    __tablename__ = "location"
    
    id = Column(Integer, primary_key=True)
    location_code = Column(String(50), unique=True, nullable=False)
    location_name = Column(String(255), nullable=False)
    location_type = Column(String(50))
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    coordinates = Column(String(100))
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Compliance metadata
    data_retention_category = Column(String(50), default="location_data")
    retention_period_years = Column(Integer, default=10)
    last_compliance_check = Column(DateTime)


class Vendor(Base):
    """Vendor table from edgp_masterdata schema"""
    __tablename__ = "vendor"
    
    id = Column(Integer, primary_key=True)
    vendor_code = Column(String(50), unique=True, nullable=False)
    vendor_name = Column(String(255), nullable=False)
    vendor_type = Column(String(50))
    contact_person = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(Text)
    country = Column(String(100))
    registration_date = Column(DateTime, default=func.now())
    last_transaction_date = Column(DateTime)
    contract_start_date = Column(DateTime)
    contract_end_date = Column(DateTime)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Compliance metadata
    data_retention_category = Column(String(50), default="vendor_data")
    retention_period_years = Column(Integer, default=7)
    last_compliance_check = Column(DateTime)


class Product(Base):
    """Product table from edgp_masterdata schema"""
    __tablename__ = "product"
    
    id = Column(Integer, primary_key=True)
    product_code = Column(String(50), unique=True, nullable=False)
    product_name = Column(String(255), nullable=False)
    category = Column(String(100))
    subcategory = Column(String(100))
    description = Column(Text)
    unit_of_measure = Column(String(50))
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Compliance metadata
    data_retention_category = Column(String(50), default="product_data")
    retention_period_years = Column(Integer, default=5)
    last_compliance_check = Column(DateTime)


# Pydantic Models for API and Business Logic
class CustomerData(BaseModel):
    """Pydantic model for Customer data with compliance analysis - matches actual schema"""
    
    id: int
    file_id: Optional[str] = None
    organization_id: Optional[str] = None
    created_date: datetime
    updated_date: datetime
    is_archived: bool = False
    domain_name: Optional[str] = None
    workflow_tracker_id: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    age: Optional[str] = None  # Note: stored as string in your schema
    gender: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    
    # Additional fields for compliance analysis (not in DB but needed for processing)
    table_name: str = "customer"
    record_type: str = "customer_data"
    data_retention_category: str = "customer_data"
    retention_period_years: int = 7
    
    class Config:
        from_attributes = True


class LocationData(BaseModel):
    """Pydantic model for Location data with compliance analysis"""
    
    id: int
    location_code: str
    location_name: str
    location_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    coordinates: Optional[str] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    
    # Compliance fields
    data_retention_category: str = "location_data"
    retention_period_years: int = 10
    last_compliance_check: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class VendorData(BaseModel):
    """Pydantic model for Vendor data with compliance analysis"""
    
    id: int
    vendor_code: str
    vendor_name: str
    vendor_type: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    registration_date: Optional[datetime] = None
    last_transaction_date: Optional[datetime] = None
    contract_start_date: Optional[datetime] = None
    contract_end_date: Optional[datetime] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    
    # Compliance fields
    data_retention_category: str = "vendor_data"
    retention_period_years: int = 7
    last_compliance_check: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ProductData(BaseModel):
    """Pydantic model for Product data with compliance analysis"""
    
    id: int
    product_code: str
    product_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    unit_of_measure: Optional[str] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    
    # Compliance fields
    data_retention_category: str = "product_data"
    retention_period_years: int = 5
    last_compliance_check: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ComplianceViolationRecord(BaseModel):
    """Model for compliance violation found during scanning"""
    
    table_name: str = Field(..., description="Name of the table where violation was found")
    record_id: int = Field(..., description="ID of the violating record")
    record_code: str = Field(..., description="Business code of the record")
    violation_type: ComplianceCategory = Field(..., description="Type of compliance violation")
    retention_status: DataRetentionStatus = Field(..., description="Data retention status")
    
    # Violation details
    retention_period_years: int = Field(..., description="Expected retention period")
    record_age_days: int = Field(..., description="Age of record in days")
    days_overdue: int = Field(..., description="Days past retention period")
    
    # Risk assessment
    risk_level: RiskLevel = Field(..., description="Risk level of this violation")
    compliance_framework: ComplianceFramework = Field(..., description="Applicable framework")
    
    # Metadata
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    record_data: Dict[str, Any] = Field(..., description="Relevant record data")
    
    # Remediation
    remediation_required: bool = Field(default=True)
    remediation_actions: List[str] = Field(default_factory=list)
    
    @validator('days_overdue')
    def validate_overdue_days(cls, v, values):
        """Ensure days_overdue is consistent with retention status"""
        if values.get('retention_status') in [DataRetentionStatus.EXPIRED, DataRetentionStatus.VIOLATION]:
            if v <= 0:
                raise ValueError("Days overdue must be positive for expired/violation status")
        return v


class DataRetentionAnalysis(BaseModel):
    """Analysis results for data retention compliance"""
    
    scan_id: str = Field(..., description="Unique identifier for this scan")
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Scan scope
    tables_scanned: List[str] = Field(..., description="Tables included in scan")
    total_records_scanned: int = Field(..., description="Total records analyzed")
    
    # Violation summary
    total_violations: int = Field(..., description="Total violations found")
    violations_by_status: Dict[DataRetentionStatus, int] = Field(default_factory=dict)
    violations_by_table: Dict[str, int] = Field(default_factory=dict)
    violations_by_risk: Dict[RiskLevel, int] = Field(default_factory=dict)
    
    # Detailed violations
    violations: List[ComplianceViolationRecord] = Field(default_factory=list)
    
    # Remediation summary
    records_requiring_deletion: int = Field(default=0)
    records_requiring_review: int = Field(default=0)
    estimated_remediation_time_hours: float = Field(default=0.0)
    
    # Compliance score
    overall_compliance_score: float = Field(..., description="Compliance score 0-100")
    compliance_status: str = Field(..., description="Overall compliance status")
    
    def calculate_compliance_score(self) -> float:
        """Calculate overall compliance score based on violations"""
        if self.total_records_scanned == 0:
            return 100.0
        
        # Weight violations by risk level
        violation_score = 0
        for violation in self.violations:
            if violation.risk_level == RiskLevel.CRITICAL:
                violation_score += 10
            elif violation.risk_level == RiskLevel.HIGH:
                violation_score += 5
            elif violation.risk_level == RiskLevel.MEDIUM:
                violation_score += 2
            else:
                violation_score += 1
        
        # Calculate score (max 100)
        max_possible_score = self.total_records_scanned * 10  # Assume worst case all critical
        if max_possible_score == 0:
            return 100.0
        
        compliance_percentage = max(0, (max_possible_score - violation_score) / max_possible_score * 100)
        return round(compliance_percentage, 2)