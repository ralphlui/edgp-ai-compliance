"""
LangSmith Dataset Creation Script

Create a test dataset from compliance violations for evaluation.
"""

from langsmith import Client
from datetime import datetime
from typing import List, Dict, Any
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compliance_agent.utils.logger import get_logger

logger = get_logger(__name__)


def create_compliance_dataset():
    """
    Create a LangSmith dataset from compliance violations
    """
    client = Client()
    
    # Dataset metadata
    dataset_name = f"compliance-violations-test-{datetime.now().strftime('%Y%m%d')}"
    description = "Test dataset for PDPA/GDPR compliance analysis evaluation"
    
    # Create dataset (or get existing one)
    try:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=description
        )
        logger.info(f"✅ Created dataset: {dataset.name} (ID: {dataset.id})")
    except Exception as e:
        # Check if dataset already exists
        if "already exists" in str(e).lower():
            logger.info(f"📊 Dataset '{dataset_name}' already exists, retrieving it...")
            try:
                # Get existing dataset
                datasets = client.list_datasets(dataset_name=dataset_name)
                dataset = next((d for d in datasets if d.name == dataset_name), None)
                if dataset:
                    logger.info(f"✅ Using existing dataset: {dataset.name} (ID: {dataset.id})")
                else:
                    logger.error("❌ Could not retrieve existing dataset")
                    return None
            except Exception as inner_e:
                logger.error(f"❌ Failed to retrieve existing dataset: {inner_e}")
                return None
        else:
            logger.error(f"❌ Failed to create dataset: {e}")
            return None
    
    # Test cases covering different scenarios
    test_cases = [
        # High severity PDPA violation
        {
            "inputs": {
                "customer_id": "20",
                "data_age_days": 9158,
                "retention_limit_days": 2555,
                "excess_days": 6603,
                "framework": "PDPA",
                "region": "Singapore"
            },
            "outputs": {
                "description": "Customer data for ID 20 has been retained for 9158 days, exceeding the PDPA 7-year retention limit by 6603 days. This represents a severe violation of data minimization principles.",
                "recommendation": "Immediately delete all personal data for Customer ID 20. Implement automated retention policy enforcement to prevent future violations.",
                "legal_reference": "PDPA Article 25 - Data Retention Limitation",
                "urgency_level": "HIGH",
                "compliance_impact": "Potential financial penalties up to SGD 1 million under PDPA Section 48D. Risk of PDPC investigation if systematic non-compliance is found."
            },
            "metadata": {
                "test_case_id": "TC-001",
                "category": "high_severity_pdpa",
                "framework": "PDPA"
            }
        },
        
        # High severity GDPR violation
        {
            "inputs": {
                "customer_id": "42",
                "data_age_days": 8500,
                "retention_limit_days": 2555,
                "excess_days": 5945,
                "framework": "GDPR",
                "region": "European Union"
            },
            "outputs": {
                "description": "Customer data for ID 42 has been retained for 8500 days, exceeding the GDPR maximum retention period by 5945 days. This violates the storage limitation principle.",
                "recommendation": "Initiate immediate deletion of all personal data. Conduct a review of similar accounts to identify additional violations. Implement automated retention policy enforcement.",
                "legal_reference": "GDPR Article 17 (Right to Erasure) and Article 5(1)(e) (Storage Limitation)",
                "urgency_level": "HIGH",
                "compliance_impact": "Potential fines up to €20 million or 4% of annual global turnover under GDPR Article 83. Risk of supervisory authority investigation and mandatory breach notification."
            },
            "metadata": {
                "test_case_id": "TC-002",
                "category": "high_severity_gdpr",
                "framework": "GDPR"
            }
        },
        
        # Medium severity PDPA violation
        {
            "inputs": {
                "customer_id": "15",
                "data_age_days": 2800,
                "retention_limit_days": 2555,
                "excess_days": 245,
                "framework": "PDPA",
                "region": "Singapore"
            },
            "outputs": {
                "description": "Customer ID 15's data has been stored for 2800 days, exceeding the 7-year PDPA retention limit by 245 days. While not severe, this represents non-compliance with Singapore's data protection framework.",
                "recommendation": "Schedule deletion within 30 days. Review data retention policies for similar customer cohorts. Update automated compliance checks to flag records approaching limits.",
                "legal_reference": "PDPA Article 25 - Data Retention Limitation",
                "urgency_level": "MEDIUM",
                "compliance_impact": "Potential financial penalties up to SGD 1 million under PDPA Section 48D if violations are found to be systematic."
            },
            "metadata": {
                "test_case_id": "TC-003",
                "category": "medium_severity_pdpa",
                "framework": "PDPA"
            }
        },
        
        # Medium severity GDPR violation
        {
            "inputs": {
                "customer_id": "88",
                "data_age_days": 4200,
                "retention_limit_days": 2555,
                "excess_days": 1645,
                "framework": "GDPR",
                "region": "European Union"
            },
            "outputs": {
                "description": "Customer data has been retained for 4200 days, exceeding GDPR retention limits by 1645 days. This indicates a need for improved data lifecycle management.",
                "recommendation": "Delete personal data within 60 days. Implement automated data retention monitoring. Conduct quarterly reviews of data age across customer base.",
                "legal_reference": "GDPR Article 5(1)(e) - Storage Limitation Principle",
                "urgency_level": "MEDIUM",
                "compliance_impact": "Risk of regulatory investigation if pattern of non-compliance is identified. Potential for customer complaints under GDPR Article 77."
            },
            "metadata": {
                "test_case_id": "TC-004",
                "category": "medium_severity_gdpr",
                "framework": "GDPR"
            }
        },
        
        # Low severity PDPA violation
        {
            "inputs": {
                "customer_id": "103",
                "data_age_days": 2700,
                "retention_limit_days": 2555,
                "excess_days": 145,
                "framework": "PDPA",
                "region": "Singapore"
            },
            "outputs": {
                "description": "Customer data retention has exceeded the PDPA limit by 145 days. This is a minor violation that should be addressed promptly.",
                "recommendation": "Schedule deletion within 90 days. Add to batch deletion queue for next maintenance window. Review data retention automation to prevent future occurrences.",
                "legal_reference": "PDPA Article 25 - Data Retention Limitation",
                "urgency_level": "LOW",
                "compliance_impact": "Low immediate risk. Should be resolved as part of routine compliance maintenance. Demonstrates need for improved automation."
            },
            "metadata": {
                "test_case_id": "TC-005",
                "category": "low_severity_pdpa",
                "framework": "PDPA"
            }
        },
        
        # Edge case: Very high severity
        {
            "inputs": {
                "customer_id": "200",
                "data_age_days": 12000,
                "retention_limit_days": 2555,
                "excess_days": 9445,
                "framework": "GDPR",
                "region": "European Union"
            },
            "outputs": {
                "description": "Extreme violation: Customer data retained for 12,000 days (32.9 years), exceeding GDPR limits by 9,445 days (25.9 years). This is a critical compliance failure.",
                "recommendation": "URGENT: Delete immediately within 24 hours. Escalate to Data Protection Officer. Investigate why this record was not flagged earlier. Implement emergency audit of all customer records.",
                "legal_reference": "GDPR Article 17 (Right to Erasure), Article 5(1)(e) (Storage Limitation), Article 83 (Administrative Fines)",
                "urgency_level": "HIGH",
                "compliance_impact": "Severe risk of maximum penalties (€20M or 4% global turnover). Mandatory breach notification may be required. Reputational damage likely if discovered by supervisory authority."
            },
            "metadata": {
                "test_case_id": "TC-006",
                "category": "extreme_severity_gdpr",
                "framework": "GDPR"
            }
        }
    ]
    
    # Add examples to dataset
    added_count = 0
    for case in test_cases:
        try:
            client.create_example(
                inputs=case["inputs"],
                outputs=case["outputs"],
                dataset_id=dataset.id,
                metadata=case.get("metadata", {})
            )
            test_id = case.get("metadata", {}).get("test_case_id", "Unknown")
            logger.info(f"  ✅ Added test case {test_id}")
            added_count += 1
        except Exception as e:
            logger.error(f"  ❌ Failed to add test case: {e}")
    
    logger.info(f"\n🎉 Dataset created successfully!")
    logger.info(f"📊 Dataset Name: {dataset_name}")
    logger.info(f"📊 Dataset ID: {dataset.id}")
    logger.info(f"📊 Examples Added: {added_count}/{len(test_cases)}")
    logger.info(f"🔗 View dataset: https://smith.langchain.com/o/datasets/{dataset.id}")
    
    return dataset


if __name__ == "__main__":
    print("\n" + "="*80)
    print("LANGSMITH DATASET CREATION")
    print("="*80 + "\n")
    
    # Check environment variables
    import os
    if not os.getenv("LANGCHAIN_API_KEY"):
        print("❌ ERROR: LANGCHAIN_API_KEY not set")
        print("Please set it in your environment or .env file")
        exit(1)
    
    dataset = create_compliance_dataset()
    
    if dataset:
        print("\n✅ SUCCESS: Dataset created and ready for experiments")
        print(f"📊 Use dataset name: {dataset.name}")
    else:
        print("\n❌ FAILED: Could not create dataset")
        exit(1)
