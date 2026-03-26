"""
Audio format conversions between SIP (8kHz u-law 8-bit) and
processing pipeline (16kHz signed 16-bit).
"""

import audioop
import struct
import numpy as np
from typing import Optional

from voice_dispatch.config import (
    SIP_SAMPLE_RATE,
    PROCESSING_SAMPLE_RATE,
    TTS_SAMPLE_RATE,
)


def sip_to_pcm16(data: bytes) -> bytes:
    """Convert pyVoIP's 8-bit unsigned 8kHz PCM → 16-bit signed 16kHz PCM.

    pyVoIP decodes u-law/a-law to 8-bit unsigned with a bias of 128.
    We reverse that, convert to 16-bit, then upsample 8k→16k.
    """
    # 8-bit unsigned → 8-bit signed (remove bias)
    signed_8 = audioop.bias(data, 1, -128)
    # 8-bit → 16-bit
    pcm16 = audioop.lin2lin(signed_8, 1, 2)
    # Resample 8kHz → 16kHz
    pcm16_resampled, _ = audioop.ratecv(
        pcm16, 2, 1, SIP_SAMPLE_RATE, PROCESSING_SAMPLE_RATE, None
    )
    return pcm16_resampled


def pcm16_to_sip(data: bytes) -> bytes:
    """Convert 16-bit signed 16kHz PCM → 8-bit unsigned 8kHz u-law for pyVoIP.

    Downsample 16k→8k, convert 16→8 bit, add bias for pyVoIP.
    """
    # Resample 16kHz → 8kHz
    resampled, _ = audioop.ratecv(
        data, 2, 1, PROCESSING_SAMPLE_RATE, SIP_SAMPLE_RATE, None
    )
    # 16-bit → 8-bit
    pcm8 = audioop.lin2lin(resampled, 2, 1)
    # 8-bit signed → 8-bit unsigned (add bias for pyVoIP)
    return audioop.bias(pcm8, 1, 128)


def tts_float_to_sip(audio_float: np.ndarray, source_rate: int = TTS_SAMPLE_RATE) -> bytes:
    """Convert TTS float32 output → 8-bit unsigned 8kHz for SIP playback.

    TTS models output float32 arrays at 22050Hz (or other rates).
    We convert to 16-bit PCM, resample down to 8kHz, then to 8-bit unsigned.
    """
    # Clip and convert float32 → int16
    audio_clipped = np.clip(audio_float, -1.0, 1.0)
    pcm16 = (audio_clipped * 32767).astype(np.int16)
    pcm16_bytes = pcm16.tobytes()

    # Resample source_rate → 8kHz
    resampled, _ = audioop.ratecv(
        pcm16_bytes, 2, 1, source_rate, SIP_SAMPLE_RATE, None
    )
    # 16-bit → 8-bit
    pcm8 = audioop.lin2lin(resampled, 2, 1)
    # Signed → unsigned
    return audioop.bias(pcm8, 1, 128)


def tts_float_to_pcm16(audio_float: np.ndarray, source_rate: int = TTS_SAMPLE_RATE) -> bytes:
    """Convert TTS float32 output → 16-bit signed 16kHz PCM."""
    audio_clipped = np.clip(audio_float, -1.0, 1.0)
    pcm16 = (audio_clipped * 32767).astype(np.int16)
    pcm16_bytes = pcm16.tobytes()
    resampled, _ = audioop.ratecv(
        pcm16_bytes, 2, 1, source_rate, PROCESSING_SAMPLE_RATE, None
    )
    return resampled


def pcm16_to_float32(data: bytes) -> np.ndarray:
    """Convert 16-bit signed PCM bytes → float32 numpy array (for whisper)."""
    pcm16 = np.frombuffer(data, dtype=np.int16)
    return pcm16.astype(np.float32) / 32768.0


def compute_rms(data: bytes, sample_width: int = 2) -> float:
    """Compute RMS level of audio data. Useful for silence detection."""
    try:
        return audioop.rms(data, sample_width)
    except Exception:
        return 0.0


def chunk_audio(data: bytes, chunk_size: int) -> list[bytes]:
    """Split audio bytes into fixed-size chunks."""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
