# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false

"""Diagnostic script to verify microphone capture and optional Groq transcription."""

import argparse
import io
import os
import wave
from typing import Optional

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

try:
    from groq import Groq
except Exception:
    Groq = None

SAMPLE_RATE = 16000
CHANNELS = 1
DEFAULT_DURATION_SECONDS = 4


def list_input_devices() -> None:
    """Print all available input devices with indices and channel counts."""
    devices = sd.query_devices()
    default_input = None
    try:
        default_input = int(sd.default.device[0])
    except Exception:
        try:
            default_input = int(sd.default.device)
        except Exception:
            default_input = None

    print("Available input devices:")
    for idx, dev in enumerate(devices):
        in_channels = int(dev.get("max_input_channels", 0))
        if in_channels > 0:
            marker = " (default)" if default_input == idx else ""
            print(f"  {idx}: {dev.get('name')} | in={in_channels}{marker}")


def choose_input_device(device_index: Optional[int], device_name: Optional[str]) -> Optional[int]:
    """Resolve a valid input device using index/name arguments or environment settings."""
    devices = sd.query_devices()

    if device_index is not None:
        if 0 <= device_index < len(devices) and int(devices[device_index].get("max_input_channels", 0)) > 0:
            return device_index
        return None

    if device_name:
        target = device_name.lower().strip()
        for idx, dev in enumerate(devices):
            if int(dev.get("max_input_channels", 0)) <= 0:
                continue
            name = str(dev.get("name", "")).lower()
            if target in name:
                return idx

    env_name = (os.getenv("MIC_DEVICE_NAME") or "").strip().lower()
    if env_name:
        for idx, dev in enumerate(devices):
            if int(dev.get("max_input_channels", 0)) <= 0:
                continue
            name = str(dev.get("name", "")).lower()
            if env_name in name:
                return idx

    env_index = os.getenv("MIC_DEVICE_INDEX")
    if env_index:
        try:
            idx = int(env_index)
            if 0 <= idx < len(devices) and int(devices[idx].get("max_input_channels", 0)) > 0:
                return idx
        except Exception:
            pass

    try:
        default_idx = int(sd.default.device[0])
        if 0 <= default_idx < len(devices) and int(devices[default_idx].get("max_input_channels", 0)) > 0:
            return default_idx
    except Exception:
        pass

    for idx, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0)) > 0:
            return idx

    return None


def record_audio(duration_seconds: int, device_index: Optional[int]) -> np.ndarray:
    """Record fixed-duration mono audio and return float32 numpy array."""
    frames = int(SAMPLE_RATE * duration_seconds)
    audio = sd.rec(
        frames,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocking=True,
        device=device_index,
    )
    return audio


def audio_to_wav_bytes(audio: np.ndarray) -> bytes:
    """Convert float audio samples to WAV bytes for API transcription."""
    audio_int16 = (audio * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    buffer.seek(0)
    return buffer.read()


def transcribe_with_groq(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes using Groq Whisper when API key is available."""
    if Groq is None:
        return "Groq SDK is not installed in this interpreter."

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "GROQ_API_KEY not set. Skipping transcription."

    try:
        client = Groq(api_key=api_key)
        result = client.audio.transcriptions.create(
            file=("audio.wav", wav_bytes),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text",
        )
        text = str(result).strip()
        return text or "(empty transcription)"
    except Exception as exc:
        return f"Transcription failed: {exc}"


def main() -> None:
    """Run microphone diagnostics and optional transcription."""
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description="Test Jarvis voice input path.")
    parser.add_argument("--list-devices", action="store_true", help="Only list input devices and exit.")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_SECONDS, help="Recording duration in seconds.")
    parser.add_argument("--device-index", type=int, default=None, help="Specific microphone index to use.")
    parser.add_argument("--device-name", type=str, default=None, help="Partial microphone device name to match.")
    parser.add_argument("--no-transcribe", action="store_true", help="Skip Groq transcription test.")
    args = parser.parse_args()

    list_input_devices()
    if args.list_devices:
        return

    selected_device = choose_input_device(args.device_index, args.device_name)
    if selected_device is None:
        print("\nNo valid input device found.")
        return

    selected_name = sd.query_devices(selected_device).get("name", "Unknown input")
    print(f"\nUsing microphone: {selected_name} (index={selected_device})")
    print(f"Recording for {args.duration} seconds. Speak now...")

    try:
        audio = record_audio(args.duration, selected_device)
    except Exception as exc:
        print(f"Recording failed: {exc}")
        return

    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    print(f"Capture stats -> RMS: {rms:.6f}, Peak: {peak:.6f}")

    if rms < 0.0002:
        print("Mic signal is extremely low. Check OS input device and microphone volume.")
    else:
        print("Mic signal detected.")

    if args.no_transcribe:
        print("Transcription skipped (--no-transcribe).")
        return

    wav_bytes = audio_to_wav_bytes(audio)
    transcript = transcribe_with_groq(wav_bytes)
    print(f"Transcription: {transcript}")


if __name__ == "__main__":
    main()
