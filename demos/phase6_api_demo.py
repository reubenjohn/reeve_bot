#!/usr/bin/env python3
"""
Phase 6 Demo: HTTP REST API

This demo verifies:
- Health check endpoint
- Bearer token authentication
- POST /api/pulse/trigger - Schedule pulses via HTTP
- GET /api/pulse/upcoming - List upcoming pulses
- GET /api/status - Daemon status
- Error handling and validation

Note: This demo requires the daemon to be running.
Run: uv run python -m reeve.pulse
"""

import asyncio
import os
import sys
from typing import Optional

import httpx

# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8765"
API_TOKEN = os.getenv("PULSE_API_TOKEN", "test-token")

# ============================================================================
# Formatting Utilities
# ============================================================================

SEPARATOR_HEAVY = "=" * 60
SEPARATOR_LIGHT = "-" * 60
SEPARATOR_CODE = "─" * 60


def print_section(title: str, heavy: bool = False) -> None:
    """Print a formatted section header."""
    separator = SEPARATOR_HEAVY if heavy else SEPARATOR_LIGHT
    print(f"\n{separator}")
    print(title)
    print(SEPARATOR_LIGHT)


def print_code_block(content: str, title: Optional[str] = None) -> None:
    """Print content in a code block with optional title."""
    if title:
        print(f"\n{title}:")
    print(SEPARATOR_CODE)
    print(content.strip())
    print(SEPARATOR_CODE)


def print_success(message: str, details: Optional[dict] = None) -> None:
    """Print a success message with optional details."""
    print(f"✓ {message}")
    if details:
        for key, value in details.items():
            print(f"  {key}: {value}")


def print_error(message: str, error: Optional[Exception] = None) -> None:
    """Print an error message."""
    print(f"❌ {message}")
    if error:
        print(f"   {error}")


def print_response(response: httpx.Response) -> None:
    """Print HTTP response details."""
    print(f"\nResponse: {response.status_code} {response.reason_phrase}")
    if response.status_code >= 400:
        print(f"Error: {response.text}")
    else:
        try:
            data = response.json()
            import json

            print_code_block(json.dumps(data, indent=2), "Response Body")
        except Exception:
            print(f"Body: {response.text}")


# ============================================================================
# HTTP Client Helpers
# ============================================================================


def get_headers(include_auth: bool = True) -> dict:
    """Get headers for API requests."""
    headers = {"Content-Type": "application/json"}
    if include_auth:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers


async def check_daemon_running() -> bool:
    """Check if the daemon is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/api/health", timeout=2.0)
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# ============================================================================
# Demo Functions
# ============================================================================


async def demo_health_check() -> None:
    """Demo 1: Health check endpoint."""
    print_section("Demo 1: Health check")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/api/health")
        print_success(
            "Health check successful",
            {"Status": response.status_code, "Response": response.json()["status"]},
        )


async def demo_auth_test() -> None:
    """Demo 2: Authentication test."""
    print_section("Demo 2: Bearer token authentication")

    async with httpx.AsyncClient() as client:
        # Test without auth header
        print("\nAttempting request without auth header...")
        response = await client.get(f"{API_BASE_URL}/api/pulse/upcoming")
        if response.status_code == 401:
            print_success("✓ Correctly rejected unauthenticated request", {"Status": 401})
        else:
            print_error(f"Unexpected status: {response.status_code}")

        # Test with valid auth header
        print("\nAttempting request with valid auth header...")
        response = await client.get(
            f"{API_BASE_URL}/api/pulse/upcoming", headers=get_headers()
        )
        if response.status_code == 200:
            print_success("✓ Authenticated request accepted", {"Status": 200})
        else:
            print_error(f"Unexpected status: {response.status_code}")


async def demo_schedule_immediate() -> None:
    """Demo 3: Schedule an immediate pulse."""
    print_section("Demo 3: Schedule immediate pulse", heavy=True)

    payload = {
        "scheduled_at": "now",
        "prompt": "Test pulse from HTTP API - immediate execution",
        "priority": "normal",
    }

    print("Request payload:")
    import json

    print_code_block(json.dumps(payload, indent=2))

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/api/pulse/trigger", json=payload, headers=get_headers()
        )
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            print_success("Pulse scheduled", {"Pulse ID": data["pulse_id"]})


async def demo_schedule_relative() -> None:
    """Demo 4: Schedule a pulse with relative time."""
    print_section("Demo 4: Schedule pulse with relative time")

    payload = {
        "scheduled_at": "in 5 minutes",
        "prompt": "Test pulse from HTTP API - scheduled 5 minutes from now",
        "priority": "high",
        "tags": ["test", "api_demo"],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/api/pulse/trigger", json=payload, headers=get_headers()
        )
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            print_success(
                "Pulse scheduled",
                {"Pulse ID": data["pulse_id"], "Scheduled": data["scheduled_at"]},
            )


async def demo_schedule_iso() -> None:
    """Demo 5: Schedule a pulse with ISO 8601 timestamp."""
    print_section("Demo 5: Schedule pulse with ISO 8601 timestamp")

    from datetime import datetime, timedelta, timezone

    # Schedule 2 hours from now
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=2)
    time_str = scheduled_time.isoformat().replace("+00:00", "Z")

    payload = {
        "scheduled_at": time_str,
        "prompt": "Test pulse from HTTP API - ISO 8601 timestamp",
        "priority": "low",
        "sticky_notes": ["Note 1: This is a demo pulse", "Note 2: Testing sticky notes via API"],
    }

    print(f"Scheduling for: {time_str}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/api/pulse/trigger", json=payload, headers=get_headers()
        )
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            print_success("Pulse scheduled", {"Pulse ID": data["pulse_id"]})


async def demo_list_upcoming() -> None:
    """Demo 6: List upcoming pulses."""
    print_section("Demo 6: List upcoming pulses", heavy=True)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE_URL}/api/pulse/upcoming?limit=10", headers=get_headers()
        )
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            print_success("Retrieved upcoming pulses", {"Count": len(data["pulses"])})


async def demo_status() -> None:
    """Demo 7: Check daemon status."""
    print_section("Demo 7: Daemon status")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/api/status", headers=get_headers())
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            print_success(
                "Status retrieved",
                {"Running": data["daemon_running"], "Executing": data["executing_pulses"]},
            )


async def demo_cleanup() -> None:
    """Clean up: Cancel test pulses."""
    print_section("Cleanup: Cancel demo pulses")

    print("Fetching pulses with 'test' or 'api_demo' tags...")

    async with httpx.AsyncClient() as client:
        # Get upcoming pulses
        response = await client.get(
            f"{API_BASE_URL}/api/pulse/upcoming?limit=50", headers=get_headers()
        )

        if response.status_code != 200:
            print_error("Could not fetch upcoming pulses")
            return

        data = response.json()
        test_pulses = [
            pulse
            for pulse in data["pulses"]
            if pulse.get("tags") and any(tag in ["test", "api_demo"] for tag in pulse["tags"])
        ]

        if not test_pulses:
            print("✓ No test pulses to clean up")
            return

        print(f"Found {len(test_pulses)} test pulse(s) to cancel")

        # Cancel each test pulse
        for pulse in test_pulses:
            pulse_id = pulse["id"]
            print(f"  Canceling pulse {pulse_id}...")

            # Note: We would normally have a cancel endpoint
            # For now, just show what we would cancel
            print(f"    → Would cancel: {pulse['prompt'][:60]}...")

        print("\n✓ Cleanup complete")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Main entry point."""
    print("🚀 Phase 6 Demo: HTTP REST API\n")
    print(SEPARATOR_HEAVY)
    print(f"API URL: {API_BASE_URL}")
    print(f"API Token: {API_TOKEN[:10]}... (from PULSE_API_TOKEN env var)")
    print(SEPARATOR_HEAVY)

    # Check if daemon is running
    print("\nChecking if daemon is running...")
    daemon_running = await check_daemon_running()

    if not daemon_running:
        print_error(
            "Daemon is not running",
            Exception(
                f"Could not connect to API at {API_BASE_URL}\n"
                "Please start the daemon first: uv run python -m reeve.pulse"
            ),
        )
        print("\nTo start the daemon:")
        print("  1. Open a new terminal")
        print("  2. Run: uv run python -m reeve.pulse")
        print("  3. Return here and press Enter to continue")

        input("\nPress Enter when daemon is running...")

        # Check again
        daemon_running = await check_daemon_running()
        if not daemon_running:
            print_error("Still cannot connect to daemon. Exiting.")
            return

    print_success("Daemon is running!")

    # Run all demos
    try:
        await demo_health_check()
        await demo_auth_test()
        await demo_schedule_immediate()
        await demo_schedule_relative()
        await demo_schedule_iso()
        await demo_list_upcoming()
        await demo_status()
        await demo_cleanup()
    except Exception as e:
        print_error("Demo failed", e)
        import traceback

        traceback.print_exc()
        return

    # Summary
    print_section("✅ Phase 6 Demo Complete!", heavy=True)

    summary = """
Key features demonstrated:
  1. Health check endpoint (GET /api/health)
  2. Bearer token authentication
  3. Schedule immediate pulse (scheduled_at: "now")
  4. Schedule relative pulse (scheduled_at: "in 5 minutes")
  5. Schedule ISO 8601 pulse (scheduled_at: "2026-01-20T09:00:00Z")
  6. List upcoming pulses (GET /api/pulse/upcoming)
  7. Check daemon status (GET /api/status)

Technical details:
  - FastAPI server running on port 8765
  - Bearer token authentication via Authorization header
  - JSON request/response format
  - Flexible time parsing (ISO 8601, relative, keywords)
  - Integration with PulseQueue for scheduling
  - Concurrent execution with daemon scheduler

API Endpoints:
  GET  /api/health          - Health check (no auth)
  POST /api/pulse/trigger   - Schedule a new pulse
  GET  /api/pulse/upcoming  - List upcoming pulses
  GET  /api/status          - Daemon status
"""
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
