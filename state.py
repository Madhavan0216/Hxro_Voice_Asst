"""Shared runtime state for Jarvis.

Allows skills.py to signal jarvis.py to enter silence mode
without circular imports. Both modules import this.
"""

import time

# Epoch timestamp until which Jarvis should stay silent (0 = not muted)
_muted_until: float = 0.0


def set_mute(seconds: int) -> None:
    """Tell Jarvis to stay silent for this many seconds from now."""
    global _muted_until
    _muted_until = time.time() + seconds
    print(f"🔇 Muted for {seconds}s (until {time.strftime('%H:%M:%S', time.localtime(_muted_until))})")


def is_muted() -> bool:
    """Return True if Jarvis is currently in silence mode."""
    return time.time() < _muted_until


def remaining_seconds() -> int:
    """How many seconds of silence are left."""
    return max(0, int(_muted_until - time.time()))
