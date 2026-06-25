"""2.3 Reaction-Diffusion — skin / morphogenesis (Gray-Scott).
F modulated by valence, k by coherence. growth_signal -> valence."""
from __future__ import annotations
import numpy as np

GROWTH_SCALE = 3000.0


class ReactionDiffusion:
    def __init__(self, cfg: dict, rng: np.random.Generator):
        self.clamp = cfg["clamp"]
        self.grid = int(cfg["grid"])
        self.Du = float(cfg["Du"])
        self.Dv = float(cfg["Dv"])
        self.F = float(cfg["F"])
        self.k = float(cfg["k"])
        self.dt = 1.0
        self.reseed(rng)

    def reseed(self, rng: np.random.Generator):
        n = self.grid
        self.U = np.ones((n, n), np.float32)
        self.V = np.zeros((n, n), np.float32)
        for _ in range(int(rng.integers(2, 5))):
            r = int(rng.integers(6, 14))
            cx = int(rng.integers(r, n - r)); cy = int(rng.integers(r, n - r))
            self.U[cx - r:cx + r, cy - r:cy + r] = 0.50
            self.V[cx - r:cx + r, cy - r:cy + r] = 0.25
        self.U += (rng.random((n, n)).astype(np.float32) - 0.5) * 0.02
        self._prev = float(self.V.sum())

    @staticmethod
    def _lap(Z):
        return (-Z
                + 0.2 * (np.roll(Z, 1, 0) + np.roll(Z, -1, 0) + np.roll(Z, 1, 1) + np.roll(Z, -1, 1))
                + 0.05 * (np.roll(np.roll(Z, 1, 0), 1, 1) + np.roll(np.roll(Z, 1, 0), -1, 1)
                          + np.roll(np.roll(Z, -1, 0), 1, 1) + np.roll(np.roll(Z, -1, 0), -1, 1)))

    def step(self) -> float:
        U, V = self.U, self.V
        uvv = U * V * V
        self.U = np.clip(U + (self.Du * self._lap(U) - uvv + self.F * (1 - U)) * self.dt, 0, 1).astype(np.float32)
        self.V = np.clip(V + (self.Dv * self._lap(V) + uvv - (self.F + self.k) * V) * self.dt, 0, 1).astype(np.float32)
        vs = float(self.V.sum())
        raw = (vs - self._prev) / (self.grid * self.grid)
        self._prev = vs
        return float(np.tanh(raw * GROWTH_SCALE))

    def set_params(self, F=None, k=None):
        if F is not None:
            lo, hi = self.clamp["F"]; self.F = float(np.clip(F, lo, hi))
        if k is not None:
            lo, hi = self.clamp["k"]; self.k = float(np.clip(k, lo, hi))

    def regime(self) -> str:
        # coarse (F,k) -> texture label
        if self.k < 0.056:
            return "mitosis" if self.F > 0.035 else "coral"
        return "stripes" if self.F > 0.045 else "spots"

    def downsample_bytes(self, ds: int):
        idx = np.linspace(0, self.grid - 1, ds).astype(int)
        sub = self.V[np.ix_(idx, idx)]
        return (np.clip(sub * 600.0, 0, 255).astype(np.uint8).tobytes(), ds)
