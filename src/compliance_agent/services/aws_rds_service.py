"""
AWS RDS Database Service for EDGP Master Data Connection
Supports AWS Secrets Manager for secure credential management
Used when EDGP_DB_SECRET_NAME is configured or AWS RDS connection is detected
"""

import logging
import json
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AWSSecretsManager:
    """Service for retrieving database credentials from AWS Secrets Manager"""
    
    def __init__(self, region_name: str = "ap-southeast-1"):
        self.region_name = region_name
        self.client = None
    
    def _get_client(self):
        """Get or create Secrets Manager client"""
        if not self.client:
            self.client = boto3.client(
                'secretsmanager',
                region_name=self.region_name
            )
        return self.client
    
    async def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve database credentials from AWS Secrets Manager
        
        Args:
            secret_name: Name of the secret in AWS Secrets Manager
            
        Returns:
            Dictionary containing database credentials
            
        Raises:
            ClientError: If secret cannot be retrieved
        """
        try:
            client = self._get_client()
            
            logger.info(f"Retrieving secret: {secret_name}")
            response = client.get_secret_value(SecretId=secret_name)
            
            # Parse the secret value
            secret_string = response['SecretString']
            secret_dict = json.loads(secret_string)
            
            logger.info("Successfully retrieved database credentials from Secrets Manager")
            return secret_dict
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'DecryptionFailureException':
                logger.error("Secrets Manager can't decrypt the protected secret text using the provided KMS key")
            elif error_code == 'InternalServiceErrorException':
                logger.error("An error occurred on the server side")
            elif error_code == 'InvalidParameterException':
                logger.error("You provided an invalid value for a parameter")
            elif error_code == 'InvalidRequestException':
                logger.error("You provided a parameter value that is not valid for the current state of the resource")
            elif error_code == 'ResourceNotFoundException':
                logger.error(f"The requested secret {secret_name} was not found")
            else:
                logger.error(f"Unknown error retrieving secret: {error_code}")
            
            raise e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret JSON: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret: {str(e)}")
            raise e


class AWSRDSConfig:
    """Configuration builder for AWS RDS connections"""
    
    @staticmethod
    def build_connection_config(
        host: str,
        port: int,
        database: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        secret_name: Optional[str] = None,
        region: str = "ap-southeast-1",
        use_secrets_manager: bool = False
    ) -> Dict[str, Any]:
        """
        Build database connection configuration for AWS RDS
        
        Args:
            host: RDS endpoint
            port: Database port  
            database: Database name (from environment file)
            username: Database username (if not using Secrets Manager)
            password: Database password (if not using Secrets Manager)
            secret_name: AWS Secrets Manager secret name
            region: AWS region
            use_secrets_manager: Whether to use AWS Secrets Manager
            
        Returns:
            Dictionary with connection configuration
        """
        
        config = {
            'host': host,
            'port': port,
            'db': database,
            'charset': 'utf8mb4',
            'autocommit': True,
            'connect_timeout': 60
        }
        
        if use_secrets_manager and secret_name:
            logger.info(f"Will use AWS Secrets Manager for credentials: {secret_name}")
            config['secret_name'] = secret_name
            config['region'] = region
            config['use_secrets_manager'] = True
        elif username and password:
            logger.info(f"Using provided credentials for RDS connection")
            config['user'] = username
            config['password'] = password
            config['use_secrets_manager'] = False
        else:
            raise ValueError("Either provide username/password or enable Secrets Manager with secret_name")
        
        logger.info(f"AWS RDS config built: host={host}, database={database}")
        return config
    
    @staticmethod
    async def resolve_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve database credentials from AWS Secrets Manager if needed
        
        Args:
            config: Database configuration
            
        Returns:
            Configuration with resolved credentials
        """
        if not config.get('use_secrets_manager', False):
            return config
        
        secret_name = config.get('secret_name')
        region = config.get('region', 'ap-southeast-1')
        
        if not secret_name:
            raise ValueError("secret_name is required when using Secrets Manager")
        
        # Get credentials from Secrets Manager
        secrets_manager = AWSSecretsManager(region)
        credentials = await secrets_manager.get_secret(secret_name)
        
        # Update config with retrieved credentials
        resolved_config = config.copy()
        resolved_config['user'] = credentials.get('username')
        resolved_config['password'] = credentials.get('password')
        
        # Also update host and port if they come from secrets manager
        if credentials.get('host'):
            resolved_config['host'] = credentials.get('host')
        if credentials.get('port'):
            resolved_config['port'] = int(credentials.get('port'))
        
        # Remove secrets manager specific keys from final config
        resolved_config.pop('secret_name', None)
        resolved_config.pop('region', None)
        resolved_config.pop('use_secrets_manager', None)
        
        logger.info("Database credentials resolved from AWS Secrets Manager")
        return resolved_config


class RDSConnectionValidator:
    """Utility for validating RDS connections"""
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """
        Validate RDS connection configuration
        
        Args:
            config: Database configuration
            
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        required_fields = ['host', 'port', 'db']
        
        for field in required_fields:
            if not config.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        # Check if credentials are provided
        has_direct_creds = config.get('user') and config.get('password')
        has_secrets_manager = config.get('use_secrets_manager') and config.get('secret_name')
        
        if not has_direct_creds and not has_secrets_manager:
            raise ValueError("Must provide either direct credentials or Secrets Manager configuration")
        
        # Validate port range
        port = config.get('port')
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ValueError(f"Invalid port number: {port}")
        
        logger.info("RDS configuration validation passed")
        return True