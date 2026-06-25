"""4.3 Re-grounding — the fight for sanity. At low coherence, a corrupted cue is fired
into the Hopfield net; it settles into the nearest attractor = a surfaced memory.
Sometimes a true recall (a moment of clarity). Sometimes a spurious state = FALSE MEMORY."""
from __future__ import annotations
from core.psyche.corruption import corrupt_vec


async def reground(coherence: float, curr_text: str, ctx, tick: int):
    if coherence >= ctx.cfg["loop"]["ground_below"]:
        return None
    xi, _ = await ctx.encoder.encode(curr_text or ".")
    cue = corrupt_vec(xi, 0.5)
    rec = ctx.hopfield.recall(cue)
    pid = ctx.hopfield.is_stored(rec)
    true_recall = pid is not None
    if not true_recall:
        pid, _ = ctx.hopfield.nearest(rec)   # spurious -> grab nearest anyway = false memory
    frag = ctx.sediment.get_text(pid) if pid else None
    ctx.sediment.insert_recall(ctx.soul_id, tick, cue, pid or "", true_recall)
    return {"frag": frag, "true_recall": true_recall, "recalled_id": pid}
