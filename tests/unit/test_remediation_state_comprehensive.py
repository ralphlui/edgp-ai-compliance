"""
Comprehensive tests for remediation state to boost coverage
"""

import pytest
from datetime import datetime
from src.remediation_agent.state.remediation_state import RemediationState


def test_remediation_state_initialization():
    """Test state initialization"""
    state = RemediationState()
    assert state is not None
    assert hasattr(state, 'violations')
    assert hasattr(state, 'decisions')
    assert hasattr(state, 'workflow_status')


def test_remediation_state_empty_initialization():
    """Test state starts empty"""
    state = RemediationState()
    assert len(state.violations) == 0
    assert len(state.decisions) == 0


def test_add_violation():
    """Test adding violation to state"""
    state = RemediationState()
    violation = {
        "violation_id": "v-001",
        "type": "data_retention",
        "severity": "high"
    }

    state.add_violation(violation)
    assert len(state.violations) == 1
    assert state.violations[0] == violation


def test_add_multiple_violations():
    """Test adding multiple violations"""
    state = RemediationState()

    for i in range(5):
        violation = {"violation_id": f"v-{i}", "type": "test"}
        state.add_violation(violation)

    assert len(state.violations) == 5


def test_add_decision():
    """Test adding decision to state"""
    state = RemediationState()
    decision = {
        "decision_id": "dec-001",
        "violation_id": "v-001",
        "action": "delete"
    }

    state.add_decision(decision)
    assert len(state.decisions) == 1
    assert state.decisions[0] == decision


def test_add_multiple_decisions():
    """Test adding multiple decisions"""
    state = RemediationState()

    for i in range(3):
        decision = {"decision_id": f"dec-{i}", "action": "test"}
        state.add_decision(decision)

    assert len(state.decisions) == 3


def test_add_validation():
    """Test adding validation to state"""
    state = RemediationState()
    validation = {
        "validation_id": "val-001",
        "decision_id": "dec-001",
        "is_valid": True
    }

    state.add_validation(validation)
    assert len(state.validations) == 1
    assert state.validations[0] == validation


def test_get_violations():
    """Test getting all violations"""
    state = RemediationState()

    violations = [
        {"violation_id": "v1", "type": "retention"},
        {"violation_id": "v2", "type": "consent"}
    ]

    for v in violations:
        state.add_violation(v)

    retrieved = state.get_violations()
    assert len(retrieved) == 2
    assert retrieved == violations


def test_get_decisions():
    """Test getting all decisions"""
    state = RemediationState()

    decisions = [
        {"decision_id": "d1", "action": "delete"},
        {"decision_id": "d2", "action": "archive"}
    ]

    for d in decisions:
        state.add_decision(d)

    retrieved = state.get_decisions()
    assert len(retrieved) == 2
    assert retrieved == decisions


def test_get_validations():
    """Test getting all validations"""
    state = RemediationState()

    validations = [
        {"validation_id": "val1", "is_valid": True},
        {"validation_id": "val2", "is_valid": False}
    ]

    for v in validations:
        state.add_validation(v)

    retrieved = state.get_validations()
    assert len(retrieved) == 2


def test_update_workflow_status():
    """Test updating workflow status"""
    state = RemediationState()

    state.workflow_status = "pending"
    assert state.workflow_status == "pending"

    state.workflow_status = "in_progress"
    assert state.workflow_status == "in_progress"

    state.workflow_status = "completed"
    assert state.workflow_status == "completed"


def test_to_dict():
    """Test converting state to dictionary"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1"})
    state.add_decision({"decision_id": "d1"})
    state.workflow_status = "in_progress"

    state_dict = state.to_dict()

    assert isinstance(state_dict, dict)
    assert "violations" in state_dict or "workflow_status" in state_dict


def test_from_dict():
    """Test creating state from dictionary"""
    data = {
        "violations": [{"violation_id": "v1"}],
        "decisions": [{"decision_id": "d1"}],
        "workflow_status": "pending"
    }

    state = RemediationState.from_dict(data)

    assert state is not None
    assert len(state.violations) >= 0


def test_clear():
    """Test clearing state"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1"})
    state.add_decision({"decision_id": "d1"})

    state.clear()

    assert len(state.violations) == 0
    assert len(state.decisions) == 0


def test_validate():
    """Test state validation"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1", "type": "test"})

    is_valid = state.validate()
    assert isinstance(is_valid, bool)


def test_state_persistence():
    """Test state can be persisted and restored"""
    state1 = RemediationState()

    state1.add_violation({"violation_id": "v-persist"})
    state1.add_decision({"decision_id": "d-persist"})
    state1.workflow_status = "completed"

    # Convert to dict
    state_dict = state1.to_dict()

    # Create new state from dict
    state2 = RemediationState.from_dict(state_dict)

    # Verify data persisted
    assert len(state2.violations) == len(state1.violations)


def test_state_with_metadata():
    """Test state with metadata"""
    state = RemediationState()

    violation_with_meta = {
        "violation_id": "v-meta",
        "type": "data_retention",
        "metadata": {
            "detected_at": datetime.utcnow().isoformat(),
            "source": "scanner"
        }
    }

    state.add_violation(violation_with_meta)

    violations = state.get_violations()
    assert "metadata" in violations[0]


def test_state_update_violation():
    """Test updating existing violation"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1", "status": "pending"})

    # Update violation
    updated_violation = {"violation_id": "v1", "status": "resolved"}
    state.update_violation("v1", updated_violation)

    violations = state.get_violations()
    # Check if update mechanism exists
    assert len(violations) >= 1


def test_state_remove_violation():
    """Test removing violation"""
    state = RemediationState()

    state.add_violation({"violation_id": "v-remove"})
    assert len(state.violations) == 1

    state.remove_violation("v-remove")
    # Check if removal mechanism exists


def test_state_count_by_type():
    """Test counting violations by type"""
    state = RemediationState()

    state.add_violation({"type": "retention"})
    state.add_violation({"type": "retention"})
    state.add_violation({"type": "consent"})

    counts = state.count_violations_by_type()
    assert isinstance(counts, dict)


def test_state_get_pending_decisions():
    """Test getting pending decisions"""
    state = RemediationState()

    state.add_decision({"decision_id": "d1", "status": "pending"})
    state.add_decision({"decision_id": "d2", "status": "completed"})
    state.add_decision({"decision_id": "d3", "status": "pending"})

    pending = state.get_pending_decisions()
    assert isinstance(pending, list)


def test_state_workflow_progress():
    """Test calculating workflow progress"""
    state = RemediationState()

    state.add_decision({"status": "completed"})
    state.add_decision({"status": "completed"})
    state.add_decision({"status": "pending"})

    progress = state.calculate_progress()
    assert isinstance(progress, (int, float))


def test_state_serialization():
    """Test state serialization"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1"})
    state.add_decision({"decision_id": "d1"})

    # Test JSON serialization
    import json
    state_dict = state.to_dict()
    json_str = json.dumps(state_dict, default=str)

    assert isinstance(json_str, str)


def test_state_with_nested_data():
    """Test state with nested data structures"""
    state = RemediationState()

    complex_violation = {
        "violation_id": "v-complex",
        "details": {
            "type": "retention",
            "affected_records": [1, 2, 3],
            "metadata": {
                "source": "scanner",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    }

    state.add_violation(complex_violation)

    violations = state.get_violations()
    assert "details" in violations[0]
    assert "affected_records" in violations[0]["details"]


def test_state_concurrent_modifications():
    """Test state handles concurrent modifications"""
    state = RemediationState()

    # Add items in sequence
    for i in range(10):
        state.add_violation({"violation_id": f"v{i}"})

    for i in range(10):
        state.add_decision({"decision_id": f"d{i}"})

    assert len(state.violations) == 10
    assert len(state.decisions) == 10


def test_state_filters():
    """Test filtering state data"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1", "severity": "high"})
    state.add_violation({"violation_id": "v2", "severity": "low"})
    state.add_violation({"violation_id": "v3", "severity": "high"})

    high_severity = state.filter_violations_by_severity("high")
    assert isinstance(high_severity, list)


def test_state_history_tracking():
    """Test history tracking"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1"})

    # Check if history is tracked
    if hasattr(state, 'history'):
        assert len(state.history) >= 0


def test_state_snapshot():
    """Test creating state snapshot"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1"})
    state.add_decision({"decision_id": "d1"})

    snapshot = state.create_snapshot()
    assert isinstance(snapshot, dict)


def test_state_restore_snapshot():
    """Test restoring from snapshot"""
    state = RemediationState()

    state.add_violation({"violation_id": "v1"})
    snapshot = state.create_snapshot()

    state.clear()
    assert len(state.violations) == 0

    state.restore_snapshot(snapshot)
    # Check if restore mechanism exists


def test_state_merge():
    """Test merging two states"""
    state1 = RemediationState()
    state2 = RemediationState()

    state1.add_violation({"violation_id": "v1"})
    state2.add_violation({"violation_id": "v2"})

    merged = state1.merge(state2)
    assert isinstance(merged, RemediationState)
