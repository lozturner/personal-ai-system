"""
Session logging — every call is recorded as a structured log file.
Logs transcripts, timestamps, and optionally raw audio.
"""

import json
import wave
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from voice_dispatch.config import LOG_DIR, SAVE_AUDIO_RECORDINGS, SIP_SAMPLE_RATE

logger = logging.getLogger("dispatch.session")


class SessionLogger:
    """Logs a single call session."""

    def __init__(self, caller_id: str = "unknown"):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.caller_id = caller_id
        self.start_time = datetime.now()
        self.turns: list[dict] = []
        self.audio_chunks: list[bytes] = []

        self.session_dir = LOG_DIR / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.session_dir / "transcript.json"
        self.audio_file = self.session_dir / "recording.wav"

        logger.info(f"Session {self.session_id} started for caller {caller_id}")

    def log_turn(self, role: str, text: str, duration_ms: Optional[int] = None):
        """Log a conversation turn (user spoke or AI responded)."""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "text": text,
        }
        if duration_ms is not None:
            turn["duration_ms"] = duration_ms
        self.turns.append(turn)
        logger.info(f"[{role}] {text}")
        self._save_transcript()

    def log_event(self, event: str, details: str = ""):
        """Log a system event (call started, error, etc.)."""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "role": "system",
            "event": event,
            "details": details,
        }
        self.turns.append(turn)
        logger.info(f"[system] {event}: {details}")
        self._save_transcript()

    def add_audio(self, chunk: bytes):
        """Buffer audio for optional recording save."""
        if SAVE_AUDIO_RECORDINGS:
            self.audio_chunks.append(chunk)

    def finish(self):
        """Finalize session — save transcript and audio."""
        self.log_event("call_ended", f"duration={self._duration_str()}")
        self._save_transcript()
        if SAVE_AUDIO_RECORDINGS and self.audio_chunks:
            self._save_audio()
        logger.info(f"Session {self.session_id} finished ({self._duration_str()})")

    def _save_transcript(self):
        """Write transcript JSON to disk."""
        data = {
            "session_id": self.session_id,
            "caller_id": self.caller_id,
            "start_time": self.start_time.isoformat(),
            "turns": self.turns,
        }
        self.log_file.write_text(json.dumps(data, indent=2))

    def _save_audio(self):
        """Save buffered audio as a WAV file."""
        try:
            all_audio = b"".join(self.audio_chunks)
            with wave.open(str(self.audio_file), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(1)  # 8-bit from SIP
                wf.setframerate(SIP_SAMPLE_RATE)
                wf.writeframes(all_audio)
            logger.info(f"Audio saved to {self.audio_file}")
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")

    def _duration_str(self) -> str:
        delta = datetime.now() - self.start_time
        minutes = int(delta.total_seconds() // 60)
        seconds = int(delta.total_seconds() % 60)
        return f"{minutes}m{seconds}s"

    def get_conversation_history(self) -> list[dict]:
        """Return conversation turns for Claude context."""
        return [
            {"role": t["role"], "content": t["text"]}
            for t in self.turns
            if t["role"] in ("user", "assistant") and "text" in t
        ]
