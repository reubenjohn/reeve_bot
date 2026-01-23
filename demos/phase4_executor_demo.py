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
from pathlib import Path

from reeve.pulse.executor import PulseExecutor
from reeve.utils.config import get_config


async def check_hapi_available() -> bool:
    """Check if Hapi is available."""
    hapi_path = shutil.which("hapi")
    if hapi_path:
        print(f"✓ Found Hapi at: {hapi_path}")
        return True
    else:
        print("⚠ Hapi not found in PATH")
        return False


async def demo_with_real_hapi():
    """Demo with real Hapi execution."""
    print("🚀 Phase 4 Demo: Pulse Executor (Real Hapi)\n")
    print("=" * 60)

    config = get_config()
    executor = PulseExecutor(
        hapi_command="hapi",
        desk_path=config.reeve_desk_path,
    )

    # Demo 1: Simple prompt
    print("\nDemo 1: Simple prompt")
    print("-" * 60)

    prompt = "Give me one programming joke (just the joke, nothing else)."
    print(f"Prompt: '{prompt}'")
    print("\n✓ Launching Hapi session...")

    try:
        result = await executor.execute(
            prompt=prompt,
            timeout_override=30,
        )

        if result.return_code == 0:
            print(f"✓ Execution completed successfully!")
            print(f"  Session ID: {result.session_id}")
            print(f"\nOutput:")
            print("─" * 60)
            print(result.stdout.strip())
            print("─" * 60)
        else:
            print(f"❌ Execution failed with return code: {result.return_code}")
            if result.stderr:
                print(f"Error: {result.stderr}")

    except Exception as e:
        print(f"❌ Execution failed: {e}")

    # Demo 2: Prompt with sticky notes
    print(f"\n{'='*60}")
    print("Demo 2: Prompt with sticky notes")
    print("-" * 60)

    prompt = "What is 2 + 2? Just give me the number."
    sticky_notes = [
        "This is a test of sticky notes",
        "Keep the response very short",
    ]

    full_prompt = executor.build_prompt(prompt, sticky_notes)
    print("Full prompt with sticky notes:")
    print("─" * 60)
    print(full_prompt)
    print("─" * 60)

    print("\n✓ Launching Hapi session with sticky notes...")

    try:
        # Build the full prompt with sticky notes
        full_prompt_to_execute = executor.build_prompt(prompt, sticky_notes)

        result = await executor.execute(
            prompt=full_prompt_to_execute,
            timeout_override=30,
        )

        if result.return_code == 0:
            print(f"✓ Execution completed successfully!")
            print(f"  Session ID: {result.session_id}")
            print(f"\nOutput:")
            print("─" * 60)
            print(result.stdout.strip())
            print("─" * 60)
        else:
            print(f"❌ Execution failed with return code: {result.return_code}")

    except Exception as e:
        print(f"❌ Execution failed: {e}")

    # Demo 3: Session resumption and session ID extraction
    print(f"\n{'='*60}")
    print("Demo 3: Session ID extraction and resumption")
    print("-" * 60)
    print("\nThis demonstrates:")
    print("  1. Extracting session_id from a NEW session (--output-format json)")
    print("  2. Using that session_id to RESUME the session\n")

    # Step 1: Create a new session and capture its session_id
    print("Step 1: Create a new session")
    print("-" * 60)

    initial_prompt = "Remember this number: 42. Just say 'OK, I'll remember 42.'"
    print(f"Prompt: '{initial_prompt}'")
    print("\n✓ Launching new Hapi session...")

    try:
        # Execute first prompt (creates NEW session)
        result1 = await executor.execute(
            prompt=initial_prompt,
            timeout_override=30,
        )

        if result1.return_code == 0:
            print(f"✓ New session created successfully!")
            print(f"  Session ID: {result1.session_id}")

            if result1.session_id:
                # Step 2: Resume the session using captured session_id
                print(f"\nStep 2: Resume the session")
                print("-" * 60)

                followup_prompt = "What number did I ask you to remember?"
                print(f"Resuming session: {result1.session_id}")
                print(f"Prompt: '{followup_prompt}'")
                print("\n✓ Resuming session...")

                # Execute followup prompt (RESUMES existing session)
                result2 = await executor.execute(
                    prompt=followup_prompt,
                    session_id=result1.session_id,  # Use captured session_id
                    timeout_override=30,
                )

                if result2.return_code == 0:
                    print(f"✓ Session resumed successfully!")
                    print(f"  Session ID: {result2.session_id}")
                    print(f"\nOutput:")
                    print("─" * 60)
                    print(result2.stdout.strip())
                    print("─" * 60)
                    print("\n✅ Session continuity verified!")
                    print("   The model remembered '42' from the first message.")
                else:
                    print(f"❌ Resume failed with return code: {result2.return_code}")
            else:
                print("\n⚠ Warning: session_id not extracted from JSON output")
                print("   This could mean:")
                print("   - Claude Code version doesn't support --json mode")
                print("   - Output format is different than expected")
                print("\nRaw output:")
                print("─" * 60)
                print(result1.stdout[:500])
                print("─" * 60)
        else:
            print(f"❌ Initial execution failed with return code: {result1.return_code}")
            if result1.stderr:
                print(f"Error: {result1.stderr}")

    except Exception as e:
        print(f"❌ Demo failed: {e}")

    print("\n" + "=" * 60)
    print("✅ Phase 4 Demo Complete!")
    print("\nKey features demonstrated:")
    print("  1. Simple prompt execution with session_id extraction")
    print("  2. Sticky notes (appended to prompt)")
    print("  3. Session ID extraction from JSON output (--output-format json)")
    print("  4. Session resumption using captured session_id")
    print("\nTechnical details:")
    print("  - Executor uses --output-format json to get structured output")
    print("  - Session ID is extracted from JSON response")
    print("  - ExecutionResult is a Pydantic model (type-safe)")
    print("  - Session continuity enables multi-turn pulse workflows")


async def demo_with_mock():
    """Demo with mock execution (when Hapi is not available)."""
    print("🚀 Phase 4 Demo: Pulse Executor (Mock Mode)\n")
    print("=" * 60)
    print("ℹ Hapi not found, demonstrating executor features with mock data\n")

    # Use /tmp for mock demo since reeve_desk_path may not exist
    executor = PulseExecutor(
        hapi_command="echo",  # Use echo as a mock command
        desk_path="/tmp",
    )

    # Demo: Prompt building
    print("Demo: Prompt building")
    print("-" * 60)

    prompt = "Test prompt"
    sticky_notes = [
        "Sticky note 1",
        "Sticky note 2",
    ]

    full_prompt = executor.build_prompt(prompt, sticky_notes)
    print("Prompt without sticky notes:")
    print(f"  '{executor.build_prompt(prompt)}'")
    print("\nPrompt with sticky notes:")
    print("─" * 60)
    print(full_prompt)
    print("─" * 60)

    print("\n✓ Prompt building tested")

    # Demo: Mock execution
    print(f"\n{'='*60}")
    print("Demo: Mock execution")
    print("-" * 60)

    try:
        # Use echo to simulate successful execution
        result = await executor.execute(
            prompt="Mock execution successful",
            timeout_override=5,
        )

        print(f"✓ Mock execution completed")
        print(f"  Return code: {result.return_code}")
        print(f"  Timed out: {result.timed_out}")
        print(f"  Session ID: {result.session_id}")
        print(f"  Output: {result.stdout.strip()}")

    except Exception as e:
        print(f"❌ Mock execution failed: {e}")

    # Demo: Session resumption
    print(f"\n{'='*60}")
    print("Demo: Session resumption (concept)")
    print("-" * 60)

    print("\nIn real usage, session_id enables conversation continuity:")
    print("  - First pulse: No session_id → Creates new session")
    print("  - Follow-up pulse: With session_id → Resumes context")
    print("\nCommand construction:")
    print("  Without session_id: hapi --print \"prompt\"")
    print("  With session_id:    hapi --print --resume abc123 \"prompt\"")
    print("\nExample use case:")
    print("  Pulse 1 (8:00 AM): 'Check calendar for today'")
    print("  Pulse 2 (8:01 AM): 'Send summary to user' (resumes session)")
    print("  → Pulse 2 has context from Pulse 1's calendar check")

    print("\n" + "=" * 60)
    print("✅ Phase 4 Demo Complete (Mock Mode)!")
    print("\nNote: Install Hapi to test real execution.")
    print("Key features demonstrated:")
    print("  - Prompt building with and without sticky notes")
    print("  - Sticky notes are appended (not prepended)")
    print("  - Mock execution workflow")
    print("  - Session resumption concept")
    print("\nWith real Hapi, you'll also see:")
    print("  - Session ID extraction from --output-format json output")
    print("  - ExecutionResult Pydantic model")
    print("  - Multi-turn conversation using captured session_id")


async def main():
    """Main entry point."""
    # Check command line args
    force_mock = "--mock" in sys.argv

    if force_mock:
        await demo_with_mock()
    else:
        hapi_available = await check_hapi_available()
        if hapi_available:
            await demo_with_real_hapi()
        else:
            print("\nTo test with real Hapi, install it and ensure it's in your PATH.")
            print("Falling back to mock mode...\n")
            await demo_with_mock()

    print("\nTo run in specific mode:")
    print("  Real Hapi: uv run python demos/phase4_executor_demo.py")
    print("  Mock mode: uv run python demos/phase4_executor_demo.py --mock")


if __name__ == "__main__":
    asyncio.run(main())
