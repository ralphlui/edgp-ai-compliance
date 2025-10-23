from types import SimpleNamespace

import pytest

from src.compliance_agent.services import llm_service as llm_module


@pytest.fixture
def llm_service(monkeypatch):
    fake_openai = SimpleNamespace(
        api_key=None,
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"description": "Parsed"}'))
        ]))),
        embeddings=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(data=[SimpleNamespace(embedding=[0.42])]))
    )
    monkeypatch.setattr(llm_module, "get_openai_api_key", lambda secret_name=None: "test-key")

    monkeypatch.setattr(
        "src.compliance_agent.services.ai_secrets_service.get_openai_api_key",
        lambda secret_name=None: "test-key",
        raising=False,
    )
    monkeypatch.setattr(llm_module, "openai", fake_openai)

    return llm_module.LLMComplianceService(), fake_openai


@pytest.mark.asyncio
async def test_llm_initialize_sets_api_key(llm_service):
    service, fake_openai = llm_service

    initialized = await service.initialize(secret_name="dummy-secret")

    assert initialized is True
    assert service.is_initialized is True
    assert fake_openai.api_key == "test-key"


@pytest.mark.asyncio
async def test_generate_compliance_suggestion_fallback_when_uninitialized():
    service = llm_module.LLMComplianceService()
    service.is_initialized = False

    suggestion = await service.generate_compliance_suggestion({"excess_days": 10}, framework="PDPA")

    assert suggestion["urgency_level"] == "MEDIUM"
    assert "PDPA Section" in suggestion["legal_reference"]


def test_create_compliance_prompt_contains_violation_details(llm_service):
    service, _ = llm_service
    violation = {
        "customer_id": "123",
        "data_age_days": 900,
        "retention_limit_days": 365,
        "excess_days": 535,
        "violation_type": "DATA_RETENTION_EXCEEDED",
    }

    prompt = service._create_compliance_prompt(violation, "GDPR")

    assert "Customer ID: 123" in prompt
    assert "Framework: GDPR" in prompt


def test_parse_llm_response_handles_json(llm_service):
    service, _ = llm_service
    raw = '{"description":"Issue","recommendation":"Act","legal_reference":"Ref","urgency_level":"LOW","compliance_impact":"Minor"}'

    parsed = service._parse_llm_response(raw)

    assert parsed["description"] == "Issue"
    assert parsed["urgency_level"] == "LOW"


def test_parse_llm_response_handles_text(llm_service):
    service, _ = llm_service
    parsed = service._parse_llm_response("Plain text response")

    assert parsed["urgency_level"] == "HIGH"
    assert "Plain text" in parsed["description"]


@pytest.mark.asyncio
async def test_generate_remediation_plan_uses_fallback_when_uninitialized():
    service = llm_module.LLMComplianceService()
    plan = await service.generate_remediation_plan([{"customer_id": "123"}], framework="GDPR")

    assert "priority_actions" in plan
    assert plan["priority_actions"], "Expected fallback actions to be populated"


def test_format_violations_for_prompt_limits_entries(llm_service):
    service, _ = llm_service
    text = service._format_violations_for_prompt(
        [{"customer_id": str(i), "excess_days": i * 10} for i in range(1, 10)]
    )

    assert text.count("\n") <= 4
