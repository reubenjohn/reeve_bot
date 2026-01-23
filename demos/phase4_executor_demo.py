#!/usr/bin/env python3
"""
Phase 4 Demo: Pulse Executor

This demo verifies:
- PulseExecutor initialization
- Prompt building with sticky notes
- Hapi subprocess execution
- Timeout handling
- Error handling

Note: This demo requires Hapi to be installed and accessible.
If Hapi is not found, it will run in mock mode.
"""

import asyncio
import sys
import shutil
from typing import Optional

from reeve.pulse.executor import PulseExecutor, ExecutionResult
from reeve.utils.config import get_config

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


# ============================================================================
# Execution Helpers
# ============================================================================


async def execute_and_display(
    executor: PulseExecutor,
    prompt: str,
    sticky_notes: Optional[list[str]] = None,
    session_id: Optional[str] = None,
    timeout: int = 30,
) -> Optional[ExecutionResult]:
    """Execute a prompt and display the result."""
    full_prompt = executor.build_prompt(prompt, sticky_notes or [])

    print(f"Prompt: '{prompt}'")
    if sticky_notes:
        print(f"Sticky notes: {len(sticky_notes)} note(s)")
    if session_id:
        print(f"Resuming session: {session_id}")

    print("\n✓ Launching Hapi session...")

    try:
        result = await executor.execute(
            prompt=full_prompt,
            session_id=session_id,
            timeout_override=timeout,
        )

        if result.return_code == 0:
            print_success("Execution completed successfully!", {"Session ID": result.session_id})
            print_code_block(result.stdout, "Output")
            return result
        else:
            print_error(f"Execution failed with return code: {result.return_code}")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return None

    except Exception as e:
        print_error("Execution failed", e)
        return None


async def check_hapi_available() -> bool:
    """Check if Hapi is available."""
    hapi_path = shutil.which("hapi")
    if hapi_path:
        print(f"✓ Found Hapi at: {hapi_path}")
        return True
    else:
        print("⚠ Hapi not found in PATH")
        return False


# ============================================================================
# Real Hapi Demos
# ============================================================================


async def demo_simple_prompt(executor: PulseExecutor) -> None:
    """Demo 1: Execute a simple prompt."""
    print_section("Demo 1: Simple prompt")

    prompt = "Give me one programming joke (just the joke, nothing else)."
    await execute_and_display(executor, prompt)


async def demo_sticky_notes(executor: PulseExecutor) -> None:
    """Demo 2: Execute a prompt with sticky notes."""
    print_section("Demo 2: Prompt with sticky notes", heavy=True)

    prompt = "What is 2 + 2? Just give me the number."
    sticky_notes = [
        "This is a test of sticky notes",
        "Keep the response very short",
    ]

    # Show the full prompt structure
    full_prompt = executor.build_prompt(prompt, sticky_notes)
    print_code_block(full_prompt, "Full prompt with sticky notes")

    # Execute with sticky notes
    print("\n✓ Launching Hapi session with sticky notes...")
    await execute_and_display(executor, prompt, sticky_notes)


async def demo_session_resumption(executor: PulseExecutor) -> None:
    """Demo 3: Create a session and resume it."""
    print_section("Demo 3: Session ID extraction and resumption", heavy=True)

    print("""
This demonstrates:
  1. Extracting session_id from a NEW session (--output-format json)
  2. Using that session_id to RESUME the session
""")

    # Step 1: Create new session
    print_section("Step 1: Create a new session")

    initial_prompt = "Remember this number: 42. Just say 'OK, I'll remember 42.'"
    result1 = await execute_and_display(executor, initial_prompt)

    if not result1 or not result1.session_id:
        print_error("Could not extract session_id from initial execution")
        print("""
⚠ Warning: session_id not extracted from JSON output
   This could mean:
   - Claude Code version doesn't support --json mode
   - Output format is different than expected
""")
        if result1:
            print_code_block(result1.stdout[:500], "Raw output")
        return

    # Step 2: Resume session
    print_section("Step 2: Resume the session")

    followup_prompt = "What number did I ask you to remember?"
    result2 = await execute_and_display(executor, followup_prompt, session_id=result1.session_id)

    assert result2 and "42" in result2.stdout
    print("\n✅ Session continuity verified!")
    print("   The model remembered '42' from the first message.")


async def demo_with_real_hapi():
    """Demo with real Hapi execution."""
    print("🚀 Phase 4 Demo: Pulse Executor (Real Hapi)\n")
    print(SEPARATOR_HEAVY)

    config = get_config()
    executor = PulseExecutor(
        hapi_command="hapi",
        desk_path=config.reeve_desk_path,
    )

    # Run all demos
    await demo_simple_prompt(executor)
    await demo_sticky_notes(executor)
    await demo_session_resumption(executor)

    # Summary
    print_section("✅ Phase 4 Demo Complete!", heavy=True)

    summary = """
Key features demonstrated:
  1. Simple prompt execution with session_id extraction
  2. Sticky notes (appended to prompt)
  3. Session ID extraction from JSON output (--output-format json)
  4. Session resumption using captured session_id

Technical details:
  - Executor uses --output-format json to get structured output
  - Session ID is extracted from JSON response
  - ExecutionResult is a Pydantic model (type-safe)
  - Session continuity enables multi-turn pulse workflows
"""
    print(summary)


# ============================================================================
# Mock Demos
# ============================================================================


async def demo_prompt_building(executor: PulseExecutor) -> None:
    """Demo: Show how prompts are built with and without sticky notes."""
    print_section("Demo: Prompt building")

    prompt = "Test prompt"
    sticky_notes = ["Sticky note 1", "Sticky note 2"]

    print("Prompt without sticky notes:")
    print(f"  '{executor.build_prompt(prompt)}'")

    full_prompt = executor.build_prompt(prompt, sticky_notes)
    print_code_block(full_prompt, "\nPrompt with sticky notes")

    print("\n✓ Prompt building tested")


async def demo_mock_execution(executor: PulseExecutor) -> None:
    """Demo: Execute a mock command to test the executor."""
    print_section("Demo: Mock execution", heavy=True)

    try:
        result = await executor.execute(
            prompt="Mock execution successful",
            timeout_override=5,
        )

        print_success(
            "Mock execution completed",
            {
                "Return code": result.return_code,
                "Timed out": result.timed_out,
                "Session ID": result.session_id,
                "Output": result.stdout.strip(),
            },
        )

    except Exception as e:
        print_error("Mock execution failed", e)


def demo_session_concept() -> None:
    """Demo: Explain the session resumption concept."""
    print_section("Demo: Session resumption (concept)", heavy=True)

    concept_explanation = """
In real usage, session_id enables conversation continuity:
  - First pulse: No session_id → Creates new session
  - Follow-up pulse: With session_id → Resumes context

Command construction:
  Without session_id: hapi --print "prompt"
  With session_id:    hapi --print --resume abc123 "prompt"

Example use case:
  Pulse 1 (8:00 AM): 'Check calendar for today'
  Pulse 2 (8:01 AM): 'Send summary to user' (resumes session)
  → Pulse 2 has context from Pulse 1's calendar check
"""
    print(concept_explanation)


async def demo_with_mock():
    """Demo with mock execution (when Hapi is not available)."""
    print("🚀 Phase 4 Demo: Pulse Executor (Mock Mode)\n")
    print(SEPARATOR_HEAVY)
    print("ℹ Hapi not found, demonstrating executor features with mock data\n")

    # Use /tmp for mock demo since reeve_desk_path may not exist
    executor = PulseExecutor(
        hapi_command="echo",  # Use echo as a mock command
        desk_path="/tmp",
    )

    # Run all demos
    await demo_prompt_building(executor)
    await demo_mock_execution(executor)
    demo_session_concept()

    # Summary
    print_section("✅ Phase 4 Demo Complete (Mock Mode)!", heavy=True)

    summary = """
Note: Install Hapi to test real execution.

Key features demonstrated:
  - Prompt building with and without sticky notes
  - Sticky notes are appended (not prepended)
  - Mock execution workflow
  - Session resumption concept

With real Hapi, you'll also see:
  - Session ID extraction from --output-format json output
  - ExecutionResult Pydantic model
  - Multi-turn conversation using captured session_id
"""
    print(summary)


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Main entry point."""
    force_mock = "--mock" in sys.argv

    if force_mock:
        await demo_with_mock()
        return

    # Check if Hapi is available
    hapi_available = await check_hapi_available()

    if hapi_available:
        await demo_with_real_hapi()
    else:
        print("\nTo test with real Hapi, install it and ensure it's in your PATH.")
        print("Falling back to mock mode...\n")
        await demo_with_mock()

    # Usage instructions
    usage = """
To run in specific mode:
  Real Hapi: uv run python demos/phase4_executor_demo.py
  Mock mode: uv run python demos/phase4_executor_demo.py --mock
"""
    print(usage)


if __name__ == "__main__":
    asyncio.run(main())
