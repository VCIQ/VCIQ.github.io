from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from tools.build_pipeline_health import (
    build_snapshots,
    load_registry,
    validate_registry,
    write_snapshots,
)
from tools.run_pipeline import (
    build_deployment_provenance,
    finalize_pipeline,
    make_run_context,
)


def fixture_registry() -> dict:
    return {
        "schemaVersion": 1,
        "pipelineVersion": "test-v1",
        "publicObjectTypes": [
            {"id": "technology", "label": "核心技术", "route": "/technologies"},
            {"id": "track", "label": "核心赛道", "route": "/technology"},
            {"id": "person", "label": "核心人物", "route": "/people"},
            {"id": "company", "label": "核心公司", "route": "/companies"},
        ],
        "jobs": [
            {
                "id": "source-refresh",
                "name": "Source refresh",
                "owner": "test",
                "workflow": ".github/workflows/source.yml",
                "schedule": None,
                "trigger": "manual",
                "dependencies": [],
                "inputs": ["config/source.json"],
                "outputs": [
                    {
                        "path": "public/data/source.json",
                        "required": True,
                        "shared": False,
                        "public": True,
                    }
                ],
                "freshnessSlaHours": 4,
                "timeoutMinutes": 10,
                "retry": 1,
                "failurePolicy": "retain-last-good",
                "qualityGate": "source-quality",
            },
            {
                "id": "pages-deploy",
                "name": "Pages",
                "owner": "test",
                "workflow": ".github/workflows/pages.yml",
                "schedule": None,
                "trigger": "manual",
                "dependencies": ["source-refresh"],
                "inputs": ["public/data/source.json"],
                "outputs": [],
                "healthMode": "dependencies",
                "freshnessSlaHours": 4,
                "timeoutMinutes": 10,
                "retry": 1,
                "failurePolicy": "retain-last-good",
                "qualityGate": "pages-quality",
            },
        ],
    }


class PipelineControlPlaneTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "public/data").mkdir(parents=True)
        (self.root / ".github/workflows").mkdir(parents=True)
        (self.root / ".github/workflows/source.yml").write_text(
            "name: source\n", encoding="utf-8"
        )
        (self.root / ".github/workflows/pages.yml").write_text(
            "name: pages\n", encoding="utf-8"
        )
        (self.root / "config/source.json").write_text("{}\n", encoding="utf-8")
        (self.root / "config/automation_jobs.json").write_text(
            json.dumps(fixture_registry(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_registry_requires_exact_four_object_scope_and_acyclic_jobs(self) -> None:
        registry = load_registry(self.root)
        self.assertEqual(
            [item["id"] for item in registry["publicObjectTypes"]],
            ["technology", "track", "person", "company"],
        )

        cyclic = fixture_registry()
        cyclic["jobs"][0]["dependencies"] = ["pages-deploy"]
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            validate_registry(cyclic, self.root)

    def test_health_uses_content_hash_and_freshness_sla(self) -> None:
        output = self.root / "public/data/source.json"
        output.write_text(
            json.dumps({"generatedAt": "2026-08-06T00:00:00Z", "rows": [1]}) + "\n",
            encoding="utf-8",
        )
        registry = load_registry(self.root)

        lineage, health = build_snapshots(
            self.root,
            registry,
            now=datetime(2026, 8, 6, 2, tzinfo=UTC),
        )
        artifact = lineage["artifacts"]["public/data/source.json"]
        self.assertEqual(artifact["status"], "healthy")
        self.assertEqual(artifact["ageHours"], 2.0)
        self.assertEqual(len(artifact["contentSha256"]), 64)
        self.assertEqual(health["overallStatus"], "healthy")
        self.assertEqual(
            next(job for job in health["jobs"] if job["jobId"] == "pages-deploy")[
                "status"
            ],
            "healthy",
        )

        _, stale_health = build_snapshots(
            self.root,
            registry,
            now=datetime(2026, 8, 6, 8, tzinfo=UTC),
        )
        self.assertEqual(stale_health["overallStatus"], "stale")

    def test_missing_required_output_is_fail_closed(self) -> None:
        registry = load_registry(self.root)
        _, health = build_snapshots(
            self.root,
            registry,
            now=datetime(2026, 8, 6, 2, tzinfo=UTC),
        )
        self.assertEqual(health["overallStatus"], "degraded")
        self.assertEqual(
            health["summary"]["missingJobs"],
            1,
        )

        context = make_run_context(
            self.root,
            registry,
            "source-refresh",
            started_at=datetime(2026, 8, 6, 1, tzinfo=UTC),
            run_id="test-run",
        )
        with self.assertRaises(FileNotFoundError):
            finalize_pipeline(
                self.root,
                registry,
                "source-refresh",
                context=context,
                completed_at=datetime(2026, 8, 6, 2, tzinfo=UTC),
            )

    def test_successful_finalize_records_exact_run_lineage(self) -> None:
        output = self.root / "public/data/source.json"
        output.write_text(
            json.dumps({"generatedAt": "2026-08-06T02:00:00Z", "rows": [1]}) + "\n",
            encoding="utf-8",
        )
        registry = load_registry(self.root)
        context = make_run_context(
            self.root,
            registry,
            "source-refresh",
            started_at=datetime(2026, 8, 6, 1, tzinfo=UTC),
            run_id="test-run",
        )
        context["codeSha"] = "abc123"
        context["sourceRef"] = "refs/heads/test"

        current, lineage, health = finalize_pipeline(
            self.root,
            registry,
            "source-refresh",
            context=context,
            completed_at=datetime(2026, 8, 6, 2, tzinfo=UTC),
        )
        producer = lineage["artifacts"]["public/data/source.json"]["producer"]
        self.assertEqual(current["qualityGate"], "passed")
        self.assertEqual(producer["runId"], "test-run")
        self.assertEqual(producer["codeSha"], "abc123")
        self.assertEqual(producer["qualityGate"], "passed")
        self.assertEqual(health["overallStatus"], "healthy")
        self.assertTrue((self.root / "public/data/data_lineage.json").is_file())
        self.assertTrue((self.root / "public/data/pipeline_health.json").is_file())

    def test_only_research_agent_can_publish_a_contract_valid_degraded_run(self) -> None:
        output = self.root / "public/data/source.json"
        output.write_text(
            json.dumps({"generatedAt": "2026-08-06T02:00:00Z", "rows": [1]}) + "\n",
            encoding="utf-8",
        )
        registry = load_registry(self.root)
        with self.assertRaisesRegex(ValueError, "only supported for research-agent-daily"):
            finalize_pipeline(
                self.root,
                registry,
                "source-refresh",
                status="degraded",
                completed_at=datetime(2026, 8, 6, 2, tzinfo=UTC),
            )

        payload = fixture_registry()
        payload["jobs"][0]["id"] = "research-agent-daily"
        payload["jobs"][1]["dependencies"] = ["research-agent-daily"]
        (self.root / "config/automation_jobs.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        registry = load_registry(self.root)
        current, lineage, health = finalize_pipeline(
            self.root,
            registry,
            "research-agent-daily",
            status="degraded",
            quality_gate="passed",
            completed_at=datetime(2026, 8, 6, 2, tzinfo=UTC),
        )

        artifact = lineage["artifacts"]["public/data/source.json"]
        self.assertEqual(current["status"], "degraded")
        self.assertEqual(current["qualityGate"], "passed")
        self.assertEqual(artifact["producer"]["status"], "degraded")
        self.assertEqual(artifact["status"], "degraded")
        self.assertEqual(health["overallStatus"], "degraded")

    def test_repeated_finalize_preserves_the_original_source_sha(self) -> None:
        output = self.root / "public/data/source.json"
        output.write_text(
            json.dumps({"generatedAt": "2026-08-06T02:00:00Z", "rows": [1]}) + "\n",
            encoding="utf-8",
        )
        registry = load_registry(self.root)
        context = make_run_context(
            self.root,
            registry,
            "source-refresh",
            started_at=datetime(2026, 8, 6, 1, tzinfo=UTC),
            run_id="test-run",
        )
        context["codeSha"] = "source-commit"
        context["sourceRef"] = "refs/heads/main"
        finalize_pipeline(
            self.root,
            registry,
            "source-refresh",
            context=context,
            completed_at=datetime(2026, 8, 6, 2, tzinfo=UTC),
        )

        with patch.dict(
            "os.environ",
            {"GITHUB_SHA": "transient-rebased-data-commit"},
            clear=False,
        ):
            current, lineage, _ = finalize_pipeline(
                self.root,
                registry,
                "source-refresh",
                run_id="test-run",
                completed_at=datetime(2026, 8, 6, 3, tzinfo=UTC),
            )

        producer = lineage["artifacts"]["public/data/source.json"]["producer"]
        self.assertEqual(current["codeSha"], "source-commit")
        self.assertEqual(producer["codeSha"], "source-commit")
        self.assertEqual(producer["sourceRef"], "refs/heads/main")

    def test_deployment_provenance_hashes_control_plane_inputs(self) -> None:
        output = self.root / "public/data/source.json"
        output.write_text(
            json.dumps({"generatedAt": "2026-08-06T02:00:00Z"}) + "\n",
            encoding="utf-8",
        )
        registry = load_registry(self.root)
        write_snapshots(
            self.root,
            registry,
            lineage_output=self.root / "public/data/data_lineage.json",
            health_output=self.root / "public/data/pipeline_health.json",
            now=datetime(2026, 8, 6, 2, tzinfo=UTC),
        )
        provenance_path = self.root / "out/build-provenance.json"
        with patch.dict(
            "os.environ",
            {
                "GITHUB_SHA": "deadbeef",
                "GITHUB_REF": "refs/heads/test",
                "GITHUB_REPOSITORY": "VCIQ/VCIQ.github.io",
                "VCIQ_PIPELINE_RUN_ID": "deploy-test",
            },
            clear=False,
        ):
            provenance = build_deployment_provenance(
                self.root,
                registry,
                output=provenance_path,
                generated_at=datetime(2026, 8, 6, 3, tzinfo=UTC),
            )

        self.assertEqual(provenance["sourceSha"], "deadbeef")
        self.assertEqual(provenance["runId"], "deploy-test")
        self.assertEqual(
            len(provenance["controlPlane"]["dataLineage"]["sha256"]),
            64,
        )
        self.assertTrue(provenance_path.is_file())


if __name__ == "__main__":
    unittest.main()
