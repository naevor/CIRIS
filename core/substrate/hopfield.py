"""2.4 Associative network — real memory (Hopfield).
Held intentionally AT capacity edge: >70 patterns -> spurious states = false memories."""
from __future__ import annotations
import numpy as np


class Hopfield:
    def __init__(self, N: int, capacity: int):
        self.N = int(N)
        self.capacity = int(capacity)
        self.W = np.zeros((self.N, self.N), np.float32)
        self.patterns: list[tuple[str, np.ndarray]] = []  # (thought_id, xi ±1)

    def reset(self):
        self.W[:] = 0.0
        self.patterns.clear()

    def add(self, pid: str, xi: np.ndarray):
        xi = xi.astype(np.float32)
        self.W += np.outer(xi, xi) / self.N
        np.fill_diagonal(self.W, 0.0)
        self.patterns.append((pid, xi))
        while len(self.patterns) > self.capacity:      # forget oldest at the edge
            _, oxi = self.patterns.pop(0)
            self.W -= np.outer(oxi, oxi) / self.N
            np.fill_diagonal(self.W, 0.0)

    def recall(self, cue: np.ndarray, steps: int = 8) -> np.ndarray:
        x = np.sign(cue).astype(np.float32)
        x[x == 0] = 1.0
        for _ in range(steps):
            xn = np.sign(self.W @ x)
            xn[xn == 0] = 1.0
            if np.array_equal(xn, x):
                break
            x = xn
        return x

    def settle_energy(self, cue: np.ndarray) -> float:
        """Fraction of bits that flip while settling — instability proxy [0,1]."""
        if not self.patterns:
            return 0.3
        rec = self.recall(cue)
        c = np.sign(cue); c[c == 0] = 1.0
        return float(np.clip(np.mean(rec != c), 0.0, 1.0))

    def is_stored(self, xi: np.ndarray, tol: float = 0.05):
        for pid, p in self.patterns:
            if np.mean(p != xi) <= tol:
                return pid
        return None

    def nearest(self, xi: np.ndarray):
        best, bestd = None, 2.0
        for pid, p in self.patterns:
            d = float(np.mean(p != xi))
            if d < bestd:
                bestd, best = d, pid
        return best, bestd

    def attractor_norms(self, limit: int = 24):
        """Coarse 'weights of attractors' for god-view: per-pattern self-overlap energy."""
        out = []
        for pid, p in self.patterns[-limit:]:
            out.append({"id": pid, "e": round(float((p @ (self.W @ p)) / self.N), 3)})
        return out
