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
                config = await AWSRDSConfig.resolve_credentials(config)
                
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
                raise ValueError("EDGP_DB_USERNAME and EDGP_DB_PASSWORD are required for local MySQL")
            
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
                logger.warning(f"Could not connect to database: {db_error}")
                if self.is_aws_rds:
                    # For AWS RDS, this is a critical error
                    raise db_error
                else:
                    # For local development, allow fallback to mock mode
                    logger.info("Using mock database mode for compliance agent")
                    self.pool = None
            
        except Exception as e:
            logger.error(f"Failed to initialize database service: {str(e)}")
            if self.is_aws_rds:
                # Don't allow mock mode for AWS RDS
                raise e
            else:
                # Allow mock mode for local development
                self.pool = None
    
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
                # Fall back to mock data
                return self._get_mock_customers()
        else:
            # Mock data for testing when no database is available
            return self._get_mock_customers()
    
    def _get_mock_customers(self) -> List[CustomerData]:
        """Generate mock customer data for testing compliance agent"""
        
        mock_customers = [
            # Old customer data that should trigger compliance violations
            CustomerData(
                id=1,
                email="old.customer@example.com",
                phone="+6591234567",
                firstname="Old",
                lastname="Customer",
                created_date=datetime.now() - timedelta(days=8*365),  # 8 years old
                updated_date=datetime.now() - timedelta(days=4*365),  # Last activity 4 years ago
                is_archived=False,
                domain_name="example.com",
                workflow_tracker_id="WF_TRACK_001"
            ),
            # Recent customer data that should be compliant
            CustomerData(
                id=2,
                email="recent.customer@example.com",
                phone="+6591234568",
                firstname="Recent",
                lastname="Customer",
                created_date=datetime.now() - timedelta(days=30),  # 30 days old
                updated_date=datetime.now() - timedelta(days=1),   # Recent activity
                is_archived=False,
                domain_name="example.com",
                workflow_tracker_id="WF_TRACK_002"
            ),
            # Inactive customer that exceeds retention limit
            CustomerData(
                id=3,
                email="inactive.customer@example.com",
                phone="+6591234569",
                firstname="Inactive",
                lastname="Customer",
                created_date=datetime.now() - timedelta(days=5*365),  # 5 years old
                updated_date=datetime.now() - timedelta(days=4*365),  # No activity for 4 years
                is_archived=False,
                domain_name="example.com",
                workflow_tracker_id="WF_TRACK_003"
            )
        ]
        
        logger.info(f"Generated {len(mock_customers)} mock customer records for compliance testing")
        return mock_customers
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connections closed")