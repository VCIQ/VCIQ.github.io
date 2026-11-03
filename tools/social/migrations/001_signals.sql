-- Independent shadow content database; never the scheduler or production DB.
CREATE TABLE storage_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), migration_hash TEXT NOT NULL);
CREATE TABLE batches (
 run_id TEXT PRIMARY KEY, manifest_hash TEXT NOT NULL UNIQUE,
 manifest_json TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE TABLE attempts (
 attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES batches(run_id),
 query_id TEXT NOT NULL, job_json TEXT NOT NULL, receipt_json TEXT NOT NULL
);
CREATE TABLE signals (
 signal_id TEXT PRIMARY KEY, platform TEXT NOT NULL, native_id TEXT NOT NULL,
 content_type TEXT NOT NULL, identity_json TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
 latest_key TEXT NOT NULL, latest_hash TEXT NOT NULL, latest_json TEXT NOT NULL,
 UNIQUE(platform, content_type, native_id)
);
CREATE TABLE versions (
 signal_id TEXT NOT NULL REFERENCES signals(signal_id), content_hash TEXT NOT NULL,
 content_json TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
 PRIMARY KEY(signal_id, content_hash)
);
CREATE TABLE observations (
 observation_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
 signal_id TEXT NOT NULL, content_hash TEXT NOT NULL, observed_at TEXT NOT NULL,
 payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
 UNIQUE(attempt_id, signal_id),
 FOREIGN KEY(signal_id, content_hash) REFERENCES versions(signal_id, content_hash) ON DELETE CASCADE
);
CREATE INDEX observations_by_signal ON observations(signal_id, observed_at);
CREATE TABLE aliases (
 platform TEXT NOT NULL, alias TEXT NOT NULL, signal_id TEXT NOT NULL REFERENCES signals(signal_id),
 PRIMARY KEY(platform, alias)
);
CREATE INDEX aliases_by_signal ON aliases(signal_id);
CREATE TABLE evidence_pins (
 reference_id TEXT PRIMARY KEY, signal_id TEXT NOT NULL, content_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(signal_id, content_hash) REFERENCES versions(signal_id, content_hash) ON DELETE RESTRICT
);
CREATE TABLE retention_events (
 plan_hash TEXT PRIMARY KEY, cutoff TEXT NOT NULL, applied_at TEXT NOT NULL,
 versions_removed INTEGER NOT NULL, observations_removed INTEGER NOT NULL
);
