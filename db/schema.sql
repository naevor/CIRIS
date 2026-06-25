-- CIRIS sediment (§8). Полный лог + долговременная память. Одна .sqlite на душу-линию.
CREATE TABLE IF NOT EXISTS souls (
  soul_id TEXT PRIMARY KEY, born_at INT, died_at INT, cause TEXT,
  peak_coherence REAL, n_thoughts INT, dominant_voice TEXT, drift_summary TEXT);

CREATE TABLE IF NOT EXISTS thoughts (
  thought_id TEXT PRIMARY KEY, soul_id TEXT, tick INT, round INT,
  text TEXT, vector BLOB, dominant TEXT, vote TEXT);

CREATE TABLE IF NOT EXISTS utterances (
  id INTEGER PRIMARY KEY, soul_id TEXT, tick INT, voice TEXT, text TEXT, corrupted INT);

CREATE TABLE IF NOT EXISTS objections (
  id INTEGER PRIMARY KEY, thought_id TEXT, items TEXT, max_severity REAL, can_proceed INT);

CREATE TABLE IF NOT EXISTS verdicts (
  id INTEGER PRIMARY KEY, thought_id TEXT, stance TEXT, dominant TEXT, vote TEXT, self_note TEXT);

CREATE TABLE IF NOT EXISTS recalls (
  id INTEGER PRIMARY KEY, soul_id TEXT, tick INT, cue BLOB, recalled_id TEXT, is_true INT);

CREATE TABLE IF NOT EXISTS skills (
  edit_id TEXT PRIMARY KEY, soul_id TEXT, kind TEXT, target TEXT, content TEXT,
  param TEXT, delta REAL, born_tick INT, lifespan INT, calcified INT);

CREATE TABLE IF NOT EXISTS state_samples (   -- даунсемпл ~1 Гц
  id INTEGER PRIMARY KEY, soul_id TEXT, tick INT,
  coherence REAL, valence REAL, arousal REAL, aperture REAL,
  vitality REAL, decoherence REAL, rho REAL);

CREATE TABLE IF NOT EXISTS deaths (
  soul_id TEXT PRIMARY KEY, died_at INT, cause TEXT, final_thought TEXT, tombstone TEXT);

CREATE INDEX IF NOT EXISTS idx_thoughts_soul ON thoughts(soul_id);
CREATE INDEX IF NOT EXISTS idx_utter_soul ON utterances(soul_id);
CREATE INDEX IF NOT EXISTS idx_state_soul ON state_samples(soul_id);
