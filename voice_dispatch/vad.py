"""
Voice Activity Detection using Silero VAD.

Detects when the user starts and stops speaking.
Buffers audio and returns complete utterances.
"""

import logging
import time
import numpy as np
import torch

from voice_dispatch.config import (
    VAD_THRESHOLD,
    SILENCE_TIMEOUT,
    PROCESSING_SAMPLE_RATE,
)

logger = logging.getLogger("dispatch.vad")


class VoiceActivityDetector:
    """Silero VAD wrapper that collects complete utterances."""

    def __init__(self, threshold: float = VAD_THRESHOLD,
                 silence_timeout: float = SILENCE_TIMEOUT):
        self.threshold = threshold
        self.silence_timeout = silence_timeout
        self.model = None
        self._speech_buffer: list[bytes] = []
        self._is_speaking = False
        self._silence_start: float = 0.0
        self._loaded = False

    def load(self):
        """Load the Silero VAD model."""
        if self._loaded:
            return
        logger.info("Loading Silero VAD model...")
        self.model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self.model.eval()
        self._loaded = True
        logger.info("Silero VAD loaded")

    def reset(self):
        """Reset state for a new utterance."""
        self._speech_buffer.clear()
        self._is_speaking = False
        self._silence_start = 0.0
        if self.model is not None:
            self.model.reset_states()

    def process_chunk(self, pcm16_chunk: bytes) -> bytes | None:
        """Feed a chunk of 16-bit 16kHz PCM audio.

        Returns:
            Complete utterance bytes when speech ends (silence detected),
            or None if still collecting.
        """
        if not self._loaded:
            self.load()

        # Convert to float32 tensor for Silero
        audio_int16 = np.frombuffer(pcm16_chunk, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_float)

        # Silero VAD expects chunks of 512 samples at 16kHz (32ms)
        # Process in 512-sample windows
        chunk_size = 512
        speech_detected_in_chunk = False

        for i in range(0, len(tensor), chunk_size):
            window = tensor[i:i + chunk_size]
            if len(window) < chunk_size:
                # Pad short windows
                window = torch.nn.functional.pad(window, (0, chunk_size - len(window)))

            confidence = self.model(window, PROCESSING_SAMPLE_RATE).item()

            if confidence >= self.threshold:
                speech_detected_in_chunk = True

        if speech_detected_in_chunk:
            if not self._is_speaking:
                logger.debug("Speech started")
                self._is_speaking = True
            self._silence_start = 0.0
            self._speech_buffer.append(pcm16_chunk)
        else:
            if self._is_speaking:
                # Currently in speech, silence detected
                if self._silence_start == 0.0:
                    self._silence_start = time.time()
                    self._speech_buffer.append(pcm16_chunk)  # include transition
                elif time.time() - self._silence_start >= self.silence_timeout:
                    # Silence long enough — utterance complete
                    logger.debug(
                        f"Speech ended after {len(self._speech_buffer)} chunks "
                        f"({self.silence_timeout}s silence)"
                    )
                    utterance = b"".join(self._speech_buffer)
                    self.reset()
                    return utterance
                else:
                    self._speech_buffer.append(pcm16_chunk)

        return None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def buffered_duration_seconds(self) -> float:
        """Approximate duration of buffered audio."""
        total_bytes = sum(len(c) for c in self._speech_buffer)
        # 16-bit = 2 bytes per sample, 16kHz
        return total_bytes / (2 * PROCESSING_SAMPLE_RATE)
