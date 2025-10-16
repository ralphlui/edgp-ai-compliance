"""
Simplified Compliance Remediation Integration Service

Service for integrating compliance violations with the existing remediation agent.
This service converts compliance violations into API calls to the remediation agent.
"""

import logging
import os
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RemediationRequest(BaseModel):
    """Request format for calling the remediation agent API"""
    id: str = Field(..., description="Unique identifier for the remediation request")
    action: str = Field(..., description="Action to take (e.g., 'delete', 'anonymize', 'archive')")
    message: str = Field(..., description="Human-readable message explaining the remediation")
    field_name: str = Field(..., description="Field/table being remediated")
    domain_name: str = Field(..., description="Domain/schema name")
    framework: str = Field(..., description="Compliance framework (e.g., 'gdpr_eu', 'pdpa_singapore')")
    urgency: str = Field(..., description="Urgency level ('low', 'medium', 'high', 'critical')")
    user_id: str = Field(..., description="ID of the affected user/record")
    
    # Optional metadata for additional context
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ComplianceRemediationService:
    """
    Service for handling compliance remediation requests.
    Integrates with the existing remediation agent to trigger corrective actions.
    """
    
    def __init__(self):
        """Initialize the remediation service"""
        # Get remediation endpoint from environment
        self.remediation_endpoint = os.getenv('REMEDIATION_ENDPOINT', 'http://localhost:8001')
        self.timeout = 30
        
        # Mapping of compliance frameworks to remediation framework names
        self.framework_mapping = {
            "gdpr_eu": "gdpr_eu",
            "pdpa_singapore": "pdpa_singapore", 
            "ccpa_california": "ccpa_california",
            "pipeda_canada": "pipeda_canada"
        }
        
        # Mapping of risk levels to urgency (using strings instead of enums)
        self.risk_to_urgency = {
            "LOW": "low",
            "MEDIUM": "medium", 
            "HIGH": "high",
            "CRITICAL": "critical"
        }
        
        logger.info("Compliance Remediation Service initialized")
        logger.info(f"Remediation endpoint: {self.remediation_endpoint}")
    
    async def trigger_remediation(self, remediation_data: Dict[str, Any]) -> bool:
        """
        Trigger remediation by calling the remediation agent API endpoint
        
        Args:
            remediation_data: Dictionary containing remediation request data in the exact format:
            {
                "id": "customer_record_id",
                "action": "delete", 
                "message": "Customer requested data deletion under GDPR Article 17",
                "field_name": "customer_profile",
                "domain_name": "customer",
                "framework": "gdpr_eu",
                "urgency": "high",
                "user_id": "customer_123"
            }
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use the exact format provided by the user
            remediation_payload = {
                "id": remediation_data.get("id", f"customer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                "action": remediation_data.get("action", "delete"),
                "message": remediation_data.get("message", "Customer data retention compliance violation"),
                "field_name": remediation_data.get("field_name", "customer_profile"),
                "domain_name": remediation_data.get("domain_name", "customer"),
                "framework": remediation_data.get("framework", "gdpr_eu"),
                "urgency": remediation_data.get("urgency", "high"),
                "user_id": remediation_data.get("user_id", "unknown")
            }
            
            logger.info(f"🔧 Triggering remediation API call to: http://localhost:8000/api/v1/remediation/trigger")
            logger.info(f"📤 Payload: {remediation_payload}")
            
            # Enhanced logging for debugging - print the complete request record (controlled by configuration)
            try:
                from config.settings import settings
                if settings.enable_detailed_request_logging:
                    logger.info("=" * 80)
                    logger.info("📋 COMPLETE REMEDIATION REQUEST RECORD")
                    logger.info("=" * 80)
                    logger.info(f"🆔 Request ID: {remediation_payload['id']}")
                    logger.info(f"⚡ Action: {remediation_payload['action']}")
                    logger.info(f"📝 Message: {remediation_payload['message']}")
                    logger.info(f"🏷️  Field Name: {remediation_payload['field_name']}")
                    logger.info(f"🏢 Domain Name: {remediation_payload['domain_name']}")
                    logger.info(f"⚖️  Framework: {remediation_payload['framework']}")
                    logger.info(f"🚨 Urgency: {remediation_payload['urgency']}")
                    logger.info(f"👤 User ID: {remediation_payload['user_id']}")
                    logger.info("📦 Raw Input Data:")
                    for key, value in remediation_data.items():
                        logger.info(f"   {key}: {value}")
                    logger.info("=" * 80)
            except ImportError:
                # Fallback - always show detailed logging if settings unavailable
                logger.info("=" * 80)
                logger.info("📋 COMPLETE REMEDIATION REQUEST RECORD")
                logger.info("=" * 80)
                logger.info(f"🆔 Request ID: {remediation_payload['id']}")
                logger.info(f"⚡ Action: {remediation_payload['action']}")
                logger.info(f"📝 Message: {remediation_payload['message']}")
                logger.info(f"🏷️  Field Name: {remediation_payload['field_name']}")
                logger.info(f"🏢 Domain Name: {remediation_payload['domain_name']}")
                logger.info(f"⚖️  Framework: {remediation_payload['framework']}")
                logger.info(f"🚨 Urgency: {remediation_payload['urgency']}")
                logger.info(f"👤 User ID: {remediation_payload['user_id']}")
                logger.info("📦 Raw Input Data:")
                for key, value in remediation_data.items():
                    logger.info(f"   {key}: {value}")
                logger.info("=" * 80)
            
            # Make the actual HTTP call to the remediation endpoint
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/remediation/trigger",
                    json=remediation_payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Remediation API call successful: {response.status_code}")
                    logger.info(f"📨 Data sent to dev-remediation-workflow-dlq queue")
                    return True
                elif response.status_code == 202:
                    logger.info(f"✅ Remediation request accepted: {response.status_code}")
                    logger.info(f"📨 Data queued for processing - will be sent to dev-remediation-workflow-dlq")
                    return True
                else:
                    logger.error(f"❌ Remediation API call failed: {response.status_code} - {response.text}")
                    return False
            
        except httpx.TimeoutException:
            logger.error("⏰ Remediation API call timed out")
            return False
        except httpx.ConnectError:
            logger.error("🔌 Cannot connect to remediation API - is it running on localhost:8000?")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to trigger remediation: {str(e)}")
            return False
