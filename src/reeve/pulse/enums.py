"""
Pulse Queue Enums

Type-safe enumerations for pulse priority levels and status states.
"""

from enum import Enum


class PulsePriority(str, Enum):
    """
    Priority levels for pulses, determining execution order when multiple
    pulses are due at the same time.

    Higher priority pulses are processed first. Priority also affects
    interrupt behavior and user notification urgency.
    """

    CRITICAL = "critical"  # 🚨 Emergency: User messages, system failures
    # - Interrupts deep work
    # - Bypasses DND settings
    # - Example: "Wife texted: Emergency"

    HIGH = "high"  # 🔔 Important: External events, user-facing tasks
    # - Scheduled alarms the user set
    # - External triggers (Telegram, Email)
    # - Example: "Check flight status before departure"

    NORMAL = "normal"  # ⏰ Standard: Regular maintenance, scheduled checks
    # - Periodic pulses (hourly check)
    # - Calendar event reminders
    # - Example: "Daily 9 AM: Review calendar"

    LOW = "low"  # 📋 Background: Non-urgent maintenance
    # - Cleanup tasks
    # - Background research
    # - Example: "Weekly: Archive old notes"

    DEFERRED = "deferred"  # 🕐 Postponed: Intentionally delayed
    # - User explicitly snoozed a task
    # - Rescheduled due to conflicts
    # - Example: "Moved from Monday to Friday"

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value


class PulseStatus(str, Enum):
    """
    Status of a pulse in its lifecycle.

    State transitions:
    PENDING -> PROCESSING -> COMPLETED (success)
                          -> FAILED (error, will retry)
                          -> CANCELLED (user/system cancelled)
    """

    PENDING = "pending"  # Waiting to be executed
    PROCESSING = "processing"  # Currently executing
    COMPLETED = "completed"  # Successfully executed
    FAILED = "failed"  # Execution failed (see error_message)
    CANCELLED = "cancelled"  # Manually cancelled by user/system

    def __str__(self) -> str:
        """Return the string value for easy serialization."""
        return self.value
