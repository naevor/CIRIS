"""3.3 corrupt(text, d) — the degrading signal (испорченный телефон).
token dropout (p=0.15*d) + adjacent swaps + rare clause reorder. d is clamped: we keep
the skeleton, otherwise it's raw delirium from round one and there's no drift to watch.
Also corrupt_vec(xi, d) — bit-flips a bipolar cue for re-grounding."""
from __future__ import annotations
import random
import numpy as np


def corrupt_text(text: str, d: float, dropout: float = 0.15, max_d: float = 0.9) -> str:
    d = max(0.0, min(max_d, float(d)))
    if d <= 0.0 or not text.strip():
        return text
    toks = text.split()
    out = [t for t in toks if random.random() >= dropout * d]
    if not out:
        out = toks[: max(1, len(toks) // 2)]          # never destroy completely
    for _ in range(int(len(out) * 0.1 * d)):           # adjacent swaps
        if len(out) < 2:
            break
        i = random.randrange(len(out) - 1)
        out[i], out[i + 1] = out[i + 1], out[i]
    if d > 0.5 and random.random() < 0.3:              # rare clause reorder
        clauses = [c.strip() for c in " ".join(out).split(",") if c.strip()]
        if len(clauses) > 2:
            random.shuffle(clauses)
            return ", ".join(clauses)
    res = " ".join(out).strip()
    return res if res else text


def corrupt_vec(xi: np.ndarray, d: float) -> np.ndarray:
    xi = np.array(xi, copy=True)
    n = len(xi)
    k = int(n * 0.5 * max(0.0, min(1.0, float(d))))
    if k > 0:
        idx = np.random.choice(n, k, replace=False)
        xi[idx] = -xi[idx]
    return xi
