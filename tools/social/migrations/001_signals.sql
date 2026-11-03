CREATE TABLE IF NOT EXISTS social_content_schema (version INTEGER PRIMARY KEY CHECK(version=1));
INSERT OR IGNORE INTO social_content_schema VALUES(1);
CREATE TABLE IF NOT EXISTS social_batches (
 batch_hash TEXT PRIMARY KEY, run_id TEXT NOT NULL, manifest TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_content_attempts (
 attempt_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, job TEXT NOT NULL, receipt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_batch_attempts (
 batch_hash TEXT NOT NULL, attempt_id TEXT NOT NULL, PRIMARY KEY(batch_hash,attempt_id)
);
CREATE TABLE IF NOT EXISTS social_content_signals (
 signal_id TEXT PRIMARY KEY, platform TEXT NOT NULL, native_id TEXT NOT NULL, content_type TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, current_hash TEXT NOT NULL, current_observation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_content_revisions (
 signal_id TEXT NOT NULL, content_hash TEXT NOT NULL, payload TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY(signal_id,content_hash)
);
CREATE TABLE IF NOT EXISTS social_content_observations (
 observation_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, signal_id TEXT NOT NULL,
 content_hash TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS social_observation_signal ON social_content_observations(signal_id,observed_at);
CREATE TABLE IF NOT EXISTS social_content_aliases (
 alias TEXT PRIMARY KEY, signal_id TEXT NOT NULL, proof_observation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_evidence_refs (
 candidate_key TEXT NOT NULL, signal_id TEXT NOT NULL, content_hash TEXT NOT NULL,
 PRIMARY KEY(candidate_key,signal_id,content_hash)
);
