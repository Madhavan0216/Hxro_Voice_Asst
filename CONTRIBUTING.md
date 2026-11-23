# Contributing

Hxro Voice Assistant is currently maintained by Madhavan0216.

## Before opening an issue

- Confirm the problem is reproducible on Windows.
- Include the Python version, a minimal reproduction, and relevant console output.
- Never include API keys, phone numbers, personal messages, or screenshots containing private information.

## Before proposing a change

Run the validation commands in the README:

```powershell
python -m compileall -q -f -x '(^|[\\/])(\.venv|venv|__pycache__)([\\/]|$)' .
python test_keys.py
python test_interrupt.py
python test_threshold.py
```

Keep changes focused, preserve existing Windows behavior, and update the README when setup or configuration changes.
