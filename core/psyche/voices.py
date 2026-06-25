"""3.2 The four voices — one resident engine, four masks. Calls SERIALIZED (one lock):
parallel calls on one model = VRAM race (grab #5). Free voices stream token-by-token;
JSON voices are strict-parsed with one retry then a fallback (grab #2)."""
from __future__ import annotations
import asyncio
import json
import httpx

from core.psyche import prompts


class Voices:
    def __init__(self, cfg: dict, client: httpx.AsyncClient):
        self.cfg = cfg
        self.client = client
        self.host = cfg["model"]["host"]
        self.model = cfg["model"]["name"]
        self.num_ctx = int(cfg["model"].get("num_ctx", 3072))
        self.keep_alive = cfg["model"].get("keep_alive", -1)
        self.register = cfg["loop"]["register"]
        self.sampling = cfg["sampling"]
        self.self_frags = {v: [] for v in prompts.VOICES}
        self.lock = asyncio.Lock()

    def reset_self(self):
        self.self_frags = {v: [] for v in prompts.VOICES}

    def add_self_fragment(self, voice: str, text: str):
        if voice in self.self_frags and text:
            self.self_frags[voice].append(text[:280])
            self.self_frags[voice] = self.self_frags[voice][-6:]

    def inherit_fragment(self, voice: str, text: str):
        self.add_self_fragment(voice, text)

    def _system(self, name: str, soma: str) -> str:
        block = prompts.VOICES[name].format(register=self.register)
        if soma:
            block += "\n\n" + soma
        frags = self.self_frags.get(name, [])
        if frags:                                  # [self] appended AFTER static — never cancels §0
            block += "\n\n[self]\n" + "\n".join("- " + f for f in frags)
        return block

    async def call(self, name: str, user: str, soma: str = "", on_token=None, system_override=None) -> str:
        samp = self.sampling.get(name, {"temp": 0.5, "top_p": 0.9, "think": False})
        system = system_override if system_override is not None else self._system(name, soma)
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "options": {"temperature": samp["temp"], "top_p": samp["top_p"], "num_ctx": self.num_ctx},
            "keep_alive": self.keep_alive,
            "stream": on_token is not None,
        }
        if samp.get("think"):
            payload["think"] = True
        async with self.lock:
            if on_token is None:
                r = await self.client.post(self.host + "/api/chat", json=payload, timeout=180)
                return r.json().get("message", {}).get("content", "")
            chunks = []
            async with self.client.stream("POST", self.host + "/api/chat", json=payload, timeout=180) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    tok = obj.get("message", {}).get("content", "")
                    if tok:
                        chunks.append(tok)
                        res = on_token(tok)
                        if asyncio.iscoroutine(res):
                            await res
                    if obj.get("done"):
                        break
            return "".join(chunks)

    async def call_json(self, name: str, user: str, soma: str = ""):
        """Returns (parsed_dict, raw_text, ok). Never raises on bad JSON."""
        raw = await self.call(name, user, soma)
        obj = prompts.extract_json(raw)
        if obj is None:
            raw = await self.call(name, user + "\n\nreturn ONLY valid JSON, no other text.", soma)
            obj = prompts.extract_json(raw)
        if obj is None:
            fb = prompts.CASSIEL_FALLBACK if name == "CASSIEL" else prompts.COGITO_FALLBACK
            return dict(fb), raw, False
        return obj, raw, True
