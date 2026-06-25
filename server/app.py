"""PROCESS B — the server. Spawns the substrate (PROCESS A), folds body+memory signals into
the six axes, broadcasts state @30Hz + psyche events, runs the ouroboros, gates death/rebirth.
'Two clocks': the body keeps breathing (reader task) while a single thought takes seconds."""
from __future__ import annotations
import asyncio
import multiprocessing as mp
import os
import queue
import time
from collections import Counter
from contextlib import asynccontextmanager

import httpx
import numpy as np
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from core.contracts import SubstrateFrame
from core.substrate import modulators
from core.substrate.hopfield import Hopfield
from core.substrate.graph import ThoughtGraph
from core.substrate.substrate_process import run_substrate
from core.memory.encode import Encoder
from core.memory.sediment import Sediment
from core.memory.skills import SelfAuthor
from core.psyche.voices import Voices
from core.psyche.loop import Psyche
from core.psyche.corruption import corrupt_vec
from core.life.mortality import Mortality
from core.life import lineage
from core.sensorium.sensors import Sensorium
from server.ws import Hub
from server.schemas import pack_state

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEUTRAL = {"coherence": 0.6, "valence": 0.0, "arousal": 0.5,
           "aperture": 0.4, "vitality": 1.0, "decoherence": 0.0}


class Ciris:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.hub = Hub()
        self.ctx = mp.get_context("spawn")
        self.state_q = self.ctx.Queue(maxsize=8)
        self.cmd_q = self.ctx.Queue()
        self.proc = None
        self.client: httpx.AsyncClient | None = None

        self.souls_dir = os.path.join(ROOT, cfg["paths"]["souls_dir"])
        self.graveyard_dir = os.path.join(ROOT, cfg["paths"]["graveyard_dir"])
        os.makedirs(self.souls_dir, exist_ok=True)
        os.makedirs(self.graveyard_dir, exist_ok=True)
        schema = open(os.path.join(ROOT, "db", "schema.sql"), encoding="utf-8").read()
        self.sediment = Sediment(os.path.join(self.souls_dir, cfg["paths"]["db_name"]), schema)

        self.self_author = SelfAuthor(cfg)
        self.mortality = Mortality(cfg)
        self.sensorium = Sensorium(cfg)

        self.latest_frame: SubstrateFrame | None = None
        self.latest_axes = dict(NEUTRAL)
        self.current_tick = 0
        self.decoherence = 0.0
        self.mem_signals = {"hopfield_settle": 0.3, "structure_entropy": 0.3}
        self.sens_biases = {"arousal_bias": 0.0, "aperture_bias": 0.0}
        self.override = None        # (axis, value, expiry)
        self._dying = False
        self._tasks: list[asyncio.Task] = []

        self.soul_id = None
        self.hopfield = None
        self.graph = None
        self.psyche: Psyche | None = None

    # ── startup / shutdown ──
    async def startup(self):
        self.client = httpx.AsyncClient()
        self.voices = Voices(self.cfg, self.client)
        seed = lineage.new_seed()
        self.proc = self.ctx.Process(target=run_substrate,
                                     args=(self.cfg, self.state_q, self.cmd_q, seed), daemon=True)
        self.proc.start()

        self.psyche = Psyche(
            self.cfg, self.voices, self.sediment, self.self_author, self.cmd_q,
            emit=self.emit, get_axes=lambda: dict(self.latest_axes),
            set_decoherence=self._set_decoh, get_tick=lambda: self.current_tick,
            souls_dir=self.souls_dir,
        )
        self.birth_soul(first=True)

        self._tasks = [
            asyncio.create_task(self.reader_task()),
            asyncio.create_task(self.mem_task()),
            asyncio.create_task(self.graph_task()),
        ]
        if self.cfg["sensorium"]["enabled"]:
            self._tasks.append(asyncio.create_task(self.sensorium_task()))

    async def shutdown(self):
        if self.psyche:
            await self.psyche.stop()
        for t in self._tasks:
            t.cancel()
        try:
            self.cmd_q.put({"type": "shutdown"})
        except Exception:
            pass
        if self.proc:
            self.proc.terminate()
        if self.client:
            await self.client.aclose()

    def _set_decoh(self, v):
        self.decoherence = float(v)

    # ── life ──
    def birth_soul(self, first=False, inherit=None):
        soul_id = lineage.new_soul_id()
        seed = lineage.new_seed()
        proj = lineage.new_projection(seed, self.cfg["embed"]["dim"], self.cfg["embed"]["project_to"])
        encoder = Encoder(self.cfg, self.client, proj)
        self.hopfield = Hopfield(self.cfg["hopfield"]["N"], self.cfg["hopfield"]["capacity"])
        self.graph = ThoughtGraph(self.cfg["graph"], np.random.default_rng(seed))
        self.voices.reset_self()
        self.self_author.reset()
        self.mortality.reset()
        self.decoherence = 0.0
        self.mem_signals = {"hopfield_settle": 0.3, "structure_entropy": 0.3}

        if inherit is None:
            inherit = self.cfg["life"].get("inherit", False)
        inherited = []
        if inherit:
            for sk in self.sediment.calcified_skills():
                if sk["kind"] == "prompt_fragment" and sk["target"] in ("NOEMA", "CASSIEL", "LYRA", "COGITO"):
                    self.voices.inherit_fragment(sk["target"], sk["content"])
                    inherited.append(sk["content"][:40])

        self.soul_id = soul_id
        self.born_tick = self.current_tick
        self.psyche.bind_soul(soul_id, encoder, self.hopfield, self.graph)
        self.sediment.insert_soul(soul_id, self.born_tick)
        if not first:
            self.cmd_q.put({"type": "rebirth"})
        self.psyche.start()
        asyncio.create_task(self.emit("birth", {"soul_id": soul_id, "seed": seed,
                                                "inherited": inherited,
                                                "theme": self.cfg["loop"].get("theme", "")}))

    async def handle_death(self, cause: str):
        if self._dying:
            return
        self._dying = True
        await self.psyche.stop()
        died = self.current_tick
        final = self.psyche.last_thought or "(no last thought)"
        doms = list(self.psyche.dominants)
        dom_life = Counter(doms).most_common(1)[0][0] if doms else "NOEMA"
        drift = (f"thoughts={self.psyche.n_thoughts} peak_coh={self.psyche.peak_coherence:.2f} "
                 f"decoherence={self.psyche.decoh:.2f}")
        self.sediment.calcify_soul_skills(self.soul_id)   # self-edits harden into inheritable remains
        archived = lineage.archive_skills(self.souls_dir, self.graveyard_dir, self.soul_id)
        tomb = lineage.build_tombstone(self.soul_id, self.born_tick, died, cause, final,
                                       dom_life, self.psyche.peak_coherence,
                                       self.psyche.n_thoughts, drift, archived)
        self.sediment.finalize_soul(self.soul_id, died, cause, drift)
        self.sediment.insert_death(self.soul_id, died, cause, final, tomb)
        await self.emit("death", {"tombstone": tomb})
        await asyncio.sleep(2.5)            # signal-loss -> black -> reboot (death animation)
        self.birth_soul()
        self._dying = False

    # ── background tasks ──
    async def reader_task(self):
        period = 1.0 / self.cfg["ws"]["state_hz"]
        sample_every = int(self.cfg["ws"]["state_hz"])
        i = 0
        while True:
            frame = None
            try:
                while True:
                    frame = self.state_q.get_nowait()
            except queue.Empty:
                pass
            if frame is not None:
                self.latest_frame = frame
                self.current_tick = frame.tick
                ax = modulators.combine(frame, self.mem_signals, self.sens_biases, self.decoherence)
                if self.override:
                    axis, val, exp = self.override
                    if time.time() < exp:
                        ax[axis] = val
                    else:
                        self.override = None
                self.latest_axes = ax

                await self.hub.broadcast_bytes(
                    pack_state(frame.tick, ax, frame.rho, frame.heartbeat,
                               frame.lenia, frame.lenia_dim, frame.rd, frame.rd_dim))

                i += 1
                if i % sample_every == 0:
                    self.sediment.sample_state(self.soul_id, frame.tick, ax, frame.rho)

                if not self._dying:
                    n = self.psyche.n_thoughts if self.psyche else 0
                    cause = self.mortality.check(ax, n)
                    if cause:
                        asyncio.create_task(self.handle_death(cause))
            await asyncio.sleep(period)

    async def mem_task(self):
        while True:
            try:
                if self.hopfield is not None and self.hopfield.patterns:
                    _, last_xi = self.hopfield.patterns[-1]
                    cue = corrupt_vec(last_xi.astype(np.int8), 0.3)
                    hse = self.hopfield.settle_energy(cue)
                else:
                    hse = 0.3
                sent = self.graph.structure_entropy() if self.graph is not None else 0.3
                self.mem_signals = {"hopfield_settle": hse, "structure_entropy": sent}
            except Exception:
                pass
            await asyncio.sleep(0.5)

    async def graph_task(self):
        period = float(self.cfg["ws"]["graph_every_s"])
        while True:
            try:
                if self.graph is not None:
                    snap = self.graph.snapshot()
                    snap["attractors"] = self.hopfield.attractor_norms() if self.hopfield else []
                    snap["regime"] = self.latest_frame.regime if self.latest_frame else ""
                    snap["texture"] = self.latest_frame.texture_regime if self.latest_frame else ""
                    snap["degraded"] = bool(self.latest_frame.degraded) if self.latest_frame else False
                    await self.emit("graph", snap)
            except Exception:
                pass
            await asyncio.sleep(period)

    async def sensorium_task(self):
        period = 1.0 / self.cfg["clocks"]["sensorium_hz"]
        loop = asyncio.get_event_loop()
        while True:
            try:
                self.sens_biases = await loop.run_in_executor(None, self.sensorium.sample)
            except Exception:
                pass
            await asyncio.sleep(period)

    async def emit(self, event_type: str, payload: dict):
        msg = {"type": event_type, "tick": self.current_tick}
        msg.update(payload)
        await self.hub.broadcast_json(msg)


# ── FastAPI app ──
def load_cfg():
    return yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))


ciris: Ciris | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ciris
    ciris = Ciris(load_cfg())
    await ciris.startup()
    try:
        yield
    finally:
        await ciris.shutdown()


app = FastAPI(title="CIRIS", lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse(os.path.join(ROOT, "frontend", "index.html"))


@app.get("/healthz")
async def healthz():
    return {"ok": True, "soul": ciris.soul_id, "tick": ciris.current_tick,
            "axes": ciris.latest_axes, "thoughts": ciris.psyche.n_thoughts if ciris.psyche else 0}


@app.get("/api/state")
async def api_state():
    return {"axes": ciris.latest_axes, "tick": ciris.current_tick,
            "regime": ciris.latest_frame.regime if ciris.latest_frame else "",
            "decoherence": ciris.decoherence,
            "theme": ciris.cfg["loop"].get("theme", ""),
            "soul": ciris.soul_id}


@app.get("/api/souls")
async def api_souls():
    return ciris.sediment.list_souls()


@app.get("/api/tombstone/{soul_id}")
async def api_tombstone(soul_id: str):
    t = ciris.sediment.get_tombstone(soul_id)
    return t or JSONResponse({"error": "not found"}, status_code=404)


@app.post("/control/override")
async def control_override(req: Request):
    """Manual axis override for acceptance testing, e.g. push valence negative."""
    body = await req.json()
    axis = body.get("axis")
    if axis not in NEUTRAL:
        return JSONResponse({"error": "bad axis"}, status_code=400)
    val = float(body.get("value", 0.0))
    ttl = float(body.get("ttl_s", 20.0))
    ciris.override = (axis, val, time.time() + ttl)
    return {"override": {"axis": axis, "value": val, "ttl_s": ttl}}


@app.post("/control/clear_override")
async def control_clear():
    ciris.override = None
    return {"override": None}


@app.post("/control/nudge")
async def control_nudge(req: Request):
    body = await req.json()
    target = body.get("target")
    param = body.get("param")
    value = float(body.get("value"))
    ciris.cmd_q.put({"type": "nudge", "target": target, "param": param, "value": value})
    return {"nudged": {"target": target, "param": param, "value": value}}


@app.post("/control/kill")
async def control_kill():
    asyncio.create_task(ciris.handle_death("forced"))
    return {"killing": ciris.soul_id}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ciris.hub.connect(ws)
    try:
        while True:
            await ws.receive_text()       # clients don't send; keep the socket open
    except WebSocketDisconnect:
        ciris.hub.disconnect(ws)
    except Exception:
        ciris.hub.disconnect(ws)
