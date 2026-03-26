"""
Voice Dispatch System — Main Entry Point.

Starts all components:
  1. SIP Registrar (port 5060)
  2. pyVoIP phone (registers on port 5062, answers calls)
  3. Loads all AI models (VAD, STT, TTS, Brain)
  4. Optionally auto-calls the user's phone on startup

One command to run: python -m voice_dispatch.main
"""

import logging
import os
import sys
import time
import threading
import signal
from pathlib import Path

# Load .env file if present
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from voice_dispatch.config import (
    LAN_IP,
    SIP_HOST,
    SIP_PORT,
    VOIP_SIP_PORT,
    RTP_PORT_LOW,
    RTP_PORT_HIGH,
    DISPATCH_EXTENSION,
    DISPATCH_PASSWORD,
    PHONE_EXTENSION,
    AUTO_CALL_ON_START,
    AUTO_CALL_GREETING,
    LOG_DIR,
)
from voice_dispatch.sip_registrar import SIPRegistrar
from voice_dispatch.vad import VoiceActivityDetector
from voice_dispatch.stt import SpeechToText
from voice_dispatch.brain import Brain
from voice_dispatch.tts_engine import TTSEngine
from voice_dispatch.call_handler import CallHandler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging():
    log_file = LOG_DIR / "dispatch.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file), encoding="utf-8"),
        ],
    )
    # Reduce noise from libraries
    logging.getLogger("pyVoIP").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("dispatch.main")


def _kill_port_holders():
    """Kill any processes holding our SIP/RTP ports from a previous run."""
    import subprocess
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
        pids = set()
        for line in result.stdout.splitlines():
            if ":5060 " in line or ":5062 " in line:
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        if pid != 0 and pid != os.getpid():
                            pids.add(pid)
                    except ValueError:
                        pass
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                             capture_output=True, timeout=5)
                logger.info(f"Killed stale process on SIP port (PID {pid})")
            except Exception:
                pass
        if pids:
            import time
            time.sleep(1)  # Let ports free up
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main startup
# ---------------------------------------------------------------------------
class VoiceDispatchSystem:
    """Orchestrates all components."""

    def __init__(self):
        self.registrar: SIPRegistrar = None
        self.phone = None  # pyVoIP VoIPPhone
        self.call_handler: CallHandler = None
        self.vad = VoiceActivityDetector()
        self.stt = SpeechToText()
        self.brain = Brain()
        self.tts = TTSEngine()
        self._shutdown = threading.Event()

    def start(self):
        """Start the full system."""
        setup_logging()

        banner = f"""
╔══════════════════════════════════════════════╗
║        VOICE DISPATCH SYSTEM v1.0            ║
║                                              ║
║  LAN IP:     {LAN_IP:<33s}║
║  SIP Port:   {SIP_PORT:<33d}║
║  Extension:  {DISPATCH_EXTENSION:<33s}║
║                                              ║
║  From your phone, call: {LAN_IP:<21s}║
╚══════════════════════════════════════════════╝
"""
        print(banner)
        logger.info("Starting Voice Dispatch System...")

        # 0. Kill any stale processes holding our ports
        _kill_port_holders()

        # 1. Start SIP Registrar + set auto-call callback EARLY
        #    (phone may register before models finish loading)
        self._start_registrar()
        if AUTO_CALL_ON_START:
            self.registrar.set_phone_registered_callback(self._auto_call)

        # 2. Load AI models (parallel)
        self._load_models()

        # 3. Create call handler
        self.call_handler = CallHandler(self.vad, self.stt, self.brain, self.tts)

        # 4. Quick TTS sanity test — make sure voice works before first call
        self._test_tts()

        # 5. Start pyVoIP phone
        self._start_voip()

        # 6. If phone already registered while we were loading, auto-call now
        if AUTO_CALL_ON_START and self.registrar.is_extension_registered(PHONE_EXTENSION):
            logger.info("Phone already registered — triggering auto-call")
            threading.Thread(target=self._auto_call, daemon=True).start()

        logger.info("System ready. Waiting for calls...")
        print(f"\n✓ System is LIVE. Call {LAN_IP} from your phone.")
        print(f"  Phone extension: {PHONE_EXTENSION} / password: phone123")
        print(f"  Dial extension {DISPATCH_EXTENSION} to reach the AI.\n")

        # Wait for shutdown
        self._shutdown.wait()

    def _start_registrar(self):
        """Start the built-in SIP registrar."""
        logger.info(f"Starting SIP Registrar on {SIP_HOST}:{SIP_PORT}")
        self.registrar = SIPRegistrar(
            host=SIP_HOST,
            port=SIP_PORT,
            lan_ip=LAN_IP,
        )
        self.registrar.start()
        logger.info("SIP Registrar started")

    def _load_models(self):
        """Load all AI models. Parallel where possible."""
        logger.info("Loading AI models...")

        errors = []

        def load_with_catch(name, fn):
            try:
                fn()
            except Exception as e:
                errors.append((name, e))
                logger.error(f"Failed to load {name}: {e}")

        threads = [
            threading.Thread(target=load_with_catch, args=("VAD", self.vad.load)),
            threading.Thread(target=load_with_catch, args=("STT", self.stt.load)),
            threading.Thread(target=load_with_catch, args=("Brain", self.brain.load)),
            threading.Thread(target=load_with_catch, args=("TTS", self.tts.load)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            for name, err in errors:
                logger.error(f"FAILED: {name} — {err}")
            # Don't stop — some components may still work
            print(f"\n⚠ {len(errors)} model(s) failed to load. Check logs.")
        else:
            logger.info("All models loaded successfully")

    def _test_tts(self):
        """Synthesize a short test phrase to verify TTS works."""
        try:
            logger.info("Testing TTS output...")
            audio, rate = self.tts.synthesize("Ready.")
            if len(audio) > 0:
                from voice_dispatch.audio_utils import tts_float_to_sip
                sip = tts_float_to_sip(audio, source_rate=rate)
                logger.info(
                    f"TTS test OK: {len(audio)} samples at {rate}Hz → "
                    f"{len(sip)} SIP bytes, range=[{audio.min():.2f}, {audio.max():.2f}]"
                )
            else:
                logger.error("TTS test FAILED: produced empty audio")
        except Exception as e:
            logger.error(f"TTS test FAILED: {e}", exc_info=True)

    def _start_voip(self):
        """Start pyVoIP phone and register with our SIP registrar."""
        logger.info("Starting pyVoIP phone...")

        try:
            from pyVoIP.VoIP.VoIP import VoIPPhone
            from pyVoIP.VoIP.VoIP import CallState  # noqa: F401

            self.phone = VoIPPhone(
                server=LAN_IP,
                port=SIP_PORT,
                username=DISPATCH_EXTENSION,
                password=DISPATCH_PASSWORD,
                myIP=LAN_IP,
                callCallback=self._on_incoming_call,
                sipPort=VOIP_SIP_PORT,
                rtpPortLow=RTP_PORT_LOW,
                rtpPortHigh=RTP_PORT_HIGH,
            )
            self.phone.start()
            logger.info(f"pyVoIP phone started on port {VOIP_SIP_PORT}")

        except ImportError:
            # Try alternate import path
            try:
                from pyVoIP.VoIP import VoIPPhone

                self.phone = VoIPPhone(
                    server=LAN_IP,
                    port=SIP_PORT,
                    username=DISPATCH_EXTENSION,
                    password=DISPATCH_PASSWORD,
                    myIP=LAN_IP,
                    callCallback=self._on_incoming_call,
                    sipPort=VOIP_SIP_PORT,
                    rtpPortLow=RTP_PORT_LOW,
                    rtpPortHigh=RTP_PORT_HIGH,
                )
                self.phone.start()
                logger.info(f"pyVoIP phone started on port {VOIP_SIP_PORT}")
            except ImportError:
                logger.error("pyVoIP not installed. Run: pip install pyVoIP")
                raise
        except Exception as e:
            logger.error(f"Failed to start pyVoIP: {e}", exc_info=True)
            raise

    def _on_incoming_call(self, call):
        """Called by pyVoIP when a SIP call comes in."""
        logger.info("Incoming call!")
        # Handle in a new thread so we don't block pyVoIP
        thread = threading.Thread(
            target=self.call_handler.handle_call,
            args=(call,),
            daemon=True,
        )
        thread.start()

    def _auto_call(self):
        """Auto-call the user's phone when it registers. Retries up to 3 times."""
        logger.info("Phone registered! Waiting for system to be ready...")

        # Wait for pyVoIP and call handler to be ready
        for _ in range(60):
            if self.phone is not None and self.call_handler is not None:
                break
            time.sleep(1)

        time.sleep(3)  # Let SIP registration settle

        if self.phone is None:
            logger.warning("pyVoIP phone not ready for auto-call after 60s")
            return

        # Try auto-call up to 3 times
        for attempt in range(1, 4):
            try:
                logger.info(f"Auto-call attempt {attempt}/3...")
                call = self.phone.call(PHONE_EXTENSION)
                if call:
                    logger.info("Auto-call initiated — waiting for answer")
                    self.call_handler.handle_greeting_call(call)
                    return  # Success or handled
                else:
                    logger.warning(f"Auto-call attempt {attempt} returned no call object")
            except Exception as e:
                logger.error(f"Auto-call attempt {attempt} failed: {e}")

            time.sleep(3)  # Wait before retry

        logger.warning("Auto-call failed after 3 attempts. User can still dial 100.")

    def stop(self):
        """Graceful shutdown."""
        logger.info("Shutting down...")
        if self.phone:
            try:
                self.phone.stop()
            except Exception:
                pass
        if self.registrar:
            self.registrar.stop()
        self._shutdown.set()
        logger.info("Shutdown complete")


def main():
    system = VoiceDispatchSystem()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nShutting down...")
        system.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        system.start()
    except KeyboardInterrupt:
        system.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n✗ Fatal error: {e}")
        print("  Check logs at: voice_dispatch/logs/dispatch.log")
        sys.exit(1)


if __name__ == "__main__":
    main()
