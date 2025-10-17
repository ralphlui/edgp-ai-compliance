#!/usr/bin/env python3
"""
Clean EDGP Data Retention Compliance Agent
Focused on Customer table data retention compliance checking
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass

from src.compliance_agent.services.edgp_database_service_simple import EDGPDatabaseService
from src.compliance_agent.services.ai_analyzer import AIComplianceAnalyzer
from src.compliance_agent.services.remediation_integration_service import ComplianceRemediationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ComplianceViolation:
    """Represents a compliance violation found in customer data."""
    customer_id: int
    violation_type: str
    severity: str  # HIGH, MEDIUM, LOW
    description: str
    data_age_days: int
    retention_limit_days: int
    recommended_action: str
    raw_data: Dict[str, Any]

class CleanEDGPComplianceAgent:
    """
    Simple, focused compliance agent for EDGP customer data retention.
    
    Core functionality:
    1. Read customer data from MySQL database periodically
    2. Use LLM to analyze data retention compliance
    3. Trigger remediation for violations
    4. Focus on Customer table only
    """
    
    def __init__(self):
        self.db_service = EDGPDatabaseService()
        self.ai_analyzer = AIComplianceAnalyzer()
        self.remediation_service = ComplianceRemediationService()
        
        # Data retention limits (in days)
        self.retention_limits = {
            'customer_default': 7 * 365,  # 7 years
            'inactive_customer': 3 * 365,  # 3 years for inactive
            'deleted_customer': 30,       # 30 days after deletion request
        }
    
    async def initialize(self) -> bool:
        """Initialize all services."""
        try:
            await self.db_service.initialize()
            logger.info("✅ EDGP Compliance Agent initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {str(e)}")
            return False
    
    async def scan_customer_compliance(self) -> List[ComplianceViolation]:
        """
        Main compliance scanning function for customer data.
        
        Returns:
            List of compliance violations found
        """
        violations = []
        
        try:
            logger.info("🔍 Starting customer data retention compliance scan...")
            
            # 1. Read all customer data from database
            customers = await self.db_service.get_customers()
            logger.info(f"📊 Found {len(customers)} customers to analyze")
            
            # 2. Analyze each customer for compliance violations
            for customer in customers:
                violation = await self._analyze_customer_retention(customer)
                if violation:
                    violations.append(violation)
            
            logger.info(f"⚠️  Found {len(violations)} compliance violations")
            
            # 3. Trigger remediation for high-severity violations
            for violation in violations:
                if violation.severity == 'HIGH':
                    await self._trigger_remediation(violation)
            
            return violations
            
        except Exception as e:
            logger.error(f"❌ Compliance scan failed: {str(e)}")
            return []
    
    async def _analyze_customer_retention(self, customer) -> Optional[ComplianceViolation]:
        """
        Analyze individual customer record for data retention compliance.
        
        Args:
            customer: CustomerData object from database
            
        Returns:
            ComplianceViolation if violation found, None otherwise
        """
        try:
            # Calculate data age
            created_date = customer.created_date
            last_activity = customer.updated_date  # Use updated_date as last activity
            
            if not created_date:
                return None
            
            data_age = (datetime.now() - created_date).days
            last_activity_age = (datetime.now() - last_activity).days if last_activity else data_age
            
            # Determine applicable retention limit
            retention_limit = self._get_retention_limit(customer, last_activity_age)
            
            # Check if data exceeds retention period
            if data_age > retention_limit:
                # Use LLM to analyze the violation context
                ai_analysis = await self._get_ai_violation_analysis(customer, data_age, retention_limit)
                
                violation = ComplianceViolation(
                    customer_id=customer.id,
                    violation_type='DATA_RETENTION_EXCEEDED',
                    severity=ai_analysis['severity'],
                    description=ai_analysis['description'],
                    data_age_days=data_age,
                    retention_limit_days=retention_limit,
                    recommended_action=ai_analysis['recommended_action'],
                    raw_data=customer.dict()  # Convert to dict for storage
                )
                
                logger.warning(f"⚠️  Violation found: Customer {customer.id} - {violation.description}")
                return violation
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze customer {getattr(customer, 'id', 'unknown')}: {str(e)}")
            return None
    
    def _get_retention_limit(self, customer, last_activity_age: int) -> int:
        """Determine the applicable data retention limit for a customer."""
        
        # Check if customer is archived (equivalent to deletion requested)
        if customer.is_archived:
            return self.retention_limits['deleted_customer']
        
        # Check if customer is inactive (no activity for 2+ years)
        if last_activity_age > (2 * 365):
            return self.retention_limits['inactive_customer']
        
        # Default retention period
        return self.retention_limits['customer_default']
    
    async def _get_ai_violation_analysis(self, customer, data_age: int, retention_limit: int) -> Dict[str, str]:
        """
        Use LLM to analyze the compliance violation and provide recommendations.
        
        Args:
            customer: CustomerData object
            data_age: Age of customer data in days
            retention_limit: Applicable retention limit in days
            
        Returns:
            AI analysis with severity, description, and recommended action
        """
        
        # Prepare data for AI analysis
        analysis_context = {
            "customer_id": customer.id,
            "data_age_days": data_age,
            "retention_limit_days": retention_limit,
            "excess_days": data_age - retention_limit,
            "is_archived": customer.is_archived,
            "last_activity": customer.updated_date,
            "has_email": bool(customer.email),
            "has_phone": bool(customer.phone),
            "customer_name": f"{customer.firstname or ''} {customer.lastname or ''}".strip()
        }
        
        # AI prompt for compliance analysis
        prompt = f"""
        Analyze this customer data retention compliance violation:
        
        Customer ID: {analysis_context['customer_id']}
        Data Age: {analysis_context['data_age_days']} days
        Retention Limit: {analysis_context['retention_limit_days']} days
        Excess Period: {analysis_context['excess_days']} days
        Customer Status: {analysis_context['customer_status']}
        Last Activity: {analysis_context['last_activity']}
        Deletion Requested: {analysis_context['deletion_requested']}
        Has Active Orders: {analysis_context['has_active_orders']}
        
        Based on GDPR and PDPA data retention requirements, provide:
        1. Severity level (HIGH/MEDIUM/LOW)
        2. Violation description
        3. Recommended action
        
        Consider:
        - Legal obligations for data retention
        - Customer's current status and activity
        - Business requirements vs compliance
        - Risk level of continued storage
        
        Respond in JSON format:
        {{"severity": "HIGH/MEDIUM/LOW", "description": "detailed description", "recommended_action": "specific action to take"}}
        """
        
        try:
            # Get AI analysis
            ai_response = await self.ai_analyzer.analyze_text(prompt)
            
            # Parse AI response
            if ai_response and ai_response.strip().startswith('{'):
                analysis = json.loads(ai_response.strip())
                return {
                    'severity': analysis.get('severity', 'MEDIUM'),
                    'description': analysis.get('description', f'Customer data exceeds retention period by {analysis_context["excess_days"]} days'),
                    'recommended_action': analysis.get('recommended_action', 'Delete customer data immediately')
                }
            else:
                # Fallback analysis
                return self._fallback_violation_analysis(analysis_context)
                
        except Exception as e:
            logger.error(f"❌ AI analysis failed: {str(e)}")
            return self._fallback_violation_analysis(analysis_context)
    
    def _fallback_violation_analysis(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Fallback analysis when AI fails."""
        excess_days = context['excess_days']
        
        if excess_days > 365:  # Over 1 year excess
            severity = 'HIGH'
            description = f"Customer data severely exceeds retention period by {excess_days} days (over 1 year)"
            action = "Immediate data deletion required to comply with GDPR/PDPA"
        elif excess_days > 90:  # Over 3 months excess
            severity = 'MEDIUM'
            description = f"Customer data exceeds retention period by {excess_days} days"
            action = "Schedule data deletion within 30 days"
        else:
            severity = 'LOW'
            description = f"Customer data recently exceeded retention period by {excess_days} days"
            action = "Review and plan data deletion"
        
        return {
            'severity': severity,
            'description': description,
            'recommended_action': action
        }
    
    async def _trigger_remediation(self, violation: ComplianceViolation) -> bool:
        """
        Trigger remediation action for high-severity violations.
        
        Args:
            violation: The compliance violation to remediate
            
        Returns:
            True if remediation was successfully triggered
        """
        try:
            remediation_request = {
                "violation_id": f"CUST_{violation.customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "customer_id": violation.customer_id,
                "violation_type": violation.violation_type,
                "severity": violation.severity,
                "description": violation.description,
                "recommended_action": violation.recommended_action,
                "data_age_days": violation.data_age_days,
                "retention_limit_days": violation.retention_limit_days,
                "timestamp": datetime.now().isoformat()
            }
            
            # Enhanced logging for debugging - print the complete remediation request (controlled by configuration)
            if self._should_log_detailed_requests():
                logger.info("=" * 80)
                logger.info("🏢 CLEAN EDGP COMPLIANCE REMEDIATION REQUEST")
                logger.info("=" * 80)
                logger.info(f"🆔 Violation ID: {remediation_request['violation_id']}")
                logger.info(f"👤 Customer ID: {remediation_request['customer_id']}")
                logger.info(f"⚠️  Violation Type: {remediation_request['violation_type']}")
                logger.info(f"🚨 Severity: {remediation_request['severity']}")
                logger.info(f"📝 Description: {remediation_request['description']}")
                logger.info(f"🔧 Recommended Action: {remediation_request['recommended_action']}")
                logger.info(f"📅 Data Age: {remediation_request['data_age_days']} days")
                logger.info(f"⏰ Retention Limit: {remediation_request['retention_limit_days']} days")
                logger.info(f"🕐 Timestamp: {remediation_request['timestamp']}")
                logger.info("=" * 80)
            
            success = await self.remediation_service.trigger_remediation(remediation_request)
            
            if success:
                logger.info(f"✅ Remediation triggered for customer {violation.customer_id}")
            else:
                logger.error(f"❌ Failed to trigger remediation for customer {violation.customer_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Remediation trigger failed: {str(e)}")
            return False
    
    def _should_log_detailed_requests(self) -> bool:
        """Helper method to check if detailed request logging is enabled."""
        from config.settings import settings
        return getattr(settings, 'enable_detailed_request_logging', False)

    async def run_periodic_scan(self, interval_hours: float = 5/60) -> None:
        """
        Run compliance scanning periodically.
        
        Args:
            interval_hours: Hours between scans (default: 5 minutes = 0.083 hours)
        """
        interval_minutes = interval_hours * 60
        logger.info(f"🚀 Starting periodic compliance scanning (every {interval_minutes:.1f} minutes)")
        
        while True:
            try:
                scan_start = datetime.now()
                logger.info(f"📅 Starting compliance scan at {scan_start.strftime('%Y-%m-%d %H:%M:%S')}")
                
                violations = await self.scan_customer_compliance()
                
                scan_duration = (datetime.now() - scan_start).total_seconds()
                logger.info(f"✅ Compliance scan completed in {scan_duration:.2f} seconds")
                logger.info(f"📊 Summary: {len(violations)} violations found")
                
                # Wait for next scan
                await asyncio.sleep(interval_hours * 3600)
                
            except Exception as e:
                logger.error(f"❌ Periodic scan error: {str(e)}")
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.db_service.close()
        logger.info("🧹 Compliance agent cleaned up")

# Example usage and testing
async def main():
    """Main function for testing the compliance agent."""
    agent = CleanEDGPComplianceAgent()
    
    try:
        # Initialize
        if not await agent.initialize():
            logger.error("Failed to initialize compliance agent")
            return
        
        # Run a single scan
        logger.info("🧪 Running test compliance scan...")
        violations = await agent.scan_customer_compliance()
        
        # Print results
        print(f"\n📊 Compliance Scan Results:")
        print(f"   Total violations: {len(violations)}")
        
        for violation in violations:
            print(f"\n⚠️  Violation Details:")
            print(f"   Customer ID: {violation.customer_id}")
            print(f"   Severity: {violation.severity}")
            print(f"   Description: {violation.description}")
            print(f"   Data Age: {violation.data_age_days} days")
            print(f"   Limit: {violation.retention_limit_days} days")
            print(f"   Action: {violation.recommended_action}")
        
    except KeyboardInterrupt:
        logger.info("Scan interrupted by user")
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(main())