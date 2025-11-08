"""
Data Retention Compliance Scanner

This service scans EDGP master data for data retention compliance violations
and identifies records that exceed their retention periods.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tracers import LangChainTracer
from langchain.callbacks.base import BaseCallbackHandler

from src.compliance_agent.models.edgp_models import (
    CustomerData, LocationData, VendorData, ProductData,
    ComplianceViolationRecord, DataRetentionAnalysis,
    DataRetentionStatus, ComplianceCategory
)
from src.compliance_agent.models.compliance_models import ComplianceFramework, RiskLevel
from src.compliance_agent.services.ai_analyzer import AIComplianceAnalyzer
from src.compliance_agent.services.edgp_database_service_simple import EDGPDatabaseService

# Initialize service instance
edgp_db_service = EDGPDatabaseService()

logger = logging.getLogger(__name__)


class DataRetentionScanner:
    """Service for scanning master data for data retention compliance violations"""
    
    def __init__(self):
        # Import here to avoid circular imports
        from config.settings import settings
        from src.compliance_agent.services.ai_secrets_service import get_openai_api_key

        # Use the model specified in environment configuration
        model_name = settings.ai_model_name or "gpt-3.5-turbo"

        # Fetch API key from Secrets Manager
        api_key = get_openai_api_key()

        if not api_key:
            logger.warning("No OpenAI API key found - AI analysis will be disabled")
            self.llm = None
            self.callbacks = []
        else:
            # Check if LangSmith tracing is enabled
            langsmith_enabled = os.getenv('LANGCHAIN_TRACING_V2', '').lower() == 'true'
            
            if langsmith_enabled:
                # Initialize LangSmith tracer for compliance agent only
                langsmith_tracer = LangChainTracer(
                    project_name=os.getenv('LANGCHAIN_PROJECT', 'edgp-ai-compliance')
                )
                self.callbacks = [langsmith_tracer]
                logger.info(f"✅ LangSmith tracing enabled for Compliance Agent (Project: {os.getenv('LANGCHAIN_PROJECT', 'edgp-ai-compliance')})")
            else:
                self.callbacks = []
                logger.info("ℹ️  LangSmith tracing disabled for Compliance Agent")
            
            self.llm = ChatOpenAI(
                api_key=api_key,
                model=model_name,
                temperature=0.1,
                timeout=30,
                callbacks=self.callbacks  # Attach callbacks for selective tracing
            )
            logger.info(f"Data Retention Scanner initialized with model: {model_name}")
        
        # Default retention periods (in years)
        self.default_retention_periods = {
            "customer": 7,
            "location": 10,
            "vendor": 7,
            "product": 5
        }
        
        # Risk assessment thresholds (days overdue)
        self.risk_thresholds = {
            RiskLevel.LOW: 30,      # 1 month overdue
            RiskLevel.MEDIUM: 90,   # 3 months overdue
            RiskLevel.HIGH: 180,    # 6 months overdue
            RiskLevel.CRITICAL: 365 # 1 year overdue
        }
        
        if self.llm:
            self.analysis_prompt = self._create_analysis_prompt()
        
        logger.info("Data Retention Scanner initialized")
    
    def _create_analysis_prompt(self) -> ChatPromptTemplate:
        """Create prompt for AI-powered compliance analysis"""
        template = """
You are an expert data protection compliance analyst. Analyze the following master data record for data retention compliance violations.

RECORD INFORMATION:
Table: {table_name}
Record ID: {record_id}
Record Code: {record_code}
Created Date: {created_date}
Last Activity Date: {last_activity_date}
Record Age (days): {record_age_days}
Retention Period (years): {retention_period_years}
Days Overdue: {days_overdue}
Status: {record_status}

RECORD DATA:
{record_data}

COMPLIANCE CONTEXT:
- This is master data from an enterprise system
- Default retention periods: Customer=7yr, Vendor=7yr, Location=10yr, Product=5yr
- Consider business value, legal requirements, and data sensitivity
- GDPR/PDPA require deletion when no longer necessary

Please analyze and provide:

1. RETENTION ASSESSMENT:
   - Is this record overdue for retention review?
   - What is the appropriate retention status?
   - Consider business dependencies and legal requirements

2. RISK ANALYSIS:
   - What is the compliance risk level (low/medium/high/critical)?
   - Consider data sensitivity, regulatory exposure, business impact
   - Factor in how long overdue and type of data

3. REMEDIATION ACTIONS:
   - What specific actions should be taken?
   - Should the record be deleted, archived, or reviewed?
   - Any prerequisites before deletion (backup, notification, etc.)?

4. BUSINESS IMPACT:
   - Could deletion impact ongoing operations?
   - Are there dependencies on this record?
   - Recommended approach for handling

Respond in JSON format:
{{
    "retention_status": "compliant|warning|expired|violation",
    "risk_level": "low|medium|high|critical",
    "compliance_score": <0-100>,
    "violations_found": [
        {{
            "type": "data_retention",
            "description": "<description>",
            "severity": "low|medium|high|critical"
        }}
    ],
    "remediation_actions": [
        "<action1>", "<action2>"
    ],
    "business_impact": "low|medium|high",
    "recommended_action": "delete|archive|review|retain",
    "rationale": "<explanation>",
    "confidence": <0-1>
}}
"""
        return ChatPromptTemplate.from_template(template)
    
    async def scan_all_tables(
        self,
        tables: Optional[List[str]] = None,
        compliance_framework: ComplianceFramework = ComplianceFramework.GDPR_EU
    ) -> DataRetentionAnalysis:
        """Scan all master data tables for retention compliance"""
        
        scan_id = f"retention_scan_{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting comprehensive data retention scan: {scan_id}")
        
        # Default to all tables if none specified
        if tables is None:
            tables = ["customer", "location", "vendor", "product"]
        
        analysis = DataRetentionAnalysis(
            scan_id=scan_id,
            tables_scanned=tables,
            total_records_scanned=0,
            total_violations=0,
            violations_by_status={},
            violations_by_table={},
            violations_by_risk={},
            violations=[],
            overall_compliance_score=100.0,
            compliance_status="compliant"
        )
        
        try:
            # Initialize database service
            await edgp_db_service.initialize()
            
            # Scan each table
            for table_name in tables:
                logger.info(f"Scanning table: {table_name}")
                table_violations = await self._scan_table(table_name, compliance_framework)
                
                # Add violations to analysis
                analysis.violations.extend(table_violations)
                analysis.violations_by_table[table_name] = len(table_violations)
                
                # Update statistics
                for violation in table_violations:
                    # Count by status
                    status = violation.retention_status
                    analysis.violations_by_status[status] = analysis.violations_by_status.get(status, 0) + 1
                    
                    # Count by risk level
                    risk = violation.risk_level
                    analysis.violations_by_risk[risk] = analysis.violations_by_risk.get(risk, 0) + 1
            
            # Calculate final statistics
            analysis.total_violations = len(analysis.violations)
            analysis.records_requiring_deletion = len([
                v for v in analysis.violations 
                if v.retention_status in [DataRetentionStatus.EXPIRED, DataRetentionStatus.VIOLATION]
            ])
            analysis.records_requiring_review = len([
                v for v in analysis.violations 
                if v.retention_status == DataRetentionStatus.WARNING
            ])
            
            # Calculate compliance score
            analysis.overall_compliance_score = analysis.calculate_compliance_score()
            
            # Determine compliance status
            if analysis.overall_compliance_score >= 90:
                analysis.compliance_status = "compliant"
            elif analysis.overall_compliance_score >= 70:
                analysis.compliance_status = "warning"
            else:
                analysis.compliance_status = "non_compliant"
            
            logger.info(f"Scan completed: {analysis.total_violations} violations found")
            return analysis
            
        except Exception as e:
            logger.error(f"Error during retention scan: {str(e)}")
            raise
        finally:
            await edgp_db_service.close()
    
    async def _scan_table(
        self, 
        table_name: str,
        compliance_framework: ComplianceFramework
    ) -> List[ComplianceViolationRecord]:
        """Scan a specific table for retention violations"""
        
        violations = []
        
        try:
            # Get records that may violate retention policies
            if table_name == "customer":
                records = await edgp_db_service.get_customers_for_retention_check()
                violations = await self._analyze_customer_records(records, compliance_framework)
                
            elif table_name == "location":
                records = await edgp_db_service.get_locations_for_retention_check()
                violations = await self._analyze_location_records(records, compliance_framework)
                
            elif table_name == "vendor":
                records = await edgp_db_service.get_vendors_for_retention_check()
                violations = await self._analyze_vendor_records(records, compliance_framework)
                
            elif table_name == "product":
                records = await edgp_db_service.get_products_for_retention_check()
                violations = await self._analyze_product_records(records, compliance_framework)
            
            else:
                logger.warning(f"Unknown table name: {table_name}")
            
            logger.info(f"Found {len(violations)} violations in table {table_name}")
            return violations
            
        except Exception as e:
            logger.error(f"Error scanning table {table_name}: {str(e)}")
            return []
    
    async def _analyze_customer_records(
        self, 
        customers: List[CustomerData],
        compliance_framework: ComplianceFramework
    ) -> List[ComplianceViolationRecord]:
        """Analyze customer records for retention violations"""
        
        violations = []
        
        for customer in customers:
            try:
                # Create a customer name from firstname/lastname
                customer_name = f"{customer.firstname or ''} {customer.lastname or ''}".strip()
                if not customer_name:
                    customer_name = f"Customer ID {customer.id}"
                
                violation = await self._analyze_record_retention(
                    table_name="customer",
                    record_id=customer.id,
                    record_code=customer.file_id or f"CUST_{customer.id}",  # Use file_id or generate
                    created_date=customer.created_date,
                    last_activity_date=customer.updated_date,
                    retention_period_years=customer.retention_period_years,
                    record_data={
                        "customer_name": customer_name,
                        "firstname": customer.firstname,
                        "lastname": customer.lastname,
                        "email": customer.email,
                        "country": customer.country,
                        "domain_name": customer.domain_name,
                        "is_archived": customer.is_archived
                    },
                    compliance_framework=compliance_framework
                )
                
                if violation:
                    violations.append(violation)
                    
                # Note: Skip timestamp update since we don't have that column in actual schema
                # await edgp_db_service.update_compliance_check_timestamp("customer", customer.id)
                
            except Exception as e:
                logger.error(f"Error analyzing customer {customer.firstname} {customer.lastname} (ID: {customer.id}): {str(e)}")
                continue
        
        return violations
    
    async def _analyze_location_records(
        self, 
        locations: List[LocationData],
        compliance_framework: ComplianceFramework
    ) -> List[ComplianceViolationRecord]:
        """Analyze location records for retention violations"""
        
        violations = []
        
        for location in locations:
            try:
                violation = await self._analyze_record_retention(
                    table_name="location",
                    record_id=location.id,
                    record_code=location.location_code,
                    created_date=location.created_at,
                    last_activity_date=location.updated_at,
                    retention_period_years=location.retention_period_years,
                    record_data={
                        "location_name": location.location_name,
                        "location_type": location.location_type,
                        "status": location.status,
                        "country": location.country,
                        "city": location.city
                    },
                    compliance_framework=compliance_framework
                )
                
                if violation:
                    violations.append(violation)
                    
                # Update compliance check timestamp
                await edgp_db_service.update_compliance_check_timestamp("location", location.id)
                
            except Exception as e:
                logger.error(f"Error analyzing location {location.location_code}: {str(e)}")
                continue
        
        return violations
    
    async def _analyze_vendor_records(
        self, 
        vendors: List[VendorData],
        compliance_framework: ComplianceFramework
    ) -> List[ComplianceViolationRecord]:
        """Analyze vendor records for retention violations"""
        
        violations = []
        
        for vendor in vendors:
            try:
                # Use contract end date if available, otherwise use last transaction date
                last_activity = vendor.contract_end_date or vendor.last_transaction_date or vendor.updated_at
                
                violation = await self._analyze_record_retention(
                    table_name="vendor",
                    record_id=vendor.id,
                    record_code=vendor.vendor_code,
                    created_date=vendor.created_at,
                    last_activity_date=last_activity,
                    retention_period_years=vendor.retention_period_years,
                    record_data={
                        "vendor_name": vendor.vendor_name,
                        "vendor_type": vendor.vendor_type,
                        "status": vendor.status,
                        "country": vendor.country,
                        "contract_end_date": vendor.contract_end_date.isoformat() if vendor.contract_end_date else None
                    },
                    compliance_framework=compliance_framework
                )
                
                if violation:
                    violations.append(violation)
                    
                # Update compliance check timestamp
                await edgp_db_service.update_compliance_check_timestamp("vendor", vendor.id)
                
            except Exception as e:
                logger.error(f"Error analyzing vendor {vendor.vendor_code}: {str(e)}")
                continue
        
        return violations
    
    async def _analyze_product_records(
        self, 
        products: List[ProductData],
        compliance_framework: ComplianceFramework
    ) -> List[ComplianceViolationRecord]:
        """Analyze product records for retention violations"""
        
        violations = []
        
        for product in products:
            try:
                violation = await self._analyze_record_retention(
                    table_name="product",
                    record_id=product.id,
                    record_code=product.product_code,
                    created_date=product.created_at,
                    last_activity_date=product.updated_at,
                    retention_period_years=product.retention_period_years,
                    record_data={
                        "product_name": product.product_name,
                        "category": product.category,
                        "status": product.status,
                        "description": product.description
                    },
                    compliance_framework=compliance_framework
                )
                
                if violation:
                    violations.append(violation)
                    
                # Update compliance check timestamp
                await edgp_db_service.update_compliance_check_timestamp("product", product.id)
                
            except Exception as e:
                logger.error(f"Error analyzing product {product.product_code}: {str(e)}")
                continue
        
        return violations
    
    async def _analyze_record_retention(
        self,
        table_name: str,
        record_id: int,
        record_code: str,
        created_date: datetime,
        last_activity_date: datetime,
        retention_period_years: int,
        record_data: Dict[str, Any],
        compliance_framework: ComplianceFramework
    ) -> Optional[ComplianceViolationRecord]:
        """Analyze a single record for retention compliance using AI"""
        
        try:
            # Calculate retention dates
            current_date = datetime.utcnow()
            record_age_days = (current_date - created_date).days
            retention_cutoff_date = created_date + timedelta(days=retention_period_years * 365)
            days_overdue = (current_date - retention_cutoff_date).days
            
            # Quick check - if not overdue, no violation
            if days_overdue <= 0:
                return None
            
            # Prepare data for AI analysis
            prompt_vars = {
                "table_name": table_name,
                "record_id": record_id,
                "record_code": record_code,
                "created_date": created_date.isoformat(),
                "last_activity_date": last_activity_date.isoformat(),
                "record_age_days": record_age_days,
                "retention_period_years": retention_period_years,
                "days_overdue": days_overdue,
                "record_status": record_data.get("status", "unknown"),
                "record_data": str(record_data)
            }
            
            # Get AI analysis if available
            if self.llm:
                # Debug: Log callback status
                if self.callbacks:
                    logger.info(f"🔍 LangSmith: Tracing LLM call for {record_code} (callbacks: {len(self.callbacks)})")
                
                # Pass callbacks explicitly to ensure LangSmith tracing
                response = await self.llm.ainvoke(
                    self.analysis_prompt.format(**prompt_vars),
                    config={"callbacks": self.callbacks} if self.callbacks else None
                )
                
                # Parse AI response
                analysis_result = self._parse_ai_response(response.content)
                
                # Determine retention status and risk level from AI
                retention_status = self._map_retention_status(analysis_result.get("retention_status", "violation"))
                risk_level = self._map_risk_level(analysis_result.get("risk_level", "medium"), days_overdue)
                remediation_actions = analysis_result.get("remediation_actions", ["Review and delete if appropriate"])
                ai_analysis_summary = analysis_result.get("summary", "AI analysis completed")
            else:
                # Fallback analysis without AI
                logger.info(f"AI not available - using rule-based analysis for {record_code}")
                
                # Simple rule-based analysis
                if days_overdue > 365:
                    retention_status = DataRetentionStatus.VIOLATION
                    risk_level = RiskLevel.HIGH
                elif days_overdue > 180:
                    retention_status = DataRetentionStatus.EXPIRED
                    risk_level = RiskLevel.MEDIUM
                else:
                    retention_status = DataRetentionStatus.REVIEW_REQUIRED
                    risk_level = RiskLevel.LOW
                
                remediation_actions = ["Review record for deletion", "Verify business need", "Delete if no longer required"]
                ai_analysis_summary = f"Rule-based analysis: {days_overdue} days overdue, automatic classification"
            
            # Create violation record
            violation = ComplianceViolationRecord(
                table_name=table_name,
                record_id=record_id,
                record_code=record_code,
                violation_type=ComplianceCategory.DATA_RETENTION,
                retention_status=retention_status,
                retention_period_years=retention_period_years,
                record_age_days=record_age_days,
                days_overdue=days_overdue,
                risk_level=risk_level,
                compliance_framework=compliance_framework,
                record_data=record_data,
                remediation_required=True,
                remediation_actions=remediation_actions
            )
            
            # Add AI analysis summary as an attribute for testing
            violation.ai_analysis_summary = ai_analysis_summary
            violation.recommended_action = remediation_actions[0] if remediation_actions else "Review record"
            
            logger.debug(f"Found retention violation: {table_name}:{record_code} ({days_overdue} days overdue)")
            return violation
            
        except Exception as e:
            logger.error(f"Error analyzing retention for {table_name}:{record_code}: {str(e)}")
            # Create fallback violation record
            return self._create_fallback_violation(
                table_name, record_id, record_code, record_age_days, 
                days_overdue, retention_period_years, record_data, compliance_framework
            )
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse AI analysis response"""
        import json
        
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
            else:
                json_str = response.strip()
            
            return json.loads(json_str)
            
        except Exception as e:
            logger.warning(f"Failed to parse AI response: {str(e)}")
            # Return fallback response
            return {
                "retention_status": "violation",
                "risk_level": "medium",
                "remediation_actions": ["Manual review required", "Consider deletion"],
                "confidence": 0.5
            }
    
    def _map_retention_status(self, ai_status: str) -> DataRetentionStatus:
        """Map AI response to retention status enum"""
        mapping = {
            "compliant": DataRetentionStatus.COMPLIANT,
            "warning": DataRetentionStatus.WARNING,
            "expired": DataRetentionStatus.EXPIRED,
            "violation": DataRetentionStatus.VIOLATION
        }
        return mapping.get(ai_status.lower(), DataRetentionStatus.VIOLATION)
    
    def _map_risk_level(self, ai_risk: str, days_overdue: int) -> RiskLevel:
        """Map AI response and days overdue to risk level"""
        # Use AI assessment as base, but override based on severity
        if days_overdue >= self.risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif days_overdue >= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif days_overdue >= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _create_fallback_violation(
        self,
        table_name: str,
        record_id: int,
        record_code: str,
        record_age_days: int,
        days_overdue: int,
        retention_period_years: int,
        record_data: Dict[str, Any],
        compliance_framework: ComplianceFramework
    ) -> ComplianceViolationRecord:
        """Create fallback violation when AI analysis fails"""
        
        # Determine risk based on days overdue
        if days_overdue >= 365:
            risk_level = RiskLevel.CRITICAL
            retention_status = DataRetentionStatus.VIOLATION
        elif days_overdue >= 180:
            risk_level = RiskLevel.HIGH
            retention_status = DataRetentionStatus.EXPIRED
        elif days_overdue >= 90:
            risk_level = RiskLevel.MEDIUM
            retention_status = DataRetentionStatus.EXPIRED
        else:
            risk_level = RiskLevel.LOW
            retention_status = DataRetentionStatus.WARNING
        
        violation = ComplianceViolationRecord(
            table_name=table_name,
            record_id=record_id,
            record_code=record_code,
            violation_type=ComplianceCategory.DATA_RETENTION,
            retention_status=retention_status,
            retention_period_years=retention_period_years,
            record_age_days=record_age_days,
            days_overdue=days_overdue,
            risk_level=risk_level,
            compliance_framework=compliance_framework,
            record_data=record_data,
            remediation_required=True,
            remediation_actions=[
                "Review retention policy compliance",
                "Consider data deletion if no business need",
                "Backup data before deletion if required"
            ]
        )
        
        # Add analysis summary for consistency
        violation.ai_analysis_summary = f"Fallback analysis: {days_overdue} days overdue, risk level {risk_level.value}"
        violation.recommended_action = "Review retention policy compliance"
        
        return violation
    
    async def scan_customer_data_retention(
        self,
        edgp_db_service,
        compliance_framework: ComplianceFramework = ComplianceFramework.GDPR_EU,
        retention_period_years: int = 7
    ) -> List[ComplianceViolationRecord]:
        """Scan customer table for data retention compliance violations"""
        
        logger.info(f"Starting customer data retention scan with {retention_period_years} year retention")
        
        try:
            # Get customers that need retention check
            customers = await edgp_db_service.get_customers_for_retention_check(retention_period_years)
            logger.info(f"Found {len(customers)} customers to analyze for retention compliance")
            
            # Analyze each customer
            violations = await self._analyze_customer_records(customers, compliance_framework)
            
            logger.info(f"Customer retention scan completed - found {len(violations)} violations")
            return violations
            
        except Exception as e:
            logger.error(f"Error during customer retention scan: {e}")
            raise