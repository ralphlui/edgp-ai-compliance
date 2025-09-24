#!/usr/bin/env python3
"""
Application entry point
Run the AI Compliance Agent API server
"""

import uvicorn
import sys
import os
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.compliance_agent.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if not settings.debug else 1,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )