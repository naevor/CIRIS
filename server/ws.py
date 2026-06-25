"""WS hub — broadcast binary 'state' frames + JSON 'psyche' events to all clients.
Full psyche log is also written to SQLite by the orchestrator (any life is replayable)."""
from __future__ import annotations
import json
from starlette.websockets import WebSocket


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def broadcast_bytes(self, data: bytes):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_bytes(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def broadcast_json(self, obj: dict):
        text = json.dumps(obj, ensure_ascii=False)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)
