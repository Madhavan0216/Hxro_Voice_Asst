"""Skills (tools) executor for Jarvis — Windows implementations."""

import json
import os
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Any, Dict

import pyautogui
import requests

from voice import speak

import state  # shared mute state

# Disable pyautogui fail-safe for smoother automation
# (move mouse to top-left corner still triggers it unless disabled)
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------

def _set_volume(level: int) -> str:
    try:
        from ctypes import cast as c_cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = c_cast(interface, POINTER(IAudioEndpointVolume))
        scalar = max(0.0, min(1.0, level / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)  # type: ignore[union-attr]
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Volume error: {e}"


# ---------------------------------------------------------------------------
# App / URL opener
# ---------------------------------------------------------------------------

_APP_MAP: Dict[str, str] = {
    "chrome":        "chrome",
    "google chrome": "chrome",
    "firefox":       "firefox",
    "notepad":       "notepad",
    "calculator":    "calc",
    "explorer":      "explorer",
    "file explorer": "explorer",
    "task manager":  "taskmgr",
    "settings":      "ms-settings:",
    "spotify":       "spotify:",
    "calendar":      "outlookcal:",
    "mail":          "outlookmail:",
    "photos":        "ms-photos:",
    "paint":         "mspaint",
    "word":          "winword",
    "excel":         "excel",
    "powerpoint":    "powerpnt",
    "vs code":       "code",
    "vscode":        "code",
    "terminal":      "wt",
    "cmd":           "cmd",
    "powershell":    "powershell",
    "discord":       "discord",
    "telegram":      "telegram",
    "whatsapp":      "https://web.whatsapp.com",
}


def _open_app(app_name: str) -> str:
    name_lower = app_name.lower().strip()
    target = _APP_MAP.get(name_lower)

    if target is None:
        if name_lower.startswith("http") or "." in name_lower:
            target = app_name if name_lower.startswith("http") else f"https://{app_name}"
        else:
            target = name_lower

    try:
        if target.startswith("http"):
            webbrowser.open(target)
        elif target.endswith(":"):
            subprocess.Popen(["start", "", target], shell=True)
        else:
            subprocess.Popen(target, shell=True)
        return f"Opening {app_name}."
    except Exception as e:
        return f"Could not open {app_name}: {e}"


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------

def _load_contacts() -> Dict[str, str]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _send_whatsapp(contact_name: str, message: str) -> str:
    contacts = _load_contacts()
    number = contacts.get(contact_name.lower())
    if not number:
        return f"Contact '{contact_name}' not found in contacts.json."
    try:
        from pywhatkit.whats import sendwhatmsg_instantly
        sendwhatmsg_instantly(number, message, wait_time=10, tab_close=True)
        return f"WhatsApp message sent to {contact_name}."
    except Exception as e:
        return f"WhatsApp error: {e}"


def _whatsapp_call(contact_name: str) -> str:
    contacts = _load_contacts()
    number = contacts.get(contact_name.lower(), "")
    if not number:
        return f"Contact '{contact_name}' not found in contacts.json."
    clean = number.replace("+", "").replace(" ", "")
    url = f"https://web.whatsapp.com/send?phone={clean}"
    webbrowser.open(url)
    return f"Opened WhatsApp chat for {contact_name}. Click the call button."


# ---------------------------------------------------------------------------
# Spotify — open app via URI, then use keyboard to search and play
# ---------------------------------------------------------------------------

def _play_spotify(query: str) -> str:
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")

    # Check if credentials are real (not placeholders)
    _placeholder_id = client_id in ("", "your_spotify_client_id_here")
    _placeholder_secret = client_secret in ("", "your_spotify_client_secret_here")
    _has_real_creds = not _placeholder_id and not _placeholder_secret

    # ── Path 1: Spotify API (Premium required for playback) ──────────────────
    if _has_real_creds:
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri="http://localhost:8888/callback",
                scope="user-modify-playback-state user-read-playback-state"
            ))
            results = sp.search(q=query, limit=1, type="track")
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                uri = tracks[0]["uri"]
                sp.start_playback(uris=[uri])
                return f"Playing '{tracks[0]['name']}' by {tracks[0]['artists'][0]['name']}."
            return f"No Spotify results for '{query}'."
        except Exception:
            return "Spotify API error. Make sure Spotify is open and you have Premium."

    # ── Path 2: Open Spotify app via URI then automate keyboard ──────────────
    # Only reached when credentials are placeholders (no real API configured)
    encoded = urllib.parse.quote(query)
    subprocess.Popen(f'start "" "spotify:search:{encoded}"', shell=True)
    time.sleep(3.0)

    # 2. Press Tab once to move focus from the search bar to the first result
    pyautogui.press("tab")
    time.sleep(0.3)

    # 3. Press Enter to play the focused result
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Playing '{query}' on Spotify."


# ---------------------------------------------------------------------------
# System commands
# ---------------------------------------------------------------------------

_SYSTEM_CMDS: Dict[str, str] = {
    "shutdown": "shutdown /s /t 5",
    "restart":  "shutdown /r /t 5",
    "lock":     "rundll32.exe user32.dll,LockWorkStation",
    "sleep":    "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
}


def _system_command(command: str) -> str:
    cmd = _SYSTEM_CMDS.get(command.lower())
    if not cmd:
        return f"Unknown system command: {command}"
    try:
        subprocess.Popen(cmd, shell=True)
        return f"Executing {command}."
    except Exception as e:
        return f"System command error: {e}"


# ---------------------------------------------------------------------------
# Weather (wttr.in — no API key needed)
# ---------------------------------------------------------------------------

def _get_weather(city: str) -> str:
    try:
        url = f"https://wttr.in/{requests.utils.quote(city)}?format=3"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
        return f"Could not fetch weather for {city}."
    except Exception as e:
        return f"Weather error: {e}"


# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------

def _web_search(query: str) -> str:
    encoded = requests.utils.quote(query)
    webbrowser.open(f"https://duckduckgo.com/?q={encoded}")
    return f"Searching the web for '{query}'."


# ---------------------------------------------------------------------------
# Time / Date
# ---------------------------------------------------------------------------

def _get_time(query_type: str = "both") -> str:
    now = datetime.now()
    if query_type == "time":
        return f"It's {now.strftime('%I:%M %p')}."
    if query_type == "date":
        return f"Today is {now.strftime('%A, %B %d, %Y')}."
    return f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

def _take_screenshot() -> str:
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = os.path.join(desktop, filename)
        screenshot = pyautogui.screenshot()
        screenshot.save(path)
        return f"Screenshot saved to Desktop as {filename}."
    except Exception as e:
        return f"Screenshot error: {e}"


# ---------------------------------------------------------------------------
# Reminder
# ---------------------------------------------------------------------------

def _set_reminder(minutes: int, message: str) -> str:
    def _remind() -> None:
        time.sleep(minutes * 60)
        speak(f"Reminder: {message}")

    threading.Thread(target=_remind, daemon=True).start()
    return f"Reminder set for {minutes} minute{'s' if minutes != 1 else ''}: {message}"


# ---------------------------------------------------------------------------
# Silence — actually pauses the Jarvis main loop
# ---------------------------------------------------------------------------

def _set_silence(minutes: int) -> str:
    """Signal jarvis.py to stop listening/responding for N minutes."""
    state.set_mute(minutes * 60)
    return f"Going silent for {minutes} minute{'s' if minutes != 1 else ''}."


# ---------------------------------------------------------------------------
# Browser / computer control via pyautogui
# ---------------------------------------------------------------------------

def _browser_action(action: str, value: str = "") -> str:
    try:
        if action == "click":
            if value and "," in value:
                x, y = [int(v.strip()) for v in value.split(",", 1)]
                pyautogui.click(x, y)
                return f"Clicked at ({x}, {y})."
            else:
                pyautogui.click()
                return "Clicked at current position."

        elif action == "double_click":
            if value and "," in value:
                x, y = [int(v.strip()) for v in value.split(",", 1)]
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.doubleClick()
            return "Double-clicked."

        elif action == "right_click":
            if value and "," in value:
                x, y = [int(v.strip()) for v in value.split(",", 1)]
                pyautogui.rightClick(x, y)
            else:
                pyautogui.rightClick()
            return "Right-clicked."

        elif action == "type":
            pyautogui.typewrite(value, interval=0.04)
            return f"Typed: {value}"

        elif action == "press_key":
            pyautogui.press(value.lower())
            return f"Pressed key: {value}"

        elif action == "hotkey":
            keys = [k.strip() for k in value.lower().split("+")]
            pyautogui.hotkey(*keys)
            return f"Pressed hotkey: {value}"

        elif action == "scroll_up":
            amount = int(value) if value.isdigit() else 3
            pyautogui.scroll(amount)
            return f"Scrolled up {amount} clicks."

        elif action == "scroll_down":
            amount = int(value) if value.isdigit() else 3
            pyautogui.scroll(-amount)
            return f"Scrolled down {amount} clicks."

        elif action == "move_to":
            if value and "," in value:
                x, y = [int(v.strip()) for v in value.split(",", 1)]
                pyautogui.moveTo(x, y, duration=0.3)
                return f"Moved mouse to ({x}, {y})."
            return "Move requires 'x,y' coordinates."

        return f"Unknown browser action: {action}"

    except Exception as e:
        return f"Browser action error: {e}"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def execute_skill(name: str, args: Dict[str, Any]) -> str:
    """Route a skill name + args dict to the correct implementation."""
    try:
        if name == "set_volume":
            return _set_volume(int(args.get("level", 50)))
        if name == "open_app":
            return _open_app(str(args.get("app_name", "")))
        if name == "send_whatsapp":
            return _send_whatsapp(str(args.get("contact_name", "")), str(args.get("message", "")))
        if name == "whatsapp_call":
            return _whatsapp_call(str(args.get("contact_name", "")))
        if name == "play_spotify":
            return _play_spotify(str(args.get("query", "")))
        if name == "system_command":
            return _system_command(str(args.get("command", "")))
        if name == "get_weather":
            return _get_weather(str(args.get("city", "Karur")))
        if name == "web_search":
            return _web_search(str(args.get("query", "")))
        if name == "get_time":
            qt = args.get("query_type") or args.get("type") or "both"
            return _get_time(str(qt))
        if name == "take_screenshot":
            return _take_screenshot()
        if name == "set_reminder":
            return _set_reminder(int(args.get("minutes", 1)), str(args.get("message", "reminder")))
        if name == "set_silence":
            return _set_silence(int(args.get("minutes", 5)))
        if name == "browser_action":
            return _browser_action(str(args.get("action", "")), str(args.get("value", "")))
        return f"Unknown skill: {name}"
    except Exception as e:
        return f"Skill '{name}' error: {e}"
