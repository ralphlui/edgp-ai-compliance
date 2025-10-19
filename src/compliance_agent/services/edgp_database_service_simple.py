"""
Enhanced Database Service for EDGP Master Data Connection
Supports both local MySQL and AWS RDS with Secrets Manager
Using direct aiomysql without SQLAlchemy for Python 3.13 compatibility
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

import aiomysql

from config.settings import settings
from .aws_rds_service import AWSRDSConfig, RDSConnectionValidator

logger = logging.getLogger(__name__)


class CustomerData:
    """Simple customer data class"""
    def __init__(self, id: int, email: str = None, phone: str = None, 
                 firstname: str = None, lastname: str = None,
                 created_date: datetime = None, updated_date: datetime = None,
                 is_archived: bool = False, domain_name: str = None,
                 workflow_tracker_id: str = None):
        self.id = id
        self.email = email
        self.phone = phone
        self.firstname = firstname
        self.lastname = lastname
        self.created_date = created_date
        self.updated_date = updated_date
        self.is_archived = is_archived
        self.domain_name = domain_name
        self.workflow_tracker_id = workflow_tracker_id
        self.created_date = created_date
        self.updated_date = updated_date
        self.is_archived = is_archived
        self.domain_name = domain_name


class EDGPDatabaseService:
    """Enhanced service for connecting to EDGP master data database with AWS RDS support"""
    
    def __init__(self):
        self.connection_config = None
        self.pool = None
        self.is_aws_rds = False
        
        logger.info("Initialized Enhanced EDGP Database Service")
    
    async def _build_connection_config(self) -> dict:
        """Build database connection configuration with auto-detection of AWS RDS vs Local"""
        
        # Get basic database configuration
        host = getattr(settings, 'edgp_db_host', None)
        port = getattr(settings, 'edgp_db_port', 3306)
        username = getattr(settings, 'edgp_db_username', None)
        password = getattr(settings, 'edgp_db_password', None)
        secret_name = getattr(settings, 'edgp_db_secret_name', None)
        database = getattr(settings, 'edgp_db_name', None)
        
        if not database:
            raise ValueError("EDGP_DB_NAME is required in environment configuration")
        
        # Auto-detect if this is AWS RDS or local based on host and secret_name
        is_aws_rds = False
        
        # Check if it's AWS RDS by looking for AWS RDS hostname pattern or secret name
        if host and ('rds.amazonaws.com' in host or secret_name):
            is_aws_rds = True
            self.is_aws_rds = True
            logger.info("AWS RDS mode detected")
        else:
            self.is_aws_rds = False
            logger.info("Local MySQL mode detected")
        
        if is_aws_rds:
            # AWS RDS Configuration
            if not host:
                raise ValueError("EDGP_DB_HOST is required for AWS RDS connection")
            
            if secret_name:
                # Use AWS Secrets Manager
                logger.info(f"Using AWS Secrets Manager for credentials: {secret_name}")
                region = getattr(settings, 'aws_region', 'ap-southeast-1')
                
                # Get credentials from Secrets Manager
                config = AWSRDSConfig.build_connection_config(
                    host=host,
                    port=port,
                    database=database,
                    secret_name=secret_name,
                    region=region,
                    use_secrets_manager=True
                )
                
                # Resolve credentials from Secrets Manager
                try:
                    config = await AWSRDSConfig.resolve_credentials(config)
                except Exception as exc:
                    logger.error(
                        "Unable to load credentials from Secrets Manager (%s). "
                        "Database connection failed.",
                        exc,
                    )
                    # Don't fallback to mock mode - let the error propagate
                    self.is_aws_rds = False
                    raise Exception(f"Database configuration failed: Unable to load credentials from Secrets Manager: {exc}")
                
            elif username and password:
                # Use direct credentials for AWS RDS
                logger.info("Using direct credentials for AWS RDS connection")
                config = AWSRDSConfig.build_connection_config(
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password=password,
                    use_secrets_manager=False
                )
            else:
                raise ValueError("Either EDGP_DB_SECRET_NAME or EDGP_DB_USERNAME/EDGP_DB_PASSWORD must be provided for AWS RDS")
            
            # Validate the configuration
            RDSConnectionValidator.validate_config(config)
            
        else:
            # Local MySQL Configuration
            if not host:
                host = 'localhost'  # Default for local
            
            if not username or not password:
                logger.error("Missing local database credentials. Please provide database username and password.")
                raise Exception("Database configuration incomplete: Missing username or password")
            
            config = {
                'host': host,
                'port': port,
                'user': username,
                'password': password,
                'db': database,
                'charset': 'utf8mb4',
                'autocommit': True
            }
        
        logger.info(f"Database config built: host={config['host']}, database={config['db']}, aws_rds={self.is_aws_rds}")
        return config
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            # Build connection config (async for AWS RDS Secrets Manager support)
            self.connection_config = await self._build_connection_config()

            if not self.connection_config:
                logger.error("Database connection configuration unavailable.")
                raise Exception("Database configuration failed: No valid connection configuration available")
            
            # Try to establish connection pool
            try:
                self.pool = await aiomysql.create_pool(
                    minsize=1,
                    maxsize=10 if self.is_aws_rds else 5,  # More connections for AWS RDS
                    **self.connection_config
                )
                await self._test_connection()
                
                connection_type = "AWS RDS" if self.is_aws_rds else "Local MySQL"
                logger.info(f"EDGP Database Service initialized successfully with {connection_type}")
                
            except Exception as db_error:
                logger.error(f"Could not connect to database: {db_error}")
                # Don't allow fallback - raise the error
                raise Exception(f"Database connection failed: {db_error}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database service: {str(e)}")
            # Don't allow mock mode - raise the error
            raise e
    
    async def _test_connection(self):
        """Test database connection"""
        if not self.pool:
            return
            
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                if not (result and result[0] == 1):
                    raise Exception("Database test query failed")
    
    async def get_customers(self) -> List[CustomerData]:
        """Get all customers from the database or mock data for testing"""
        
        if self.pool:
            # Real database query
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        query = """
                        SELECT id, email, phone, firstname, lastname, 
                               created_date, updated_date, is_archived, domain_name, workflow_tracker_id
                        FROM customer 
                        ORDER BY created_date DESC
                        """
                        await cursor.execute(query)
                        rows = await cursor.fetchall()
                        
                        customers = []
                        for row in rows:
                            customer = CustomerData(
                                id=row[0],
                                email=row[1],
                                phone=row[2],
                                firstname=row[3],
                                lastname=row[4],
                                created_date=row[5],
                                updated_date=row[6],
                                is_archived=bool(row[7]) if row[7] is not None else False,
                                domain_name=row[8],
                                workflow_tracker_id=row[9]
                            )
                            customers.append(customer)
                        
                        logger.info(f"Retrieved {len(customers)} customer records from database")
                        return customers
                        
            except Exception as e:
                logger.error(f"Failed to query customers from database: {str(e)}")
                # Don't fall back to mock data - raise the error
                raise Exception(f"Database query failed: {str(e)}")
        else:
            # No database connection available
            raise Exception("No database connection available. Please check database configuration.")
    
    def _get_mock_customers(self) -> List[CustomerData]:
        """
        Generate mock customer data for testing purposes
        Returns a list of mock CustomerData objects
        """
        now = datetime.now()

        mock_customers = [
            CustomerData(
                id=1,
                email="customer1@example.com",
                phone="+65-1234-5678",
                firstname="John",
                lastname="Doe",
                created_date=now - timedelta(days=365*8),  # 8 years ago
                updated_date=now - timedelta(days=30),
                is_archived=False,
                domain_name="example.com",
                workflow_tracker_id="WF-001"
            ),
            CustomerData(
                id=2,
                email="customer2@example.eu",
                phone="+44-2345-6789",
                firstname="Jane",
                lastname="Smith",
                created_date=now - timedelta(days=365*10),  # 10 years ago
                updated_date=now - timedelta(days=60),
                is_archived=False,
                domain_name="example.eu",
                workflow_tracker_id="WF-002"
            ),
            CustomerData(
                id=3,
                email="customer3@test.sg",
                phone="+65-9876-5432",
                firstname="Alice",
                lastname="Tan",
                created_date=now - timedelta(days=365*2),  # 2 years ago
                updated_date=now - timedelta(days=10),
                is_archived=False,
                domain_name="test.sg",
                workflow_tracker_id="WF-003"
            ),
            CustomerData(
                id=4,
                email="old_customer@archived.com",
                phone="+1-555-1234",
                firstname="Bob",
                lastname="Johnson",
                created_date=now - timedelta(days=365*15),  # 15 years ago
                updated_date=now - timedelta(days=365*5),  # Not updated in 5 years
                is_archived=True,
                domain_name="archived.com",
                workflow_tracker_id="WF-004"
            ),
            CustomerData(
                id=5,
                email="recent@newdomain.com",
                phone="+65-8888-9999",
                firstname="Charlie",
                lastname="Lee",
                created_date=now - timedelta(days=180),  # 6 months ago
                updated_date=now - timedelta(days=1),
                is_archived=False,
                domain_name="newdomain.com",
                workflow_tracker_id="WF-005"
            )
        ]

        logger.info(f"Generated {len(mock_customers)} mock customers for testing")
        return mock_customers

    async def close(self):
        """Close database connections"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connections closed")
