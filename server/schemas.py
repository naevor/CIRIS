"""7.1 Wire format. The 'state' frames are binary (~30Hz); 'psyche' events are JSON text.
Binary layout: Float32[11] header + uint8 lenia grid + uint8 rd grid."""
from __future__ import annotations
import struct

# header: tick, 6 axes, rho, heartbeat, lenia_dim, rd_dim  -> 11 float32 = 44 bytes
_HEAD = struct.Struct("<11f")


def pack_state(tick: int, ax: dict, rho: float, heartbeat: float,
               lenia: bytes, lenia_dim: int, rd: bytes, rd_dim: int) -> bytes:
    head = _HEAD.pack(float(tick), ax["coherence"], ax["valence"], ax["arousal"],
                      ax["aperture"], ax["vitality"], ax["decoherence"],
                      float(rho), float(heartbeat), float(lenia_dim), float(rd_dim))
    return head + lenia + rd
