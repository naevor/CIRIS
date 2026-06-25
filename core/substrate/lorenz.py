"""2.1 Continuous chaotic flow — affect / tremor (Lorenz).
rho drifts through the 24.74 bifurcation: below -> fixed point (catatonia),
above -> strange attractor (free association / chaos). Cost: negligible."""
from __future__ import annotations
import math
import numpy as np

BIFURCATION = 24.74


class Lorenz:
    def __init__(self, cfg: dict, rng: np.random.Generator):
        self.sigma = float(cfg["sigma"])
        self.beta = float(cfg["beta"])
        self.rho_min = float(cfg["rho_min"])
        self.rho_max = float(cfg["rho_max"])
        self.dt = float(cfg["dt"])
        self.reseed(rng)

    def reseed(self, rng: np.random.Generator):
        self.x = float(rng.uniform(-9, 9))
        self.y = float(rng.uniform(-9, 9))
        self.z = float(rng.uniform(5, 30))
        self.walk_r = 0.0
        self.t = 0
        self._rng = rng

    def step(self, arousal: float) -> dict:
        # OU noise on rho-walk, clamp +-0.5
        self.walk_r += -0.02 * self.walk_r + float(self._rng.normal(0, 0.05))
        self.walk_r = max(-0.5, min(0.5, self.walk_r))
        rho = 28.0 + 11.0 * math.sin(0.011 * self.t + 0.7) + self.walk_r * 16.0
        rho = max(self.rho_min, min(self.rho_max, rho))

        substeps = int(round(2 + 6 * max(0.0, min(1.0, arousal))))
        vmag = 0.0
        for _ in range(substeps):
            dx = self.sigma * (self.y - self.x)
            dy = self.x * (rho - self.z) - self.y
            dz = self.x * self.y - self.beta * self.z
            self.x += dx * self.dt
            self.y += dy * self.dt
            self.z += dz * self.dt
            vmag += math.sqrt(dx * dx + dy * dy + dz * dz)
        vmag /= max(1, substeps)
        self.t += 1

        arousal_out = math.tanh(vmag / 150.0)
        return {
            "rho": rho,
            "x": self.x,
            "affect_sign": 1.0 if self.x >= 0 else -1.0,
            "arousal": arousal_out,
            "regime": "strange" if rho >= BIFURCATION else "catatonia",
        }
