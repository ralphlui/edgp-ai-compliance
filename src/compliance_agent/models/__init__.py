"""
Models package initialization
"""

from .compliance_models import (
    ComplianceFramework,
    DataType,
    RiskLevel,
    ComplianceStatus,
    DataSubject,
    DataProcessingActivity,
    ComplianceRule,
    ComplianceViolation,
    ComplianceAssessment,
    PrivacyImpactAssessment,
    ConsentRecord,
    DataBreachIncident,
)

# from .edgp_models import (
#     Customer,
#     Location,
#     Vendor,
#     Product,
#     CustomerData,
#     LocationData,
#     VendorData,
#     ProductData,
#     ComplianceViolationRecord,
#     DataRetentionAnalysis,
#     DataRetentionStatus,
#     ComplianceCategory
# )

__all__ = [
    "ComplianceFramework",
    "DataType", 
    "RiskLevel",
    "ComplianceStatus",
    "DataSubject",
    "DataProcessingActivity",
    "ComplianceRule",
    "ComplianceViolation",
    "ComplianceAssessment",
    "PrivacyImpactAssessment",
    "ConsentRecord",
    "DataBreachIncident",
    # "Customer",
    # "Location", 
    # "Vendor",
    # "Product",
    # "CustomerData",
    # "LocationData",
    # "VendorData", 
    # "ProductData",
    # "ComplianceViolationRecord",
    # "DataRetentionAnalysis",
    # "DataRetentionStatus",
    # "ComplianceCategory"
]