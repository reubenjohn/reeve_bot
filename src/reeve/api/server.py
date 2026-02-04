"""
HTTP API Server - REST endpoints for external pulse triggers.

This API allows external systems (Telegram listeners, webhooks, etc.) to
trigger pulses without using the MCP protocol.

Endpoints:
    POST /api/pulse/schedule - Create a new pulse
    GET  /api/pulse/upcoming - List upcoming pulses
    GET  /api/health - Health check
    GET  /api/status - Daemon status
"""

from datetime import datetime
from typing import List, Literal, Optional, cast

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from reeve.pulse.enums import PulsePriority
from reeve.pulse.queue import PulseQueue
from reeve.utils.config import ReeveConfig
from reeve.utils.time_parser import parse_time_string

# ========================================================================
# Request/Response Models
# ========================================================================


class SchedulePulseRequest(BaseModel):
    """Request body for scheduling a pulse."""

    prompt: str = Field(
        ...,
        description="The instruction/context for Reeve",
        min_length=10,
        max_length=2000,
    )

    scheduled_at: str = Field(
        default="now",
        description="When to execute: 'now', ISO timestamp, or 'in X minutes/hours/days'",
        examples=["now", "2026-01-20T09:00:00Z", "in 5 minutes"],
    )

    priority: Literal["critical", "high", "normal", "low", "deferred"] = Field(
        default="high",
        description="Priority level (external events default to 'high')",
    )

    session_id: Optional[str] = Field(
        default=None,
        description="Optional Hapi session ID to resume",
    )

    sticky_notes: Optional[List[str]] = Field(
        default=None,
        description="Optional reminder strings to inject into prompt",
    )

    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional tags for categorization",
    )

    source: str = Field(
        default="external",
        description="Source identifier (e.g., 'telegram', 'email', 'webhook')",
    )


class SchedulePulseResponse(BaseModel):
    """Response after scheduling a pulse."""

    pulse_id: int
    scheduled_at: str
    message: str


class UpcomingPulseItem(BaseModel):
    """Single pulse item in upcoming pulses list."""

    id: int
    scheduled_at: str
    priority: str
    prompt: str
    status: str


class UpcomingPulsesResponse(BaseModel):
    """Response for upcoming pulses list."""

    count: int
    pulses: List[UpcomingPulseItem]


class PulseDetailResponse(BaseModel):
    """Full pulse details response."""

    id: int
    scheduled_at: str
    prompt: str
    priority: str
    status: str
    session_id: Optional[str] = None
    sticky_notes: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    executed_at: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int
    max_retries: int
    created_at: str
    created_by: str


class PulseListItem(BaseModel):
    """Single pulse item in pulse list."""

    id: int
    scheduled_at: str
    priority: str
    prompt: str
    status: str
    executed_at: Optional[str] = None
    error_message: Optional[str] = None


class PulseListResponse(BaseModel):
    """Response for pulse list with count."""

    count: int
    pulses: List[PulseListItem]


class PulseStatsResponse(BaseModel):
    """Queue statistics response."""

    pending: int
    overdue: int
    failed: int
    completed_today: int
    processing: int


class RecentFailureItem(BaseModel):
    """Recent failure item in execution stats."""

    id: int
    prompt: str
    error_message: Optional[str] = None


class ExecutionStatsResponse(BaseModel):
    """Execution statistics response."""

    total_completed: int
    total_failed: int
    success_rate: float
    avg_duration_ms: float
    recent_failures: List[RecentFailureItem]


# ========================================================================
# Authentication
# ========================================================================


# HTTPBearer security scheme for OpenAPI/Swagger UI
security = HTTPBearer()


def create_bearer_token_dependency(config: ReeveConfig):
    """
    Create a dependency for bearer token authentication.

    Args:
        config: ReeveConfig instance with API token

    Returns:
        FastAPI dependency function for token verification
    """

    async def verify_bearer_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> bool:
        """
        Verify API token from Authorization header.

        Args:
            credentials: HTTP Bearer credentials from Authorization header

        Returns:
            True if authorized

        Raises:
            HTTPException: 401 if missing token, 403 if invalid token, 500 if not configured
        """
        # Authentication is always required (no dev mode)
        api_token = config.pulse_api_token

        if not api_token:
            raise HTTPException(
                status_code=500,
                detail="API token not configured. Set PULSE_API_TOKEN environment variable.",
            )

        if credentials.credentials != api_token:
            raise HTTPException(status_code=403, detail="Invalid API token")

        return True

    return verify_bearer_token


# ========================================================================
# App Factory
# ========================================================================


def create_app(queue: PulseQueue, config: ReeveConfig) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        queue: PulseQueue instance for managing pulses
        config: ReeveConfig instance with configuration

    Returns:
        FastAPI app instance
    """
    app = FastAPI(
        title="Reeve Pulse API",
        description="HTTP API for triggering pulses from external systems",
        version="0.1.0",
    )

    # Create authentication dependency
    verify_token = create_bearer_token_dependency(config)

    # ========================================================================
    # Endpoints
    # ========================================================================

    @app.post("/api/pulse/schedule", response_model=SchedulePulseResponse)
    async def schedule_pulse(
        request: SchedulePulseRequest, authorized: bool = Depends(verify_token)
    ):
        """
        Schedule a new pulse (create and schedule).

        This is the primary endpoint for external systems to inject events
        into Reeve's attention queue.

        Example:
            curl -X POST http://localhost:8765/api/pulse/schedule \\
                 -H "Authorization: Bearer your_token_here" \\
                 -H "Content-Type: application/json" \\
                 -d '{
                   "prompt": "Telegram message from Alice: Can we meet tomorrow?",
                   "scheduled_at": "now",
                   "priority": "high",
                   "source": "telegram"
                 }'
        """
        # Parse scheduled_at using time_parser utility
        try:
            scheduled_at = parse_time_string(request.scheduled_at)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Create pulse
        try:
            pulse_id = await queue.schedule_pulse(
                scheduled_at=scheduled_at,
                prompt=request.prompt,
                priority=PulsePriority(request.priority),
                session_id=request.session_id,
                sticky_notes=request.sticky_notes,
                tags=request.tags,
                created_by=request.source,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to schedule pulse: {str(e)}")

        return SchedulePulseResponse(
            pulse_id=pulse_id,
            scheduled_at=scheduled_at.isoformat(),
            message=f"Pulse {pulse_id} scheduled successfully",
        )

    @app.get("/api/pulse/upcoming", response_model=UpcomingPulsesResponse)
    async def list_upcoming(limit: int = 20, authorized: bool = Depends(verify_token)):
        """
        List upcoming pulses.

        Args:
            limit: Maximum number of pulses to return (default: 20)

        Returns:
            List of upcoming pulses with metadata

        Example:
            curl -X GET http://localhost:8765/api/pulse/upcoming?limit=10 \\
                 -H "Authorization: Bearer your_token_here"
        """
        try:
            pulses = await queue.get_upcoming_pulses(limit=limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve pulses: {str(e)}")

        pulse_items = [
            UpcomingPulseItem(
                id=cast(int, p.id),
                scheduled_at=p.scheduled_at.isoformat(),
                priority=p.priority.value,
                prompt=(
                    cast(str, p.prompt)[:100] + "..."
                    if len(cast(str, p.prompt)) > 100
                    else cast(str, p.prompt)
                ),
                status=p.status.value,
            )
            for p in pulses
        ]

        return UpcomingPulsesResponse(count=len(pulse_items), pulses=pulse_items)

    @app.get("/api/health")
    async def health_check():
        """
        Health check endpoint (no auth required).

        Returns:
            Simple health status indicator

        Example:
            curl -X GET http://localhost:8765/api/health
        """
        return {"status": "healthy", "service": "reeve-pulse-daemon"}

    @app.get("/api/status")
    async def daemon_status(authorized: bool = Depends(verify_token)):
        """
        Daemon status and configuration information.

        Returns:
            Current daemon status and configuration details

        Example:
            curl -X GET http://localhost:8765/api/status \\
                 -H "Authorization: Bearer your_token_here"
        """
        return {
            "status": "running",
            "database": config.pulse_db_url,
            "desk_path": config.reeve_desk_path,
            "api_port": config.pulse_api_port,
        }

    @app.get("/api/pulse/list", response_model=PulseListResponse)
    async def list_pulses(
        status: str = "pending",
        limit: int = 20,
        authorized: bool = Depends(verify_token),
    ):
        """
        List pulses filtered by status.

        Args:
            status: Filter by status (pending, failed, completed, cancelled, processing, overdue, all)
            limit: Maximum number of pulses to return (1-100, default: 20)

        Returns:
            List of pulses with count

        Example:
            curl -X GET "http://localhost:8765/api/pulse/list?status=failed&limit=10" \\
                 -H "Authorization: Bearer your_token_here"
        """
        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

        # Validate status
        valid_statuses = {
            "pending",
            "failed",
            "completed",
            "cancelled",
            "processing",
            "overdue",
            "all",
        }
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}",
            )

        try:
            pulses = await queue.get_pulses_by_status(status=status, limit=limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve pulses: {str(e)}")

        pulse_items = [
            PulseListItem(
                id=cast(int, p.id),
                scheduled_at=p.scheduled_at.isoformat(),
                priority=p.priority.value,
                prompt=(
                    cast(str, p.prompt)[:100] + "..."
                    if len(cast(str, p.prompt)) > 100
                    else cast(str, p.prompt)
                ),
                status=p.status.value,
                executed_at=p.executed_at.isoformat() if p.executed_at else None,
                error_message=p.error_message,
            )
            for p in pulses
        ]

        return PulseListResponse(count=len(pulse_items), pulses=pulse_items)

    @app.get("/api/pulse/stats", response_model=PulseStatsResponse)
    async def get_pulse_stats(authorized: bool = Depends(verify_token)):
        """
        Get queue statistics.

        Returns:
            Counts of pending, overdue, failed, completed_today, and processing pulses

        Example:
            curl -X GET http://localhost:8765/api/pulse/stats \\
                 -H "Authorization: Bearer your_token_here"
        """
        try:
            stats = await queue.get_pulse_stats()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")

        return PulseStatsResponse(**stats)

    @app.get("/api/pulse/{pulse_id}", response_model=PulseDetailResponse)
    async def get_pulse_detail(pulse_id: int, authorized: bool = Depends(verify_token)):
        """
        Get full details of a specific pulse.

        Args:
            pulse_id: The ID of the pulse to retrieve

        Returns:
            Full pulse object with all fields

        Example:
            curl -X GET http://localhost:8765/api/pulse/123 \\
                 -H "Authorization: Bearer your_token_here"
        """
        try:
            pulse = await queue.get_pulse(pulse_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve pulse: {str(e)}")

        if not pulse:
            raise HTTPException(status_code=404, detail=f"Pulse {pulse_id} not found")

        return PulseDetailResponse(
            id=cast(int, pulse.id),
            scheduled_at=pulse.scheduled_at.isoformat(),
            prompt=cast(str, pulse.prompt),
            priority=pulse.priority.value,
            status=pulse.status.value,
            session_id=pulse.session_id,
            sticky_notes=pulse.sticky_notes,
            tags=pulse.tags,
            executed_at=pulse.executed_at.isoformat() if pulse.executed_at else None,
            execution_duration_ms=pulse.execution_duration_ms,
            error_message=pulse.error_message,
            retry_count=cast(int, pulse.retry_count),
            max_retries=cast(int, pulse.max_retries),
            created_at=pulse.created_at.isoformat(),
            created_by=cast(str, pulse.created_by),
        )

    @app.get("/api/stats", response_model=ExecutionStatsResponse)
    async def get_execution_stats(authorized: bool = Depends(verify_token)):
        """
        Get execution statistics for the last 7 days.

        Returns:
            Success rate, average duration, and recent failures

        Example:
            curl -X GET http://localhost:8765/api/stats \\
                 -H "Authorization: Bearer your_token_here"
        """
        try:
            stats = await queue.get_execution_stats()
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve execution stats: {str(e)}"
            )

        return ExecutionStatsResponse(
            total_completed=stats["total_completed"],
            total_failed=stats["total_failed"],
            success_rate=stats["success_rate"],
            avg_duration_ms=stats["avg_duration_ms"],
            recent_failures=[
                RecentFailureItem(
                    id=f["id"],
                    prompt=f["prompt"],
                    error_message=f["error_message"],
                )
                for f in stats["recent_failures"]
            ],
        )

    return app
