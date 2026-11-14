CREATE TABLE review_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), migration_hash TEXT NOT NULL);
CREATE TABLE candidates (
 candidate_key TEXT PRIMARY KEY, lead_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 item_json TEXT NOT NULL, snapshot_json TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
 created_at TEXT NOT NULL
);
CREATE INDEX candidate_active ON candidates(active,candidate_key);
CREATE TABLE decisions (
 candidate_key TEXT PRIMARY KEY REFERENCES candidates(candidate_key),
 fingerprint TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected')),
 request_json TEXT NOT NULL, decided_at TEXT NOT NULL, result_json TEXT NOT NULL
);
CREATE TABLE requests (
 request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result_json TEXT NOT NULL
);
