"""
Test audio format conversions.
Run: python -m voice_dispatch.tests.test_audio
"""

import numpy as np
import sys


def test_audio_conversions():
    print("Testing audio format conversions...")

    from voice_dispatch.audio_utils import (
        sip_to_pcm16,
        pcm16_to_sip,
        tts_float_to_sip,
        pcm16_to_float32,
        compute_rms,
        chunk_audio,
    )

    # Test SIP → PCM16 conversion
    # Simulate pyVoIP's 8-bit unsigned PCM at 8kHz (160 bytes = 20ms)
    sip_silence = bytes([128] * 160)  # 128 = silence in unsigned 8-bit
    pcm16 = sip_to_pcm16(sip_silence)
    assert len(pcm16) > 0, "sip_to_pcm16 produced empty output"
    # Should be 2x sample rate = 2x samples, 2 bytes each
    # 160 samples at 8kHz → 320 samples at 16kHz → 640 bytes
    expected_len = 160 * 2 * 2  # upsampled x2, 16-bit = x2 bytes
    print(f"  ✓ SIP→PCM16: {len(sip_silence)}→{len(pcm16)} bytes (expected ~{expected_len})")

    # Test PCM16 → SIP conversion
    pcm16_data = np.zeros(320, dtype=np.int16).tobytes()  # 20ms at 16kHz
    sip_data = pcm16_to_sip(pcm16_data)
    assert len(sip_data) > 0, "pcm16_to_sip produced empty output"
    print(f"  ✓ PCM16→SIP: {len(pcm16_data)}→{len(sip_data)} bytes")

    # Test TTS float → SIP conversion
    # Simulate 1 second of TTS output at 22050Hz
    tts_audio = np.sin(2 * np.pi * 440 * np.arange(22050) / 22050).astype(np.float32)
    sip_tts = tts_float_to_sip(tts_audio, source_rate=22050)
    sip_duration = len(sip_tts) / 8000
    assert len(sip_tts) > 0, "tts_float_to_sip produced empty output"
    print(f"  ✓ TTS float→SIP: {len(tts_audio)} samples → {len(sip_tts)} bytes ({sip_duration:.2f}s)")

    # Test PCM16 → float32
    pcm16_tone = (np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 16000).astype(np.int16)
    float32 = pcm16_to_float32(pcm16_tone.tobytes())
    assert len(float32) == len(pcm16_tone), "Length mismatch"
    assert float32.max() <= 1.0 and float32.min() >= -1.0, "Float32 out of range"
    print(f"  ✓ PCM16→float32: {len(pcm16_tone)} samples, range [{float32.min():.2f}, {float32.max():.2f}]")

    # Test RMS
    rms = compute_rms(pcm16_tone.tobytes(), 2)
    assert rms > 0, "RMS should be > 0 for a tone"
    rms_silence = compute_rms(np.zeros(1000, dtype=np.int16).tobytes(), 2)
    assert rms_silence == 0, "RMS should be 0 for silence"
    print(f"  ✓ RMS: tone={rms:.0f}, silence={rms_silence:.0f}")

    # Test chunking
    data = b'\x00' * 1000
    chunks = chunk_audio(data, 160)
    assert len(chunks) == 7, f"Expected 7 chunks, got {len(chunks)}"  # ceil(1000/160)
    assert len(chunks[0]) == 160
    print(f"  ✓ Chunking: 1000 bytes → {len(chunks)} chunks of 160")

    print("  ✓ All audio conversion tests passed\n")
    return True


if __name__ == "__main__":
    success = test_audio_conversions()
    sys.exit(0 if success else 1)
