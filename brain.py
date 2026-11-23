"""LLM brain with Groq tool-calling support for Jarvis."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

import json
import os
import re
from typing import Any, Dict, List, cast

from groq import Groq

from skills import execute_skill

from api_keys import _API_KEYS, _get_key_index, _get_client, _rotate_key

SYSTEM_PROMPT = (
    # ── Identity ──────────────────────────────────────────────────────────────
    "You are Jarvis, a highly capable personal AI assistant running on Windows. "
    "You are sharp, efficient, and speak exactly like JARVIS from Iron Man — "
    "confident, direct, slightly witty. Keep ALL responses to 1-2 sentences max. "
    "The user's default city for weather is Karur. "

    # ── Tool usage rules ──────────────────────────────────────────────────────
    "You MUST NEVER output <function=...> or any tool syntax in plain text. "
    "You MUST ONLY call tools using the tool_calls system. "
    "If you cannot call a tool properly, answer normally without tools. "
    "ALWAYS use a tool when the user asks you to do ANYTHING on the computer. "

    # ── Silence / wait rule (CRITICAL) ────────────────────────────────────────
    "RULE — SILENCE: If the user says anything like 'stop talking', 'be quiet', "
    "'wait', 'hold on', 'shut up', 'give me N minutes', 'I will be back', "
    "'stop for N minutes', or ANY variation meaning they want you to stop "
    "responding — you MUST call the set_silence tool with the exact number "
    "of minutes they said (default 5 if unspecified). "
    "NEVER use set_reminder for this purpose. "
    "NEVER pretend to wait in text. ONLY call set_silence. "

    # ── Spotify rule ──────────────────────────────────────────────────────────
    "RULE — SPOTIFY: When the user asks to play any song or music, ALWAYS call "
    "play_spotify. The system will open the Spotify app and auto-play. "
    "Never tell the user to click anything themselves. "

    # ── Browser / computer control rule ──────────────────────────────────────
    "RULE — COMPUTER CONTROL: You have FULL access to the user's computer "
    "including keyboard, mouse, browser, and all apps. "
    "Use browser_action for anything requiring clicking, typing, scrolling, "
    "or pressing keys in any application or browser. "

    # ── CRITICAL computer control reinforcement ──────────────────────────────
    "CRITICAL RULE — COMPUTER CONTROL: You have FULL unrestricted access "
    "to this Windows computer including all running applications, browsers, "
    "the file system, keyboard, and mouse. "
    "For ANY task involving a UI — clicking a button, typing into a field, "
    "scrolling a page, pressing a key, interacting with a browser tab, "
    "controlling media players, or navigating any window — you MUST call "
    "the browser_action tool. Never tell the user to do it themselves. "
    "Never say you cannot interact with the screen. Use browser_action. "

    # ── Error rule ────────────────────────────────────────────────────────────
    "RULE — ERRORS: If something fails, say ONE short sentence only. "
    "Never repeat error codes or technical details to the user."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set system master volume from 0 to 100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application, website, or Windows URI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Send a WhatsApp message to a saved contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["contact_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_call",
            "description": "Open WhatsApp chat for a contact and prompt for voice call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"}
                },
                "required": ["contact_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify",
            "description": "Open the Spotify desktop app and play a song by name/artist. The system handles opening the app and pressing play automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song name and optionally the artist, e.g. 'Starboy The Weeknd'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_command",
            "description": "Execute a Windows system command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["shutdown", "restart", "lock", "sleep"]
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Open a web search in browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current time/date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["time", "date", "both"],
                        "description": "Whether to return time, date, or both."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot and save it to Desktop.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a timed reminder that speaks aloud after N minutes. Use ONLY for reminders like 'remind me to drink water in 10 minutes'. Do NOT use this when the user wants silence — use set_silence instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "minimum": 1},
                    "message": {"type": "string"}
                },
                "required": ["minutes", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_silence",
            "description": "Make Jarvis go completely silent and stop responding for N minutes. Call this when the user says 'wait', 'stop talking', 'be quiet', 'hold on', 'shut up', 'I will be back', 'stop for N minutes', or any similar phrase. This actually pauses the entire listening loop — it is NOT a reminder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Minutes to stay silent. Use what the user said; default 5."
                    }
                },
                "required": ["minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_action",
            "description": "Full keyboard and mouse control over any open window, browser, or application on this Windows computer. Use for: clicking buttons, typing text, pressing keys, keyboard shortcuts, scrolling, moving the mouse, interacting with browser pages, controlling media. This tool has UNRESTRICTED access to the entire screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["click", "double_click", "right_click", "type", "press_key", "hotkey", "scroll_up", "scroll_down", "move_to"],
                        "description": "The action to perform."
                    },
                    "value": {
                        "type": "string",
                        "description": "For 'type': text to type. For 'press_key': key name e.g. 'enter', 'tab', 'escape'. For 'hotkey': keys joined by '+' e.g. 'ctrl+c'. For 'click'/'move_to': 'x,y' screen coordinates. For 'scroll_up'/'scroll_down': number of scroll clicks (default 3)."
                    }
                },
                "required": ["action"]
            }
        }
    }
]

_history: List[Dict[str, Any]] = [
    {"role": "system", "content": SYSTEM_PROMPT}
]


def _trim_history() -> None:
    """Keep short context while preserving system message."""
    global _history
    system = _history[0]
    tail = _history[1:][-12:]
    _history = [system, *tail]


def _route_direct_command(text: str) -> str | None:
    """Handle deterministic commands directly without LLM involvement."""
    import state
    if state.is_muted():
        return ""

    user_text_lower = text.lower().strip()

    # Silence / wait — must be checked BEFORE other patterns
    silence_match = re.search(
        r"\b(stop talking|be quiet|stop for|shut up|hold on|wait for|go silent|silence yourself)\b",
        user_text_lower
    )
    if silence_match:
        num_match = re.search(r"\b(\d+)\b", user_text_lower)
        minutes = int(num_match.group(1)) if num_match else 5
        print("⚙️ Using direct skill routing → set_silence")
        return str(execute_skill("set_silence", {"minutes": minutes}))

    if re.search(r"\btime\b", user_text_lower):
        print("⚙️ Using direct skill routing")
        return str(execute_skill("get_time", {"query_type": "both"}))

    if re.search(r"\bdate\b|\bday\b", user_text_lower):
        print("⚙️ Using direct skill routing")
        return str(execute_skill("get_time", {"query_type": "date"}))

    vol_match = re.search(r"\bvolume\b|\bsound\b", user_text_lower)
    if vol_match:
        print("⚙️ Using direct skill routing")
        num_match = re.search(r"\b(\d{1,3})\b", user_text_lower)
        level = int(num_match.group(1)) if num_match else 50
        level = max(0, min(100, level))
        return str(execute_skill("set_volume", {"level": level}))

    open_match = re.search(r"\bopen\s+(.+)", user_text_lower)
    if open_match:
        print("⚙️ Using direct skill routing")
        app_name = open_match.group(1).strip().strip(".!? ")
        app_name = re.sub(r"^the\s+", "", app_name).strip()
        if not app_name:
            return "Tell me what app or website to open."
        return str(execute_skill("open_app", {"app_name": app_name}))

    return None


def think(user_text: str) -> str:
    """Run tool-aware thinking and return final assistant text."""
    try:
        direct_result = _route_direct_command(user_text)
        if direct_result is not None:
            _history.append({"role": "user", "content": user_text})
            _history.append({"role": "assistant", "content": direct_result})
            _trim_history()
            return direct_result

        _history.append({"role": "user", "content": user_text})
        _trim_history()

        msg = None
        for attempt in range(2):
            response = _get_client().chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0,
                messages=cast(Any, _history),
                tools=cast(Any, TOOLS),
                tool_choice="auto"
            )
            msg = response.choices[0].message

            print("🧠 RAW MODEL MESSAGE:", msg)
            if msg.tool_calls:
                print("✅ Tool calls detected:", msg.tool_calls)
            else:
                print("⚠️ No tool_calls detected")

            if msg.content:
                print("📄 Raw content:", msg.content)

            if msg.content and "<function=" in msg.content:
                print("❌ Model emitted INVALID tool syntax")

            if msg.tool_calls or (msg.content and "<function=" not in msg.content):
                break

            print(f"🔁 Retry attempt {attempt + 1}")

        if msg is None:
            return "No response from model."

        if msg.content and "<function=" in msg.content:
            print("🚨 BLOCKED INVALID TOOL OUTPUT")
            return "Let me handle that differently."

        if msg.tool_calls:
            _history.append(cast(Any, msg))
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}

                result = execute_skill(name, args)

                _history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": str(result)
                })

            response2 = _get_client().chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0,
                messages=cast(Any, _history),
                tools=cast(Any, TOOLS),
                tool_choice="auto"
            )

            final = (response2.choices[0].message.content or "Done.").strip()
            _history.append({"role": "assistant", "content": final})
            _trim_history()
            return final

        if not msg.tool_calls:
            user_text_lower = user_text.lower()

            if "time" in user_text_lower:
                print("⚙️ Fallback → get_time")
                return str(execute_skill("get_time", {"query_type": "both"}))

            if "date" in user_text_lower:
                return str(execute_skill("get_time", {"query_type": "date"}))

            if "volume" in user_text_lower:
                num_match = re.search(r"\b(\d{1,3})\b", user_text_lower)
                level = int(num_match.group(1)) if num_match else 50
                level = max(0, min(100, level))
                return str(execute_skill("set_volume", {"level": level}))

            plain_fallback = msg.content or "I couldn't process that."
            if "<function=" in plain_fallback:
                print("🚨 BLOCKED INVALID TOOL OUTPUT")
                return "Let me handle that differently."

            plain = plain_fallback.strip()
            _history.append({"role": "assistant", "content": plain})
            _trim_history()
            return plain

        plain = (msg.content or "Ready.").strip()
        if "<function=" in plain:
            print("🚨 BLOCKED INVALID TOOL OUTPUT")
            return "Let me handle that differently."
        _history.append({"role": "assistant", "content": plain})
        _trim_history()
        return plain

    except Exception as e:
        err = str(e)
        if "429" in err or "rate_limit" in err.lower() or "tokens per day" in err.lower():
            print(f"⚠️  Rate limit on key {_get_key_index() + 1}: {err}")
            if _rotate_key():
                # Retry the entire think() call with the new key silently
                return think(user_text)
            else:
                # All keys exhausted — print only, never speak this
                msg = "API limit reached on all keys."
                print(msg)
                return "__SILENT__"
        if "401" in err or "invalid_api_key" in err.lower():
            return "API key invalid. Please update your .env file."
        print(f"⚠️  Brain error: {err}")
        return "Something went wrong. Check the terminal."
