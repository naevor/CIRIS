"""5. SELF-AUTHORING — the creature drifts its character by rewriting prompt fragments and
nudging params. THE ONE HARD RULE (§0): text only, no exec/eval. Every nudge is CLAMPED
to config ranges BEFORE it is applied. The creature can drift, not blow up the laptop."""
from __future__ import annotations
import os
import uuid
import numpy as np

# nudgeable substrate params -> (substrate_group, param_name, config_group, clamp_key)
NUDGE_MAP = {
    "lenia.mu":    ("lenia", "mu", "lenia", "mu"),
    "lenia.sigma": ("lenia", "sigma", "lenia", "sigma"),
    "lenia.T":     ("lenia", "T", "lenia", "T"),
    "rd.F":        ("rd", "F", "rd", "F"),
    "rd.k":        ("rd", "k", "rd", "k"),
}


class SelfAuthor:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.reset()

    def reset(self):
        c = self.cfg
        self.params = {
            "lenia.mu": float(c["lenia"]["mu"]), "lenia.sigma": float(c["lenia"]["sigma"]),
            "lenia.T": float(c["lenia"]["T"]), "rd.F": float(c["rd"]["F"]), "rd.k": float(c["rd"]["k"]),
        }

    def build_edit(self, parsed: dict, born_tick: int):
        """parsed = COGITO reflection JSON -> validated SelfEdit dict (or None)."""
        kind = parsed.get("kind")
        if kind == "prompt_fragment":
            target = parsed.get("target", "NOEMA")
            if target not in ("NOEMA", "CASSIEL", "LYRA", "COGITO"):
                target = "NOEMA"
            content = str(parsed.get("content", "")).strip()[:280]   # ≤280 chars (§5)
            if not content:
                return None
            return self._edit("prompt_fragment", target, content, "", 0.0, born_tick, parsed)
        if kind == "param_nudge":
            param = parsed.get("param", "")
            if param not in NUDGE_MAP:
                return None
            try:
                delta = float(parsed.get("delta", 0.0))
            except (TypeError, ValueError):
                return None
            delta = max(-0.5, min(0.5, delta))   # bounded; absolute value re-clamped on apply
            return self._edit("param_nudge", "substrate", "", param, delta, born_tick, parsed)
        return None

    @staticmethod
    def _edit(kind, target, content, param, delta, born_tick, parsed):
        return {"edit_id": uuid.uuid4().hex[:10], "kind": kind, "target": target,
                "content": content, "param": param, "delta": delta, "born_tick": born_tick,
                "lifespan": int(parsed.get("lifespan", 400)), "calcified": 0}

    def apply(self, edit: dict, voices, cmd_q):
        if edit["kind"] == "prompt_fragment":
            voices.add_self_fragment(edit["target"], edit["content"])
            return {"applied": True, "value": None}
        # param_nudge — clamp BEFORE applying (machine survival)
        grp, name, cgrp, ckey = NUDGE_MAP[edit["param"]]
        lo, hi = self.cfg[cgrp]["clamp"][ckey]
        newv = float(np.clip(self.params[edit["param"]] + edit["delta"], lo, hi))
        self.params[edit["param"]] = newv
        cmd_q.put({"type": "nudge", "target": grp, "param": name, "value": newv})
        return {"applied": True, "value": newv}

    def store_md(self, souls_dir: str, soul_id: str, edit: dict) -> str:
        d = os.path.join(souls_dir, soul_id, "skills")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, edit["edit_id"] + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"---\nedit_id: {edit['edit_id']}\nkind: {edit['kind']}\ntarget: {edit['target']}\n"
                f"param: {edit['param']}\ndelta: {edit['delta']}\nborn_tick: {edit['born_tick']}\n"
                f"lifespan: {edit['lifespan']}\nauthor: COGITO\n---\n\n{edit['content']}\n"
            )
        return path
