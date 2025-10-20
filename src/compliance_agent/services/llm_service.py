"""
LLM Service for Compliance Analysis
Provides AI-powered compliance suggestions and analysis using OpenAI GPT models.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
import openai
from ..utils.logger import get_logger
from .ai_secrets_service import get_openai_api_key

logger = get_logger(__name__)


class LLMComplianceService:
    """
    Service for generating compliance suggestions using Large Language Models
    """
    
    def __init__(self):
        self.client = None
        self.model_name = "gpt-3.5-turbo"
        self.temperature = 0.1
        self.max_tokens = 500
        self.is_initialized = False
    
    async def initialize(self, secret_name: Optional[str] = None) -> bool:
        """
        Initialize the LLM service with OpenAI API key
        
        Args:
            secret_name: AWS Secrets Manager secret name for API key
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            print(f"🔑 LLM Service: Getting API key from secret: {secret_name}")
            # Get API key from AWS Secrets Manager or environment
            api_key = get_openai_api_key(secret_name)
            
            if not api_key:
                logger.warning("No OpenAI API key found - LLM suggestions will be disabled")
                print("⚠️ No OpenAI API key found - LLM suggestions will be disabled")
                return False
            
            # Initialize OpenAI client
            openai.api_key = api_key
            self.client = openai
            self.is_initialized = True
            
            logger.info("LLM Compliance Service initialized successfully")
            logger.info(f"Model: {self.model_name}, Temperature: {self.temperature}")
            print(f"✅ LLM Service initialized with model: {self.model_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {str(e)}")
            print(f"❌ Failed to initialize LLM service: {str(e)}")
            self.is_initialized = False
            return False
    
    async def generate_compliance_suggestion(
        self, 
        violation_data: Dict[str, Any], 
        framework: str = "PDPA"
    ) -> Dict[str, str]:
        """
        Generate AI-powered compliance suggestion for a violation
        
        Args:
            violation_data: Dictionary containing violation details
            framework: Compliance framework (PDPA, GDPR, etc.)
            
        Returns:
            Dictionary with description, recommendation, and legal_reference
        """
        if not self.is_initialized:
            logger.warning("LLM service not initialized - using fallback suggestions")
            return self._get_fallback_suggestion(violation_data, framework)
        
        try:
            # Create detailed prompt for compliance analysis
            prompt = self._create_compliance_prompt(violation_data, framework)
            
            # Generate response using OpenAI
            response = await self._call_openai_chat(prompt)
            
            # Log the raw LLM response for debugging
            logger.info("🔍 RAW LLM RESPONSE")
            logger.info("-" * 40)
            logger.info(response)
            logger.info("-" * 40)
            
            # Parse the response
            suggestion = self._parse_llm_response(response)
            
            # Log the detailed LLM suggestions
            logger.info("🤖 LLM COMPLIANCE SUGGESTION GENERATED")
            logger.info("=" * 60)
            logger.info(f"🆔 Customer ID: {violation_data.get('customer_id', 'Unknown')}")
            logger.info(f"⚖️  Framework: {framework}")
            logger.info(f"📝 AI Description: {suggestion.get('description', 'N/A')}")
            logger.info(f"🔧 AI Recommendation: {suggestion.get('recommendation', 'N/A')}")
            logger.info(f"📚 Legal Reference: {suggestion.get('legal_reference', 'N/A')}")
            logger.info(f"⚡ Urgency Level: {suggestion.get('urgency_level', 'N/A')}")
            logger.info(f"⚠️  Compliance Impact: {suggestion.get('compliance_impact', 'N/A')}")
            logger.info("=" * 60)
            
            # Also print to console for immediate visibility
            print("🤖 LLM COMPLIANCE SUGGESTION GENERATED")
            print("=" * 60)
            print(f"🆔 Customer ID: {violation_data.get('customer_id', 'Unknown')}")
            print(f"⚖️  Framework: {framework}")
            print(f"📝 AI Description: {suggestion.get('description', 'N/A')}")
            print(f"🔧 AI Recommendation: {suggestion.get('recommendation', 'N/A')}")
            print(f"📚 Legal Reference: {suggestion.get('legal_reference', 'N/A')}")
            print(f"⚡ Urgency Level: {suggestion.get('urgency_level', 'N/A')}")
            print(f"⚠️  Compliance Impact: {suggestion.get('compliance_impact', 'N/A')}")
            print("=" * 60)
            
            logger.info(f"Generated LLM compliance suggestion for {framework} violation")
            return suggestion
            
        except Exception as e:
            logger.error(f"Error generating LLM suggestion: {str(e)}")
            return self._get_fallback_suggestion(violation_data, framework)
    
    def _create_compliance_prompt(self, violation_data: Dict[str, Any], framework: str) -> str:
        """Create a detailed prompt for compliance analysis"""
        
        # Extract customer ID from multiple possible field names
        customer_id = (
            violation_data.get('customer_id') or 
            violation_data.get('id') or 
            violation_data.get('user_id') or 
            'Unknown'
        )
        data_age = violation_data.get('data_age_days', 0)
        excess_days = violation_data.get('excess_days', 0)
        retention_limit = violation_data.get('retention_limit_days', 0)
        is_archived = violation_data.get('is_archived', False)
        violation_type = violation_data.get('violation_type', 'DATA_RETENTION_EXCEEDED')
        
        prompt = f"""You are a compliance expert specializing in {framework} data protection regulations.

VIOLATION DETAILS:
- Customer ID: {customer_id}
- Violation Type: {violation_type}
- Data Age: {data_age} days
- Retention Limit: {retention_limit} days
- Excess Period: {excess_days} days
- Customer Archived: {is_archived}
- Framework: {framework}

TASK: Provide a comprehensive compliance analysis in JSON format with these exact fields:

1. "description": A detailed explanation of why this is a violation (2-3 sentences)
2. "recommendation": Specific action steps to remediate this violation (be detailed and actionable)
3. "legal_reference": Specific {framework} article/section that applies to this violation
4. "urgency_level": HIGH/MEDIUM/LOW based on risk assessment
5. "compliance_impact": Potential consequences if not addressed

Focus on practical, actionable advice that a compliance officer can immediately implement.

Respond ONLY with valid JSON in this format:
{{
    "description": "...",
    "recommendation": "...", 
    "legal_reference": "...",
    "urgency_level": "...",
    "compliance_impact": "..."
}}"""

        return prompt
    
    async def _call_openai_chat(self, prompt: str) -> str:
        """Call OpenAI Chat Completion API"""
        try:
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a compliance expert specializing in data protection regulations. Provide precise, actionable compliance advice."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise
    
    def _parse_llm_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response and extract structured data"""
        try:
            # Try to parse as JSON first
            if response.startswith('{') and response.endswith('}'):
                parsed = json.loads(response)
                return {
                    'description': parsed.get('description', 'Compliance violation detected'),
                    'recommendation': parsed.get('recommendation', 'Review and remediate data retention policies'),
                    'legal_reference': parsed.get('legal_reference', 'Data Protection Act'),
                    'urgency_level': parsed.get('urgency_level', 'HIGH'),
                    'compliance_impact': parsed.get('compliance_impact', 'Potential regulatory penalties')
                }
            else:
                # Fallback: extract information from text
                return {
                    'description': response[:200] + "..." if len(response) > 200 else response,
                    'recommendation': 'Immediate review and remediation required based on AI analysis',
                    'legal_reference': 'Data Protection Regulations',
                    'urgency_level': 'HIGH',
                    'compliance_impact': 'Regulatory compliance risk'
                }
                
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON, using fallback")
            return {
                'description': response[:200] + "..." if len(response) > 200 else response,
                'recommendation': 'Immediate review and remediation required based on AI analysis',
                'legal_reference': 'Data Protection Regulations',
                'urgency_level': 'HIGH',
                'compliance_impact': 'Regulatory compliance risk'
            }
    
    def _get_fallback_suggestion(self, violation_data: Dict[str, Any], framework: str) -> Dict[str, str]:
        """Generate fallback suggestions when LLM is not available"""
        
        excess_days = violation_data.get('excess_days', 0)
        violation_type = violation_data.get('violation_type', 'DATA_RETENTION_EXCEEDED')
        
        if framework == "PDPA":
            legal_ref = "PDPA Section 24 - Data Retention Limitation"
            impact = "Potential penalty up to S$1 million under PDPA"
        elif framework == "GDPR":
            legal_ref = "GDPR Article 17 - Right to Erasure"
            impact = "Potential fine up to 4% of annual global turnover under GDPR"
        else:
            legal_ref = "Data Protection Regulations"
            impact = "Regulatory compliance risk and potential penalties"
        
        return {
            'description': f"Data retention period exceeded by {excess_days} days, violating {framework} requirements for lawful data processing and storage limitations.",
            'recommendation': f"Immediately delete or anonymize customer data that exceeds retention period. Review data retention policies and implement automated cleanup processes to prevent future violations.",
            'legal_reference': legal_ref,
            'urgency_level': 'HIGH' if excess_days > 30 else 'MEDIUM',
            'compliance_impact': impact
        }
    
    async def generate_remediation_plan(
        self,
        violations: List[Dict[str, Any]],
        framework: str = "PDPA"
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive remediation plan for multiple violations
        
        Args:
            violations: List of violation data
            framework: Compliance framework
            
        Returns:
            Dictionary with remediation plan and timeline
        """
        if not self.is_initialized:
            logger.warning("LLM service not initialized - using basic remediation plan")
            return self._get_basic_remediation_plan(violations, framework)
        
        try:
            prompt = f"""You are a compliance expert. Create a comprehensive remediation plan for {len(violations)} {framework} violations.

VIOLATIONS SUMMARY:
{self._format_violations_for_prompt(violations)}

Create a JSON response with:
1. "priority_actions": List of immediate actions (next 24-48 hours)
2. "short_term_plan": Actions for next 1-4 weeks
3. "long_term_plan": Strategic improvements for next 3-6 months
4. "estimated_timeline": Overall timeline estimate
5. "resources_needed": Required resources and expertise
6. "compliance_monitoring": Ongoing monitoring recommendations

Respond ONLY with valid JSON."""

            response = await self._call_openai_chat(prompt)
            return self._parse_remediation_response(response)
            
        except Exception as e:
            logger.error(f"Error generating remediation plan: {str(e)}")
            return self._get_basic_remediation_plan(violations, framework)
    
    def _format_violations_for_prompt(self, violations: List[Dict[str, Any]]) -> str:
        """Format violations for LLM prompt"""
        summary = []
        for i, v in enumerate(violations[:5], 1):  # Limit to 5 for prompt size
            excess = v.get('excess_days', 0)
            summary.append(f"{i}. Customer {v.get('customer_id', 'Unknown')}: {excess} days over retention limit")
        return "\n".join(summary)
    
    def _parse_remediation_response(self, response: str) -> Dict[str, Any]:
        """Parse remediation plan response"""
        try:
            if response.startswith('{') and response.endswith('}'):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        return self._get_basic_remediation_plan([], "")
    
    def _get_basic_remediation_plan(self, violations: List[Dict[str, Any]], framework: str) -> Dict[str, Any]:
        """Basic remediation plan fallback"""
        return {
            "priority_actions": [
                "Immediately identify and delete/anonymize expired customer data",
                "Notify data protection officer of compliance violations",
                "Document all remediation actions taken"
            ],
            "short_term_plan": [
                "Review and update data retention policies",
                "Implement automated data cleanup processes",
                "Train staff on compliance requirements"
            ],
            "long_term_plan": [
                "Establish ongoing compliance monitoring",
                "Regular audits of data retention practices",
                "Integration with privacy management systems"
            ],
            "estimated_timeline": "Priority: 24-48 hours, Short-term: 2-4 weeks, Long-term: 3-6 months",
            "resources_needed": ["Compliance team", "IT/Database administrators", "Legal review"],
            "compliance_monitoring": "Monthly compliance audits and automated retention period monitoring"
        }