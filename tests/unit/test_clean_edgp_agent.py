from datetime import datetime, timedelta

import pytest

from src.compliance_agent import clean_edgp_agent as agent_module


class _DBStub:
    def __init__(self, customers=None):
        self.customers = customers or []
        self.initialized = False
        self.closed = False

    async def initialize(self):
        self.initialized = True
        return True

    async def get_customers(self):
        return self.customers

    async def close(self):
        self.closed = True


class _AIAnalyzerStub:
    async def initialize(self):
        return True


class _RemediationStub:
    def __init__(self):
        self.calls = []

    async def trigger_remediation(self, violation):
        self.calls.append(violation)
        return True


@pytest.fixture
def agent(monkeypatch):
    db_stub = _DBStub()
    monkeypatch.setattr(agent_module, "EDGPDatabaseService", lambda: db_stub)
    monkeypatch.setattr(agent_module, "AIComplianceAnalyzer", lambda: _AIAnalyzerStub())
    monkeypatch.setattr(agent_module, "ComplianceRemediationService", lambda: _RemediationStub())

    compliance_agent = agent_module.CleanEDGPComplianceAgent()
    compliance_agent.db_service = db_stub
    compliance_agent.remediation_service = compliance_agent.remediation_service  # type: ignore[attr-defined]
    return compliance_agent


@pytest.mark.asyncio
async def test_agent_initialize_calls_database(agent):
    assert await agent.initialize() is True
    assert agent.db_service.initialized is True


@pytest.mark.asyncio
async def test_scan_customer_compliance_detects_violation(agent, monkeypatch):
    class CustomerStub:
        def __init__(self, created_days, updated_days, archived=False):
            now = datetime.utcnow()
            self.id = 1
            self.created_date = now - timedelta(days=created_days)
            self.updated_date = now - timedelta(days=updated_days)
            self.is_archived = archived
            self.retention_period_years = 1
            self.firstname = "Ada"
            self.lastname = "Lovelace"
            self.email = "ada@example.com"
            self.phone = "1234"
            self.domain_name = "example.com"

        def dict(self):
            return {"id": self.id}

    customer = CustomerStub(created_days=2000, updated_days=1900)
    agent.db_service.customers = [customer]

    async def fake_analysis(customer, data_age, retention_limit):
        return {
            "severity": "HIGH",
            "description": "Over retention limit",
            "recommended_action": "Delete immediately",
        }

    remediation_calls = []

    async def fake_trigger(violation):
        remediation_calls.append(violation)

    monkeypatch.setattr(agent, "_get_ai_violation_analysis", fake_analysis)
    monkeypatch.setattr(agent, "_trigger_remediation", fake_trigger)

    violations = await agent.scan_customer_compliance()

    assert len(violations) == 1
    assert violations[0].severity == "HIGH"
    assert remediation_calls, "High severity violation should trigger remediation"


def test_get_retention_limit(agent):
    class CustomerSimple:
        def __init__(self, archived=False):
            self.is_archived = archived

    customer = CustomerSimple()
    limit = agent._get_retention_limit(customer, last_activity_age=100)
    assert limit == agent.retention_limits["customer_default"]

    archived_customer = CustomerSimple(archived=True)
    assert agent._get_retention_limit(archived_customer, 10) == agent.retention_limits["deleted_customer"]

    inactive_customer = CustomerSimple()
    assert agent._get_retention_limit(inactive_customer, last_activity_age=800) == agent.retention_limits["inactive_customer"]
