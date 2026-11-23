import os
import io
import wave
import numpy as np
import sounddevice as sd
from groq import Groq
from typing import Optional
from api_keys import _API_KEYS, _get_key_index, _rotate_key

sd.default.latency = 'low'
sd.default.blocksize = 1024

SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_THRESHOLD = 0.001
SILENCE_DURATION = 2.5
MAX_DURATION = 20
FIXED_RECORD_SECONDS = 4
# Minimum RMS for a chunk to be considered voice.
# 0.00025 is calibrated to reject fan/hiss noise on a typical
# Windows laptop mic. Override via MIC_RMS_THRESHOLD in .env.
VOICE_RMS_THRESHOLD = float(os.getenv("MIC_RMS_THRESHOLD", "0.00025"))
_active_threshold: float = VOICE_RMS_THRESHOLD


def _calibrate_noise_floor(
    device_index: Optional[int],
    sample_seconds: float = 1.5,
    multiplier: float = 4.0,
) -> float:
    """
    Record 1.5 s of silence at startup and return a threshold
    set at (multiplier × measured ambient RMS).
    Falls back to VOICE_RMS_THRESHOLD if recording fails.
    Called once by start_stream() only.
    """
    try:
        print("   (calibrating mic noise floor — stay silent...)")
        sample = sd.rec(
            int(SAMPLE_RATE * sample_seconds),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocking=True,
            device=device_index,
        )
        ambient_rms = float(np.sqrt(np.mean(np.square(sample))))
        calibrated = max(ambient_rms * multiplier, VOICE_RMS_THRESHOLD)
        print(f"   (noise floor: {ambient_rms:.6f} → threshold set to {calibrated:.6f})")
        return calibrated
    except Exception as e:
        print(f"   (calibration failed: {e} — using default threshold)")
        return VOICE_RMS_THRESHOLD

_stream_started = False
_stream_device_index: Optional[int] = None


def _is_device_usable(device_index: int) -> bool:
    """Return True if PortAudio accepts this input device for our settings."""
    try:
        sd.check_input_settings(
            device=device_index,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
        )
        return True
    except Exception:
        return False


def _get_input_device() -> Optional[int]:
    """Resolve input device from env override, then preferred names, then default."""
    devices = sd.query_devices()

    env_index = (os.getenv("MIC_DEVICE_INDEX") or "").strip()
    if env_index:
        try:
            i = int(env_index)
            if (
                0 <= i < len(devices)
                and int(devices[i]["max_input_channels"]) > 0
                and _is_device_usable(i)
            ):
                print(f"   (using mic index {i}: {devices[i]['name']})")
                return i
            else:
                print(f"⚠️  MIC_DEVICE_INDEX={i} found but device is not usable "
                      f"(channels={devices[i]['max_input_channels'] if 0<=i<len(devices) else 'N/A'}). "
                      f"Falling through.")
        except Exception as e:
            print(f"⚠️  MIC_DEVICE_INDEX={env_index} is invalid or unavailable: {e}")
            print(f"   (falling through to automatic device selection)")

    env_name = (os.getenv("MIC_DEVICE_NAME") or "").strip().lower()
    if env_name:
        for i, d in enumerate(devices):
            name = str(d["name"]).lower()
            if env_name in name and int(d["max_input_channels"]) > 0 and _is_device_usable(i):
                print(f"   (using mic: {d['name']})")
                return i
        if env_name:
            print(f"⚠️  MIC_DEVICE_NAME='{env_name}' not found among connected devices.")
            print(f"   Available input devices: "
                  f"{[d['name'] for d in devices if int(d['max_input_channels']) > 0]}")

    for i, d in enumerate(devices):
        name = str(d["name"]).lower()
        if "oneplus" in name or "buds" in name or "headset" in name:
            if int(d["max_input_channels"]) > 0 and _is_device_usable(i):
                print(f"   (using mic: {d['name']})")
                return i

    for i, d in enumerate(devices):
        name = str(d["name"]).lower()
        if int(d["max_input_channels"]) <= 0:
            continue
        if "microphone" in name and "array" not in name and "stereo mix" not in name and _is_device_usable(i):
            print(f"   ✅ Using mic: {d['name']} (index {i})")
            return i

    print("⚠️  No named mic found. Using system default input device.")
    print("   Set MIC_DEVICE_INDEX or MIC_DEVICE_NAME in .env to override.")
    return None


def _record_chunk(chunk_size: int, device_index: Optional[int]) -> np.ndarray:
    """Record one small audio chunk from the selected input device."""
    return sd.rec(
        chunk_size,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocking=True,
        device=device_index,
    )


def _to_wav_bytes(audio_data: np.ndarray) -> bytes:
    """Convert float audio numpy array to WAV bytes."""
    audio_int16 = (audio_data * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    buf.seek(0)
    return buf.read()


def start_stream() -> bool:
    """Initialize background listening state once and cache chosen microphone."""
    global _stream_started, _stream_device_index
    _stream_device_index = _get_input_device()
    global _active_threshold
    _active_threshold = _calibrate_noise_floor(_stream_device_index)
    _stream_started = True
    return _stream_started


def get_audio_chunk() -> Optional[bytes]:
    """Capture one audio chunk from the initialized microphone stream state."""
    global _stream_started
    if not _stream_started:
        start_stream()
    try:
        fixed = sd.rec(
            int(SAMPLE_RATE * FIXED_RECORD_SECONDS),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocking=True,
            device=_stream_device_index,
        )
        fixed_rms = float(np.sqrt(np.mean(np.square(fixed))))
        print(f"   [mic] RMS={fixed_rms:.8f}", end="\r")
        if fixed_rms > _active_threshold:
            print(f"   [mic] Speech detected! RMS={fixed_rms:.6f}")
            return _to_wav_bytes(fixed)
        return None
    except Exception as e:
        print(f"   Mic error: {e}")
        if _stream_device_index is not None:
            # Fallback path for broken/locked device handles.
            try:
                fixed = sd.rec(
                    int(SAMPLE_RATE * FIXED_RECORD_SECONDS),
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    blocking=True,
                    device=None,
                )
                fixed_rms = float(np.sqrt(np.mean(np.square(fixed))))
                print(f"   [mic-default] RMS={fixed_rms:.8f}", end="\r")
                if fixed_rms > _active_threshold:
                    print(f"   [mic-default] Speech detected! RMS={fixed_rms:.6f}")
                    return _to_wav_bytes(fixed)
            except Exception as e2:
                print(f"   Mic fallback error: {e2}")
        return None


def listen() -> Optional[bytes]:
    """Record audio from mic until silence. Returns raw bytes or None."""
    try:
        print("   (speak now...)")
        print(f"   (recording for {FIXED_RECORD_SECONDS}s...)")
        audio = get_audio_chunk()
        if audio:
            return audio

        print("⚠️  No speech detected in recorded clip. Speak closer to mic and retry.")
        return None

    except Exception as e:
        print(f"⚠️  Mic error: {e}")
        return None


def transcribe(audio_bytes: Optional[bytes]) -> str:
    """Send audio bytes to Groq Whisper and return transcribed text."""
    if not audio_bytes:
        return ""
    try:
        client = Groq(api_key=_API_KEYS[_get_key_index()])
        transcription = client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text",
        )
        return str(transcription).strip()
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate_limit" in err_str.lower() or "tokens per day" in err_str.lower():
            print(f"⚠️  Transcription rate limit on key {_get_key_index() + 1}: {err_str}")
            if _rotate_key():
                try:
                    client = Groq(api_key=_API_KEYS[_get_key_index()])
                    transcription = client.audio.transcriptions.create(
                        file=("audio.wav", audio_bytes),
                        model="whisper-large-v3-turbo",
                        language="en",
                        response_format="text",
                    )
                    return str(transcription).strip()
                except Exception as e2:
                    print(f"⚠️  Transcription retry failed: {e2}")
                    return ""
            return ""
        if "invalid_api_key" in err_str.lower() or "401" in err_str:
            print("⚠️  GROQ_API_KEY is invalid. Update your .env with a valid key from console.groq.com.")
            return "__API_KEY_INVALID__"
        print(f"⚠️  Transcription error: {e}")
        return ""


def get_device_index():
    """Return the cached microphone device index."""
    return _stream_device_index

