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

    prompt = "Tell me a short programming joke (one-liner) and then exit"
    print(f"Prompt: '{prompt}'")
    print("\n✓ Launching Hapi session...")

    try:
        result = await executor.execute(
            prompt=prompt,
            timeout_override=30,
        )

        if result["return_code"] == 0:
            print(f"✓ Execution completed successfully!")
            print(f"\nOutput:")
            print("─" * 60)
            print(result["stdout"].strip())
            print("─" * 60)
        else:
            print(f"❌ Execution failed with return code: {result['return_code']}")
            if result["stderr"]:
                print(f"Error: {result['stderr']}")

    except Exception as e:
        print(f"❌ Execution failed: {e}")

    # Demo 2: Prompt with sticky notes
    print(f"\n{'='*60}")
    print("Demo 2: Prompt with sticky notes")
    print("-" * 60)

    prompt = "What is 2 + 2? Just give me the number and exit."
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

        if result["return_code"] == 0:
            print(f"✓ Execution completed successfully!")
            print(f"\nOutput:")
            print("─" * 60)
            print(result["stdout"].strip())
            print("─" * 60)
        else:
            print(f"❌ Execution failed with return code: {result['return_code']}")

    except Exception as e:
        print(f"❌ Execution failed: {e}")

    print("\n" + "=" * 60)
    print("✅ Phase 4 Demo Complete!")


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
        print(f"  Return code: {result['return_code']}")
        print(f"  Timed out: {result['timed_out']}")
        print(f"  Output: {result['stdout'].strip()}")

    except Exception as e:
        print(f"❌ Mock execution failed: {e}")

    print("\n" + "=" * 60)
    print("✅ Phase 4 Demo Complete (Mock Mode)!")
    print("\nNote: Install Hapi to test real execution.")
    print("Key features demonstrated:")
    print("  - Prompt building with and without sticky notes")
    print("  - Sticky notes are appended (not prepended)")
    print("  - Mock execution workflow")


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
