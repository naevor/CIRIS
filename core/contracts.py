"""Shared cross-process contracts. Picklable dataclasses passed via multiprocessing.Queue."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SubstrateFrame:
    """Raw signals + grids emitted by PROCESS A every substrate-tick.
    The server folds these with memory-derived signals -> final StateVector."""
    tick: int
    rho: float
    regime: str            # 'catatonia' | 'strange'
    heartbeat: float       # phase [0,1), rate ∝ vitality
    slow_osc: float        # slow aperture oscillator [0,1]
    arousal: float         # Lorenz |velocity| norm [0,1]
    affect_sign: float     # sign(x) ∈ {-1,+1}
    lenia_mass: float
    lenia_frag_norm: float # #components / FRAG_REF, clamped [0,1]
    lenia_vitality: float  # mass / mass_ref [0,1]
    rd_growth: float       # max(0, +growth)
    rd_decay: float        # max(0, -growth)
    texture_regime: str
    lenia: bytes           # uint8 downsample, lenia_dim²
    lenia_dim: int
    rd: bytes              # uint8 downsample, rd_dim²
    rd_dim: int
    degraded: bool = False


@dataclass
class StateVector:
    """The only interface from body to psyche + the wire format to the frontend."""
    tick: int
    soul_id: str
    coherence: float
    valence: float
    arousal: float
    aperture: float
    vitality: float
    decoherence: float
    rho: float
    regime: str
    heartbeat: float
    lenia: bytes
    lenia_dim: int
    rd: bytes
    rd_dim: int
