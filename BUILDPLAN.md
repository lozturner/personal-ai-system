# Voice Dispatch System — Build Plan

## What This Is

A local voice dispatch system. You call a number from your Android phone over WiFi, speak a task, and Claude executes it on your PC and talks back. No cloud. No Twilio. No subscriptions. Everything runs on your machine except the Anthropic API call.

**How it works:** Your phone → SIP over WiFi → your PC answers → listens → transcribes → sends to Claude → speaks the response back to you. Like calling a smart assistant that lives in your house.

---

## 1. Dependency Audit

| Package | Version | Windows OK? | Notes |
|---------|---------|-------------|-------|
| `pyVoIP` | 1.6.8 | ✅ | Uses `audioop` (removed in Python 3.13). **Use Python 3.12.** Set `pyVoIP.TRANSMIT_DELAY_REDUCTION = 0.75` if audio jitters on Windows. |
| `faster-whisper` | 1.1.0 | ✅ | Requires `ctranslate2`. CPU works out of the box. CUDA requires matching cuDNN. |
| `ctranslate2` | ≥4.0.0 | ✅ | Installed as faster-whisper dependency. Pre-built Windows wheels available. |
| `coqui-tts` | 0.27.5 | ⚠️ | Community fork (Coqui shut down 2023). Works on Windows but first model download is slow (~500MB). Falls back to `pyttsx3` if it fails. |
| `pyttsx3` | ≥2.98 | ✅ | Uses Windows SAPI voices. Always works. Robotic but reliable fallback. |
| `anthropic` | ≥0.86.0 | ✅ | Pure Python wheel. No platform issues. |
| `torch` | ≥2.1.0 | ✅ | **Install separately with CUDA index URL.** Do NOT `pip install torch` — it gives CPU-only. Use: `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121` |
| `torchaudio` | ≥2.1.0 | ✅ | Must match torch version. Install together. |
| `numpy` | ≥1.26,<2.0 | ✅ | Pin below 2.0 to avoid breaking changes with older torch/coqui. |
| `sounddevice` | ≥0.5.0 | ✅ | PortAudio bundled. Threading issues possible on Windows — we don't use threading with it. |
| `silero-vad` | (via torch.hub) | ✅ | Downloaded automatically on first run. ~2MB. No pip package needed. |

### Critical: Python Version

**Use Python 3.12.x.** Not 3.13+.

`audioop` was removed in Python 3.13. pyVoIP depends on it. If you must use 3.13+, install `audioop-lts` — but 3.12 is the safe path.

---

## 2. Architecture Diagram

```
┌─────────────────┐
│  Android Phone   │
│  (Obi Linphone)  │
│  SIP Client      │
└────────┬────────┘
         │ SIP INVITE (UDP)
         │ over home WiFi
         ▼
┌─────────────────┐
│  SIP Registrar   │  ← Port 5060 (built-in, lightweight)
│  sip_registrar.py│     Routes calls between phone & dispatch
└────────┬────────┘
         │ Forward INVITE
         ▼
┌─────────────────┐
│  pyVoIP Phone    │  ← Port 5062 (registered as ext 100)
│  Answers call    │     Reads/writes 8-bit unsigned PCM @ 8kHz
│  160 bytes/20ms  │
└────────┬────────┘
         │ Raw audio (8-bit unsigned, 8kHz)
         ▼
┌─────────────────┐
│  audio_utils     │  Convert: 8-bit 8kHz → 16-bit signed 16kHz
│  sip_to_pcm16()  │  Format: bytes (640 bytes = 20ms @ 16kHz)
└────────┬────────┘
         │ PCM16 audio (16-bit signed, 16kHz)
         ▼
┌─────────────────┐
│  Silero VAD      │  Detects speech start/stop
│  vad.py          │  Buffers until 1.5s silence
│                  │  Returns: complete utterance (bytes)
└────────┬────────┘
         │ Complete utterance (16-bit PCM bytes)
         ▼
┌─────────────────┐
│  faster-whisper  │  Transcribes audio → text
│  stt.py          │  Input: float32 numpy array
│                  │  Output: string
└────────┬────────┘
         │ Transcribed text (string)
         ▼
┌─────────────────┐
│  Claude Brain    │  Sends to Anthropic API
│  brain.py        │  Maintains conversation history
│                  │  Returns: response text (string)
└────────┬────────┘
         │ Response text (string)
         ▼
┌─────────────────┐
│  Coqui TTS       │  Converts text → audio
│  tts_engine.py   │  Output: float32 numpy array @ 22050Hz
│  (fallback:      │  Fallback: pyttsx3 (Windows SAPI)
│   pyttsx3)       │
└────────┬────────┘
         │ float32 audio array
         ▼
┌─────────────────┐
│  audio_utils     │  Convert: float32 22050Hz → 8-bit 8kHz
│  tts_float_to_   │  Resample + quantize for SIP
│  sip()           │
└────────┬────────┘
         │ 8-bit unsigned PCM (160-byte chunks)
         ▼
┌─────────────────┐
│  pyVoIP Phone    │  Writes audio back to SIP call
│  call.write_     │  Phone plays the AI's voice
│  audio()         │
└─────────────────┘
```

### Data Format Summary

| Stage | Format | Rate | Width |
|-------|--------|------|-------|
| SIP in/out | 8-bit unsigned PCM (u-law decoded) | 8kHz | 1 byte |
| VAD/STT input | 16-bit signed PCM | 16kHz | 2 bytes |
| Whisper input | float32 numpy array | 16kHz | 4 bytes |
| Claude I/O | UTF-8 string | — | — |
| TTS output | float32 numpy array | 22050Hz | 4 bytes |

---

## 3. File Structure

```
personal-ai-system/
├── BUILDPLAN.md                    # This file
├── requirements.txt                # Python dependencies (excludes torch)
├── install.bat                     # Double-click installer (calls install.ps1)
├── install.ps1                     # PowerShell installer — full auto-setup
├── run.bat                         # Double-click launcher (with watchdog)
├── .env                            # API key + settings (created by installer)
│
└── voice_dispatch/
    ├── __init__.py                 # Package marker
    ├── config.py                   # All settings in one place, auto-detects LAN IP
    ├── audio_utils.py              # Audio format conversions (SIP↔PCM↔float)
    ├── sip_registrar.py            # Built-in SIP server (REGISTER + call routing)
    ├── vad.py                      # Silero VAD — detects speech start/stop
    ├── stt.py                      # faster-whisper — speech to text
    ├── brain.py                    # Claude API — conversation engine
    ├── tts_engine.py               # Coqui TTS + pyttsx3 fallback
    ├── call_handler.py             # Main pipeline: listen→think→speak
    ├── session_logger.py           # Logs every call (transcript + audio)
    ├── main.py                     # Entry point — starts everything
    ├── watchdog_runner.py          # Auto-restart wrapper
    │
    ├── logs/                       # Call logs (auto-created)
    │   ├── dispatch.log            # System log
    │   └── YYYYMMDD_HHMMSS/       # Per-call session
    │       ├── transcript.json     # Full conversation
    │       └── recording.wav       # Audio recording
    │
    ├── models/                     # Cached AI models
    │
    └── tests/
        ├── __init__.py
        ├── test_audio.py           # Test format conversions
        ├── test_sip.py             # Test SIP registrar
        ├── test_vad.py             # Test voice activity detection
        ├── test_stt.py             # Test speech-to-text
        ├── test_tts.py             # Test text-to-speech
        └── test_brain.py           # Test Claude API connection
```

---

## 4. Build Order

| # | File(s) | Why This Order | Test Before Moving On |
|---|---------|----------------|----------------------|
| 1 | `config.py` | Everything depends on config. No external deps. | `python -c "from voice_dispatch.config import LAN_IP; print(LAN_IP)"` |
| 2 | `audio_utils.py` | Pure conversion functions. Needed by everything else. | `python -m voice_dispatch.tests.test_audio` |
| 3 | `session_logger.py` | Simple file I/O. No AI deps. | Verify logs/ directory created |
| 4 | `sip_registrar.py` | Core networking. Must work before calls can happen. | `python -m voice_dispatch.tests.test_sip` |
| 5 | `vad.py` | First AI model. Downloads silero on first run. | `python -m voice_dispatch.tests.test_vad` |
| 6 | `stt.py` | Second AI model. Downloads whisper model. | `python -m voice_dispatch.tests.test_stt` |
| 7 | `brain.py` | Needs API key. Quick to test. | `python -m voice_dispatch.tests.test_brain` |
| 8 | `tts_engine.py` | Heaviest dependency (Coqui). Has fallback. | `python -m voice_dispatch.tests.test_tts` |
| 9 | `call_handler.py` | Wires everything together. Needs all above. | Manual: make a SIP call |
| 10 | `main.py` | Entry point. Starts all components. | `python -m voice_dispatch.main` |
| 11 | `watchdog_runner.py` | Wraps main.py. Last piece. | Kill main.py, verify restart |
| 12 | `install.ps1`, `run.bat` | Deployment. After code works. | Run installer on fresh machine |

---

## 5. Test Plan Per Component

### SIP Registrar
```bash
python -m voice_dispatch.tests.test_sip
```
Sends a REGISTER message, verifies 200 OK response, checks extension stored.

### VAD (Voice Activity Detection)
```bash
python -m voice_dispatch.tests.test_vad
```
Loads Silero model, feeds silence (should not trigger), feeds tone (may trigger), verifies utterance boundary detection.

### STT (Speech-to-Text)
```bash
python -m voice_dispatch.tests.test_stt
```
Loads faster-whisper, transcribes silence (should be empty), transcribes tone. For real test: record a WAV of yourself speaking.

### TTS (Text-to-Speech)
```bash
python -m voice_dispatch.tests.test_tts
```
Loads Coqui (or pyttsx3 fallback), synthesizes "Voice dispatch is online", verifies audio output, converts to SIP format, optionally plays through speakers.

### Brain (Claude API)
```bash
python -m voice_dispatch.tests.test_brain
```
Requires `ANTHROPIC_API_KEY` in `.env`. Sends test message, verifies response, tests conversation memory, tests reset.

### Audio Conversions
```bash
python -m voice_dispatch.tests.test_audio
```
Tests all format conversions: SIP→PCM16, PCM16→SIP, TTS float→SIP, PCM16→float32, RMS computation, chunking.

### Full System
```bash
python -m voice_dispatch.main
```
Then call from your phone. Verify: greeting plays, speech detected, transcribed, Claude responds, TTS speaks back.

---

## 6. Known Failure Points (Windows)

| Problem | Error You'll See | Exact Fix |
|---------|-----------------|-----------|
| **Python 3.13 + pyVoIP** | `ModuleNotFoundError: No module named 'audioop'` | Use Python 3.12, or `pip install audioop-lts` |
| **Port 5060 blocked** | Connection timeout from phone | Run `install.ps1` as Administrator, or manually: `netsh advfirewall firewall add rule name="SIP" dir=in action=allow protocol=UDP localport=5060` |
| **RTP ports blocked** | Call connects but no audio | Open UDP 10000-20000: `netsh advfirewall firewall add rule name="RTP" dir=in action=allow protocol=UDP localport=10000-20000` |
| **PyTorch CPU-only installed** | Whisper/VAD very slow | Reinstall: `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121` |
| **Coqui TTS fails to load** | Various import errors | System auto-falls back to pyttsx3. Check `pip install coqui-tts==0.27.5` |
| **numpy 2.0 breaks things** | `AttributeError` in torch/coqui | Pin: `pip install "numpy>=1.26,<2.0"` |
| **pyVoIP audio jitter** | Choppy/distorted audio | Add to top of main.py: `import pyVoIP; pyVoIP.TRANSMIT_DELAY_REDUCTION = 0.75` |
| **Whisper model download fails** | Timeout on first run | Pre-download: `python -c "from faster_whisper import WhisperModel; WhisperModel('base')"` |
| **Windows Defender blocks** | Random connection failures | Add Python and project folder to Windows Defender exclusions |
| **Multiple NICs / VPN** | Wrong LAN IP detected | Set manually: `DISPATCH_LAN_IP=192.168.1.X` in `.env` |
| **ASIO audio conflict** | `sounddevice` import interrupts audio | Set `SD_ENABLE_ASIO=0` before import, or disable exclusive mode in Windows Sound settings |
| **Antivirus blocks UDP** | SIP registration fails | Whitelist `python.exe` in your antivirus |

---

## 7. Android Setup

### App: Obi Linphone (free, open source)

1. **Install** — Google Play Store → search "Linphone" → Install
2. **Open Linphone** → tap the menu (☰) → **Settings**
3. **Add SIP Account:**
   - Tap **SIP Accounts** → **Add account**
   - **Username:** `200`
   - **Password:** `phone123`
   - **Domain:** `YOUR_PC_IP` (e.g. `192.168.1.50` — shown when system starts)
   - **Transport:** `UDP`
   - **Proxy:** leave empty (same as domain)
   - **Registration expiry:** `3600`
   - Tap **Save** / **Connect**

4. **Verify connection:**
   - Status should show green dot / "Registered"
   - If red/yellow: check PC IP, firewall, both on same WiFi

5. **Make a call:**
   - In Linphone's dialer, type `100`
   - Tap the call button
   - You should hear: "Voice dispatch online. Go ahead."

### Alternative Apps
- **GSWave** (Grandstream) — same config fields
- **Obi WiFi Dialer** — same config fields
- **Built-in Android SIP** (Settings → Calls → SIP accounts) — limited, not recommended

### Auto-Call Feature
If `AUTO_CALL=true` in `.env`, the system will **call your phone** as soon as it detects your phone has registered. You'll receive an incoming call saying "Voice dispatch is online and ready."

---

## 8. Estimated Build Time

These are realistic times assuming dependencies install cleanly:

| Phase | Time | Notes |
|-------|------|-------|
| Install Python 3.12 | 5 min | If not already installed |
| Run `install.bat` | 15–30 min | PyTorch download is ~2GB. Coqui models ~500MB |
| Configure `.env` | 2 min | Just the API key |
| Set up Linphone on phone | 5 min | Account config |
| Open firewall (if not admin during install) | 2 min | Manual netsh commands |
| Test individual components | 10 min | Run each test_*.py |
| First real call | 5 min | Moment of truth |
| **Total** | **~45–60 min** | First time. Subsequent starts: double-click run.bat |

---

## Quick Start (TL;DR)

```
1. Double-click install.bat (as admin)
2. Enter your Anthropic API key when prompted
3. Install Linphone on your phone
4. Configure: username=200, password=phone123, domain=YOUR_PC_IP
5. Double-click run.bat
6. Your phone rings. Pick up. Talk.
```
