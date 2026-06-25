"""2.6 Vitals — the six numbers that are the ONLY interface from body to psyche.
Folds substrate signals (PROCESS A) with memory-derived signals (server)."""
from __future__ import annotations
from core.contracts import SubstrateFrame


def _clamp(x, a, b):
    return a if x < a else (b if x > b else x)


def combine(frame: SubstrateFrame, mem: dict, sens: dict, decoherence: float) -> dict:
    frag = frame.lenia_frag_norm
    hse = mem.get("hopfield_settle", 0.3)
    sent = mem.get("structure_entropy", 0.3)

    coherence = _clamp(0.4 * (1 - frag) + 0.3 * (1 - hse) + 0.3 * (1 - sent), 0.0, 1.0)
    arousal = _clamp(frame.arousal + sens.get("arousal_bias", 0.0), 0.0, 1.0)
    valence = _clamp(0.6 * frame.affect_sign * arousal + 0.4 * (frame.rd_growth - frame.rd_decay), -1.0, 1.0)
    aperture = _clamp(frame.slow_osc + sens.get("aperture_bias", 0.0), 0.0, 1.0)
    vitality = _clamp(frame.lenia_vitality, 0.0, 1.0)
    return {
        "coherence": coherence,
        "valence": valence,
        "arousal": arousal,
        "aperture": aperture,
        "vitality": vitality,
        "decoherence": _clamp(decoherence, 0.0, 1.0),
    }
