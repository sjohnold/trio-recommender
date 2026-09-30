PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('A','B')),
  language TEXT NOT NULL CHECK (language IN ('ru','en','sr')),
  script TEXT NOT NULL CHECK (script IN ('Latn','Cyrl')),
  variant TEXT CHECK (variant IN ('ekavian','ijekavian') OR variant IS NULL),
  profile TEXT NOT NULL,
  snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_mode ON sessions(mode);
CREATE INDEX IF NOT EXISTS idx_sessions_language ON sessions(language);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  sequence INTEGER NOT NULL CHECK (sequence > 0),
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE(session_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_events_session_sequence ON events(session_id, sequence);
CREATE TABLE IF NOT EXISTS utterances (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  terminal_event_id TEXT REFERENCES events(id),
  role TEXT NOT NULL CHECK (role IN ('pragmatist','logician','empath')),
  state TEXT NOT NULL CHECK (state IN
    ('PLANNED','CLAIMED','STREAMING','COMPLETED','INTERRUPTED','TIMED_OUT','FAILED')),
  text TEXT NOT NULL DEFAULT '',
  reason TEXT,
  generation_json TEXT NOT NULL CHECK (json_valid(generation_json)),
  latency_json TEXT NOT NULL CHECK (json_valid(latency_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_utterances_session ON utterances(session_id, created_at);
CREATE TABLE IF NOT EXISTS states (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  event_id TEXT NOT NULL REFERENCES events(id),
  raw_json TEXT NOT NULL CHECK (json_valid(raw_json)),
  validated_json TEXT NOT NULL CHECK (json_valid(validated_json)),
  source TEXT NOT NULL CHECK (source IN ('model','fallback')),
  confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_states_session ON states(session_id, id);
CREATE TABLE IF NOT EXISTS presets (
  id TEXT NOT NULL,
  version INTEGER NOT NULL CHECK (version > 0),
  persona_json TEXT NOT NULL CHECK (json_valid(persona_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY(id, version)
);
CREATE TABLE IF NOT EXISTS voice_bible (
  id TEXT PRIMARY KEY,
  language TEXT NOT NULL CHECK (language IN ('ru','en','sr')),
  role TEXT NOT NULL CHECK (role IN ('pragmatist','logician','empath')),
  fingerprint TEXT NOT NULL UNIQUE,
  example_json TEXT NOT NULL CHECK (json_valid(example_json)),
  review_status TEXT NOT NULL CHECK
    (review_status IN ('draft','reviewed','approved','rejected')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_voice_bible_language
  ON voice_bible(language, role);
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  event_id TEXT REFERENCES events(id),
  utterance_id TEXT REFERENCES utterances(id),
  name TEXT NOT NULL,
  value_json TEXT NOT NULL CHECK (json_valid(value_json)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  CHECK (event_id IS NOT NULL OR utterance_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_metrics_session
  ON metrics(session_id, name);
INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (1, '001_initial');
