"""6.2 Birth / lineage. New soul = new uuid, fresh seeds, NEW projection matrix
(a different way of encoding the world). Optional inheritance of calcified skills = ancestral memory.
The wheel: descends -> suffers -> rejects itself -> dies -> is reborn into the same cell."""
from __future__ import annotations
import os
import shutil
import uuid
import numpy as np


def new_soul_id() -> str:
    return uuid.uuid4().hex[:12]


def new_seed() -> int:
    return int.from_bytes(os.urandom(4), "little")


def new_projection(seed: int, dim: int, project_to: int) -> np.ndarray:
    """ONE fixed random_projection matrix per soul (§4.2)."""
    rng = np.random.default_rng(seed)
    return rng.standard_normal((dim, project_to)).astype(np.float32)


def build_tombstone(soul_id, born, died, cause, final_thought,
                    dominant_life, peak_coherence, n_thoughts, drift, skills_archived):
    return {
        "soul_id": soul_id,
        "born": born,
        "died": died,
        "cause": cause,
        "final_thought": final_thought,
        "dominant_voice_life": dominant_life,
        "peak_coherence": round(float(peak_coherence), 3),
        "n_thoughts": int(n_thoughts),
        "drift_summary": drift,
        "skills_archived": skills_archived,
    }


def archive_skills(souls_dir: str, graveyard_dir: str, soul_id: str) -> list[str]:
    src = os.path.join(souls_dir, soul_id, "skills")
    if not os.path.isdir(src):
        return []
    dst = os.path.join(graveyard_dir, soul_id)
    os.makedirs(dst, exist_ok=True)
    out = []
    for name in os.listdir(src):
        if name.endswith(".md"):
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
            out.append(name)
    return out
