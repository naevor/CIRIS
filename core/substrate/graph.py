"""2.5 Self-rewiring graph — topology of thoughts. dict adjacency (no networkx).
Drives context choice (k nearest past thoughts) and structure_entropy -> coherence."""
from __future__ import annotations
import math
from collections import Counter
import numpy as np


class ThoughtGraph:
    def __init__(self, cfg: dict, rng: np.random.Generator):
        self.eta = float(cfg["eta"])
        self.decay = float(cfg["decay"])
        self.prune = float(cfg["prune"])
        self.mutate_p = float(cfg["mutate_p"])
        self.rng = rng
        self.reset()

    def reset(self):
        self.nodes: dict[str, dict] = {}
        self.adj: dict[str, dict[str, float]] = {}
        self.order: list[str] = []

    def add_node(self, tid: str, tick: int, text: str = ""):
        self.nodes[tid] = {"born": tick, "text": text[:60]}
        self.adj.setdefault(tid, {})
        self.order.append(tid)

    def coactivate(self, a: str, b: str):
        if a == b or a not in self.adj or b not in self.adj:
            return
        self.adj[a][b] = self.adj[a].get(b, 0.0) + self.eta
        self.adj[b][a] = self.adj[b].get(a, 0.0) + self.eta

    def tick_decay(self):
        for a in list(self.adj):
            for b in list(self.adj[a]):
                w = self.adj[a][b] * self.decay
                if w < self.prune:
                    del self.adj[a][b]
                else:
                    self.adj[a][b] = w
        # mutate: rare random rewire
        if len(self.order) > 3 and self.rng.random() < self.mutate_p * max(1, len(self.order)):
            a, b = self.rng.choice(self.order, 2, replace=False)
            self.coactivate(str(a), str(b))

    def k_nearest(self, tid: str, k: int = 3) -> list[str]:
        if tid in self.adj and self.adj[tid]:
            ranked = sorted(self.adj[tid].items(), key=lambda kv: -kv[1])
            return [b for b, _ in ranked[:k]]
        return [t for t in self.order[-k - 1:-1]]

    def structure_entropy(self) -> float:
        degs = [len(self.adj[a]) for a in self.adj if self.adj[a]]
        if len(degs) < 2:
            return 0.3
        c = Counter(degs)
        total = sum(c.values())
        ent = -sum((v / total) * math.log(v / total + 1e-12) for v in c.values())
        maxent = math.log(len(c)) if len(c) > 1 else 1.0
        return float(min(1.0, ent / maxent)) if maxent > 0 else 0.3

    def snapshot(self, limit: int = 40) -> dict:
        ids = self.order[-limit:]
        s = set(ids)
        nodes = [{"id": i, "born": self.nodes[i]["born"], "t": self.nodes[i]["text"]} for i in ids]
        edges = []
        for a in ids:
            for b, w in self.adj.get(a, {}).items():
                if b in s and a < b:
                    edges.append({"u": a, "v": b, "w": round(w, 3)})
        return {"nodes": nodes, "edges": edges}
