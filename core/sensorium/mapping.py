"""Map raw sensor amplitudes -> small axis biases (aperture/arousal). Bounded and gentle."""
from __future__ import annotations


def to_biases(cpu: float, mic_rms: float) -> dict:
    # high CPU load -> a little more arousal; sound in the room -> turn toward the witness
    arousal_bias = min(0.15, max(0.0, (cpu - 0.5) * 0.3))
    aperture_bias = min(0.2, max(0.0, mic_rms * 4.0))
    return {"arousal_bias": arousal_bias, "aperture_bias": aperture_bias}
