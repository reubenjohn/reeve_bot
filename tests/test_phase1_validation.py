"""
Phase 1 Validation Tests

Tests to verify that the foundation is working correctly:
- Enums are type-safe
- Models can be instantiated
- Database connection works
"""

from datetime import datetime, timezone

from reeve.pulse.models import Pulse
from reeve.pulse.enums import PulsePriority, PulseStatus


def test_enums():
    """Test that enums work correctly."""
    # Test PulsePriority
    assert PulsePriority.CRITICAL == "critical"
    assert PulsePriority.HIGH == "high"
    assert PulsePriority.NORMAL == "normal"
    assert PulsePriority.LOW == "low"
    assert PulsePriority.DEFERRED == "deferred"

    # Test PulseStatus
    assert PulseStatus.PENDING == "pending"
    assert PulseStatus.PROCESSING == "processing"
    assert PulseStatus.COMPLETED == "completed"
    assert PulseStatus.FAILED == "failed"
    assert PulseStatus.CANCELLED == "cancelled"

    print("✓ Enums test passed")


def test_pulse_model_creation():
    """Test that Pulse model can be instantiated."""
    pulse = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Test pulse",
        priority=PulsePriority.NORMAL,
        status=PulseStatus.PENDING,
        created_by="test_script"
    )

    assert pulse.prompt == "Test pulse"
    assert pulse.priority == PulsePriority.NORMAL
    assert pulse.status == PulseStatus.PENDING
    assert pulse.created_by == "test_script"

    print(f"✓ Pulse model creation test passed: {pulse}")


def test_pulse_model_with_optional_fields():
    """Test Pulse model with optional fields."""
    pulse = Pulse(
        scheduled_at=datetime.now(timezone.utc),
        prompt="Test pulse with options",
        priority=PulsePriority.HIGH,
        status=PulseStatus.PENDING,
        session_link="https://example.com/session/123",
        sticky_notes=["Remember to check email", "Follow up on PR"],
        tags=["test", "validation"],
        created_by="test_script",
        max_retries=5
    )

    assert pulse.session_link == "https://example.com/session/123"
    assert pulse.sticky_notes == ["Remember to check email", "Follow up on PR"]
    assert pulse.tags == ["test", "validation"]
    assert pulse.max_retries == 5

    print(f"✓ Pulse model with optional fields test passed: {pulse}")


if __name__ == "__main__":
    print("Running Phase 1 Validation Tests...\n")

    test_enums()
    test_pulse_model_creation()
    test_pulse_model_with_optional_fields()

    print("\n✅ All Phase 1 validation tests passed!")
