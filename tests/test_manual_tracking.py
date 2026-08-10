from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import manual_tracking as manual
from tools.entity_resolution import Resolution


class ManualTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = {
            "tracking": root / "user_tracking.json",
            "inbox": root / "tracking_capture_inbox.json",
            "intents": root / "tracking_intents.json",
            "admins": root / "tracking_admins.json",
        }
        self.original_paths = (
            manual.TRACKING_PATH,
            manual.INBOX_PATH,
            manual.INTENTS_PATH,
            manual.ADMINS_PATH,
        )
        manual.TRACKING_PATH = self.paths["tracking"]
        manual.INBOX_PATH = self.paths["inbox"]
        manual.INTENTS_PATH = self.paths["intents"]
        manual.ADMINS_PATH = self.paths["admins"]
        self._write(
            "tracking",
            {
                "schemaVersion": 1,
                "unknownTopLevel": {"mustSurvive": True},
                "tracks": [
                    {
                        "slug": "ai",
                        "name": "AI / AGI",
                        "enabled": True,
                        "custom": False,
                        "keywords": ["大语言模型"],
                        "people": ["Sam Altman"],
                        "sampleCompanies": ["OpenAI"],
                        "ignoredRecommendations": {"keywords": ["API"]},
                    },
                    {
                        "slug": "robotics",
                        "name": "机器人",
                        "enabled": True,
                        "custom": False,
                        "keywords": ["具身智能"],
                        "people": [],
                        "sampleCompanies": ["宇树科技"],
                    },
                ],
                "listedCompanies": [],
                "sources": [
                    {
                        "id": "source-existing",
                        "name": "Existing",
                        "url": "https://existing.example/",
                        "sector": "AI / AGI",
                        "sourceCategory": "media",
                        "enabled": True,
                    }
                ],
            },
        )
        self._write(
            "inbox",
            {"schemaVersion": 1, "generatedAt": "", "records": []},
        )
        self._write(
            "intents",
            {
                "schemaVersion": 1,
                "updatedAt": "",
                "entities": [],
                "memberships": [],
            },
        )
        self._write("admins", {"schemaVersion": 1, "actors": ["IamVC"]})

    def tearDown(self) -> None:
        (
            manual.TRACKING_PATH,
            manual.INBOX_PATH,
            manual.INTENTS_PATH,
            manual.ADMINS_PATH,
        ) = self.original_paths
        self.tmp.cleanup()

    def _write(self, key: str, payload: dict) -> None:
        self.paths[key].write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read(self, key: str) -> dict:
        return json.loads(self.paths[key].read_text(encoding="utf-8"))

    def _run(self, *args: str, expected: int = 0) -> dict:
        argv = [
            *args,
            "--actor",
            "IamVC",
            "--triggering-actor",
            "IamVC",
            "--now",
            "2026-08-09T12:00:00+00:00",
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = manual.main(argv)
        self.assertEqual(result, expected, output.getvalue())
        return json.loads(output.getvalue().splitlines()[-1])

    def test_validate_is_read_only_and_links_all_five_recommendation_types(self) -> None:
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run(
            "--mode",
            "validate",
            "--kind",
            "technology",
            "--name",
            "端侧多模态",
            "--tracks",
            "ai",
            "--keywords",
            "on-device multimodal",
            "--reasons",
            "技术突破|个人研究兴趣",
        )

        self.assertTrue(report["ok"])
        self.assertFalse(report["changed"])
        self.assertTrue(report["preview"]["changed"])
        self.assertEqual(report["preview"]["resolution"]["entityType"], "topic")
        self.assertEqual(
            set(report["recommendations"]),
            {"tracks", "technologies", "companies", "people", "sources"},
        )
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})

    def test_technology_apply_is_pinned_compiled_and_idempotent(self) -> None:
        args = (
            "--mode",
            "apply",
            "--kind",
            "technology",
            "--name",
            "端侧多模态",
            "--tracks",
            "ai",
            "--keywords",
            "on-device multimodal",
            "--source-url",
            "https://example.com/research/on-device-multimodal",
            "--reasons",
            "技术突破|个人研究兴趣",
        )
        first = self._run(*args)
        second = self._run(*args)

        self.assertTrue(first["configChanged"])
        self.assertTrue(first["intentsChanged"])
        self.assertFalse(second["changed"])
        tracking = self._read("tracking")
        self.assertIn("端侧多模态", tracking["tracks"][0]["keywords"])
        self.assertTrue(tracking["unknownTopLevel"]["mustSurvive"])
        self.assertEqual(
            tracking["tracks"][0]["ignoredRecommendations"], {"keywords": ["API"]}
        )
        membership = self._read("intents")["memberships"][0]
        self.assertEqual(membership["trackId"], "track:ai")
        self.assertEqual(membership["role"], "keyword")
        self.assertTrue(membership["pinned"])
        self.assertEqual(self._read("inbox")["records"][0]["status"], "applied")

    def test_symbolic_technologies_remain_distinct_end_to_end(self) -> None:
        values = ["C", "C++", "C#", ".NET", "NET", "A/B", "AB"]
        report = self._run(
            "--mode",
            "apply",
            "--kind",
            "track",
            "--name",
            "ai",
            "--tracks",
            "robotics",
            "--keywords",
            "|".join(values),
            "--reasons",
            "技术突破",
        )
        self.assertTrue(report["configChanged"])
        keywords = self._read("tracking")["tracks"][0]["keywords"]
        for value in values:
            self.assertIn(value, keywords)

    def test_verified_company_applies_but_unreviewed_company_does_not(self) -> None:
        verified = self._run(
            "--mode",
            "apply",
            "--kind",
            "company",
            "--name",
            "Anthropic",
            "--tracks",
            "ai",
            "--source-url",
            "https://www.anthropic.com/news/company",
            "--reasons",
            "融资机会",
        )
        proposed = self._run(
            "--mode",
            "apply",
            "--kind",
            "company",
            "--name",
            "Imaginary Frontier Labs",
            "--tracks",
            "ai",
            "--source-url",
            "https://example.com/imaginary-frontier-labs",
            "--reasons",
            "融资机会",
        )

        self.assertTrue(verified["configChanged"])
        self.assertEqual(verified["resolution"]["source"], "company-registry")
        self.assertEqual(verified["entityId"], "company:anthropic")
        self.assertTrue(proposed["reviewQueued"])
        self.assertFalse(proposed["configChanged"])
        companies = self._read("tracking")["tracks"][0]["sampleCompanies"]
        self.assertIn("Anthropic", companies)
        self.assertNotIn("Imaginary Frontier Labs", companies)
        records = self._read("inbox")["records"]
        self.assertEqual({row["status"] for row in records}, {"applied", "queued"})

    def test_person_guard_rejects_historical_explicit_type_pollution(self) -> None:
        before = self.paths["tracking"].read_bytes()
        report = self._run(
            "--mode",
            "apply",
            "--kind",
            "person",
            "--name",
            "混合专家模型",
            "--tracks",
            "ai",
            "--reasons",
            "技术突破",
            expected=2,
        )
        self.assertFalse(report["ok"])
        self.assertIn("实体消歧", report["error"])
        self.assertEqual(before, self.paths["tracking"].read_bytes())

    def test_valid_person_is_added_to_graph_and_runtime(self) -> None:
        report = self._run(
            "--mode",
            "apply",
            "--kind",
            "person",
            "--name",
            "Demis Hassabis",
            "--tracks",
            "ai",
            "--source-url",
            "https://deepmind.google/about/",
            "--reasons",
            "个人研究兴趣",
        )
        self.assertTrue(report["configChanged"])
        self.assertIn("Demis Hassabis", self._read("tracking")["tracks"][0]["people"])

    def test_new_track_and_source_compile_with_stable_relations(self) -> None:
        track = self._run(
            "--mode",
            "apply",
            "--kind",
            "track",
            "--name",
            "具身智能基础设施",
            "--tracks",
            "robotics",
            "--keywords",
            "机器人数据采集|具身智能基础设施",
            "--reasons",
            "个人研究兴趣",
        )
        source = self._run(
            "--mode",
            "apply",
            "--kind",
            "source",
            "--name",
            "MIT Technology Review",
            "--tracks",
            "ai",
            "--keywords",
            "artificial intelligence",
            "--source-url",
            "https://www.technologyreview.com/feed/",
            "--source-category",
            "media",
            "--region",
            "美国",
            "--reasons",
            "技术突破",
        )

        self.assertTrue(track["configChanged"])
        self.assertTrue(source["configChanged"])
        tracking = self._read("tracking")
        created = next(row for row in tracking["tracks"] if row["name"] == "具身智能基础设施")
        self.assertTrue(created["custom"])
        self.assertIn("机器人数据采集", created["keywords"])
        added_source = next(row for row in tracking["sources"] if row["name"] == "MIT Technology Review")
        self.assertEqual(added_source["origin"], "owner-entered")
        self.assertEqual(added_source["sector"], "AI / AGI")
        self.assertEqual(added_source["sourceType"], "rss")
        track_entity = next(row for row in self._read("intents")["entities"] if row["kind"] == "track")
        self.assertEqual(track_entity["relatedTrackIds"], ["track:robotics"])
        self.assertEqual(manual.infer_source_type("https://example.com/feedback"), "listing-search")
        self.assertEqual(manual.infer_source_type("https://example.com/feedstock"), "listing-search")

    def test_review_entity_and_capture_migrate_to_canonical_decision(self) -> None:
        args = (
            "--mode",
            "apply",
            "--kind",
            "company",
            "--name",
            "Novel Robotics Labs",
            "--tracks",
            "robotics",
            "--source-url",
            "https://example.com/novel-robotics-labs",
            "--reasons",
            "融资机会",
        )
        queued = self._run(*args)
        self.assertTrue(queued["reviewQueued"])
        self.assertFalse(queued["configChanged"])

        decision = Resolution(
            status="resolved",
            requestedType="company",
            entityType="company",
            canonicalName="Novel Robotics",
            targetId="company:novel-robotics",
            confidence="verified",
            source="human-decision",
            reason="人工消歧已确认。",
            decisionKey="novelroboticslabs",
            reclassified=False,
        )
        with mock.patch.object(manual, "resolve_entity", return_value=decision):
            applied = self._run(*args)
            repeated = self._run(*args)

        self.assertTrue(applied["configChanged"])
        self.assertFalse(repeated["changed"])
        intents = self._read("intents")
        self.assertEqual(len(intents["entities"]), 1)
        self.assertEqual(intents["entities"][0]["id"], "company:novel-robotics")
        self.assertEqual(intents["entities"][0]["name"], "Novel Robotics")
        self.assertEqual(len(intents["memberships"]), 1)
        self.assertEqual(
            intents["memberships"][0]["entityId"], "company:novel-robotics"
        )
        records = self._read("inbox")["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "applied")
        self.assertEqual(records[0]["canonicalName"], "Novel Robotics")

    def test_canonical_identity_collision_is_never_migrated(self) -> None:
        intents = {
            "schemaVersion": 1,
            "updatedAt": "",
            "entities": [
                {
                    "id": "company:chosen",
                    "kind": "company",
                    "name": "A/B",
                    "state": "active",
                    "resolutionSource": "company-registry",
                },
                {
                    "id": "company:other",
                    "kind": "company",
                    "name": "AB",
                    "state": "active",
                    "resolutionSource": "company-registry",
                },
            ],
            "memberships": [
                {
                    "id": "membership:other",
                    "trackId": "track:robotics",
                    "entityId": "company:other",
                    "role": "actor",
                    "state": "active",
                    "origins": [],
                }
            ],
        }
        request = {"kind": "company", "name": "A/B"}

        changed = manual._migrate_provisional_entity(
            intents, request, "company:chosen"
        )

        self.assertFalse(changed)
        self.assertEqual(
            {row["id"] for row in intents["entities"]},
            {"company:chosen", "company:other"},
        )
        self.assertEqual(
            intents["memberships"][0]["entityId"], "company:other"
        )

    def test_security_and_quality_guards_fail_closed(self) -> None:
        bad_cases = [
            ("technology", "OpenAI，Anthropic", "ai", "", "技术突破"),
            ("technology", "2026-08-03", "ai", "", "技术突破"),
            ("company", "OpenAI、Anthropic", "ai", "", "融资机会"),
            ("company", "Anthropic", "ai", "", "融资机会"),
            ("source", "Internal", "ai", "http://127.0.0.1/admin", "个人研究兴趣"),
            ("source", "Internal", "ai", "https://service.internal/feed", "个人研究兴趣"),
            ("technology", "端侧推理", "ai", "", "未经治理的自定义原因"),
            ("technology", "端侧推理", "ai", "", ""),
        ]
        for kind, name, tracks, url, reasons in bad_cases:
            with self.subTest(name=name, url=url):
                report = self._run(
                    "--mode",
                    "validate",
                    "--kind",
                    kind,
                    "--name",
                    name,
                    "--tracks",
                    tracks,
                    "--source-url",
                    url,
                    "--reasons",
                    reasons,
                    expected=2,
                )
                self.assertFalse(report["ok"])

        report = self._run(
            "--mode",
            "validate",
            "--kind",
            "track",
            "--name",
            "新复合赛道",
            "--keywords",
            "OpenAI，Anthropic",
            "--reasons",
            "技术突破",
            expected=2,
        )
        self.assertFalse(report["ok"])

    def test_existing_track_can_add_an_explicit_relation_without_new_keywords(self) -> None:
        report = self._run(
            "--mode",
            "apply",
            "--kind",
            "track",
            "--name",
            "ai",
            "--tracks",
            "robotics",
            "--reasons",
            "个人研究兴趣",
        )
        self.assertTrue(report["intentsChanged"])
        self.assertFalse(report["configChanged"])
        entity = next(
            row for row in self._read("intents")["entities"] if row["id"] == "track:ai"
        )
        self.assertEqual(entity["name"], "AI / AGI")
        self.assertEqual(entity["relatedTrackIds"], ["track:robotics"])

    def test_actor_and_triggering_actor_must_both_be_allowlisted(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = manual.main(
                [
                    "--mode",
                    "validate",
                    "--kind",
                    "technology",
                    "--name",
                    "端侧推理",
                    "--tracks",
                    "ai",
                    "--actor",
                    "IamVC",
                    "--triggering-actor",
                    "Untrusted",
                ]
            )
        self.assertEqual(result, 2)
        self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_future_schema_version_fails_closed(self) -> None:
        intents = self._read("intents")
        intents["schemaVersion"] = 2
        self._write("intents", intents)
        report = self._run(
            "--mode",
            "validate",
            "--kind",
            "technology",
            "--name",
            "端侧推理",
            "--tracks",
            "ai",
            "--reasons",
            "技术突破",
            expected=2,
        )
        self.assertFalse(report["ok"])
        self.assertIn("拒绝降级写入", report["error"])

    def test_malformed_state_file_fails_closed(self) -> None:
        self.paths["inbox"].write_text("{not-json", encoding="utf-8")
        report = self._run(
            "--mode",
            "validate",
            "--kind",
            "technology",
            "--name",
            "端侧推理",
            "--tracks",
            "ai",
            "--reasons",
            "技术突破",
            expected=2,
        )
        self.assertFalse(report["ok"])
        self.assertIn("拒绝用空数据覆盖", report["error"])

    def test_missing_state_file_and_coerced_schema_fail_closed(self) -> None:
        self.paths["inbox"].unlink()
        missing = self._run(
            "--mode",
            "validate",
            "--kind",
            "technology",
            "--name",
            "端侧推理",
            "--tracks",
            "ai",
            "--reasons",
            "技术突破",
            expected=2,
        )
        self.assertIn("拒绝创建空白替代文件", missing["error"])

        self._write("inbox", {"schemaVersion": 1.0, "generatedAt": "", "records": []})
        coerced = self._run(
            "--mode",
            "validate",
            "--kind",
            "technology",
            "--name",
            "端侧推理",
            "--tracks",
            "ai",
            "--reasons",
            "技术突破",
            expected=2,
        )
        self.assertIn("拒绝降级写入", coerced["error"])

    def test_held_relations_filter_by_type_and_source_host(self) -> None:
        tracking = self._read("tracking")
        tracking["tracks"][0]["keywords"] = ["C", "C++", "C#"]
        tracking["sources"] = [
            {
                "id": "source-example",
                "name": "Example",
                "url": "https://example.com/",
                "sector": "AI / AGI",
            }
        ]
        request = {
            "kind": "technology",
            "name": "Rust",
            "keywords": [],
            "trackSlugs": ["ai"],
            "sourceUrl": "",
        }
        profile = {
            "tracks": {
                "ai": {
                    "approved": {},
                    "held": {
                        "keywords": ["C++"],
                        "people": [],
                        "sampleCompanies": [],
                        "sources": ["https://example.com/news"],
                    },
                    "seedTerms": [],
                    "sourceHosts": [],
                    "relatedTracks": [],
                }
            }
        }
        result = manual.recommendations(
            tracking,
            {"entities": [], "memberships": []},
            request,
            profile,
        )
        technologies = {row["name"] for row in result["technologies"]}
        self.assertEqual(technologies, {"C", "C#"})
        self.assertEqual(result["sources"], [])

    def test_rejected_manual_relation_never_reappears_in_recommendations(self) -> None:
        tracking = self._read("tracking")
        tracking["tracks"][0]["sampleCompanies"].append("RejectCo")
        self._write("tracking", tracking)
        self._write(
            "intents",
            {
                "schemaVersion": 1,
                "updatedAt": "2026-08-09T00:00:00Z",
                "entities": [
                    {
                        "id": "company:rejectco",
                        "kind": "company",
                        "name": "RejectCo",
                        "keywords": [],
                        "state": "rejected",
                    }
                ],
                "memberships": [
                    {
                        "id": "membership:rejectco",
                        "trackId": "track:ai",
                        "entityId": "company:rejectco",
                        "role": "actor",
                        "state": "rejected",
                        "pinned": True,
                        "origins": [],
                    }
                ],
            },
        )

        report = self._run(
            "--mode",
            "validate",
            "--kind",
            "technology",
            "--name",
            "端侧推理",
            "--tracks",
            "ai",
            "--reasons",
            "技术突破",
        )

        names = {row["name"] for row in report["recommendations"]["companies"]}
        self.assertNotIn("RejectCo", names)


if __name__ == "__main__":
    unittest.main()
