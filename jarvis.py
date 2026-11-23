"""Main entry point for Jarvis on Windows."""

import os
import sys
import time

# Force UTF-8 output so emoji in print() don't crash on Windows cp1252 terminals
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

load_dotenv(override=True)

import state                                           # shared mute state
from brain import think
from ears import get_audio_chunk, start_stream, transcribe, get_device_index
from ui import JarvisUI
from voice import speak, wait_for_speech, interrupt_speech, interruptible_wait


def main() -> None:
    """Run the interactive Jarvis voice loop."""
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY is missing. Add it to your .env file.")
        sys.exit(1)

    SILENT_RESPONSES = {"__SILENT__", "Rate limit reached.",
                        "Rate limit reached. Try again in a few minutes."}

    print("=" * 34)
    print("JARVIS v1.0 — Online")
    print("=" * 34)
    speak("Jarvis online. Ready to assist you.")
    wait_for_speech()

    app = QApplication([])
    ui = JarvisUI()
    ui.show()

    stream = start_stream()
    if not stream:
        print("Error: Could not start audio stream.")
        sys.exit(1)

    while True:
        try:
            # ── Silence / mute check ─────────────────────────────────────────
            # If set_silence was called, skip everything until the timer expires.
            if state.is_muted():
                remaining = state.remaining_seconds()
                print(f"🔇 Silent — {remaining}s remaining", end="\r")
                app.processEvents()
                time.sleep(0.5)
                continue

            # ── Normal listen → think → speak loop ───────────────────────────
            audio = get_audio_chunk()

            if not audio:
                time.sleep(0.3)
                continue

            text = transcribe(audio)
            if text == "__API_KEY_INVALID__":
                speak("API key invalid. Update your .env file.")
                wait_for_speech()
                break
            if not text:
                time.sleep(0.3)
                continue

            # Ignore near-empty transcriptions (mic noise transcribed as "." etc.)
            if len(text.strip()) <= 2:
                continue

            print(f"👤 You: {text}")

            response = think(text)

            # After think(), the skill may have just set a mute — if so, speak
            # the confirmation, then the loop will go silent on next iteration.
            if response:
                print(f"🤖 Jarvis: {response}")
                ui.update_text(f"You: {text}\nJarvis: {response}")
                app.processEvents()

                # Suppress silent / rate-limit responses from being spoken
                if response == "__SILENT__":
                    ui.update_text("API limit reached on all keys.")
                    app.processEvents()
                    continue

                if response in SILENT_RESPONSES or "rate_limit" in response.lower() \
                        or "429" in response or "tokens per day" in response.lower():
                    ui.update_text(f"[API] {response}")
                    app.processEvents()
                    continue

                speak(response)
                interrupted = interruptible_wait(get_device_index())
                if interrupted:
                    # Drain any audio buffered during TTS before re-listening.
                    # This discards the first chunk after an interrupt so speaker
                    # bleed from the tail of TTS is not transcribed.
                    get_audio_chunk()   # discard one chunk — do not transcribe
                    continue

        except KeyboardInterrupt:
            speak("Shutting down.")
            wait_for_speech()
            break


if __name__ == "__main__":
    main()
