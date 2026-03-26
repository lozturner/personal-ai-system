"""
Call Handler — the main voice processing pipeline.

When a SIP call comes in:
  1. Answer the call
  2. Play greeting
  3. Loop: listen → VAD → STT → Claude → TTS → speak back
  4. Log everything
  5. Handle errors gracefully (speak the error to the caller)
"""

import logging
import time
import threading
from typing import Optional

from voice_dispatch.audio_utils import (
    sip_to_pcm16,
    tts_float_to_sip,
    chunk_audio,
)
from voice_dispatch.config import (
    SIP_CHUNK_SIZE,
    PROCESSING_SAMPLE_RATE,
    SIP_SAMPLE_RATE,
)
from voice_dispatch.vad import VoiceActivityDetector
from voice_dispatch.stt import SpeechToText
from voice_dispatch.brain import Brain
from voice_dispatch.tts_engine import TTSEngine
from voice_dispatch.session_logger import SessionLogger

logger = logging.getLogger("dispatch.call")


class CallHandler:
    """Handles a single voice call through the full pipeline."""

    def __init__(self, vad: VoiceActivityDetector, stt: SpeechToText,
                 brain: Brain, tts: TTSEngine):
        self.vad = vad
        self.stt = stt
        self.brain = brain
        self.tts = tts
        self._active_calls = 0

    def handle_call(self, call):
        """Main call handler — called by pyVoIP when a call comes in.

        Args:
            call: pyVoIP VoIPCall object
        """
        from pyVoIP.VoIP.call import CallState

        self._active_calls += 1
        session = SessionLogger(caller_id="phone")
        session.log_event("call_started", "Incoming call answered")

        try:
            call.answer()
            logger.info("Call answered")

            # Reset conversation for new call
            self.brain.reset_conversation()
            self.vad.reset()

            # Play greeting
            self._speak(call, "Voice dispatch online. Go ahead.", session)

            # Main conversation loop
            while call.state == CallState.ANSWERED:
                try:
                    # Read audio from SIP (20ms chunks)
                    raw_audio = call.read_audio(length=SIP_CHUNK_SIZE, blocking=True)

                    if not raw_audio or len(raw_audio) == 0:
                        continue

                    # Log raw audio
                    session.add_audio(raw_audio)

                    # Convert SIP format → processing format
                    pcm16 = sip_to_pcm16(raw_audio)

                    # Feed to VAD — returns complete utterance when speech ends
                    utterance = self.vad.process_chunk(pcm16)

                    if utterance is not None:
                        # User finished speaking — process the utterance
                        self._process_utterance(call, utterance, session)

                except Exception as e:
                    logger.error(f"Error in call loop: {e}", exc_info=True)
                    # Try to tell the caller something went wrong
                    try:
                        self._speak(call, "I hit an error. Say that again?", session)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Call handler error: {e}", exc_info=True)
            session.log_event("error", str(e))
        finally:
            # Generate summary for cross-call memory
            try:
                summary = self.brain.get_summary()
                session.log_event("call_summary", summary)
            except Exception:
                pass

            session.finish()
            self._active_calls -= 1

            try:
                if call.state != CallState.ENDED:
                    call.hangup()
            except Exception:
                pass

            logger.info("Call ended")

    def _process_utterance(self, call, utterance_pcm16: bytes, session: SessionLogger):
        """Process a complete utterance: STT → Brain → TTS → speak."""
        from pyVoIP.VoIP.call import CallState

        if call.state != CallState.ANSWERED:
            return

        # 1. Transcribe
        start = time.time()
        user_text = self.stt.transcribe(utterance_pcm16)

        if not user_text:
            logger.debug("Empty transcription, ignoring")
            return

        stt_time = time.time() - start
        session.log_turn("user", user_text, duration_ms=int(stt_time * 1000))

        # 2. Send to Claude
        start = time.time()
        response_text = self.brain.think(user_text)
        brain_time = time.time() - start

        session.log_turn("assistant", response_text, duration_ms=int(brain_time * 1000))

        # 3. Speak response
        if call.state == CallState.ANSWERED:
            self._speak(call, response_text, session)

    def _speak(self, call, text: str, session: Optional[SessionLogger] = None):
        """Synthesize text and play it over the SIP call."""
        from pyVoIP.VoIP.call import CallState

        if call.state != CallState.ANSWERED:
            return

        try:
            start = time.time()

            # Synthesize
            audio_float, sample_rate = self.tts.synthesize(text)
            synth_time = time.time() - start

            if len(audio_float) == 0:
                return

            # Convert TTS output → SIP format (8-bit unsigned 8kHz)
            sip_audio = tts_float_to_sip(audio_float, source_rate=sample_rate)

            # Play in chunks matching SIP frame size
            chunks = chunk_audio(sip_audio, SIP_CHUNK_SIZE)
            for chunk in chunks:
                if call.state != CallState.ANSWERED:
                    break
                # Pad short chunks
                if len(chunk) < SIP_CHUNK_SIZE:
                    chunk = chunk + b'\x80' * (SIP_CHUNK_SIZE - len(chunk))
                call.write_audio(chunk)
                # Pace playback: 20ms per 160-byte chunk at 8kHz
                time.sleep(0.018)  # slightly under 20ms to avoid gaps

            logger.debug(f"Spoke '{text[:40]}...' ({synth_time:.1f}s synth, {len(chunks)} chunks)")

        except Exception as e:
            logger.error(f"TTS playback error: {e}", exc_info=True)

    def handle_greeting_call(self, call):
        """Handle the auto-call greeting (system startup notification)."""
        from pyVoIP.VoIP.call import CallState

        try:
            call.answer()
            time.sleep(0.5)  # Give the phone a moment
            self._speak(call, "Voice dispatch is online and ready. You can hang up now, or speak a command.")

            # Listen for a brief response
            self.vad.reset()
            listen_start = time.time()

            while call.state == CallState.ANSWERED and (time.time() - listen_start) < 15:
                try:
                    raw_audio = call.read_audio(length=SIP_CHUNK_SIZE, blocking=True)
                    if not raw_audio:
                        continue
                    pcm16 = sip_to_pcm16(raw_audio)
                    utterance = self.vad.process_chunk(pcm16)
                    if utterance is not None:
                        # They said something — process it like a normal call
                        user_text = self.stt.transcribe(utterance)
                        if user_text:
                            response = self.brain.think(user_text)
                            self._speak(call, response)
                        break
                except Exception:
                    break

            if call.state == CallState.ANSWERED:
                call.hangup()

        except Exception as e:
            logger.error(f"Greeting call error: {e}")
            try:
                call.hangup()
            except Exception:
                pass
