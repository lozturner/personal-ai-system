"""
Speech-to-Text using faster-whisper.

Converts PCM audio to text transcription.
"""

import logging
import time
import numpy as np

from voice_dispatch.config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    PROCESSING_SAMPLE_RATE,
)

logger = logging.getLogger("dispatch.stt")


class SpeechToText:
    """faster-whisper wrapper for transcription."""

    def __init__(self):
        self.model = None
        self._loaded = False

    def load(self):
        """Load the whisper model. Call once at startup."""
        if self._loaded:
            return
        logger.info(
            f"Loading faster-whisper model '{WHISPER_MODEL_SIZE}' "
            f"on {WHISPER_DEVICE} ({WHISPER_COMPUTE_TYPE})..."
        )
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        self._loaded = True
        logger.info("faster-whisper loaded")

    def transcribe(self, pcm16_audio: bytes) -> str:
        """Transcribe 16-bit 16kHz PCM audio to text.

        Args:
            pcm16_audio: Raw 16-bit signed PCM at 16kHz.

        Returns:
            Transcribed text string, or empty string if nothing detected.
        """
        if not self._loaded:
            self.load()

        # Convert to float32 numpy array (what faster-whisper expects)
        audio_int16 = np.frombuffer(pcm16_audio, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0

        if len(audio_float) == 0:
            return ""

        start = time.time()
        segments, info = self.model.transcribe(
            audio_float,
            beam_size=5,
            language="en",
            vad_filter=True,  # additional VAD filtering
        )

        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        full_text = " ".join(text_parts).strip()
        elapsed = time.time() - start

        if full_text:
            logger.info(f"Transcribed ({elapsed:.1f}s): '{full_text}'")
        else:
            logger.debug(f"No speech detected in audio ({elapsed:.1f}s)")

        return full_text
