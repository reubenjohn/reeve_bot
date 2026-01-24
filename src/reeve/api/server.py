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
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
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


# ========================================================================
# Authentication
# ========================================================================


def create_bearer_token_dependency(config: ReeveConfig):
    """
    Create a dependency for bearer token authentication.

    Args:
        config: ReeveConfig instance with API token

    Returns:
        FastAPI dependency function for token verification
    """

    async def verify_bearer_token(authorization: str = Header(None)) -> bool:
        """
        Verify API token from Authorization header.

        Args:
            authorization: Authorization header value (e.g., "Bearer token123")

        Returns:
            True if authorized

        Raises:
            HTTPException: 401 if missing/malformed header, 403 if invalid token
        """
        # Authentication is always required (no dev mode)
        api_token = config.pulse_api_token

        if not api_token:
            raise HTTPException(
                status_code=500,
                detail="API token not configured. Set PULSE_API_TOKEN environment variable.",
            )

        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header. Expected: 'Bearer <token>'",
            )

        token = authorization[7:]  # Remove "Bearer " prefix

        if token != api_token:
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
                id=int(p.id),  # type: ignore[arg-type]
                scheduled_at=p.scheduled_at.isoformat(),
                priority=p.priority.value,
                prompt=(
                    str(p.prompt[:100]) + "..." if len(p.prompt) > 100 else str(p.prompt)
                ),  # type: ignore[arg-type]
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

    return app
