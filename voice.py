"""Offline text-to-speech for Jarvis using pyttsx3.

Root cause of freeze + silence on Windows:
  pyttsx3 uses SAPI5 internally. Calling runAndWait() on a module-level
  singleton engine causes its internal COM event loop to deadlock after
  the first or second call — the thread hangs forever, producing no sound
  and freezing the entire program.

Fix:
  - Spin up a FRESH engine instance for every speak() call (fast on SAPI5).
  - Run it on a daemon thread so the main loop never blocks.
  - Expose wait_for_speech() so jarvis.py can wait until Jarvis finishes
    talking before it starts listening again (prevents mic self-capture).
"""

import os
import threading
import pyttsx3
from typing import Optional

SPEECH_RATE   = 165
SPEECH_VOLUME = 1.0

# Protects against two overlapping speak() calls
_lock = threading.Lock()

# Holds the current TTS thread so callers can join it
_current_thread: Optional[threading.Thread] = None

# Event used to signal TTS interruption
# Single module-level event — do NOT redefine this elsewhere in this file.
_stop_event = threading.Event()

# Seconds to wait after TTS ends before mic is sampled again.
# Prevents speaker bleed from being transcribed as a user command.
POST_SPEECH_COOLDOWN = float(os.getenv("POST_SPEECH_COOLDOWN", "0.8"))


def _pick_male_voice(engine: pyttsx3.Engine) -> None:
    """Select a male voice when one is available on this engine instance."""
    voices = engine.getProperty("voices")
    for voice in voices:
        lowered = f"{voice.name} {voice.id}".lower()
        if "male" in lowered or "david" in lowered or "mark" in lowered:
            engine.setProperty("voice", voice.id)
            return
    if voices:
        engine.setProperty("voice", voices[0].id)


def _speak_worker(text: str) -> None:
    """Create a fresh engine, speak once, then destroy it."""
    with _lock:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", SPEECH_RATE)
            engine.setProperty("volume", SPEECH_VOLUME)
            _pick_male_voice(engine)
            engine.say(text)

            # Watchdog thread: polls _stop_event and calls engine.stop()
            def _watchdog():
                while not _stop_event.is_set():
                    _stop_event.wait(0.1)
                try:
                    engine.stop()
                except Exception:
                    pass

            wd = threading.Thread(target=_watchdog, daemon=True)
            wd.start()

            engine.runAndWait()
            _stop_event.clear()
            engine.stop()
        except Exception as e:
            _stop_event.clear()
            print(f"⚠️  TTS error: {e}")


def speak(text: str) -> None:
    """Speak text in a background thread (non-blocking).
    Call wait_for_speech() afterward if you need to block until done.
    """
    global _current_thread
    if not text or not text.strip():
        return
    t = threading.Thread(target=_speak_worker, args=(text,), daemon=True)
    _current_thread = t
    t.start()


def wait_for_speech() -> None:
    """Block until the current TTS thread finishes speaking."""
    global _current_thread
    t = _current_thread
    if t and t.is_alive():
        t.join()


def interrupt_speech() -> None:
    """Signal the TTS engine to stop immediately."""
    _stop_event.set()


def interruptible_wait(mic_device_index, sample_rate=16000) -> bool:
    """
    Wait for TTS to finish, but monitor mic simultaneously.
    If user starts speaking (RMS > 0.015) during TTS:
      - immediately call interrupt_speech()
      - wait for TTS thread to stop
      - return True (meaning: user interrupted, re-listen immediately)
    If TTS finishes naturally with no interruption:
      - return False
    Uses sounddevice to sample mic in 0.3s chunks during wait.
    """
    import sounddevice as sd
    import numpy as np
    global _current_thread
    t = _current_thread
    if not t or not t.is_alive():
        return False
    while t.is_alive():
        try:
            chunk = sd.rec(
                int(sample_rate * 0.3),
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocking=True,
                device=mic_device_index,
            )
            rms = float(np.sqrt(np.mean(np.square(chunk))))
            if rms > 0.015:
                interrupt_speech()
                t.join(timeout=1.0)
                import time as _time
                _time.sleep(POST_SPEECH_COOLDOWN)
                return True
        except Exception:
            break
    import time as _time
    _time.sleep(POST_SPEECH_COOLDOWN)
    return False

