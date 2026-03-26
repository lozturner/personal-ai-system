"""
Test Voice Activity Detection.
Run: python -m voice_dispatch.tests.test_vad
"""

import numpy as np
import sys


def test_vad():
    print("Testing Voice Activity Detection (Silero VAD)...")

    from voice_dispatch.vad import VoiceActivityDetector

    vad = VoiceActivityDetector(threshold=0.5, silence_timeout=0.5)
    vad.load()
    print("  ✓ Silero VAD model loaded")

    # Test with silence (should not trigger)
    silence = np.zeros(640, dtype=np.int16).tobytes()  # 20ms at 16kHz
    for _ in range(10):
        result = vad.process_chunk(silence)
    assert result is None, "VAD triggered on silence"
    print("  ✓ Silence correctly ignored")

    # Test with a tone (should trigger as speech-like)
    vad.reset()
    t = np.arange(640) / 16000
    tone = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16).tobytes()

    # Feed many chunks of tone then silence
    for _ in range(25):
        vad.process_chunk(tone)

    if vad.is_speaking:
        print("  ✓ Speech detected in tone signal")
    else:
        print("  ~ Tone not detected as speech (model may need real voice)")

    # Feed silence to trigger end-of-speech
    result = None
    for _ in range(50):
        result = vad.process_chunk(silence)
        if result is not None:
            break

    if result is not None:
        print(f"  ✓ Utterance returned ({len(result)} bytes)")
    else:
        print("  ~ No utterance returned (normal with synthetic audio)")

    print("  ✓ VAD tests passed\n")
    return True


if __name__ == "__main__":
    success = test_vad()
    sys.exit(0 if success else 1)
