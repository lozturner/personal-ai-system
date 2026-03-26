"""
Text-to-Speech engine.

Primary: Coqui TTS (natural voice, runs locally)
Fallback: pyttsx3 (Windows SAPI, robotic but always works)
"""

import io
import logging
import numpy as np
from typing import Optional

from voice_dispatch.config import TTS_MODEL_NAME, TTS_FALLBACK, TTS_SAMPLE_RATE

logger = logging.getLogger("dispatch.tts")


class TTSEngine:
    """TTS with automatic fallback."""

    def __init__(self):
        self._coqui_model = None
        self._pyttsx_engine = None
        self._using_fallback = False
        self._loaded = False
        self._sample_rate = TTS_SAMPLE_RATE

    def load(self):
        """Load TTS engine. Try Coqui first, fall back to pyttsx3."""
        if self._loaded:
            return

        # Try Coqui TTS
        try:
            logger.info(f"Loading Coqui TTS model: {TTS_MODEL_NAME}")
            from TTS.api import TTS as CoquiTTS

            self._coqui_model = CoquiTTS(model_name=TTS_MODEL_NAME, progress_bar=True)
            self._sample_rate = self._coqui_model.synthesizer.output_sample_rate
            self._loaded = True
            logger.info(f"Coqui TTS loaded (sample rate: {self._sample_rate}Hz)")
            return
        except Exception as e:
            logger.warning(f"Coqui TTS failed to load: {e}")

        # Fallback to pyttsx3
        if TTS_FALLBACK:
            try:
                logger.info("Falling back to pyttsx3 (Windows SAPI)")
                import pyttsx3
                self._pyttsx_engine = pyttsx3.init()
                self._pyttsx_engine.setProperty("rate", 170)
                self._using_fallback = True
                self._loaded = True
                self._sample_rate = 22050
                logger.info("pyttsx3 loaded as fallback TTS")
                return
            except Exception as e2:
                logger.error(f"pyttsx3 also failed: {e2}")

        raise RuntimeError("No TTS engine available. Install coqui-tts or pyttsx3.")

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Convert text to audio.

        Returns:
            (audio_float32_array, sample_rate)
        """
        if not self._loaded:
            self.load()

        if not text.strip():
            return np.array([], dtype=np.float32), self._sample_rate

        if self._using_fallback:
            return self._synthesize_pyttsx(text)
        else:
            return self._synthesize_coqui(text)

    def _synthesize_coqui(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize with Coqui TTS."""
        try:
            wav = self._coqui_model.tts(text)
            audio = np.array(wav, dtype=np.float32)
            logger.debug(f"Coqui synthesized {len(audio)} samples for '{text[:40]}...'")
            return audio, self._sample_rate
        except Exception as e:
            logger.error(f"Coqui synthesis failed: {e}")
            # Try fallback if available
            if TTS_FALLBACK:
                try:
                    return self._synthesize_pyttsx(text)
                except Exception:
                    pass
            # Return silence
            return np.zeros(self._sample_rate, dtype=np.float32), self._sample_rate

    def _synthesize_pyttsx(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize with pyttsx3 — saves to temp WAV, reads back."""
        import tempfile
        import wave
        import pyttsx3

        if self._pyttsx_engine is None:
            self._pyttsx_engine = pyttsx3.init()
            self._pyttsx_engine.setProperty("rate", 170)

        # pyttsx3 can only save to file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        self._pyttsx_engine.save_to_file(text, tmp_path)
        self._pyttsx_engine.runAndWait()

        # Read the WAV file
        try:
            with wave.open(tmp_path, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
                sample_width = wf.getsampwidth()

            if sample_width == 2:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 1:
                audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
            else:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            logger.debug(f"pyttsx3 synthesized {len(audio)} samples")
            return audio, sample_rate
        except Exception as e:
            logger.error(f"Failed to read pyttsx3 output: {e}")
            return np.zeros(22050, dtype=np.float32), 22050
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def engine_name(self) -> str:
        if self._using_fallback:
            return "pyttsx3 (fallback)"
        return f"Coqui TTS ({TTS_MODEL_NAME})"
