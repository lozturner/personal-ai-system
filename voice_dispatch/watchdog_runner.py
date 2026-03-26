"""
Watchdog Runner — auto-restarts the voice dispatch system if it crashes.

Usage: python -m voice_dispatch.watchdog_runner
This is what run.bat actually calls.
"""

import logging
import subprocess
import sys
import time
import signal
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("dispatch.watchdog")

MAX_RESTARTS = 10
RESTART_COOLDOWN = 5  # seconds between restarts
CRASH_WINDOW = 60  # if crashes this many times within window, give up
LOG_DIR = Path(__file__).parent / "logs"


def run_with_watchdog():
    """Run main.py in a loop, restarting on crash."""
    LOG_DIR.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [watchdog] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(LOG_DIR / "watchdog.log"), encoding="utf-8"),
        ],
    )

    python = sys.executable
    main_module = "voice_dispatch.main"
    restart_count = 0
    crash_times: list[float] = []

    print("""
╔══════════════════════════════════════════════╗
║     VOICE DISPATCH — WATCHDOG MODE           ║
║     Auto-restarts on crash                   ║
╚══════════════════════════════════════════════╝
""")

    while restart_count < MAX_RESTARTS:
        logger.info(f"Starting voice dispatch (attempt {restart_count + 1})...")

        start_time = time.time()
        try:
            process = subprocess.Popen(
                [python, "-m", main_module],
                cwd=str(Path(__file__).parent.parent),
            )

            # Wait for process to exit
            exit_code = process.wait()

            elapsed = time.time() - start_time

            if exit_code == 0:
                logger.info("Voice dispatch exited cleanly.")
                break

            logger.warning(f"Voice dispatch crashed (exit code {exit_code}) after {elapsed:.0f}s")

        except KeyboardInterrupt:
            logger.info("Watchdog interrupted by user")
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()
            break

        except Exception as e:
            logger.error(f"Failed to start process: {e}")

        # Track crash frequency
        now = time.time()
        crash_times.append(now)
        # Remove old crash times outside the window
        crash_times = [t for t in crash_times if now - t < CRASH_WINDOW]

        if len(crash_times) >= MAX_RESTARTS:
            logger.error(
                f"Too many crashes ({len(crash_times)}) within {CRASH_WINDOW}s. Giving up."
            )
            print(f"\n✗ System crashed {len(crash_times)} times in {CRASH_WINDOW}s. Stopping.")
            print("  Check logs at: voice_dispatch/logs/dispatch.log")
            break

        restart_count += 1
        logger.info(f"Restarting in {RESTART_COOLDOWN}s...")
        time.sleep(RESTART_COOLDOWN)

    logger.info("Watchdog exiting.")


if __name__ == "__main__":
    run_with_watchdog()
