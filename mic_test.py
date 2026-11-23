import sounddevice as sd
import numpy as np

input_devices = []
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d["max_input_channels"] > 0:
        input_devices.append(i)
        print(f"  [{i}] {d['name']}")

print(f"\nDefault: device {sd.default.device[0]}")
print("\nTesting each mic for 1.5s... speak now!\n")

for idx in input_devices:
    try:
        audio = sd.rec(int(16000 * 1.5), samplerate=16000, channels=1,
                       dtype="float32", blocking=True, device=idx)
        rms = float(np.sqrt(np.mean(np.square(audio))))
        marker = "<<< GOOD" if rms > 0.00025 else ""
        print(f"  [{idx}] RMS={rms:.6f} {marker}")
    except Exception as e:
        print(f"  [{idx}] ERROR: {e}")
