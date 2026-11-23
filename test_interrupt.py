import threading, time

# Simulate the TTS thread
def fake_tts():
    time.sleep(0.5)  # "speaking" for 0.5s

# Simulate interruptible_wait with new threshold
THRESHOLD = 0.015

def fake_interruptible_wait(bleed_rms):
    """Returns True only if bleed_rms exceeds new threshold."""
    return bleed_rms > THRESHOLD

# Case 1: TTS bleed (should NOT interrupt)
bleed_rms = 0.008   # typical speaker-into-mic bleed
result = fake_interruptible_wait(bleed_rms)
assert result == False, f"FAIL: TTS self-bleed triggered interrupt at RMS={bleed_rms}"
print("PASS: TTS bleed correctly ignored")

# Case 2: real human voice (should interrupt)
voice_rms = 0.02    # human voice close to mic
result = fake_interruptible_wait(voice_rms)
assert result == True, f"FAIL: real voice not detected at RMS={voice_rms}"
print("PASS: real voice correctly triggers interrupt")

# Case 3: borderline (should NOT interrupt — stay conservative)
borderline_rms = 0.014
result = fake_interruptible_wait(borderline_rms)
assert result == False, f"FAIL: borderline RMS={borderline_rms} should not interrupt"
print("PASS: borderline RMS correctly ignored")
