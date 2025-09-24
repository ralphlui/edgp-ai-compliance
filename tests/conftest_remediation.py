"""
Test configuration for remediation agent tests.
"""

import pytest
import asyncio
from typing import Generator


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# TODO: Add remediation agent specific fixtures
# TODO: Add mock services for testing
# TODO: Add test data fixtures
# TODO: Add integration test setup