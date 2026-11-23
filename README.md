# Hxro Voice Assistant

> A Windows-first voice assistant that turns natural language into useful desktop actions.

Hxro Voice Assistant listens through your microphone, transcribes speech with Groq Whisper, uses an LLM to choose an action, and responds with offline Windows text-to-speech. It is designed for personal productivity and local desktop automation rather than unattended server use.

## Features

- Natural voice input and offline text-to-speech responses
- Groq-powered reasoning and speech transcription
- Windows volume control, application launching, screenshots, and system actions
- WhatsApp messaging and contact-based calling shortcuts
- Spotify search and playback integration
- Weather, web search, date/time, reminders, and configurable silence mode
- Optional keyboard and mouse automation through PyAutoGUI
- Microphone device selection and ambient-noise calibration
- Simple PyQt6 status window

## Requirements

- Windows 10 or later
- Python 3.11 or newer
- A working microphone and speakers
- A Groq API key
- Optional: Spotify Developer credentials for API playback

## Installation

1. Clone the repository and enter the project directory.
2. Create and activate a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Create your local configuration:

   ```powershell
   Copy-Item .env.example .env
   ```

5. Add your Groq key to `.env`:

   ```dotenv
   GROQ_API_KEY=gsk_your_key_here
   ```

6. Replace the placeholder values in `contacts.json` if you want to use WhatsApp commands.
7. Start the assistant:

   ```powershell
   python jarvis.py
   ```

Keep `.env` private. It is intentionally ignored by Git.

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Primary Groq API key |
| `GROQ_API_KEY_2`–`GROQ_API_KEY_4` | No | Optional fallback keys for rate-limit rotation |
| `SPOTIFY_CLIENT_ID` | No | Spotify Developer application ID |
| `SPOTIFY_CLIENT_SECRET` | No | Spotify Developer application secret |
| `MIC_DEVICE_INDEX` | No | Explicit PortAudio microphone index |
| `MIC_DEVICE_NAME` | No | Partial microphone name match |
| `MIC_RMS_THRESHOLD` | No | Minimum signal level for speech detection |
| `POST_SPEECH_COOLDOWN` | No | Seconds to wait after speech output before listening |

Use `python test_voice_access.py --list-devices` to inspect available microphones without starting the assistant.

## Project layout

| Path | Purpose |
| --- | --- |
| `jarvis.py` | Application entry point and listen/think/speak loop |
| `brain.py` | Groq conversation and tool-calling orchestration |
| `ears.py` | Microphone selection, calibration, recording, and transcription |
| `voice.py` | Threaded Windows text-to-speech |
| `skills/` | Desktop, browser, messaging, media, and utility actions |
| `ui.py` | Minimal PyQt6 status window |
| `state.py` | Shared silence-mode runtime state |
| `api_keys.py` | API-key validation and fallback rotation |
| `contacts.json` | Local WhatsApp contact aliases |
| `test_*.py` | Focused smoke and diagnostic scripts |

## Validation

Run the lightweight checks before making changes:

```powershell
python -m compileall -q -f -x '(^|[\\/])(\.venv|venv|__pycache__)([\\/]|$)' .
python test_keys.py
python test_interrupt.py
python test_threshold.py
```

The microphone diagnostic accesses hardware only when explicitly run:

```powershell
python test_voice_access.py --list-devices
```

## Safety and privacy

Hxro can launch applications, send messages, automate input, and issue Windows power commands. Review tool behavior before enabling it on a shared or production machine. Do not store API keys, personal contact data, or screenshots in the repository.

The assistant sends recorded audio and prompts to configured third-party services such as Groq. Review their policies before use.

## License

This project is released under the [MIT License](LICENSE).

## Maintainer

Maintained by [Madhavan0216](https://github.com/Madhavan0216).
