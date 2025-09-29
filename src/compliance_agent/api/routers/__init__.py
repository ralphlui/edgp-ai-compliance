"""
Routers package initialization
"""

from . import compliance_router, privacy_router, governance_router, remediation_router

__all__ = ["compliance_router", "privacy_router", "governance_router", "remediation_router"]