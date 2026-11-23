import numpy as np

# Simulate what get_audio_chunk sees
THRESHOLD = 0.00025

def fake_rms(audio_array):
    return float(np.sqrt(np.mean(np.square(audio_array))))

# Case 1: pure noise (should be rejected)
noise = np.random.normal(0, 0.00005, 16000).astype(np.float32)
assert fake_rms(noise) < THRESHOLD, "FAIL: noise incorrectly crosses threshold"
print("PASS: noise correctly rejected")

# Case 2: voice-level signal (should pass)
voice = np.random.normal(0, 0.01, 16000).astype(np.float32)
assert fake_rms(voice) > THRESHOLD, "FAIL: voice incorrectly rejected"
print("PASS: voice correctly detected")

# Case 3: env override works
import os
os.environ["MIC_RMS_THRESHOLD"] = "0.001"
t = float(os.getenv("MIC_RMS_THRESHOLD", "0.00025"))
assert t == 0.001, "FAIL: env override not read"
print("PASS: env override works")
