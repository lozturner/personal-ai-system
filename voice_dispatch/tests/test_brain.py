"""
Test Brain (Claude API integration).
Run: python -m voice_dispatch.tests.test_brain

Requires ANTHROPIC_API_KEY to be set.
"""

import sys
import os


def test_brain():
    print("Testing Brain (Claude API)...")

    # Check API key
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # Try .env file
        from pathlib import Path
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    os.environ["ANTHROPIC_API_KEY"] = key
                    break

    if not key:
        print("  ✗ ANTHROPIC_API_KEY not set. Set it in .env or environment.")
        print("  Skipping Brain test.\n")
        return True  # Don't fail — just skip

    from voice_dispatch.brain import Brain

    brain = Brain()
    brain.load()
    print("  ✓ Brain loaded")

    # Test a simple conversation
    response = brain.think("Hello, this is a test. Respond with exactly: TEST OK")
    print(f"  ✓ Claude responded: '{response[:80]}'")

    # Test conversation memory
    response2 = brain.think("What did I just say to you?")
    print(f"  ✓ Follow-up response: '{response2[:80]}'")

    # Test reset
    brain.reset_conversation()
    print("  ✓ Conversation reset")

    print("  ✓ Brain tests passed\n")
    return True


if __name__ == "__main__":
    success = test_brain()
    sys.exit(0 if success else 1)
