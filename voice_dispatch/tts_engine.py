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
        # NOTE: Do NOT create the engine here — pyttsx3 uses Windows COM (SAPI)
        # which is apartment-threaded. The engine must be created in the same
        # thread that will use it (the call handler thread). We just verify
        # import works here, and create the engine lazily on first synthesize.
        if TTS_FALLBACK:
            try:
                logger.info("Falling back to pyttsx3 (Windows SAPI)")
                import pyttsx3  # noqa: F401 — just verify importable
                self._pyttsx_engine = None  # created lazily in calling thread
                self._using_fallback = True
                self._loaded = True
                self._sample_rate = 22050
                logger.info("pyttsx3 available as fallback TTS (engine created on first use)")
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
        """Synthesize using Windows System.Speech via subprocess.

        Runs TTS in a separate process to avoid COM apartment threading
        issues that plague pyttsx3 when called from non-main threads.
        """
        import tempfile
        import wave
        import subprocess
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        # Use PowerShell + System.Speech — works from any thread, any process
        # Escape single quotes in text for PowerShell
        safe_text = text.replace("'", "''")
        ps_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{tmp_path}'); "
            f"$synth.Speak('{safe_text}'); "
            "$synth.Dispose()"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"PowerShell TTS failed: {result.stderr.decode()}")
                # Fall back to pyttsx3 as last resort
                return self._synthesize_pyttsx_direct(text)
        except subprocess.TimeoutExpired:
            logger.error("PowerShell TTS timed out")
            return self._synthesize_pyttsx_direct(text)
        except FileNotFoundError:
            logger.warning("PowerShell not found, trying pyttsx3 directly")
            return self._synthesize_pyttsx_direct(text)

        # Read the WAV file
        try:
            with wave.open(tmp_path, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
                sample_width = wf.getsampwidth()
                n_channels = wf.getnchannels()

            logger.info(
                f"TTS WAV: {n_frames} frames, {sample_rate}Hz, "
                f"{sample_width*8}bit, {n_channels}ch"
            )

            if n_frames == 0:
                logger.warning("TTS produced empty WAV file")
                return np.zeros(sample_rate, dtype=np.float32), sample_rate

            # Convert to mono float32
            if sample_width == 2:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 1:
                audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
            else:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            # Mix to mono if stereo
            if n_channels == 2:
                audio = audio.reshape(-1, 2).mean(axis=1)

            return audio, sample_rate
        except Exception as e:
            logger.error(f"Failed to read TTS output: {e}")
            return np.zeros(22050, dtype=np.float32), 22050
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _synthesize_pyttsx_direct(self, text: str) -> tuple[np.ndarray, int]:
        """Last-resort fallback using pyttsx3 directly."""
        import tempfile
        import wave
        import os
        import pyttsx3

        if self._pyttsx_engine is None:
            self._pyttsx_engine = pyttsx3.init()
            self._pyttsx_engine.setProperty("rate", 170)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        try:
            self._pyttsx_engine.save_to_file(text, tmp_path)
            self._pyttsx_engine.runAndWait()

            with wave.open(tmp_path, "rb") as wf:
                sample_rate = wf.getframerate()
                raw = wf.readframes(wf.getnframes())
                sample_width = wf.getsampwidth()

            if sample_width == 2:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

            return audio, sample_rate
        except Exception as e:
            logger.error(f"pyttsx3 direct also failed: {e}")
            return np.zeros(22050, dtype=np.float32), 22050
        finally:
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
