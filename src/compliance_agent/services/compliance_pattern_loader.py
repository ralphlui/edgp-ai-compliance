"""
International Compliance Pattern Loader for PDPA/GDPR
Loads compliance patterns from JSON files into OpenSearch for LLM reference
"""

import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
from datetime import datetime

from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import openai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables based on APP_ENV
app_env = os.getenv("APP_ENV", "development")
env_file = f'.env.{app_env}'
if os.path.exists(env_file):
    load_dotenv(env_file)
    logger.info(f"Loaded environment from: {env_file}")
else:
    load_dotenv('.env')
    logger.info(f"Environment file {env_file} not found, using .env")

class InternationalCompliancePatternLoader:
    """
    Loads international compliance patterns (PDPA, GDPR) into OpenSearch
    for AI agent reference during data governance compliance checks
    """
    
    def __init__(self):
        # AWS credentials for OpenSearch
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'ap-southeast-1')

        # OpenSearch configuration
        self.opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT')
        self.compliance_index = 'international-compliance-patterns'

        # OpenAI API key - fetch from Secrets Manager
        from src.compliance_agent.services.ai_secrets_service import get_openai_api_key
        api_key = get_openai_api_key()
        if not api_key:
            logger.warning("No OpenAI API key found - embeddings will not be available")
            openai.api_key = None
        else:
            openai.api_key = api_key
            logger.info("OpenAI API key configured successfully for embeddings")
        
        # Setup AWS authentication
        if self.aws_access_key and self.aws_secret_key:
            self.awsauth = AWS4Auth(
                self.aws_access_key,
                self.aws_secret_key,
                self.aws_region,
                'es'
            )
        
        # Initialize OpenSearch client
        if self.opensearch_endpoint:
            self.host = self.opensearch_endpoint.replace('https://', '').replace('http://', '')
            self.client = OpenSearch(
                hosts=[{'host': self.host, 'port': 443}],
                http_auth=self.awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=30,
                max_retries=3
            )
        else:
            raise ValueError("OPENSEARCH_ENDPOINT not configured")
    
    def load_json_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Load compliance patterns from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} patterns from {file_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {str(e)}")
            return []
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for compliance pattern text."""
        try:
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return []
    
    async def create_compliance_index(self) -> bool:
        """Create OpenSearch index for international compliance patterns."""
        try:
            index_mapping = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "compliance_id": {"type": "keyword"},
                        "framework": {"type": "keyword"},  # PDPA, GDPR
                        "title": {"type": "text"},
                        "content": {"type": "text"},
                        "category": {"type": "keyword"},
                        "applies_to": {"type": "keyword"},
                        "country": {"type": "keyword"},
                        "region": {"type": "keyword"},
                        "risk_level": {"type": "keyword"},
                        "data_types": {"type": "keyword"},
                        "violation_patterns": {"type": "text"},
                        "remediation_actions": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1536,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "lucene",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24
                                }
                            }
                        },
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"}
                    }
                }
            }
            
            if self.client.indices.exists(index=self.compliance_index):
                logger.info(f"Index '{self.compliance_index}' already exists")
                return True
            
            response = self.client.indices.create(
                index=self.compliance_index,
                body=index_mapping
            )
            
            logger.info(f"Created compliance patterns index: {self.compliance_index}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create compliance index: {str(e)}")
            return False
    
    def process_pdpa_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDPA compliance pattern for OpenSearch."""
        try:
            # Extract key information for embedding
            embedding_text = f"{pattern.get('title', '')} {pattern.get('content', '')} {pattern.get('category', '')}"
            embedding = self.generate_embedding(embedding_text)
            
            # Create standardized compliance pattern
            processed_pattern = {
                "compliance_id": pattern.get('id'),
                "framework": "PDPA",
                "title": pattern.get('title'),
                "content": pattern.get('content'),
                "category": pattern.get('category'),
                "applies_to": pattern.get('applies_to', []),
                "country": "Singapore",
                "region": "APAC",
                "risk_level": self._determine_risk_level(pattern),
                "data_types": self._extract_data_types(pattern),
                "violation_patterns": self._extract_violation_patterns(pattern),
                "remediation_actions": self._extract_remediation_actions(pattern),
                "embedding": embedding,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            return processed_pattern
            
        except Exception as e:
            logger.error(f"Failed to process PDPA pattern {pattern.get('id', 'unknown')}: {str(e)}")
            return None
    
    def process_gdpr_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Process GDPR compliance pattern for OpenSearch."""
        try:
            # Extract key information for embedding
            embedding_text = f"{pattern.get('title', '')} {pattern.get('content', '')} {pattern.get('category', '')}"
            embedding = self.generate_embedding(embedding_text)
            
            # Create standardized compliance pattern
            processed_pattern = {
                "compliance_id": pattern.get('id'),
                "framework": "GDPR",
                "title": pattern.get('title'),
                "content": pattern.get('content'),
                "category": pattern.get('category'),
                "applies_to": pattern.get('applies_to', []),
                "country": "European Union",
                "region": "EU",
                "risk_level": self._determine_risk_level(pattern),
                "data_types": self._extract_data_types(pattern),
                "violation_patterns": self._extract_violation_patterns(pattern),
                "remediation_actions": self._extract_remediation_actions(pattern),
                "embedding": embedding,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            return processed_pattern
            
        except Exception as e:
            logger.error(f"Failed to process GDPR pattern {pattern.get('id', 'unknown')}: {str(e)}")
            return None
    
    def _determine_risk_level(self, pattern: Dict[str, Any]) -> str:
        """Determine risk level based on pattern content."""
        content = pattern.get('content', '').lower()
        title = pattern.get('title', '').lower()
        
        # High risk indicators
        high_risk_keywords = ['delete', 'erasure', 'breach', 'penalty', 'fine', 'violation', 'unlawful']
        if any(keyword in content or keyword in title for keyword in high_risk_keywords):
            return "HIGH"
        
        # Medium risk indicators
        medium_risk_keywords = ['consent', 'access', 'rectification', 'portability', 'processing']
        if any(keyword in content or keyword in title for keyword in medium_risk_keywords):
            return "MEDIUM"
        
        return "LOW"
    
    def _extract_data_types(self, pattern: Dict[str, Any]) -> List[str]:
        """Extract data types mentioned in the pattern."""
        content = pattern.get('content', '').lower()
        data_types = []
        
        data_type_keywords = {
            'personal_data': ['personal data', 'personally identifiable'],
            'sensitive_data': ['sensitive data', 'special categories'],
            'customer_data': ['customer', 'client'],
            'financial_data': ['financial', 'payment', 'credit'],
            'health_data': ['health', 'medical'],
            'biometric_data': ['biometric', 'fingerprint'],
            'location_data': ['location', 'geolocation']
        }
        
        for data_type, keywords in data_type_keywords.items():
            if any(keyword in content for keyword in keywords):
                data_types.append(data_type)
        
        return data_types or ['personal_data']  # Default
    
    def _extract_violation_patterns(self, pattern: Dict[str, Any]) -> str:
        """Extract violation patterns from the compliance rule."""
        content = pattern.get('content', '')
        
        # Common violation patterns for data retention
        violation_indicators = [
            "retention period exceeded",
            "data stored beyond legal limit",
            "no consent for extended storage",
            "inactive customer data retention",
            "data not deleted after request",
            "processing without lawful basis"
        ]
        
        # Analyze content for specific violation patterns
        if 'retention' in content.lower():
            return "Data retention period violations, storing data beyond legal limits"
        elif 'consent' in content.lower():
            return "Consent-related violations, processing without valid consent"
        elif 'delete' in content.lower() or 'erasure' in content.lower():
            return "Data deletion violations, failure to delete upon request"
        
        return "General compliance violations related to data processing"
    
    def _extract_remediation_actions(self, pattern: Dict[str, Any]) -> str:
        """Extract remediation actions from the compliance rule."""
        content = pattern.get('content', '').lower()
        
        if 'delete' in content or 'erasure' in content:
            return "Delete data immediately, notify data subject, update systems"
        elif 'consent' in content:
            return "Obtain valid consent, cease processing, provide opt-out mechanism"
        elif 'access' in content:
            return "Provide data access, implement access controls, log access requests"
        elif 'retention' in content:
            return "Review retention policies, delete expired data, implement automated cleanup"
        
        return "Review compliance, implement corrective measures, document actions"
    
    async def load_patterns_to_opensearch(self) -> bool:
        """Load all compliance patterns to OpenSearch."""
        try:
            logger.info("Starting international compliance pattern loading...")
            
            # Create index if needed
            if not await self.create_compliance_index():
                return False
            
            total_loaded = 0
            
            # Load PDPA patterns
            pdpa_file = "src/compliance_agent/compliancesInfo/PDPA.json"
            if os.path.exists(pdpa_file):
                pdpa_patterns = self.load_json_file(pdpa_file)
                for pattern in pdpa_patterns:
                    processed = self.process_pdpa_pattern(pattern)
                    if processed and processed.get('embedding'):
                        try:
                            self.client.index(
                                index=self.compliance_index,
                                id=f"pdpa_{processed['compliance_id']}",
                                body=processed
                            )
                            total_loaded += 1
                            logger.info(f"Loaded PDPA pattern: {processed['compliance_id']}")
                        except Exception as e:
                            logger.error(f"Failed to index PDPA pattern: {str(e)}")
            
            # Load GDPR patterns
            gdpr_file = "src/compliance_agent/compliancesInfo/GDPR.json"
            if os.path.exists(gdpr_file):
                gdpr_patterns = self.load_json_file(gdpr_file)
                for pattern in gdpr_patterns:
                    processed = self.process_gdpr_pattern(pattern)
                    if processed and processed.get('embedding'):
                        try:
                            self.client.index(
                                index=self.compliance_index,
                                id=f"gdpr_{processed['compliance_id']}",
                                body=processed
                            )
                            total_loaded += 1
                            logger.info(f"Loaded GDPR pattern: {processed['compliance_id']}")
                        except Exception as e:
                            logger.error(f"Failed to index GDPR pattern: {str(e)}")
            
            # Refresh index
            self.client.indices.refresh(index=self.compliance_index)
            
            logger.info(f"Successfully loaded {total_loaded} international compliance patterns")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load compliance patterns: {str(e)}")
            return False
    
    async def test_pattern_search(self, query: str = "data retention customer information") -> bool:
        """Test vector search functionality."""
        try:
            logger.info(f"Testing pattern search with query: '{query}'")
            
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return False
            
            # Vector search
            search_query = {
                "size": 5,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": 5
                        }
                    }
                },
                "_source": ["compliance_id", "framework", "title", "category", "risk_level"]
            }
            
            response = self.client.search(
                index=self.compliance_index,
                body=search_query
            )
            
            logger.info(f"Found {len(response['hits']['hits'])} matching patterns:")
            for hit in response['hits']['hits']:
                source = hit['_source']
                score = hit['_score']
                logger.info(f"  - {source['compliance_id']} ({source['framework']}) - Score: {score:.4f}")
                logger.info(f"    Title: {source['title']}")
                logger.info(f"    Risk: {source['risk_level']} | Category: {source['category']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Pattern search test failed: {str(e)}")
            return False

async def main():
    """Main function to load compliance patterns."""
    loader = InternationalCompliancePatternLoader()
    
    print("🌍 Loading International Compliance Patterns (PDPA/GDPR)")
    print("=" * 60)
    
    # Load patterns
    success = await loader.load_patterns_to_opensearch()
    if success:
        print("✅ Compliance patterns loaded successfully!")
        
        # Test search
        print("\n🔍 Testing pattern search...")
        await loader.test_pattern_search()
        
    else:
        print("❌ Failed to load compliance patterns")

if __name__ == "__main__":
    asyncio.run(main())