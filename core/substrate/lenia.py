"""2.2 Lenia — visible living flesh (continuous CA). Orbium-ish config, FFT convolution.
The heaviest organ. mass -> vitality (mortality driver); fragments -> coherence."""
from __future__ import annotations
import numpy as np

FRAG_REF = 10.0


def _bell(x, m, s):
    return np.exp(-((x - m) / s) ** 2 / 2.0)


class Lenia:
    def __init__(self, cfg: dict, rng: np.random.Generator):
        self.clamp = cfg["clamp"]
        self.grid = int(cfg["grid"])
        self.R = float(cfg["R"])
        self.T = float(cfg["T"])
        self.mu = float(cfg["mu"])
        self.sigma = float(cfg["sigma"])
        self._build_kernel()
        self.reseed(rng)

    def _build_kernel(self):
        n, R = self.grid, self.R
        y, x = np.ogrid[0:n, 0:n]
        x = np.minimum(x, n - x)        # torus distance from origin (corner) -> centered conv
        y = np.minimum(y, n - y)
        D = np.sqrt(x * x + y * y) / R
        K = _bell(D, 0.5, 0.15) * (D < 1)
        K = K / (K.sum() + 1e-12)
        self.fK = np.fft.rfft2(K.astype(np.float64))

    def reseed(self, rng: np.random.Generator):
        n = self.grid
        A = np.zeros((n, n), np.float32)
        cx = cy = n // 2
        yy, xx = np.mgrid[0:n, 0:n]
        for _ in range(int(rng.integers(2, 5))):
            ox = cx + int(rng.integers(-n // 6, n // 6))
            oy = cy + int(rng.integers(-n // 6, n // 6))
            s = (rng.uniform(0.5, 1.0) * self.R) ** 2
            A += (np.exp(-(((xx - ox) ** 2 + (yy - oy) ** 2) / (2 * s)))
                  * float(rng.uniform(0.6, 1.0))).astype(np.float32)
        A += rng.random((n, n)).astype(np.float32) * 0.10
        self.A = np.clip(A, 0, 1).astype(np.float32)
        # vitality = mass / healthy_reference; gradient toward 0 as flesh dissolves -> mortality
        self.mass_ref = self.grid * self.grid * 0.18
        self._frag = 0

    def step(self):
        U = np.fft.irfft2(np.fft.rfft2(self.A.astype(np.float64)) * self.fK, s=(self.grid, self.grid))
        G = _bell(U, self.mu, self.sigma) * 2.0 - 1.0
        self.A = np.clip(self.A + (1.0 / self.T) * G, 0, 1).astype(np.float32)

    def set_params(self, mu=None, sigma=None, T=None):
        if mu is not None:
            lo, hi = self.clamp["mu"]; self.mu = float(np.clip(mu, lo, hi))
        if sigma is not None:
            lo, hi = self.clamp["sigma"]; self.sigma = float(np.clip(sigma, lo, hi))
        if T is not None:
            lo, hi = self.clamp["T"]; self.T = float(np.clip(T, lo, hi))

    def mass(self) -> float:
        return float(self.A.sum())

    def vitality(self) -> float:
        return float(np.clip(self.mass() / self.mass_ref, 0.0, 1.0))

    def frag_norm(self) -> float:
        # cheap connected-components on a 32x32 max-pooled mask
        m = self._maxpool_mask(32, 0.1)
        self._frag = _count_blobs(m)
        return float(min(1.0, self._frag / FRAG_REF))

    def _maxpool_mask(self, size, thr):
        idx = np.linspace(0, self.grid - 1, size).astype(int)
        sub = self.A[np.ix_(idx, idx)]
        return sub > thr

    def downsample_bytes(self, ds: int):
        idx = np.linspace(0, self.grid - 1, ds).astype(int)
        sub = self.A[np.ix_(idx, idx)]
        return (np.clip(sub * 255.0, 0, 255).astype(np.uint8).tobytes(), ds)


def _count_blobs(mask: np.ndarray) -> int:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    n = 0
    for i in range(h):
        for j in range(w):
            if mask[i, j] and not seen[i, j]:
                n += 1
                stack = [(i, j)]
                seen[i, j] = True
                while stack:
                    a, b = stack.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        na, nb = a + da, b + db
                        if 0 <= na < h and 0 <= nb < w and mask[na, nb] and not seen[na, nb]:
                            seen[na, nb] = True
                            stack.append((na, nb))
    return n
