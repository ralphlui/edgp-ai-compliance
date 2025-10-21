"""
Unit tests for AWS RDS Service

Tests for AWS RDS connection management including:
- AWS Secrets Manager integration
- RDS configuration building
- Connection validation
- Credential resolution
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from botocore.exceptions import ClientError
import json

from src.compliance_agent.services.aws_rds_service import (
    AWSSecretsManager,
    AWSRDSConfig,
    RDSConnectionValidator
)


class TestAWSSecretsManager:
    """Test AWS Secrets Manager client"""
    
    def test_secrets_manager_initialization(self):
        """Test creating a secrets manager instance"""
        manager = AWSSecretsManager(region_name="us-east-1")
        assert manager.region_name == "us-east-1"
        assert manager.client is None
    
    def test_secrets_manager_default_region(self):
        """Test default region is Singapore"""
        manager = AWSSecretsManager()
        assert manager.region_name == "ap-southeast-1"
    
    @patch('boto3.client')
    def test_get_client_creates_client(self, mock_boto_client):
        """Test _get_client creates boto3 client"""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSSecretsManager(region_name="us-west-2")
        client = manager._get_client()
        
        assert client == mock_client
        mock_boto_client.assert_called_once_with(
            'secretsmanager',
            region_name="us-west-2"
        )
    
    @patch('boto3.client')
    def test_get_client_reuses_existing_client(self, mock_boto_client):
        """Test _get_client reuses existing client"""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        
        manager = AWSSecretsManager()
        client1 = manager._get_client()
        client2 = manager._get_client()
        
        assert client1 == client2
        mock_boto_client.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('boto3.client')
    async def test_get_secret_success(self, mock_boto_client):
        """Test successfully retrieving a secret"""
        mock_client = MagicMock()
        secret_data = {
            "username": "db_user",
            "password": "db_password",
            "host": "rds.amazonaws.com",
            "port": "5432"
        }
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }
        mock_boto_client.return_value = mock_client
        
        manager = AWSSecretsManager()
        result = await manager.get_secret("test-secret")
        
        assert result == secret_data
        mock_client.get_secret_value.assert_called_once_with(SecretId="test-secret")
    
    @pytest.mark.asyncio
    @patch('boto3.client')
    async def test_get_secret_decryption_failure(self, mock_boto_client):
        """Test handling decryption failure"""
        mock_client = MagicMock()
        error_response = {'Error': {'Code': 'DecryptionFailureException', 'Message': 'Decryption failed'}}
        mock_client.get_secret_value.side_effect = ClientError(error_response, 'GetSecretValue')
        mock_boto_client.return_value = mock_client
        
        manager = AWSSecretsManager()
        
        with pytest.raises(ClientError) as exc_info:
            await manager.get_secret("test-secret")
        
        assert exc_info.value.response['Error']['Code'] == 'DecryptionFailureException'
    
    @pytest.mark.asyncio
    @patch('boto3.client')
    async def test_get_secret_resource_not_found(self, mock_boto_client):
        """Test handling when secret is not found"""
        mock_client = MagicMock()
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}}
        mock_client.get_secret_value.side_effect = ClientError(error_response, 'GetSecretValue')
        mock_boto_client.return_value = mock_client
        
        manager = AWSSecretsManager()
        
        with pytest.raises(ClientError) as exc_info:
            await manager.get_secret("nonexistent-secret")
        
        assert exc_info.value.response['Error']['Code'] == 'ResourceNotFoundException'
    
    @pytest.mark.asyncio
    @patch('boto3.client')
    async def test_get_secret_invalid_json(self, mock_boto_client):
        """Test handling invalid JSON in secret"""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': 'not valid json {'
        }
        mock_boto_client.return_value = mock_client
        
        manager = AWSSecretsManager()
        
        with pytest.raises(json.JSONDecodeError):
            await manager.get_secret("test-secret")


class TestAWSRDSConfig:
    """Test AWS RDS configuration builder"""
    
    def test_build_config_with_direct_credentials(self):
        """Test building config with username/password"""
        config = AWSRDSConfig.build_connection_config(
            host="rds.amazonaws.com",
            port=5432,
            database="mydb",
            username="admin",
            password="secret123"
        )
        
        assert config['host'] == "rds.amazonaws.com"
        assert config['port'] == 5432
        assert config['db'] == "mydb"
        assert config['user'] == "admin"
        assert config['password'] == "secret123"
        assert config['use_secrets_manager'] is False
        assert config['charset'] == 'utf8mb4'
        assert config['autocommit'] is True
    
    def test_build_config_with_secrets_manager(self):
        """Test building config with Secrets Manager"""
        config = AWSRDSConfig.build_connection_config(
            host="rds.amazonaws.com",
            port=3306,
            database="mydb",
            secret_name="my-db-secret",
            region="us-west-2",
            use_secrets_manager=True
        )
        
        assert config['host'] == "rds.amazonaws.com"
        assert config['port'] == 3306
        assert config['db'] == "mydb"
        assert config['secret_name'] == "my-db-secret"
        assert config['region'] == "us-west-2"
        assert config['use_secrets_manager'] is True
        assert 'user' not in config
        assert 'password' not in config
    
    def test_build_config_missing_credentials(self):
        """Test that missing credentials raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            AWSRDSConfig.build_connection_config(
                host="rds.amazonaws.com",
                port=5432,
                database="mydb"
            )
        
        assert "username/password" in str(exc_info.value).lower() or "secrets manager" in str(exc_info.value).lower()
    
    def test_build_config_with_default_region(self):
        """Test default region is applied"""
        config = AWSRDSConfig.build_connection_config(
            host="rds.amazonaws.com",
            port=3306,
            database="mydb",
            secret_name="my-secret",
            use_secrets_manager=True
        )
        
        assert config['region'] == "ap-southeast-1"
    
    @pytest.mark.asyncio
    async def test_resolve_credentials_without_secrets_manager(self):
        """Test resolving credentials when not using Secrets Manager"""
        config = {
            'host': 'localhost',
            'port': 3306,
            'db': 'testdb',
            'user': 'admin',
            'password': 'password',
            'use_secrets_manager': False
        }
        
        resolved = await AWSRDSConfig.resolve_credentials(config)
        
        assert resolved == config
        assert resolved['user'] == 'admin'
        assert resolved['password'] == 'password'
    
    @pytest.mark.asyncio
    @patch('src.compliance_agent.services.aws_rds_service.AWSSecretsManager')
    async def test_resolve_credentials_with_secrets_manager(self, mock_secrets_class):
        """Test resolving credentials from Secrets Manager"""
        mock_secrets_instance = AsyncMock()
        mock_secrets_instance.get_secret.return_value = {
            'username': 'db_admin',
            'password': 'secret_pass',
            'host': 'new-rds.amazonaws.com',
            'port': '3307'
        }
        mock_secrets_class.return_value = mock_secrets_instance
        
        config = {
            'host': 'old-host.com',
            'port': 3306,
            'db': 'mydb',
            'secret_name': 'my-secret',
            'region': 'us-east-1',
            'use_secrets_manager': True
        }
        
        resolved = await AWSRDSConfig.resolve_credentials(config)
        
        assert resolved['user'] == 'db_admin'
        assert resolved['password'] == 'secret_pass'
        assert resolved['host'] == 'new-rds.amazonaws.com'
        assert resolved['port'] == 3307
        assert 'secret_name' not in resolved
        assert 'region' not in resolved
        assert 'use_secrets_manager' not in resolved
    
    @pytest.mark.asyncio
    async def test_resolve_credentials_missing_secret_name(self):
        """Test that missing secret_name raises ValueError"""
        config = {
            'host': 'localhost',
            'port': 3306,
            'db': 'testdb',
            'use_secrets_manager': True
        }
        
        with pytest.raises(ValueError) as exc_info:
            await AWSRDSConfig.resolve_credentials(config)
        
        assert "secret_name" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @patch('src.compliance_agent.services.aws_rds_service.AWSSecretsManager')
    async def test_resolve_credentials_partial_secrets(self, mock_secrets_class):
        """Test resolving credentials when secrets don't include host/port"""
        mock_secrets_instance = AsyncMock()
        mock_secrets_instance.get_secret.return_value = {
            'username': 'db_admin',
            'password': 'secret_pass'
            # No host or port in secrets
        }
        mock_secrets_class.return_value = mock_secrets_instance
        
        config = {
            'host': 'original-host.com',
            'port': 3306,
            'db': 'mydb',
            'secret_name': 'my-secret',
            'region': 'us-east-1',
            'use_secrets_manager': True
        }
        
        resolved = await AWSRDSConfig.resolve_credentials(config)
        
        assert resolved['user'] == 'db_admin'
        assert resolved['password'] == 'secret_pass'
        assert resolved['host'] == 'original-host.com'  # Original host preserved
        assert resolved['port'] == 3306  # Original port preserved


class TestRDSConnectionValidator:
    """Test RDS connection validator"""
    
    def test_validate_config_success_with_direct_credentials(self):
        """Test validating config with direct credentials"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': 3306,
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        
        result = RDSConnectionValidator.validate_config(config)
        assert result is True
    
    def test_validate_config_success_with_secrets_manager(self):
        """Test validating config with Secrets Manager"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': 3306,
            'db': 'mydb',
            'use_secrets_manager': True,
            'secret_name': 'my-secret'
        }
        
        result = RDSConnectionValidator.validate_config(config)
        assert result is True
    
    def test_validate_config_missing_host(self):
        """Test validation fails when host is missing"""
        config = {
            'port': 3306,
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "host" in str(exc_info.value).lower()
    
    def test_validate_config_missing_port(self):
        """Test validation fails when port is missing"""
        config = {
            'host': 'rds.amazonaws.com',
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "port" in str(exc_info.value).lower()
    
    def test_validate_config_missing_database(self):
        """Test validation fails when database is missing"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': 3306,
            'user': 'admin',
            'password': 'secret'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "db" in str(exc_info.value).lower()
    
    def test_validate_config_missing_credentials(self):
        """Test validation fails when no credentials provided"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': 3306,
            'db': 'mydb'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "credentials" in str(exc_info.value).lower() or "secrets manager" in str(exc_info.value).lower()
    
    def test_validate_config_invalid_port_type(self):
        """Test validation fails with non-integer port"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': "3306",  # String instead of int
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "port" in str(exc_info.value).lower()
    
    def test_validate_config_invalid_port_range_low(self):
        """Test validation fails with port below valid range"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': 0,
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "port" in str(exc_info.value).lower()
    
    def test_validate_config_invalid_port_range_high(self):
        """Test validation fails with port above valid range"""
        config = {
            'host': 'rds.amazonaws.com',
            'port': 65536,
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        
        with pytest.raises(ValueError) as exc_info:
            RDSConnectionValidator.validate_config(config)
        
        assert "port" in str(exc_info.value).lower()
    
    def test_validate_config_valid_port_boundaries(self):
        """Test validation succeeds with ports at valid boundaries"""
        # Test port 1
        config1 = {
            'host': 'rds.amazonaws.com',
            'port': 1,
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        assert RDSConnectionValidator.validate_config(config1) is True
        
        # Test port 65535
        config2 = {
            'host': 'rds.amazonaws.com',
            'port': 65535,
            'db': 'mydb',
            'user': 'admin',
            'password': 'secret'
        }
        assert RDSConnectionValidator.validate_config(config2) is True


class TestIntegration:
    """Test integration scenarios"""
    
    @pytest.mark.asyncio
    @patch('src.compliance_agent.services.aws_rds_service.AWSSecretsManager')
    async def test_full_config_flow_with_secrets_manager(self, mock_secrets_class):
        """Test complete flow from config build to credential resolution"""
        # Mock secrets manager
        mock_secrets_instance = AsyncMock()
        mock_secrets_instance.get_secret.return_value = {
            'username': 'prod_user',
            'password': 'prod_password'
        }
        mock_secrets_class.return_value = mock_secrets_instance
        
        # Build config
        config = AWSRDSConfig.build_connection_config(
            host="prod-rds.amazonaws.com",
            port=5432,
            database="production_db",
            secret_name="prod-db-credentials",
            region="us-west-2",
            use_secrets_manager=True
        )
        
        # Validate config before resolution
        assert RDSConnectionValidator.validate_config(config) is True
        
        # Resolve credentials
        resolved = await AWSRDSConfig.resolve_credentials(config)
        
        # Validate resolved config
        assert resolved['host'] == "prod-rds.amazonaws.com"
        assert resolved['port'] == 5432
        assert resolved['db'] == "production_db"
        assert resolved['user'] == 'prod_user'
        assert resolved['password'] == 'prod_password'
        assert 'use_secrets_manager' not in resolved
        assert 'secret_name' not in resolved
    
    def test_full_config_flow_with_direct_credentials(self):
        """Test complete flow with direct credentials"""
        # Build config
        config = AWSRDSConfig.build_connection_config(
            host="dev-rds.amazonaws.com",
            port=3306,
            database="dev_db",
            username="dev_user",
            password="dev_password"
        )
        
        # Validate config
        assert RDSConnectionValidator.validate_config(config) is True
        
        # Verify config structure
        assert config['host'] == "dev-rds.amazonaws.com"
        assert config['user'] == "dev_user"
        assert config['password'] == "dev_password"
        assert config['use_secrets_manager'] is False
