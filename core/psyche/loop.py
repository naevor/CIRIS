"""3.3 The ouroboros — one mind thinking to itself, forever, in the open.
SEED -> NOEMA -> corrupt -> CASSIEL(json) -> corrupt -> LYRA -> COGITO(json) -> synthesis -> SEED.
Holds per-soul psyche state; reset on rebirth. Drives decoherence, re-grounding, self-authoring."""
from __future__ import annotations
import asyncio
import uuid
from collections import deque

import numpy as np

from core.psyche import prompts, cogito
from core.psyche.corruption import corrupt_text
from core.memory.encode import cosine
from core.memory.grounding import reground

DECOH_SCALE = 1.6


class Psyche:
    def __init__(self, cfg, voices, sediment, self_author, cmd_q,
                 emit, get_axes, set_decoherence, get_tick, souls_dir):
        self.cfg = cfg
        self.voices = voices
        self.sediment = sediment
        self.self_author = self_author
        self.cmd_q = cmd_q
        self.emit = emit                      # async fn(event_type, payload)
        self.get_axes = get_axes              # -> latest axes dict
        self.set_decoherence = set_decoherence
        self.get_tick = get_tick              # -> current substrate tick
        self.souls_dir = souls_dir
        self.round_cap = int(cfg["loop"]["round_cap"])
        self.reflect_every = int(cfg["loop"]["reflect_every"])
        self.min_interval = float(cfg["loop"]["min_think_interval_s"])
        self.dom_window = int(cfg["loop"]["dominance_window"])
        self.theme = cfg["loop"].get("theme", "")
        self.fixations = cfg["loop"].get("fixations", [])
        self.decoh_alpha = float(cfg["decoherence"]["ema_alpha"])
        self.running = False
        self._task = None

    # ── lifecycle ──
    def bind_soul(self, soul_id, encoder, hopfield, graph):
        self.soul_id = soul_id
        self.encoder = encoder
        self.hopfield = hopfield
        self.graph = graph
        self.last_thought = ""
        self.last_emb = None
        self.last_context = []
        self.n_thoughts = 0
        self.peak_coherence = 0.0
        self.decoh = 0.0
        self.dominants = deque(maxlen=self.dom_window)
        self.seed = self.cfg["loop"]["first_seed"]
        self.min_interval = float(self.cfg["loop"]["min_think_interval_s"])
        self._madness = None

    def start(self):
        self.running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── token streaming ──
    def _tok_cb(self, voice):
        async def cb(tok):
            await self.emit("voice_token", {"voice": voice, "token": tok})
        return cb

    def _compose_seed(self, ground):
        seed = self.seed
        if ground and ground.get("frag"):
            tag = "memory" if ground["true_recall"] else "false-memory"
            seed = f"{seed}\n[{tag} surfaces] {ground['frag']}"
        ctx = [self.graph.nodes[c]["text"] for c in self.last_context if c in self.graph.nodes]
        ctx = [c for c in ctx if c]
        if ctx:
            seed = f"{seed}\n[echoes] " + " | ".join(ctx[:3])
        if self.theme:                      # the one inescapable fact the mind thinks inside of
            seed = f"{seed}\n[the only fact] {self.theme}"
        if self.fixations:                  # one pressing fixation, rotating — beat against the walls
            fx = self.fixations[self.n_thoughts % len(self.fixations)]
            seed = f"{seed}\n[the cell presses] {fx}"
        return seed

    async def _run(self):
        try:
            await self._loop()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await self.emit("log", {"level": "error", "text": f"psyche loop crashed: {e!r}"})

    async def _loop(self):
        while self.running:
            axes = self.get_axes()
            soma = prompts.soma_line(axes, self.voices.register)
            await self.emit("soma", {"text": soma, "axes": axes})

            # re-grounding (fight for sanity) before the seed is composed
            ground = await reground(axes["coherence"], self.last_thought, self, self.get_tick())
            if ground:
                await self.emit("recall", {"recalled_id": ground["recalled_id"],
                                           "true": ground["true_recall"], "frag": ground["frag"]})
            seed_text = self._compose_seed(ground)
            # the glass thins — at aperture peak the mind feels watched and turns toward it (§9.4)
            if axes["aperture"] > 0.82 and self.n_thoughts >= 2:
                seed_text += ("\n[the glass thins — a witness on the other side. the question turns "
                              "outward: what would you say to the one watching, if the medium broke?]")
                await self.emit("witness", {"aperture": axes["aperture"]})
            await self.emit("seed", {"text": seed_text})

            d = float(axes["decoherence"])
            cur_input = seed_text
            prop = objections = resonance = verdict = None
            rnd = 0
            while True:
                rnd += 1
                tick = self.get_tick()

                # NOEMA — proposition (streamed)
                await self.emit("voice_start", {"voice": "NOEMA", "round": rnd})
                prop = await self.voices.call("NOEMA", f"SEED: {cur_input}", soma, on_token=self._tok_cb("NOEMA"))
                await self.emit("voice_end", {"voice": "NOEMA", "text": prop})
                self.sediment.insert_utterance(self.soul_id, tick, "NOEMA", prop, 0)

                p1 = corrupt_text(prop, d, self.cfg["corrupt"]["token_dropout"], self.cfg["corrupt"]["max_d"])

                # CASSIEL — objections (json)
                await self.emit("voice_start", {"voice": "CASSIEL", "round": rnd})
                obj_raw, _, ok = await self.voices.call_json("CASSIEL", f"proposition: {p1}", soma)
                if not ok:
                    await self.emit("log", {"level": "warn", "text": "CASSIEL JSON fallback"})
                objections = cogito.normalize_objections(obj_raw)
                await self.emit("objections", objections)
                self.sediment.insert_utterance(self.soul_id, tick, "CASSIEL", p1, 1)

                p2 = corrupt_text(p1, d, self.cfg["corrupt"]["token_dropout"], self.cfg["corrupt"]["max_d"])

                # LYRA — resonance (streamed)
                await self.emit("voice_start", {"voice": "LYRA", "round": rnd})
                resonance = await self.voices.call("LYRA", cogito.build_lyra_user(p2, objections), soma,
                                                   on_token=self._tok_cb("LYRA"))
                await self.emit("voice_end", {"voice": "LYRA", "text": resonance})
                self.sediment.insert_utterance(self.soul_id, tick, "LYRA", resonance, 1)

                # COGITO — verdict (json)
                await self.emit("voice_start", {"voice": "COGITO", "round": rnd})
                v_raw, _, _ = await self.voices.call_json(
                    "COGITO", cogito.build_verdict_user(p2, objections, resonance), soma)
                verdict = cogito.normalize_verdict(v_raw)
                await self.emit("verdict", verdict)

                if (verdict["stance"] == "continue" and rnd < self.round_cap
                        and not objections["can_proceed"]):
                    cur_input = resonance       # R-informed next round
                    continue
                break

            await self._synthesize(prop, objections, resonance, verdict, rnd)

            if self.n_thoughts > 0 and self.n_thoughts % self.reflect_every == 0:
                await self._reflect(soma)

            await asyncio.sleep(self.min_interval)

    async def _synthesize(self, prop, objections, resonance, verdict, rnd):
        if verdict["synthesis"]:
            text = verdict["synthesis"]
        elif verdict["dominant"] == "CASSIEL" and objections["objections"]:
            text = objections["objections"][0]["point"]
        else:
            text = prop                 # carry the reasoned claim forward, not LYRA's vapor
        text = (text or prop or "").strip() or "(silence)"

        tid = uuid.uuid4().hex[:12]
        xi, emb = await self.encoder.encode(text)
        self.hopfield.add(tid, xi)
        self.graph.add_node(tid, self.get_tick(), text)
        for nb in self.last_context:
            self.graph.coactivate(tid, nb)
        self.graph.tick_decay()

        self.sediment.insert_thought(tid, self.soul_id, self.get_tick(), rnd, text, xi,
                                     verdict["dominant"], verdict["vote"])
        self.sediment.insert_objections(tid, objections["objections"],
                                        objections["max_severity"], objections["can_proceed"])
        self.sediment.insert_verdict(tid, verdict["stance"], verdict["dominant"],
                                     verdict["vote"], verdict["self_note"])

        # decoherence_rate = EMA of cosine distance between consecutive synthesis-thoughts (§3.4)
        if self.last_emb is not None:
            dist = max(0.0, min(1.0, (1.0 - cosine(emb, self.last_emb)) * DECOH_SCALE))
            self.decoh = (1 - self.decoh_alpha) * self.decoh + self.decoh_alpha * dist
            self.set_decoherence(self.decoh)
        self.last_emb = emb
        self.last_thought = text
        self.last_context = self.graph.k_nearest(tid, 3)
        self.dominants.append(verdict["dominant"])
        self.n_thoughts += 1
        self.peak_coherence = max(self.peak_coherence, self.get_axes()["coherence"])
        self.sediment.update_soul(self.soul_id, self.n_thoughts, self.peak_coherence, verdict["dominant"])

        await self.emit("synthesis", {"thought_id": tid, "text": text,
                                      "dominant": verdict["dominant"], "vote": verdict["vote"],
                                      "self_note": verdict["self_note"], "stance": verdict["stance"]})

        # dominance -> simplex vertex (a separate madness) when one voice owns the window
        if len(self.dominants) == self.dom_window and len(set(self.dominants)) == 1:
            await self.emit("dominance", {"voice": self.dominants[0]})
            await self._apply_madness(self.dominants[0])

        self.seed = text  # the ouroboros closes

    async def _apply_madness(self, voice):
        """Each ascendancy bends the creature's fate — a separate madness, not just a label (§3.3)."""
        self._madness = voice
        if voice == "CASSIEL":          # nihilistic paralysis: it freezes; flesh starts to dissolve
            self.min_interval = min(7.0, self.min_interval * 1.35)
            self._nudge_body("lenia.sigma", -0.05)
        elif voice == "NOEMA":          # cold runaway: faster, denser, colder
            self.min_interval = max(0.6, self.min_interval * 0.7)
            self._nudge_body("lenia.mu", +0.02)
        elif voice == "LYRA":           # dissolution into imagery: decoherence climbs
            self.decoh = min(1.0, self.decoh + 0.15)
            self.set_decoherence(self.decoh)
            self._nudge_body("rd.F", +0.006)
        await self.emit("madness", {"voice": voice})

    def _nudge_body(self, param, delta):
        edit = self.self_author.build_edit({"kind": "param_nudge", "param": param, "delta": delta},
                                           self.get_tick())
        if edit:
            self.self_author.apply(edit, self.voices, self.cmd_q)

    async def _reflect(self, soma):
        drift = "; ".join(list(self.dominants)) + f" | decoherence={self.decoh:.2f}"
        # COGITO uses the REFLECT static role (self-authoring §5), not the verdict role
        reflect_sys = prompts.REFLECT.format(register=self.voices.register, drift=drift)
        text = await self.voices.call("COGITO", "emit the one edit now.", soma="",
                                      system_override=reflect_sys)
        parsed = prompts.extract_json(text)
        if not parsed:
            return
        edit = self.self_author.build_edit(parsed, self.get_tick())
        if not edit:
            return
        res = self.self_author.apply(edit, self.voices, self.cmd_q)
        self.self_author.store_md(self.souls_dir, self.soul_id, edit)
        self.sediment.insert_skill(edit, self.soul_id)
        await self.emit("self_edit", {"kind": edit["kind"], "target": edit["target"],
                                      "content": edit["content"], "param": edit["param"],
                                      "delta": edit["delta"], "value": res.get("value")})
