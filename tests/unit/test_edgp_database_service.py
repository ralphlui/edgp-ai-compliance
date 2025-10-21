"""
Tests for EDGP Database Service
File: tests/unit/test_edgp_database_service.py
Target: src/compliance_agent/services/edgp_database_service_simple.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import aiomysql

from src.compliance_agent.services.edgp_database_service_simple import (
    CustomerData,
    EDGPDatabaseService
)


class AsyncContextManagerMock:
    """Helper class to mock async context managers like pool.acquire()"""
    def __init__(self, return_value):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class TestCustomerData:
    """Test CustomerData class"""
    
    def test_customer_data_creation(self):
        """Test creating a customer data instance"""
        now = datetime.utcnow()
        customer = CustomerData(
            id=1,
            email="test@example.com",
            phone="+65-1234-5678",
            firstname="John",
            lastname="Doe",
            created_date=now,
            updated_date=now,
            is_archived=False,
            domain_name="example.com",
            workflow_tracker_id="WF-001"
        )
        
        assert customer.id == 1
        assert customer.email == "test@example.com"
        assert customer.phone == "+65-1234-5678"
        assert customer.firstname == "John"
        assert customer.lastname == "Doe"
        assert customer.created_date == now
        assert customer.is_archived is False
        assert customer.domain_name == "example.com"
        assert customer.workflow_tracker_id == "WF-001"
    
    def test_customer_data_minimal_fields(self):
        """Test customer with only required field"""
        customer = CustomerData(id=2)
        
        assert customer.id == 2
        assert customer.email is None
        assert customer.phone is None
        assert customer.firstname is None
        assert customer.lastname is None
        assert customer.is_archived is False


class TestEDGPDatabaseServiceInitialization:
    """Test EDGPDatabaseService initialization"""
    
    def test_service_initialization(self):
        """Test service creates with default values"""
        service = EDGPDatabaseService()
        
        assert service.connection_config is None
        assert service.pool is None
        assert service.is_aws_rds is False
    
    def test_service_initialization_logging(self, caplog):
        """Test service logs initialization"""
        service = EDGPDatabaseService()
        
        assert "Initialized Enhanced EDGP Database Service" in caplog.text


class TestBuildConnectionConfig:
    """Test _build_connection_config method"""
    
    @pytest.mark.asyncio
    async def test_build_config_local_mysql(self):
        """Test building config for local MySQL"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings:
            mock_settings.edgp_db_host = 'localhost'
            mock_settings.edgp_db_port = 3306
            mock_settings.edgp_db_username = 'testuser'
            mock_settings.edgp_db_password = 'testpass'
            mock_settings.edgp_db_name = 'testdb'
            mock_settings.aws_rds_enabled = False
            mock_settings.aws_secrets_manager_enabled = False
            mock_settings.aws_rds_secret_name = None
            mock_settings.aws_rds_database = None
            
            config = await service._build_connection_config()
            
            assert config['host'] == 'localhost'
            assert config['port'] == 3306
            assert config['user'] == 'testuser'
            assert config['password'] == 'testpass'
            assert config['db'] == 'testdb'
            assert config['charset'] == 'utf8mb4'
            assert config['autocommit'] is True
            assert service.is_aws_rds is False
    
    @pytest.mark.asyncio
    async def test_build_config_local_default_host(self):
        """Test building config with default localhost"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings:
            mock_settings.edgp_db_host = None
            mock_settings.edgp_db_port = 3306
            mock_settings.edgp_db_username = 'testuser'
            mock_settings.edgp_db_password = 'testpass'
            mock_settings.edgp_db_name = 'testdb'
            mock_settings.aws_rds_enabled = False
            mock_settings.aws_secrets_manager_enabled = False
            
            config = await service._build_connection_config()
            
            assert config['host'] == 'localhost'
            assert service.is_aws_rds is False
    
    @pytest.mark.asyncio
    async def test_build_config_missing_database_name(self):
        """Test error when database name is missing"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings:
            mock_settings.edgp_db_name = None
            mock_settings.aws_rds_database = None
            mock_settings.aws_rds_enabled = False
            
            with pytest.raises(ValueError, match="EDGP_DB_NAME is required"):
                await service._build_connection_config()
    
    @pytest.mark.asyncio
    async def test_build_config_missing_local_credentials(self):
        """Test error when local credentials are missing"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings:
            mock_settings.edgp_db_host = 'localhost'
            mock_settings.edgp_db_name = 'testdb'
            mock_settings.edgp_db_username = None
            mock_settings.edgp_db_password = None
            mock_settings.aws_rds_enabled = False
            mock_settings.aws_secrets_manager_enabled = False
            
            with pytest.raises(Exception, match="Missing username or password"):
                await service._build_connection_config()
    
    @pytest.mark.asyncio
    async def test_build_config_aws_rds_with_secrets_manager(self):
        """Test building config for AWS RDS with Secrets Manager"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings, \
             patch('src.compliance_agent.services.edgp_database_service_simple.AWSRDSConfig') as mock_rds_config:
            
            mock_settings.edgp_db_host = 'rds.amazonaws.com'
            mock_settings.edgp_db_port = 3306
            mock_settings.edgp_db_name = 'proddb'
            mock_settings.aws_rds_enabled = True
            mock_settings.aws_secrets_manager_enabled = True
            mock_settings.aws_rds_secret_name = 'prod-db-secret'
            mock_settings.aws_region = 'us-west-2'
            
            mock_config = {
                'host': 'rds.amazonaws.com',
                'port': 3306,
                'db': 'proddb',
                'user': 'admin',
                'password': 'secret123',
                'charset': 'utf8mb4',
                'autocommit': True
            }
            
            mock_rds_config.build_connection_config.return_value = mock_config.copy()
            mock_rds_config.resolve_credentials = AsyncMock(return_value=mock_config)
            
            config = await service._build_connection_config()
            
            assert service.is_aws_rds is True
            assert config['db'] == 'proddb'
    
    @pytest.mark.asyncio
    async def test_build_config_aws_rds_secrets_manager_error(self):
        """Test error handling when Secrets Manager fails"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings, \
             patch('src.compliance_agent.services.edgp_database_service_simple.AWSRDSConfig') as mock_rds_config:
            
            mock_settings.edgp_db_host = 'rds.amazonaws.com'
            mock_settings.edgp_db_name = 'proddb'
            mock_settings.aws_rds_enabled = True
            mock_settings.aws_secrets_manager_enabled = True
            mock_settings.aws_rds_secret_name = 'prod-db-secret'
            mock_settings.aws_region = 'us-west-2'
            
            mock_rds_config.build_connection_config.return_value = {'secret_name': 'test'}
            mock_rds_config.resolve_credentials = AsyncMock(
                side_effect=Exception("Secrets Manager unavailable")
            )
            
            with pytest.raises(Exception, match="Unable to load credentials from Secrets Manager"):
                await service._build_connection_config()
            
            assert service.is_aws_rds is False
    
    @pytest.mark.asyncio
    async def test_build_config_aws_rds_direct_credentials(self):
        """Test AWS RDS with direct credentials (no Secrets Manager)"""
        service = EDGPDatabaseService()
        
        with patch('src.compliance_agent.services.edgp_database_service_simple.settings') as mock_settings, \
             patch('src.compliance_agent.services.edgp_database_service_simple.AWSRDSConfig') as mock_rds_config, \
             patch('src.compliance_agent.services.edgp_database_service_simple.RDSConnectionValidator'):
            
            mock_settings.edgp_db_host = 'rds.amazonaws.com'
            mock_settings.edgp_db_port = 3306
            mock_settings.edgp_db_username = 'admin'
            mock_settings.edgp_db_password = 'password123'
            mock_settings.edgp_db_name = 'proddb'
            mock_settings.aws_rds_enabled = True
            mock_settings.aws_secrets_manager_enabled = False  # No secrets manager
            mock_settings.aws_rds_secret_name = None
            mock_settings.aws_rds_database = None
            
            mock_config = {
                'host': 'rds.amazonaws.com',
                'port': 3306,
                'db': 'proddb',
                'user': 'admin',
                'password': 'password123'
            }
            mock_rds_config.build_connection_config.return_value = mock_config
            
            config = await service._build_connection_config()
            
            # With aws_secrets_manager_enabled=False, is_aws_rds remains False
            # because the code requires BOTH aws_rds_enabled AND aws_secrets_manager_enabled to be True
            assert service.is_aws_rds is False
            # But config still comes from local settings
            assert config['host'] == 'rds.amazonaws.com'
            assert config['user'] == 'admin'


class TestDatabaseInitialization:
    """Test initialize method"""
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful database initialization"""
        service = EDGPDatabaseService()
        
        mock_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'testuser',
            'password': 'testpass',
            'db': 'testdb',
            'charset': 'utf8mb4',
            'autocommit': True
        }
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        # Setup cursor to return success for test query
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        mock_pool.maxsize = 5
        
        with patch.object(service, '_build_connection_config', return_value=mock_config), \
             patch('src.compliance_agent.services.edgp_database_service_simple.aiomysql.create_pool', 
                   return_value=mock_pool):
            
            await service.initialize()
            
            assert service.connection_config == mock_config
            assert service.pool == mock_pool
    
    @pytest.mark.asyncio
    async def test_initialize_no_config(self):
        """Test initialization fails when config is None"""
        service = EDGPDatabaseService()
        
        with patch.object(service, '_build_connection_config', return_value=None):
            with pytest.raises(Exception, match="No valid connection configuration"):
                await service.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self):
        """Test initialization fails on connection error"""
        service = EDGPDatabaseService()
        
        mock_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'testuser',
            'password': 'wrongpass',
            'db': 'testdb'
        }
        
        with patch.object(service, '_build_connection_config', return_value=mock_config), \
             patch('src.compliance_agent.services.edgp_database_service_simple.aiomysql.create_pool',
                   side_effect=Exception("Connection refused")):
            
            with pytest.raises(Exception, match="Database connection failed"):
                await service.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_aws_rds_larger_pool(self):
        """Test AWS RDS uses larger connection pool"""
        service = EDGPDatabaseService()
        service.is_aws_rds = True
        
        mock_config = {'host': 'rds.amazonaws.com', 'db': 'proddb'}
        mock_pool = AsyncMock()
        mock_pool.maxsize = 10
        
        # Setup mock for test connection
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        
        with patch.object(service, '_build_connection_config', return_value=mock_config), \
             patch('src.compliance_agent.services.edgp_database_service_simple.aiomysql.create_pool',
                   return_value=mock_pool) as mock_create:
            
            await service.initialize()
            
            # Verify maxsize=10 was used for AWS RDS
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs['maxsize'] == 10


class TestTestConnection:
    """Test _test_connection method"""
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection test"""
        service = EDGPDatabaseService()
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        service.pool = mock_pool
        
        await service._test_connection()
        
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_test_connection_no_pool(self):
        """Test connection test returns early if no pool"""
        service = EDGPDatabaseService()
        service.pool = None
        
        # Should not raise error, just return
        await service._test_connection()
    
    @pytest.mark.asyncio
    async def test_test_connection_query_failure(self):
        """Test connection test fails on query error"""
        service = EDGPDatabaseService()
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        mock_cursor.fetchone = AsyncMock(return_value=(0,))  # Wrong result
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        service.pool = mock_pool
        
        with pytest.raises(Exception, match="Database test query failed"):
            await service._test_connection()


class TestGetCustomers:
    """Test get_customers method"""
    
    @pytest.mark.asyncio
    async def test_get_customers_success(self):
        """Test retrieving customers from database"""
        service = EDGPDatabaseService()
        
        now = datetime.utcnow()
        mock_rows = [
            (1, 'john@example.com', '+65-1234', 'John', 'Doe', 
             now, now, False, 'example.com', 'WF-001'),
            (2, 'jane@test.com', '+65-5678', 'Jane', 'Smith',
             now, now, False, 'test.com', 'WF-002'),
        ]
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        mock_pool.maxsize = 5
        service.pool = mock_pool
        service.connection_config = {'host': 'localhost', 'db': 'testdb'}
        
        customers = await service.get_customers()
        
        assert len(customers) == 2
        assert customers[0].id == 1
        assert customers[0].email == 'john@example.com'
        assert customers[0].firstname == 'John'
        assert customers[1].id == 2
        assert customers[1].email == 'jane@test.com'
    
    @pytest.mark.asyncio
    async def test_get_customers_empty_result(self):
        """Test retrieving when no customers exist"""
        service = EDGPDatabaseService()
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        mock_pool.maxsize = 5
        service.pool = mock_pool
        service.connection_config = {'host': 'localhost', 'db': 'testdb'}
        
        customers = await service.get_customers()
        
        assert len(customers) == 0
    
    @pytest.mark.asyncio
    async def test_get_customers_no_pool(self):
        """Test error when no database pool available"""
        service = EDGPDatabaseService()
        service.pool = None
        
        with pytest.raises(Exception, match="No database connection available"):
            await service.get_customers()
    
    @pytest.mark.asyncio
    async def test_get_customers_query_failure(self):
        """Test error handling on query failure"""
        service = EDGPDatabaseService()
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        mock_cursor.execute = AsyncMock(side_effect=Exception("Query failed"))
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        mock_pool.maxsize = 5
        service.pool = mock_pool
        service.connection_config = {'host': 'localhost', 'db': 'testdb'}
        
        with pytest.raises(Exception, match="Database query failed"):
            await service.get_customers()
    
    @pytest.mark.asyncio
    async def test_get_customers_with_nulls(self):
        """Test handling of NULL values in customer data"""
        service = EDGPDatabaseService()
        
        now = datetime.utcnow()
        mock_rows = [
            (1, None, None, None, None, now, now, None, None, None),
        ]
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        mock_pool.maxsize = 5
        service.pool = mock_pool
        service.connection_config = {'host': 'localhost', 'db': 'testdb'}
        
        customers = await service.get_customers()
        
        assert len(customers) == 1
        assert customers[0].id == 1
        assert customers[0].email is None
        assert customers[0].phone is None
        assert customers[0].is_archived is False


class TestMockCustomers:
    """Test _get_mock_customers method"""
    
    def test_get_mock_customers_count(self):
        """Test mock customers generation returns expected count"""
        service = EDGPDatabaseService()
        
        mock_customers = service._get_mock_customers()
        
        assert len(mock_customers) == 5
    
    def test_get_mock_customers_data_quality(self):
        """Test mock customers have valid data"""
        service = EDGPDatabaseService()
        
        mock_customers = service._get_mock_customers()
        
        for customer in mock_customers:
            assert customer.id > 0
            assert customer.email is not None
            assert '@' in customer.email
            assert customer.firstname is not None
            assert customer.lastname is not None
            assert customer.created_date is not None
            assert customer.updated_date is not None
            assert isinstance(customer.is_archived, bool)
    
    def test_get_mock_customers_archived_data(self):
        """Test mock customers include archived record"""
        service = EDGPDatabaseService()
        
        mock_customers = service._get_mock_customers()
        
        # Should have at least one archived customer
        archived_customers = [c for c in mock_customers if c.is_archived]
        assert len(archived_customers) > 0
    
    def test_get_mock_customers_various_ages(self):
        """Test mock customers have various creation dates"""
        service = EDGPDatabaseService()
        
        mock_customers = service._get_mock_customers()
        
        # Customers should have different ages
        creation_dates = [c.created_date for c in mock_customers]
        unique_dates = set(creation_dates)
        assert len(unique_dates) == len(mock_customers)


class TestClose:
    """Test close method"""
    
    @pytest.mark.asyncio
    async def test_close_with_pool(self):
        """Test closing database connections"""
        service = EDGPDatabaseService()
        
        mock_pool = AsyncMock()
        mock_pool.close = MagicMock()
        mock_pool.wait_closed = AsyncMock()
        
        service.pool = mock_pool
        
        await service.close()
        
        mock_pool.close.assert_called_once()
        mock_pool.wait_closed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_without_pool(self):
        """Test close when no pool exists"""
        service = EDGPDatabaseService()
        service.pool = None
        
        # Should not raise error
        await service.close()


class TestIntegration:
    """Integration tests for full workflow"""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle_local_mysql(self):
        """Test complete workflow with local MySQL"""
        service = EDGPDatabaseService()
        
        mock_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'testuser',
            'password': 'testpass',
            'db': 'testdb',
            'charset': 'utf8mb4',
            'autocommit': True
        }
        
        now = datetime.utcnow()
        mock_rows = [
            (1, 'test@example.com', '+65-1234', 'Test', 'User',
             now, now, False, 'example.com', 'WF-001'),
        ]
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        
        # Setup for test connection
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        # Setup for get customers
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        
        # Use AsyncContextManagerMock for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
        mock_pool.maxsize = 5
        mock_pool.close = MagicMock()
        mock_pool.wait_closed = AsyncMock()
        
        with patch.object(service, '_build_connection_config', return_value=mock_config), \
             patch('src.compliance_agent.services.edgp_database_service_simple.aiomysql.create_pool',
                   return_value=mock_pool):
            
            # Initialize
            await service.initialize()
            assert service.pool is not None
            
            # Get customers
            customers = await service.get_customers()
            assert len(customers) == 1
            assert customers[0].email == 'test@example.com'
            
            # Close
            await service.close()
            mock_pool.close.assert_called_once()
