from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools.build_pipeline_health import validate_health_snapshot
from tools.pipeline_health_runtime import build_snapshots


class PipelineRuntimeHealthTests(unittest.TestCase):
    def test_successful_heartbeat_keeps_runtime_healthy_when_data_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/alpha.yml").write_text(
                "name: alpha\n", encoding="utf-8"
            )
            output = root / "public/data/out.json"
            output.parent.mkdir(parents=True)
            output.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "generatedAt": "2026-08-01T00:00:00Z",
                        "value": 1,
                    }
                ),
                encoding="utf-8",
            )

            registry = {
                "schemaVersion": 1,
                "pipelineVersion": "test-v1",
                "timezone": "UTC",
                "publicObjectTypes": [
                    {"id": "technology", "label": "Technology", "route": "/technology"},
                    {"id": "track", "label": "Track", "route": "/track"},
                    {"id": "person", "label": "Person", "route": "/person"},
                    {"id": "company", "label": "Company", "route": "/company"},
                ],
                "jobs": [
                    {
                        "id": "alpha-job",
                        "name": "Alpha",
                        "owner": "test",
                        "workflow": ".github/workflows/alpha.yml",
                        "schedule": "0 * * * * @ UTC",
                        "trigger": "scheduled-and-manual",
                        "dependencies": [],
                        "inputs": [],
                        "outputs": [
                            {
                                "path": "public/data/out.json",
                                "required": True,
                                "shared": False,
                                "public": True,
                            }
                        ],
                        "freshnessSlaHours": 6,
                        "timeoutMinutes": 5,
                        "retry": 1,
                        "failurePolicy": "retain-last-good",
                        "qualityGate": "alpha-quality",
                    }
                ],
            }
            current_run = {
                "schemaVersion": 1,
                "pipelineVersion": "test-v1",
                "jobId": "alpha-job",
                "runId": "gha:test:alpha-job",
                "codeSha": "abc123",
                "sourceRef": "refs/heads/main",
                "startedAt": "2026-08-10T11:30:00Z",
                "completedAt": "2026-08-10T12:00:00Z",
                "status": "success",
                "qualityGate": "passed",
                "inputs": [],
                "outputs": registry["jobs"][0]["outputs"],
                "freshnessSlaHours": 6,
                "failurePolicy": "retain-last-good",
            }

            lineage, health = build_snapshots(
                root,
                registry,
                current_run=current_run,
                now=datetime(2026, 8, 10, 13, 0, tzinfo=UTC),
                previous_health={},
            )

            artifact = lineage["artifacts"]["public/data/out.json"]
            job = next(row for row in health["jobs"] if row["jobId"] == "alpha-job")

            self.assertEqual(artifact["status"], "stale")
            self.assertEqual(artifact["freshnessStatus"], "stale")
            self.assertEqual(job["status"], "healthy")
            self.assertEqual(job["freshnessStatus"], "stale")
            self.assertEqual(job["lastSuccessfulRunAt"], "2026-08-10T12:00:00Z")
            self.assertEqual(job["lastCompletedAt"], "2026-08-10T12:00:00Z")
            self.assertEqual(job["runAgeHours"], 1.0)
            self.assertEqual(health["summary"]["staleJobs"], 0)
            self.assertEqual(health["summary"]["freshnessWarningJobs"], 1)
            self.assertEqual(health["summary"]["staleArtifacts"], 1)
            self.assertEqual(health["overallStatus"], "healthy")
            validate_health_snapshot(health, registry)


if __name__ == "__main__":
    unittest.main()
