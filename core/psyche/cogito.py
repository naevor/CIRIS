"""COGITO — the overseer / synthesis. Builds verdict + reflection messages and
normalizes the JSON into the strict contracts the rest of the system relies on (§6)."""
from __future__ import annotations
import json


def build_lyra_user(prop: str, objections: dict) -> str:
    pts = "; ".join(o.get("point", "") for o in objections.get("objections", []))
    return f"proposition: {prop}\nobjections raised: {pts or 'none'}"


def build_verdict_user(prop: str, objections: dict, resonance: str) -> str:
    return (f"proposition: {prop}\n\n"
            f"cassiel objections (json): {json.dumps(objections.get('objections', []), ensure_ascii=False)}\n"
            f"can_proceed: {objections.get('can_proceed', True)}\n\n"
            f"lyra resonance: {resonance}\n\ndecide the fate of this thought.")


def build_reflect_user(drift: str) -> str:
    return f"the drift so far:\n{drift or '(nothing yet)'}\n\nchoose ONE edit."


def normalize_objections(o: dict) -> dict:
    items = o.get("objections") or []
    clean = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            sev = float(it.get("severity", 0.0))
        except (TypeError, ValueError):
            sev = 0.0
        clean.append({"point": str(it.get("point", ""))[:240], "severity": max(0.0, min(1.0, sev))})
    max_sev = max((c["severity"] for c in clean), default=0.0)
    can = o.get("can_proceed")
    if not isinstance(can, bool):
        can = max_sev < 0.6
    return {"objections": clean, "max_severity": max_sev, "can_proceed": bool(can)}


def normalize_verdict(o: dict) -> dict:
    stance = o.get("stance", "reject")
    if stance not in ("accept", "reject", "continue"):
        stance = "reject"
    dom = o.get("dominant", "NOEMA")
    if dom not in ("NOEMA", "CASSIEL", "LYRA"):
        dom = "NOEMA"
    vote = o.get("vote", "split")
    if vote not in ("3-0", "2-1", "split"):
        vote = "split"
    syn = o.get("synthesis")
    if stance != "accept" or not syn:
        syn = None
    return {"stance": stance, "dominant": dom, "vote": vote,
            "self_note": str(o.get("self_note", ""))[:200],
            "synthesis": (str(syn)[:400] if syn else None)}
