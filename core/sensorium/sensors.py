"""8. Sensorium — amplitude/brightness ONLY, local, no recording, no sending (§0 rule 3).
psutil metrics; optional mic RMS. Off by default (config.sensorium.enabled). One flag to kill it."""
from __future__ import annotations

try:
    import psutil
except Exception:
    psutil = None

from core.sensorium.mapping import to_biases


class Sensorium:
    def __init__(self, cfg: dict):
        s = cfg.get("sensorium", {})
        self.enabled = bool(s.get("enabled", False))
        self.use_cpu = bool(s.get("cpu", True)) and psutil is not None
        self.use_mic = bool(s.get("mic", False))
        self._mic = None
        if self.enabled and self.use_mic:
            self._try_mic()

    def _try_mic(self):
        try:
            import sounddevice as sd  # noqa: F401
            self._mic = sd
        except Exception:
            self._mic = None

    def sample(self) -> dict:
        if not self.enabled:
            return {"arousal_bias": 0.0, "aperture_bias": 0.0}
        cpu = 0.0
        if self.use_cpu and psutil is not None:
            cpu = psutil.cpu_percent(interval=None) / 100.0
        mic_rms = 0.0
        if self._mic is not None:
            try:
                rec = self._mic.rec(1024, samplerate=16000, channels=1, blocking=True)
                import numpy as np
                mic_rms = float(np.sqrt(np.mean(rec.astype("float32") ** 2)))
            except Exception:
                mic_rms = 0.0
        return to_biases(cpu, mic_rms)
