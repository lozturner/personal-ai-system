"""
Central configuration for Voice Dispatch System.
All settings in one place. Override via .env file or environment variables.
"""

import os
import socket
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"
LOG_DIR.mkdir(exist_ok=True)
MODEL_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Network — auto-detect LAN IP so the phone can reach us
# ---------------------------------------------------------------------------
def _get_lan_ip() -> str:
    """Return this machine's LAN IP (e.g. 192.168.1.x)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LAN_IP = os.environ.get("DISPATCH_LAN_IP", _get_lan_ip())

# SIP registrar — the tiny built-in SIP server
SIP_HOST = "0.0.0.0"
SIP_PORT = int(os.environ.get("SIP_PORT", "5060"))

# pyVoIP endpoint — registers with our local registrar
VOIP_SIP_PORT = int(os.environ.get("VOIP_SIP_PORT", "5062"))
RTP_PORT_LOW = int(os.environ.get("RTP_PORT_LOW", "10000"))
RTP_PORT_HIGH = int(os.environ.get("RTP_PORT_HIGH", "20000"))

# Extensions
DISPATCH_EXTENSION = "100"   # the AI answers here
DISPATCH_PASSWORD = "dispatch123"
PHONE_EXTENSION = "200"      # the user's Android phone
PHONE_PASSWORD = "phone123"

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Haiku is 10x cheaper and ~3x faster than Sonnet — ideal for voice
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """You are Loz's voice dispatch AI running on his home PC.
He calls from his phone while out. This is a PHONE CALL — keep every
response under 2 sentences. No filler. No "certainly" or "of course".
Just answer directly. If unclear, ask one short question.
Remember the full conversation within this call."""

# ---------------------------------------------------------------------------
# Speech-to-Text (faster-whisper)
# ---------------------------------------------------------------------------
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")  # "cpu" or "cuda"
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE", "int8")

# ---------------------------------------------------------------------------
# Text-to-Speech (Coqui TTS)
# ---------------------------------------------------------------------------
TTS_MODEL_NAME = os.environ.get(
    "TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC"
)
TTS_FALLBACK = True  # fall back to pyttsx3 if Coqui fails

# ---------------------------------------------------------------------------
# Voice Activity Detection (Silero VAD)
# ---------------------------------------------------------------------------
VAD_THRESHOLD = float(os.environ.get("VAD_THRESHOLD", "0.5"))
# Seconds of silence before we consider the user done speaking
# 0.8s is snappy for voice — 1.5s feels sluggish on a call
SILENCE_TIMEOUT = float(os.environ.get("SILENCE_TIMEOUT", "0.8"))

# ---------------------------------------------------------------------------
# Auto-call — ring the user's phone when system starts
# ---------------------------------------------------------------------------
AUTO_CALL_ON_START = os.environ.get("AUTO_CALL", "true").lower() == "true"
AUTO_CALL_GREETING = "Voice dispatch is online. You're connected."

# ---------------------------------------------------------------------------
# Audio formats
# ---------------------------------------------------------------------------
SIP_SAMPLE_RATE = 8000       # u-law/a-law over SIP
SIP_SAMPLE_WIDTH = 1         # 8-bit
PROCESSING_SAMPLE_RATE = 16000  # what VAD/STT expect
PROCESSING_SAMPLE_WIDTH = 2     # 16-bit signed
TTS_SAMPLE_RATE = 22050      # Coqui TTS output rate

# pyVoIP reads 160 bytes = 20ms at 8kHz 8-bit
SIP_CHUNK_SIZE = 160
# Equivalent in 16kHz 16-bit = 640 bytes (20ms)
PROCESSING_CHUNK_SIZE = 640

# ---------------------------------------------------------------------------
# Session / logging
# ---------------------------------------------------------------------------
MAX_CONVERSATION_TURNS = 50
SAVE_AUDIO_RECORDINGS = os.environ.get("SAVE_AUDIO", "true").lower() == "true"
