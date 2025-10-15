"""
Simple Database Service for EDGP Master Data Connection
Using direct aiomysql without SQLAlchemy for Python 3.13 compatibility
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

import aiomysql

from config.settings import settings

logger = logging.getLogger(__name__)


class CustomerData:
    """Simple customer data class"""
    def __init__(self, id: int, email: str = None, phone: str = None, 
                 firstname: str = None, lastname: str = None,
                 created_date: datetime = None, updated_date: datetime = None,
                 is_archived: bool = False, domain_name: str = None):
        self.id = id
        self.email = email
        self.phone = phone
        self.firstname = firstname
        self.lastname = lastname
        self.created_date = created_date
        self.updated_date = updated_date
        self.is_archived = is_archived
        self.domain_name = domain_name


class EDGPDatabaseService:
    """Simple service for connecting to EDGP master data database"""
    
    def __init__(self):
        self.connection_config = self._build_connection_config()
        self.pool = None
        
        logger.info("Initialized EDGP Database Service (Simple)")
    
    def _build_connection_config(self) -> dict:
        """Build database connection configuration"""
        
        host = getattr(settings, 'edgp_db_host', 'localhost')
        port = getattr(settings, 'edgp_db_port', 3306)
        username = getattr(settings, 'edgp_db_username', 'root')
        password = getattr(settings, 'edgp_db_password', 'password')
        database = getattr(settings, 'edgp_db_name', 'edgp_masterdata')
        
        config = {
            'host': host,
            'port': port,
            'user': username,
            'password': password,
            'db': database,
            'charset': 'utf8mb4',
            'autocommit': True
        }
        
        logger.info(f"Database config: host={host}, database={database}")
        return config
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            # For development, use a mock approach if no real database
            # This allows the compliance agent to work without a real database
            try:
                self.pool = await aiomysql.create_pool(
                    minsize=1,
                    maxsize=5,
                    **self.connection_config
                )
                await self._test_connection()
                logger.info("EDGP Database Service initialized successfully with real database")
            except Exception as db_error:
                logger.warning(f"Could not connect to real database: {db_error}")
                logger.info("Using mock database mode for compliance agent")
                self.pool = None  # Use mock mode
            
        except Exception as e:
            logger.error(f"Failed to initialize database service: {str(e)}")
            # Don't raise error, allow mock mode
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
                               created_date, updated_date, is_archived, domain_name
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
                                domain_name=row[8]
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
                domain_name="example.com"
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
                domain_name="example.com"
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
                domain_name="example.com"
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