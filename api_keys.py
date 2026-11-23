"""Shared API key pool and rotation logic for Groq clients.

Isolated into its own module so that brain.py and ears.py can both
import the same key state without creating a circular dependency.
"""

import os

from groq import Groq  # type: ignore[import-untyped]


def _looks_like_real_key(key: str) -> bool:
    """
    Return True if key looks like a real Groq API key.
    Groq keys start with 'gsk_' and are at least 40 characters.
    Placeholders like 'your_key_here' or empty strings fail this check.
    """
    return (
        isinstance(key, str)
        and key.startswith("gsk_")
        and len(key) >= 40
    )

# --- API Key Pool ---
_API_KEYS = [
    k for k in [
        os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"),
        os.getenv("GROQ_API_KEY_4"),
    ] if k and _looks_like_real_key(k)
]

if not _API_KEYS:
    raise RuntimeError(
        "No valid Groq API keys found. "
        "Ensure at least one key starting with 'gsk_' is set in .env."
    )

print(f"   (API key pool: {len(_API_KEYS)} valid key(s) loaded)")

# Mutable container so _rotate_key can update it without `global`
_state = {"key_index": 0}


def _get_client() -> Groq:
    """Return a Groq client using the currently active API key."""
    return Groq(api_key=_API_KEYS[_state["key_index"]])


def _rotate_key(ui_callback=None) -> bool:
    """Switch to the next available API key.
    Prints a switching notice and calls ui_callback(text) if provided.
    Returns True if a new key is available, False if all keys exhausted.
    """
    if _state["key_index"] + 1 < len(_API_KEYS):
        _state["key_index"] += 1
        notice = f"[Switching API {_state['key_index']}/{len(_API_KEYS)}]"
        print(notice)
        if ui_callback:
            ui_callback(notice)
        return True
    return False


def _get_key_index() -> int:
    """Return the current key index."""
    return _state["key_index"]
