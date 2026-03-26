"""
Test Text-to-Speech.
Run: python -m voice_dispatch.tests.test_tts
"""

import sys


def test_tts():
    print("Testing Text-to-Speech...")

    from voice_dispatch.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.load()
    print(f"  ✓ TTS loaded: {tts.engine_name}")

    # Synthesize a test phrase
    audio, sample_rate = tts.synthesize("Voice dispatch is online and ready.")

    assert len(audio) > 0, "TTS produced empty audio"
    assert sample_rate > 0, "Invalid sample rate"

    duration = len(audio) / sample_rate
    print(f"  ✓ Synthesized {len(audio)} samples at {sample_rate}Hz ({duration:.1f}s)")

    # Test empty string
    audio2, sr2 = tts.synthesize("")
    print(f"  ✓ Empty string handled ({len(audio2)} samples)")

    # Test conversion to SIP format
    from voice_dispatch.audio_utils import tts_float_to_sip
    sip_audio = tts_float_to_sip(audio, source_rate=sample_rate)
    sip_duration = len(sip_audio) / 8000
    print(f"  ✓ Converted to SIP format: {len(sip_audio)} bytes ({sip_duration:.1f}s at 8kHz)")

    # Optionally play it
    try:
        import sounddevice as sd
        print("  Playing test audio...")
        import numpy as np
        sd.play(audio, sample_rate)
        sd.wait()
        print("  ✓ Audio played successfully")
    except Exception as e:
        print(f"  ~ Could not play audio: {e} (non-critical)")

    print("  ✓ TTS tests passed\n")
    return True


if __name__ == "__main__":
    success = test_tts()
    sys.exit(0 if success else 1)
