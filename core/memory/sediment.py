"""4.1 Sediment (SQLite) — the dregs of a life. Full log + long-term memory (§8 schema).
Low volume; synchronous calls under a lock are fine inside the asyncio loop."""
from __future__ import annotations
import json
import sqlite3
import threading
import numpy as np


class Sediment:
    def __init__(self, db_path: str, schema_sql: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.executescript(schema_sql)
        self.conn.commit()
        self.lock = threading.Lock()

    def _ex(self, q, args=()):
        with self.lock:
            cur = self.conn.execute(q, args)
            self.conn.commit()
            return cur

    def insert_soul(self, soul_id, born_at):
        self._ex("INSERT OR REPLACE INTO souls(soul_id,born_at,n_thoughts,peak_coherence) VALUES(?,?,0,0)",
                 (soul_id, born_at))

    def update_soul(self, soul_id, n_thoughts, peak_coherence, dominant):
        self._ex("UPDATE souls SET n_thoughts=?,peak_coherence=?,dominant_voice=? WHERE soul_id=?",
                 (n_thoughts, peak_coherence, dominant, soul_id))

    def finalize_soul(self, soul_id, died_at, cause, drift):
        self._ex("UPDATE souls SET died_at=?,cause=?,drift_summary=? WHERE soul_id=?",
                 (died_at, cause, drift, soul_id))

    def insert_thought(self, tid, soul_id, tick, rnd, text, xi, dominant, vote):
        self._ex("INSERT OR REPLACE INTO thoughts VALUES(?,?,?,?,?,?,?,?)",
                 (tid, soul_id, tick, rnd, text, np.asarray(xi, np.int8).tobytes(), dominant, vote))

    def insert_utterance(self, soul_id, tick, voice, text, corrupted):
        self._ex("INSERT INTO utterances(soul_id,tick,voice,text,corrupted) VALUES(?,?,?,?,?)",
                 (soul_id, tick, voice, text, int(corrupted)))

    def insert_objections(self, tid, items, max_sev, can_proceed):
        self._ex("INSERT INTO objections(thought_id,items,max_severity,can_proceed) VALUES(?,?,?,?)",
                 (tid, json.dumps(items), float(max_sev), int(can_proceed)))

    def insert_verdict(self, tid, stance, dominant, vote, self_note):
        self._ex("INSERT INTO verdicts(thought_id,stance,dominant,vote,self_note) VALUES(?,?,?,?,?)",
                 (tid, stance, dominant, vote, self_note))

    def insert_recall(self, soul_id, tick, cue, recalled_id, is_true):
        self._ex("INSERT INTO recalls(soul_id,tick,cue,recalled_id,is_true) VALUES(?,?,?,?,?)",
                 (soul_id, tick, np.asarray(cue, np.int8).tobytes(), recalled_id, int(is_true)))

    def insert_skill(self, e, soul_id):
        self._ex("INSERT OR REPLACE INTO skills VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (e["edit_id"], soul_id, e["kind"], e["target"], e["content"], e["param"],
                  e["delta"], e["born_tick"], e["lifespan"], int(e["calcified"])))

    def sample_state(self, soul_id, tick, ax, rho):
        self._ex("INSERT INTO state_samples(soul_id,tick,coherence,valence,arousal,aperture,vitality,decoherence,rho) "
                 "VALUES(?,?,?,?,?,?,?,?,?)",
                 (soul_id, tick, ax["coherence"], ax["valence"], ax["arousal"], ax["aperture"],
                  ax["vitality"], ax["decoherence"], rho))

    def insert_death(self, soul_id, died_at, cause, final_thought, tombstone):
        self._ex("INSERT OR REPLACE INTO deaths VALUES(?,?,?,?,?)",
                 (soul_id, died_at, cause, final_thought, json.dumps(tombstone, ensure_ascii=False)))

    def get_text(self, thought_id):
        if not thought_id:
            return None
        with self.lock:
            row = self.conn.execute("SELECT text FROM thoughts WHERE thought_id=?", (thought_id,)).fetchone()
        return row[0] if row else None

    def nearest_by_vector(self, xi, soul_id):
        with self.lock:
            rows = self.conn.execute("SELECT thought_id,text,vector FROM thoughts WHERE soul_id=?",
                                     (soul_id,)).fetchall()
        best, bestd = None, 2.0
        for tid, text, blob in rows:
            v = np.frombuffer(blob, dtype=np.int8)
            if v.shape[0] != xi.shape[0]:
                continue
            d = float(np.mean(v != xi))
            if d < bestd:
                bestd, best = d, (tid, text)
        return best

    def list_souls(self):
        with self.lock:
            rows = self.conn.execute(
                "SELECT soul_id,born_at,died_at,cause,peak_coherence,n_thoughts,dominant_voice "
                "FROM souls ORDER BY born_at DESC").fetchall()
        return [dict(soul_id=r[0], born_at=r[1], died_at=r[2], cause=r[3],
                     peak_coherence=r[4], n_thoughts=r[5], dominant_voice=r[6]) for r in rows]

    def get_tombstone(self, soul_id):
        with self.lock:
            r = self.conn.execute("SELECT tombstone FROM deaths WHERE soul_id=?", (soul_id,)).fetchone()
        return json.loads(r[0]) if r and r[0] else None

    def calcify_soul_skills(self, soul_id):
        """On death, a soul's self-edits harden into 'remains' — inheritable by the next."""
        self._ex("UPDATE skills SET calcified=1 WHERE soul_id=?", (soul_id,))

    def calcified_skills(self, limit=3):
        with self.lock:
            rows = self.conn.execute(
                "SELECT kind,target,content,param,delta FROM skills WHERE calcified=1 "
                "ORDER BY RANDOM() LIMIT ?", (limit,)).fetchall()
        return [dict(kind=r[0], target=r[1], content=r[2], param=r[3], delta=r[4]) for r in rows]
