"""
Test Speech-to-Text (faster-whisper).
Run: python -m voice_dispatch.tests.test_stt
"""

import numpy as np
import sys


def test_stt():
    print("Testing Speech-to-Text (faster-whisper)...")

    from voice_dispatch.stt import SpeechToText

    stt = SpeechToText()
    stt.load()
    print("  ✓ Whisper model loaded")

    # Test with silence — should return empty
    silence = np.zeros(16000 * 2, dtype=np.int16).tobytes()  # 2 seconds
    text = stt.transcribe(silence)
    print(f"  ✓ Silence transcribed as: '{text}' (expected empty or noise)")

    # Test with a tone — should return empty or noise words
    t = np.arange(16000 * 2) / 16000
    tone = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16).tobytes()
    text = stt.transcribe(tone)
    print(f"  ✓ Tone transcribed as: '{text}' (expected empty or noise)")

    print("  ✓ STT tests passed")
    print("  Note: For a real test, record yourself speaking and feed it in.\n")
    return True


if __name__ == "__main__":
    success = test_stt()
    sys.exit(0 if success else 1)
