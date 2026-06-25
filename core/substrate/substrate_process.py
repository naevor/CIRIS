"""PROCESS A — substrate loop @ substrate_hz. Pure math, no LLM, numpy on CPU.
Emits SubstrateFrame into a multiprocessing.Queue. Watchdog auto-degrades on overrun."""
from __future__ import annotations
import math
import queue
import time
import numpy as np

from core.contracts import SubstrateFrame
from core.substrate.lorenz import Lorenz
from core.substrate.lenia import Lenia
from core.substrate.reaction_diffusion import ReactionDiffusion


def run_substrate(cfg: dict, state_q, cmd_q, seed: int):
    rng = np.random.default_rng(seed)
    lorenz = Lorenz(cfg["lorenz"], rng)
    lenia = Lenia(cfg["lenia"], rng)
    rd = ReactionDiffusion(cfg["rd"], rng)

    hz = int(cfg["clocks"]["substrate_hz"])
    period = 1.0 / hz
    lenia_every = max(1, round(hz / cfg["clocks"]["lenia_hz"]))
    rd_every = max(1, round(hz / cfg["clocks"]["rd_hz"]))
    lenia_ds = int(cfg["ws"]["lenia_ds"])
    rd_ds = int(cfg["ws"]["rd_ds"])
    wd_ms = float(cfg["watchdog"]["frametime_ms"])
    wd_strikes = int(cfg["watchdog"]["strikes"])

    tick = 0
    arousal = 0.5
    heartbeat = 0.0
    strikes = 0
    degraded = False
    rd_growth = 0.0
    lenia_vit = 1.0
    frag = 0.0

    while True:
        t0 = time.perf_counter()

        # --- commands from server ---
        try:
            while True:
                cmd = cmd_q.get_nowait()
                kind = cmd.get("type")
                if kind == "shutdown":
                    return
                if kind == "rebirth":
                    lorenz.reseed(rng)
                    lenia.reseed(rng)
                    rd.reseed(rng)
                    arousal = 0.5
                    heartbeat = 0.0
                    degraded = False
                    lenia_every = max(1, round(hz / cfg["clocks"]["lenia_hz"]))
                elif kind == "nudge":
                    tgt = cmd.get("target")
                    p = cmd.get("param")
                    v = cmd.get("value")
                    if tgt == "lenia" and p in ("mu", "sigma", "T"):
                        lenia.set_params(**{p: v})
                    elif tgt == "rd" and p in ("F", "k"):
                        rd.set_params(**{p: v})
        except queue.Empty:
            pass

        # --- step the chimera ---
        lo = lorenz.step(arousal)
        arousal = lo["arousal"]
        if tick % lenia_every == 0:
            lenia.step()
            frag = lenia.frag_norm()
            lenia_vit = lenia.vitality()
        if tick % rd_every == 0:
            rd_growth = rd.step()

        heartbeat = (heartbeat + period * (0.5 + 1.5 * lenia_vit)) % 1.0
        slow_osc = (math.sin(2 * math.pi * tick / (hz * 45.0)) + 1.0) / 2.0

        lbytes, ld = lenia.downsample_bytes(lenia_ds)
        rbytes, rdd = rd.downsample_bytes(rd_ds)

        frame = SubstrateFrame(
            tick=tick, rho=lo["rho"], regime=lo["regime"], heartbeat=heartbeat,
            slow_osc=slow_osc, arousal=arousal, affect_sign=lo["affect_sign"],
            lenia_mass=lenia.mass(), lenia_frag_norm=frag, lenia_vitality=lenia_vit,
            rd_growth=max(0.0, rd_growth), rd_decay=max(0.0, -rd_growth),
            texture_regime=rd.regime(), lenia=lbytes, lenia_dim=ld, rd=rbytes, rd_dim=rdd,
            degraded=degraded,
        )
        try:
            state_q.put_nowait(frame)
        except queue.Full:
            try:
                state_q.get_nowait()
            except queue.Empty:
                pass
            try:
                state_q.put_nowait(frame)
            except queue.Full:
                pass

        # --- watchdog: auto-degrade (drop lenia rate) ---
        ft = (time.perf_counter() - t0) * 1000.0
        strikes = strikes + 1 if ft > wd_ms else 0
        if strikes >= wd_strikes and not degraded:
            degraded = True
            lenia_every = max(1, round(hz / 12.0))   # 20Hz -> 12Hz
            strikes = 0

        sleep = period - (time.perf_counter() - t0)
        if sleep > 0:
            time.sleep(sleep)
        tick += 1
