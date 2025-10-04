# Remediation Agent Test Suite

This directory contains comprehensive unit tests for the remediation agent components. The test suite covers all major components including agents, tools, models, and the LangGraph workflow orchestration.

## 📁 Test Structure

```
tests/remediation/
├── __init__.py                    # Package initialization
├── conftest_remediation.py       # Test configuration and fixtures
├── run_tests.py                   # Test runner script
├── unit/                          # Unit tests directory
│   ├── __init__.py
│   ├── test_models.py            # State model tests
│   ├── test_decision_agent.py    # Decision agent tests
│   ├── test_validation_agent.py  # Validation agent tests
│   ├── test_workflow_agent.py    # Workflow agent tests
│   ├── test_sqs_tool.py          # SQS tool tests
│   ├── test_notification_tool.py # Notification tool tests
│   ├── test_remediation_validator.py # Validator tests
│   └── test_remediation_graph.py # LangGraph workflow tests
```

## 🧪 Test Coverage

### Models (`test_models.py`)
- **RemediationDecision**: Decision types, validation, serialization
- **WorkflowStep**: Step creation, status transitions, prerequisites
- **RemediationWorkflow**: Workflow orchestration, step management
- **RemediationSignal**: Signal creation, context handling
- **RemediationState**: State management, transitions

### Agents

#### Decision Agent (`test_decision_agent.py`)
- **Automatic Decisions**: Low-risk operations, simple actions
- **Human-in-Loop**: Medium-risk data operations, approval workflows
- **Manual-Only**: High-risk/critical operations, complex scenarios
- **LLM Integration**: Response parsing, error handling, fallbacks
- **Risk Assessment**: Complexity analysis, cross-system impact

#### Validation Agent (`test_validation_agent.py`)
- **Feasibility Assessment**: Action classification, automation patterns
- **Blocker Identification**: Risk-based constraints, system dependencies
- **Prerequisites**: Data backups, approvals, system readiness
- **Automation Recommendations**: Confidence scoring, pattern matching
- **Edge Cases**: Empty actions, complex operations, validation consistency

#### Workflow Agent (`test_workflow_agent.py`)
- **Workflow Orchestration**: Step creation, dependency analysis
- **Step Types**: Automated, manual, approval-required
- **Execution Planning**: Duration estimation, parallel execution
- **Dependency Management**: Sequential vs parallel step identification
- **Error Handling**: Invalid inputs, missing data

### Tools

#### SQS Tool (`test_sqs_tool.py`)
- **Message Operations**: Send, receive, delete, batch operations
- **Queue Management**: Attributes, visibility timeout, dead letter queues
- **Error Handling**: Connection failures, service unavailability
- **Message Attributes**: Priority, metadata, filtering
- **Configuration**: Queue URLs, regions, credentials

#### Notification Tool (`test_notification_tool.py`)
- **Workflow Notifications**: Started, completed, failed, approval required
- **Email System**: SMTP integration, HTML templates, error handling
- **Slack Integration**: Webhook delivery, channel routing, formatting
- **Alert Severity**: Risk-based routing, escalation paths
- **Template System**: Dynamic content, localization support

#### Remediation Validator (`test_remediation_validator.py`)
- **Step Validation**: Database state, system availability, prerequisites
- **Data Integrity**: Backup verification, relationship checks, orphaned records
- **Compliance Checks**: GDPR requirements, retention policies, legal basis
- **System State**: Health monitoring, capacity validation, performance checks
- **Scoring System**: Confidence calculation, weighted validation

### LangGraph Workflow (`test_remediation_graph.py`)
- **Graph Structure**: Node definitions, edge routing, conditional logic
- **State Management**: Persistence, checkpointing, restoration
- **Flow Control**: Decision routing, validation gates, execution paths
- **Error Handling**: Node failures, recovery mechanisms, fallbacks
- **End-to-End**: Complete workflow execution, integration testing

## 🚀 Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov
```

### Run All Tests

```bash
# From the remediation test directory
python run_tests.py

# Or using pytest directly
pytest unit/ -v --cov=src/remediation_agent
```

### Run Specific Test Files

```bash
# Run model tests only
python run_tests.py models

# Run decision agent tests
python run_tests.py decision_agent

# Run all agent tests
pytest unit/test_*_agent.py -v
```

### Run Specific Test Classes

```bash
# Run specific test class
python run_tests.py models TestRemediationDecision

# Run with pytest
pytest unit/test_models.py::TestRemediationDecision -v
```

### Run with Coverage

```bash
# Generate coverage report
pytest unit/ --cov=src/remediation_agent --cov-report=html --cov-report=term-missing

# View HTML coverage report
open htmlcov/remediation/index.html
```

## 🔧 Test Configuration

### Fixtures (`conftest_remediation.py`)

The test suite includes comprehensive fixtures for:

- **Sample Data**: Compliance violations, remediation signals, workflow steps
- **Mock Objects**: LLM clients, database connections, external APIs
- **Environment Setup**: Configuration variables, credentials, test databases
- **Agent Instances**: Pre-configured agents with test settings

### Environment Variables

Tests use environment variable mocking for:

```python
# AWS Configuration
AWS_REGION = "us-west-2"
SQS_REMEDIATION_QUEUE_URL = "https://sqs.us-west-2.amazonaws.com/123456789/test-queue"

# Database Configuration
DATABASE_URL = "postgresql://test:test@localhost:5432/test_compliance"

# Notification Configuration
SMTP_SERVER = "smtp.test.com"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

# LLM Configuration
OPENAI_API_KEY = "test-api-key"
```

## 📊 Test Metrics

### Coverage Goals
- **Overall Coverage**: > 90%
- **Critical Paths**: 100% (decision logic, validation, execution)
- **Error Handling**: > 95%
- **Integration Points**: > 85%

### Test Categories
- **Unit Tests**: Component isolation, mocking external dependencies
- **Integration Tests**: Component interaction, data flow validation
- **End-to-End Tests**: Complete workflow execution
- **Error Tests**: Failure scenarios, recovery mechanisms

## 🐛 Debugging Tests

### Common Issues

1. **Import Errors**: Ensure `src/` is in Python path
2. **Mock Failures**: Check mock setup and return values
3. **Async Issues**: Use `pytest.mark.asyncio` for async tests
4. **Environment Variables**: Verify test environment setup

### Debug Mode

```bash
# Run with debug output
pytest unit/ -v -s --tb=long

# Run single test with debugging
pytest unit/test_models.py::TestRemediationDecision::test_decision_validation -v -s --pdb
```

### Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In tests, add debug output
def test_something(caplog):
    with caplog.at_level(logging.DEBUG):
        # Test code here
        pass
    assert "Expected log message" in caplog.text
```

## 🔄 Continuous Integration

### GitHub Actions

```yaml
name: Remediation Agent Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run remediation tests
        run: |
          cd tests/remediation
          python run_tests.py
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: remediation-tests
        name: Run remediation agent tests
        entry: python tests/remediation/run_tests.py
        language: system
        pass_filenames: false
```

## 📝 Writing New Tests

### Test Structure Template

```python
"""
Unit tests for [Component Name]
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from src.remediation_agent.[module] import [Component]
from src.remediation_agent.state.models import RemediationSignal


class Test[Component]:
    """Test [Component] class"""
    
    @pytest.fixture
    def component_instance(self):
        """Create component instance for testing"""
        return [Component]()
    
    @pytest.mark.asyncio
    async def test_[functionality]_success(self, component_instance, sample_data):
        """Test successful [functionality]"""
        # Arrange
        # Act
        result = await component_instance.method(sample_data)
        # Assert
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_[functionality]_error(self, component_instance):
        """Test [functionality] error handling"""
        # Test error scenarios
        pass
```

### Best Practices

1. **Descriptive Test Names**: `test_function_scenario_expected_outcome`
2. **AAA Pattern**: Arrange, Act, Assert
3. **Mock External Dependencies**: Database, APIs, file system
4. **Test Both Success and Failure**: Happy path and error scenarios
5. **Use Fixtures**: Reusable test data and setup
6. **Async Testing**: Use `pytest.mark.asyncio` for async functions
7. **Parametrized Tests**: Test multiple scenarios with `@pytest.mark.parametrize`

## 🤝 Contributing

1. **Add Tests First**: Test-driven development preferred
2. **Maintain Coverage**: Ensure new code has test coverage
3. **Update Documentation**: Update this README for new test files
4. **Follow Conventions**: Use existing test patterns and naming
5. **Mock External Dependencies**: Keep tests isolated and fast

## 📚 Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [LangGraph Testing Patterns](https://python.langchain.com/docs/langgraph)
- [Pydantic Testing](https://pydantic-docs.helpmanual.io/usage/validators/#testing)

---

*This test suite ensures the reliability and maintainability of the remediation agent system through comprehensive testing of all components and workflows.*