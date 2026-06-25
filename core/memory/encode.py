"""4.2 Encode — thought -> bipolar vector. embed (nomic) -> random_projection 768->512 -> sign.
Projection matrix is ONE per soul (fixed in birth seed). Hash fallback if embedder is down."""
from __future__ import annotations
import hashlib
import numpy as np
import httpx


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class Encoder:
    def __init__(self, cfg: dict, client: httpx.AsyncClient, projection: np.ndarray):
        self.host = cfg["model"]["host"]
        self.model = cfg["embed"]["name"]
        self.dim = int(cfg["embed"]["dim"])
        self.fallback = bool(cfg["embed"].get("fallback_hash", True))
        self.client = client
        self.R = projection  # (dim, project_to)

    async def embed(self, text: str) -> np.ndarray:
        text = (text or "").strip() or "."
        try:
            r = await self.client.post(self.host + "/api/embed",
                                       json={"model": self.model, "input": text}, timeout=30)
            if r.status_code == 200:
                v = r.json().get("embeddings")
                if v:
                    return np.asarray(v[0], dtype=np.float32)
            r = await self.client.post(self.host + "/api/embeddings",
                                       json={"model": self.model, "prompt": text}, timeout=30)
            v = r.json().get("embedding")
            if v:
                return np.asarray(v, dtype=np.float32)
        except Exception:
            pass
        if self.fallback:
            return self._hash_embed(text)
        raise RuntimeError("embedding failed and fallback disabled")

    def _hash_embed(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, np.float32)
        for tok in text.lower().split():
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
        n = float(np.linalg.norm(v))
        return v / n if n > 1e-9 else v

    def project(self, e: np.ndarray) -> np.ndarray:
        if e.shape[0] != self.R.shape[0]:
            e2 = np.zeros(self.R.shape[0], np.float32)
            m = min(e.shape[0], self.R.shape[0])
            e2[:m] = e[:m]
            e = e2
        ep = e @ self.R
        return np.where(ep - ep.mean() >= 0, 1, -1).astype(np.int8)

    async def encode(self, text: str):
        e = await self.embed(text)
        return self.project(e), e
