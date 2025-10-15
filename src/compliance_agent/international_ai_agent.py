#!/usr/bin/env python3
"""
International AI Compliance Agent for PDPA/GDPR Data Governance
Singapore-hosted Master Data Governance Application

Enhanced with OpenSearch integration for international compliance pattern matching
while maintaining clean, focused architecture for customer data retention compliance.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass
import hashlib

# from opensearch_py import OpenSearch, RequestsHttpConnection
# from requests_aws4auth import AWS4Auth
import openai
from dotenv import load_dotenv
import os

from src.compliance_agent.services.edgp_database_service_simple import EDGPDatabaseService
from src.compliance_agent.services.ai_analyzer import AIComplianceAnalyzer
from src.compliance_agent.services.remediation_integration_service import ComplianceRemediationService

# JSON-based compliance pattern loading
import json
from pathlib import Path

# Configure PII-protected logging
import structlog

# Load environment variables
load_dotenv('.env.development')

# Configure structured logging with PII protection
def mask_pii_processor(logger, method_name, event_dict):
    """Processor to mask PII data in logs."""
    event_dict = event_dict.copy()
    
    # Mask common PII fields
    pii_fields = ['email', 'phone', 'firstname', 'lastname', 'address', 'customer_name']
    for field in pii_fields:
        if field in event_dict:
            if event_dict[field]:
                # Keep only first 2 chars + mask
                value = str(event_dict[field])
                event_dict[field] = value[:2] + "***" if len(value) > 2 else "***"
    
    # Mask customer IDs to protect identity while keeping trackability
    if 'customer_id' in event_dict:
        customer_id = event_dict['customer_id']
        # Create a hash for tracking without exposing real ID
        hash_object = hashlib.md5(str(customer_id).encode())
        event_dict['customer_hash'] = hash_object.hexdigest()[:8]
        del event_dict['customer_id']
    
    return event_dict

structlog.configure(
    processors=[
        mask_pii_processor,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

@dataclass
class InternationalComplianceViolation:
    """Enhanced compliance violation with international framework support."""
    customer_hash: str  # Masked customer ID for PII protection
    violation_type: str
    framework: str  # PDPA, GDPR
    severity: str  # HIGH, MEDIUM, LOW
    description: str
    data_age_days: int
    retention_limit_days: int
    recommended_action: str
    matching_patterns: List[Dict[str, Any]]
    confidence_score: float
    region: str  # Singapore, EU
    raw_data_summary: Dict[str, Any]  # Non-PII summary only

class InternationalAIComplianceAgent:
    """
    AI Compliance Agent for International PDPA/GDPR Data Governance
    
    Core functionality:
    1. Periodic customer data retrieval from EDGP database
    2. AI analysis with international compliance patterns (PDPA/GDPR)
    3. OpenSearch-powered pattern matching for accurate compliance detection
    4. Automatic remediation triggering for violations
    5. PII-protected logging for Singapore-hosted application
    6. Async operation without user interaction
    """
    
    def __init__(self):
        # Core services
        self.db_service = EDGPDatabaseService()
        self.ai_analyzer = AIComplianceAnalyzer()
        self.remediation_service = ComplianceRemediationService()
        
        # OpenSearch configuration for compliance patterns
        self._setup_opensearch()
        
        # International compliance configuration
        self.compliance_frameworks = {
            'singapore': {
                'framework': 'PDPA',
                'region': 'APAC',
                'default_retention_years': 7,
                'inactive_retention_years': 3,
                'deletion_grace_days': 30
            },
            'international': {
                'framework': 'GDPR',
                'region': 'EU',
                'default_retention_years': 7,
                'inactive_retention_years': 3,
                'deletion_grace_days': 30
            }
        }
        
        # Data retention limits (in days) - Singapore PDPA compliance
        self.retention_limits = {
            'customer_default': 7 * 365,  # 7 years
            'inactive_customer': 3 * 365,  # 3 years for inactive
            'deleted_customer': 30,       # 30 days after deletion request
        }
        
        # Compliance patterns loaded from JSON files
        self.compliance_patterns = {
            'PDPA': [],
            'GDPR': []
        }
    
    async def load_compliance_patterns(self) -> bool:
        """Load compliance patterns from PDPA.json and GDPR.json files."""
        try:
            # Get the path to compliance info directory
            current_dir = Path(__file__).parent
            compliance_dir = current_dir / "compliancesInfo"
            
            # Load PDPA patterns
            pdpa_file = compliance_dir / "PDPA.json"
            if pdpa_file.exists():
                with open(pdpa_file, 'r', encoding='utf-8') as f:
                    self.compliance_patterns['PDPA'] = json.load(f)
                logger.info("Loaded PDPA compliance patterns", 
                           pattern_count=len(self.compliance_patterns['PDPA']))
            else:
                logger.warning("PDPA.json not found", file_path=str(pdpa_file))
            
            # Load GDPR patterns
            gdpr_file = compliance_dir / "GDPR.json"
            if gdpr_file.exists():
                with open(gdpr_file, 'r', encoding='utf-8') as f:
                    self.compliance_patterns['GDPR'] = json.load(f)
                logger.info("Loaded GDPR compliance patterns", 
                           pattern_count=len(self.compliance_patterns['GDPR']))
            else:
                logger.warning("GDPR.json not found", file_path=str(gdpr_file))
            
            total_patterns = len(self.compliance_patterns['PDPA']) + len(self.compliance_patterns['GDPR'])
            logger.info("Successfully loaded compliance patterns", 
                       total_patterns=total_patterns,
                       pdpa_patterns=len(self.compliance_patterns['PDPA']),
                       gdpr_patterns=len(self.compliance_patterns['GDPR']))
            return True
            
        except Exception as e:
            logger.error("Failed to load compliance patterns", error=str(e))
            return False
    
    def _setup_opensearch(self):
        """Setup OpenSearch connection for compliance pattern matching."""
        try:
            # Temporarily disabled OpenSearch due to import issues
            # AWS credentials would be loaded here
            self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            self.aws_region = os.getenv('AWS_REGION', 'ap-southeast-1')
            
            # OpenSearch settings would be configured here
            self.opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT')
            self.compliance_index = 'international-compliance-patterns'
            
            # Disable OpenSearch for now until dependencies are resolved
            self.opensearch_enabled = False
            logger.warning("OpenSearch temporarily disabled - using basic compliance checking")
                
        except Exception as e:
            logger.error("Failed to setup OpenSearch", error=str(e))
            self.opensearch_enabled = False
    
    async def initialize(self) -> bool:
        """Initialize all services."""
        try:
            await self.db_service.initialize()
            
            # Load compliance patterns from JSON files
            await self.load_compliance_patterns()
            
            logger.info("International AI Compliance Agent initialized", 
                       frameworks=list(self.compliance_frameworks.keys()),
                       opensearch_enabled=self.opensearch_enabled,
                       compliance_patterns_loaded=True)
            return True
        except Exception as e:
            logger.error("Failed to initialize compliance agent", error=str(e))
            return False
    
    async def scan_customer_compliance(self) -> List[InternationalComplianceViolation]:
        """
        Main compliance scanning function with international framework support.
        
        Returns:
            List of international compliance violations found
        """
        violations = []
        
        try:
            logger.info("Starting international customer data compliance scan",
                       scan_type="data_retention",
                       frameworks=["PDPA", "GDPR"])
            
            # 1. Read all customer data from database
            customers = await self.db_service.get_customers()
            logger.info("Retrieved customer records for analysis", 
                       record_count=len(customers),
                       data_governance_scope="customer_retention")
            
            # 2. Analyze each customer for international compliance violations
            for customer in customers:
                violation = await self._analyze_international_compliance(customer)
                if violation:
                    violations.append(violation)
            
            logger.info("International compliance scan completed", 
                       violations_found=len(violations),
                       high_severity_count=sum(1 for v in violations if v.severity == 'HIGH'))
            
            # 3. Trigger remediation for high-severity violations
            remediation_triggered = 0
            for violation in violations:
                if violation.severity == 'HIGH':
                    success = await self._trigger_international_remediation(violation)
                    if success:
                        remediation_triggered += 1
            
            logger.info("Remediation processing completed",
                       remediation_triggered=remediation_triggered,
                       total_violations=len(violations))
            
            return violations
            
        except Exception as e:
            logger.error("International compliance scan failed", error=str(e))
            return []
    
    async def _analyze_international_compliance(self, customer) -> Optional[InternationalComplianceViolation]:
        """
        Analyze customer record against international compliance frameworks (PDPA/GDPR).
        
        Args:
            customer: CustomerData object from database
            
        Returns:
            InternationalComplianceViolation if violation found, None otherwise
        """
        try:
            # Calculate data age
            created_date = customer.created_date
            last_activity = customer.updated_date
            
            if not created_date:
                return None
            
            data_age = (datetime.now() - created_date).days
            last_activity_age = (datetime.now() - last_activity).days if last_activity else data_age
            
            # Determine applicable retention limit
            retention_limit = self._get_retention_limit(customer, last_activity_age)
            
            # Check if data exceeds retention period
            if data_age > retention_limit:
                # Enhanced analysis with international compliance patterns
                analysis_result = await self._get_international_compliance_analysis(
                    customer, data_age, retention_limit
                )
                
                # Create masked customer hash for tracking
                customer_hash = hashlib.md5(str(customer.id).encode()).hexdigest()[:8]
                
                violation = InternationalComplianceViolation(
                    customer_hash=customer_hash,
                    violation_type='DATA_RETENTION_EXCEEDED',
                    framework=analysis_result['framework'],
                    severity=analysis_result['severity'],
                    description=analysis_result['description'],
                    data_age_days=data_age,
                    retention_limit_days=retention_limit,
                    recommended_action=analysis_result['recommended_action'],
                    matching_patterns=analysis_result.get('matching_patterns', []),
                    confidence_score=analysis_result.get('confidence_score', 0.0),
                    region=analysis_result.get('region', 'Singapore'),
                    raw_data_summary={
                        'has_email': bool(customer.email),
                        'has_phone': bool(customer.phone),
                        'is_archived': customer.is_archived,
                        'domain': customer.domain_name,
                        'data_age_days': data_age
                    }
                )
                
                logger.warning("International compliance violation detected",
                             customer_hash=customer_hash,
                             framework=violation.framework,
                             severity=violation.severity,
                             excess_days=data_age - retention_limit,
                             confidence=violation.confidence_score)
                
                return violation
            
            return None
            
        except Exception as e:
            logger.error("Failed to analyze customer compliance", 
                        error=str(e),
                        analysis_type="international_framework")
            return None
    
    async def _get_international_compliance_analysis(self, customer, data_age: int, retention_limit: int) -> Dict[str, Any]:
        """
        Enhanced compliance analysis using international patterns from OpenSearch.
        
        Args:
            customer: CustomerData object
            data_age: Age of customer data in days
            retention_limit: Applicable retention limit in days
            
        Returns:
            Analysis result with framework, severity, patterns, and recommendations
        """
        
        # Prepare context for analysis
        analysis_context = {
            "data_age_days": data_age,
            "retention_limit_days": retention_limit,
            "excess_days": data_age - retention_limit,
            "is_archived": customer.is_archived,
            "last_activity": customer.updated_date,
            "has_contact_info": bool(customer.email or customer.phone),
            "application_region": "Singapore"
        }
        
        # Try JSON pattern matching first
        json_analysis = await self._get_json_pattern_analysis(analysis_context)
        if json_analysis:
            return json_analysis
        
        # Fallback to basic analysis
        return self._get_basic_compliance_analysis(analysis_context)
    
    async def _get_json_pattern_analysis(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use JSON compliance patterns to analyze violations."""
        try:
            excess_days = context['excess_days']
            
            # Search for relevant patterns in loaded JSON data
            relevant_patterns = self._find_relevant_patterns(context)
            
            if not relevant_patterns:
                return None
            
            # Determine framework (PDPA for Singapore-hosted application)
            framework = "PDPA"
            region = "Singapore"
            
            # Check for international applicability
            if context.get('international_data', False):
                framework = "GDPR"
                region = "International"
            
            # Determine severity based on patterns and excess days
            severity = self._calculate_pattern_severity(context, relevant_patterns)
            
            # Generate AI-enhanced description using patterns
            description = await self._generate_pattern_description(context, relevant_patterns, framework)
            
            return {
                'framework': framework,
                'region': region,
                'severity': severity,
                'description': description,
                'matching_patterns': relevant_patterns,
                'confidence_score': 0.8,  # High confidence for JSON pattern matching
                'recommended_action': f"Delete customer data immediately - exceeds {framework} retention requirements by {excess_days} days"
            }
            
        except Exception as e:
            logger.error("JSON pattern analysis failed", error=str(e))
            return None
    
    def _find_relevant_patterns(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find relevant compliance patterns from loaded JSON data."""
        relevant_patterns = []
        
        # Keywords to search for in patterns
        retention_keywords = ["retention", "storage", "kept", "period", "data protection", "personal data"]
        
        # Search PDPA patterns
        for pattern in self.compliance_patterns['PDPA']:
            content_lower = pattern.get('content', '').lower()
            title_lower = pattern.get('title', '').lower()
            
            if any(keyword in content_lower or keyword in title_lower for keyword in retention_keywords):
                relevant_patterns.append({
                    'id': pattern.get('id'),
                    'title': pattern.get('title'),
                    'content': pattern.get('content'),
                    'category': pattern.get('category'),
                    'framework': 'PDPA'
                })
        
        # Search GDPR patterns
        for pattern in self.compliance_patterns['GDPR']:
            content_lower = pattern.get('content', '').lower()
            title_lower = pattern.get('title', '').lower()
            
            if any(keyword in content_lower or keyword in title_lower for keyword in retention_keywords):
                relevant_patterns.append({
                    'id': pattern.get('id'),
                    'title': pattern.get('title'),
                    'content': pattern.get('content'),
                    'category': pattern.get('category'),
                    'framework': 'GDPR'
                })
        
        return relevant_patterns[:5]  # Return top 5 relevant patterns
    
    def _calculate_pattern_severity(self, context: Dict[str, Any], patterns: List[Dict[str, Any]]) -> str:
        """Calculate severity based on patterns and context."""
        excess_days = context['excess_days']
        
        # Base severity on excess days
        if excess_days > 365:  # Over 1 year excess
            return 'HIGH'
        elif excess_days > 90:  # Over 3 months excess
            return 'MEDIUM'
        else:
            return 'LOW'
    
    async def _generate_pattern_description(self, context: Dict[str, Any], patterns: List[Dict[str, Any]], framework: str) -> str:
        """Generate AI-enhanced description using compliance patterns."""
        try:
            # Create prompt with compliance patterns
            pattern_context = "\n".join([
                f"- {p['title']}: {p['content'][:200]}..." 
                for p in patterns[:3]  # Use top 3 patterns
            ])
            
            prompt = f"""
Based on {framework} compliance requirements, analyze this data retention violation:

Relevant Compliance Patterns:
{pattern_context}

Violation Context:
- Data age: {context['data_age_days']} days
- Retention limit: {context['retention_limit_days']} days
- Excess period: {context['excess_days']} days
- Customer archived: {context['is_archived']}
- Singapore region: {context['application_region']}

Provide a concise compliance violation description in 1-2 sentences.
"""
            
            # Use AI analyzer to generate description
            description = await self.ai_analyzer.analyze_text(prompt)
            
            if description and len(description.strip()) > 10:
                return description.strip()
            else:
                # Fallback description
                return f"Customer data exceeds {framework} retention period by {context['excess_days']} days, violating data protection requirements"
                
        except Exception as e:
            logger.error("Failed to generate pattern description", error=str(e))
            return f"Customer data exceeds {framework} retention period by {context['excess_days']} days"
    
    async def _get_opensearch_pattern_analysis(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use OpenSearch to find matching compliance patterns."""
        try:
            # Create search query based on violation context
            search_text = f"data retention customer information {context['excess_days']} days exceeded limit"
            
            # Generate embedding for search
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=search_text,
                encoding_format="float"
            )
            query_embedding = response.data[0].embedding
            
            # Vector search for matching patterns
            search_query = {
                "size": 3,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": query_embedding,
                                        "k": 3
                                    }
                                }
                            }
                        ],
                        "filter": [
                            {"terms": {"framework": ["PDPA", "GDPR"]}},
                            {"terms": {"data_types": ["customer_data", "personal_data"]}}
                        ]
                    }
                },
                "_source": ["compliance_id", "framework", "title", "risk_level", 
                           "remediation_actions", "violation_patterns", "region"]
            }
            
            response = self.opensearch_client.search(
                index=self.compliance_index,
                body=search_query
            )
            
            hits = response['hits']['hits']
            if not hits:
                return None
            
            # Analyze matching patterns
            best_match = hits[0]['_source']
            confidence_score = hits[0]['_score']
            
            # Determine framework preference (PDPA for Singapore)
            framework = "PDPA"  # Default for Singapore-hosted application
            region = "Singapore"
            
            # Check if GDPR patterns have higher confidence
            for hit in hits:
                if hit['_source']['framework'] == 'GDPR' and hit['_score'] > confidence_score * 1.2:
                    framework = "GDPR"
                    region = "International"
                    break
            
            # Determine severity based on pattern analysis and excess days
            severity = self._calculate_severity(context, best_match)
            
            return {
                'framework': framework,
                'region': region,
                'severity': severity,
                'description': f"{framework} compliance violation: {best_match.get('violation_patterns', 'Data retention period exceeded')}",
                'recommended_action': best_match.get('remediation_actions', 'Delete expired customer data'),
                'matching_patterns': [hit['_source'] for hit in hits],
                'confidence_score': confidence_score
            }
            
        except Exception as e:
            logger.error("OpenSearch pattern analysis failed", error=str(e))
            return None
    
    def _calculate_severity(self, context: Dict[str, Any], pattern: Dict[str, Any]) -> str:
        """Calculate violation severity based on context and pattern."""
        excess_days = context['excess_days']
        pattern_risk = pattern.get('risk_level', 'MEDIUM')
        
        # High severity conditions
        if excess_days > 365 or pattern_risk == 'HIGH':  # Over 1 year excess or high-risk pattern
            return 'HIGH'
        elif excess_days > 90 or pattern_risk == 'MEDIUM':  # Over 3 months excess
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _get_basic_compliance_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis when OpenSearch is not available."""
        excess_days = context['excess_days']
        
        if excess_days > 365:  # Over 1 year excess
            severity = 'HIGH'
            description = "PDPA violation: Customer data severely exceeds retention period"
            action = "Immediate data deletion required for PDPA compliance"
        elif excess_days > 90:  # Over 3 months excess
            severity = 'MEDIUM'
            description = "PDPA violation: Customer data exceeds retention period"
            action = "Schedule data deletion within 30 days"
        else:
            severity = 'LOW'
            description = "PDPA violation: Customer data recently exceeded retention period"
            action = "Review and plan data deletion"
        
        return {
            'framework': 'PDPA',
            'region': 'Singapore',
            'severity': severity,
            'description': description,
            'recommended_action': action,
            'matching_patterns': [],
            'confidence_score': 0.7  # Basic confidence
        }
    
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
    
    async def _trigger_international_remediation(self, violation: InternationalComplianceViolation) -> bool:
        """
        Trigger remediation action for international compliance violations.
        
        Args:
            violation: The international compliance violation to remediate
            
        Returns:
            True if remediation was successfully triggered
        """
        try:
            remediation_request = {
                "violation_id": f"INTL_{violation.customer_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "customer_hash": violation.customer_hash,  # Masked ID
                "violation_type": violation.violation_type,
                "framework": violation.framework,
                "region": violation.region,
                "severity": violation.severity,
                "description": violation.description,
                "recommended_action": violation.recommended_action,
                "data_age_days": violation.data_age_days,
                "retention_limit_days": violation.retention_limit_days,
                "confidence_score": violation.confidence_score,
                "matching_patterns_count": len(violation.matching_patterns),
                "timestamp": datetime.now().isoformat()
            }
            
            success = await self.remediation_service.trigger_remediation(remediation_request)
            
            if success:
                logger.info("International remediation triggered successfully",
                           customer_hash=violation.customer_hash,
                           framework=violation.framework,
                           severity=violation.severity)
            else:
                logger.error("Failed to trigger international remediation",
                            customer_hash=violation.customer_hash,
                            framework=violation.framework)
            
            return success
            
        except Exception as e:
            logger.error("International remediation trigger failed", 
                        error=str(e),
                        customer_hash=violation.customer_hash)
            return False
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.db_service.close()
        logger.info("International AI compliance agent cleaned up")

# Example usage and testing
async def main():
    """Main function for testing the international compliance agent."""
    agent = InternationalAIComplianceAgent()
    
    try:
        # Initialize
        if not await agent.initialize():
            logger.error("Failed to initialize international compliance agent")
            return
        
        # Run a single scan
        logger.info("Running international compliance scan")
        violations = await agent.scan_customer_compliance()
        
        # Print results
        print(f"\n🌍 International Compliance Scan Results:")
        print(f"   Total violations: {len(violations)}")
        
        for violation in violations:
            print(f"\n⚠️  {violation.framework} Violation Details:")
            print(f"   Customer Hash: {violation.customer_hash}")
            print(f"   Framework: {violation.framework} ({violation.region})")
            print(f"   Severity: {violation.severity}")
            print(f"   Description: {violation.description}")
            print(f"   Data Age: {violation.data_age_days} days")
            print(f"   Limit: {violation.retention_limit_days} days")
            print(f"   Confidence: {violation.confidence_score:.2f}")
            print(f"   Action: {violation.recommended_action}")
        
    except KeyboardInterrupt:
        logger.info("Scan interrupted by user")
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(main())