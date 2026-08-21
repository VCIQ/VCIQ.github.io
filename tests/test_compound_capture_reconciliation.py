from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.entity_resolution import (
    normalize_decision_manifest,
    normalize_identity,
    resolve_entity,
)
from tools.reconcile_entity_resolution import reconcile_payloads
from tools.tracking_entity_integrity import (
    find_compound_tracking_entities,
    split_compound_tracking_entity_name,
)


ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = ROOT / "config" / "entity_resolution_decisions.json"
INBOX_PATH = ROOT / "config" / "tracking_capture_inbox.json"

WANG = "王慧文、陈天桥、"
GOOGLE = "Quoc Le、Jeff Dean、Sanjay Ghemawat、Quoc Le、Oriol Vinyals"
RESEARCH = "Jeff Dean、陶哲轩、李飞飞、Dawn Song、Oriol Vinyals"
INVESTORS = (
    "Aliya Capital Partners、Atreides Management、Artisan Partners、"
    "Battery Ventures、Diagonal Capital、Intel Capital、Key1 Capital"
)
KNOWN_HISTORICAL_COMPOUNDS = {WANG, GOOGLE, RESEARCH, INVESTORS}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CompoundCaptureReconciliationTests(unittest.TestCase):
    def test_every_historical_compound_person_company_capture_has_a_nonresolved_decision(self) -> None:
        inbox = load_json(INBOX_PATH)
        decisions = normalize_decision_manifest(load_json(DECISIONS_PATH))
        found: set[str] = set()
        missing: list[dict[str, object]] = []
        invalid: list[dict[str, object]] = []

        for record in inbox.get("records", []):
            if not isinstance(record, dict):
                continue
            kind = str(record.get("entityType") or "")
            if kind not in {"person", "company"}:
                continue
            name = str(record.get("rawSelection") or record.get("canonicalName") or "").strip()
            if len(split_compound_tracking_entity_name(name)) < 2:
                continue

            found.add(name)
            audit_row = {
                "id": str(record.get("id") or ""),
                "entityType": kind,
                "name": name,
                "trackSlugs": record.get("trackSlugs", []),
                "recordStatus": record.get("status"),
                "recordDecisionKey": (
                    record.get("resolution", {}).get("decisionKey")
                    if isinstance(record.get("resolution"), dict)
                    else ""
                ),
            }
            decision = decisions.get(normalize_identity(name))
            if decision is None:
                missing.append(audit_row)
                continue

            problems: list[str] = []
            if decision["status"] not in {"review", "rejected"}:
                problems.append(f"status={decision['status']}")
            if decision["entityType"] != kind:
                problems.append(
                    f"entityType={decision['entityType']} expected={kind}"
                )
            if decision["targetId"] != "":
                problems.append(f"targetId={decision['targetId']}")
            if problems:
                invalid.append({**audit_row, "decisionProblems": problems})

        self.assertFalse(
            missing,
            "historical compound captures missing quarantine decisions: "
            + json.dumps(missing, ensure_ascii=False, sort_keys=True),
        )
        self.assertFalse(
            invalid,
            "historical compound captures have unsafe quarantine decisions: "
            + json.dumps(invalid, ensure_ascii=False, sort_keys=True),
        )
        self.assertTrue(
            KNOWN_HISTORICAL_COMPOUNDS.issubset(found),
            f"known historical compound captures disappeared from the audit surface: {sorted(KNOWN_HISTORICAL_COMPOUNDS - found)}",
        )

    def test_versioned_quarantine_decisions_win_over_registry_and_explicit_type_fallback(self) -> None:
        decisions = load_json(DECISIONS_PATH)
        fixtures = (
            ("person", WANG),
            ("person", GOOGLE),
            ("person", RESEARCH),
            ("company", INVESTORS),
        )

        for kind, name in fixtures:
            with self.subTest(kind=kind, name=name):
                resolution = resolve_entity(
                    kind,
                    name,
                    {"title": f"historical {kind} capture"},
                    decisions_payload=decisions,
                    company_registry_payload={
                        "companies": [{"slug": "legacy-compound", "name": name}]
                        if kind == "company"
                        else []
                    },
                    people_payload={
                        "people": [{"slug": "legacy-compound", "name": name}]
                        if kind == "person"
                        else []
                    },
                    tracking_payload={"tracks": []},
                )
                self.assertEqual(resolution.status, "review")
                self.assertEqual(resolution.source, "human-decision")
                self.assertEqual(resolution.targetId, "")
                self.assertEqual(resolution.canonicalName, name)

    def test_historical_replay_removes_exact_ten_compounds_and_preserves_atomic_values(self) -> None:
        google_atoms = ["Quoc Le", "Jeff Dean", "Sanjay Ghemawat", "Oriol Vinyals"]
        research_atoms = ["Jeff Dean", "陶哲轩", "李飞飞", "Dawn Song", "Oriol Vinyals"]
        investor_atoms = [
            "Aliya Capital Partners",
            "Atreides Management",
            "Artisan Partners",
            "Battery Ventures",
            "Diagonal Capital",
            "Intel Capital",
            "Key1 Capital",
        ]

        def track(slug: str, name: str, *, people=None, companies=None):
            return {
                "slug": slug,
                "name": name,
                "enabled": True,
                "custom": False,
                "keywords": [],
                "people": list(people or []),
                "sampleCompanies": list(companies or []),
            }

        config = {
            "schemaVersion": 1,
            "tracks": [
                track(
                    "ai",
                    "AI / AGI",
                    people=[
                        "王慧文",
                        "陈天桥",
                        *google_atoms,
                        *research_atoms,
                        WANG,
                        GOOGLE,
                        RESEARCH,
                    ],
                ),
                track(
                    "robotics",
                    "机器人",
                    people=[*google_atoms, *research_atoms, GOOGLE, RESEARCH],
                ),
                track(
                    "ai-2",
                    "AI安全",
                    people=[*google_atoms, *research_atoms, GOOGLE, RESEARCH],
                ),
                track(
                    "semiconductor",
                    "半导体",
                    companies=[*investor_atoms, INVESTORS],
                ),
                track(
                    "track-1ccjq49",
                    "风险投资",
                    people=["王慧文", "陈天桥", WANG],
                    companies=[*investor_atoms, INVESTORS],
                ),
            ],
            "listedCompanies": [],
            "sources": [],
        }
        self.assertEqual(len(find_compound_tracking_entities(config)), 10)

        def capture(capture_id: str, kind: str, value: str, slugs: list[str], field: str):
            return {
                "id": capture_id,
                "entityType": kind,
                "canonicalName": value,
                "rawSelection": value,
                "aliases": [],
                "trackSlugs": slugs,
                "trackNames": slugs,
                "source": {"title": "historical capture"},
                "capturedAt": "2026-08-09T00:00:00Z",
                "capturedBy": "VCIQ",
                "status": "applied",
                "appliedTo": [f"{slug}:{field}" for slug in slugs],
                "reasons": ["个人研究兴趣"],
                "note": "",
            }

        inbox = {
            "schemaVersion": 1,
            "generatedAt": "",
            "records": [
                capture("capture-wang", "person", WANG, ["ai", "track-1ccjq49"], "people"),
                capture("capture-google", "person", GOOGLE, ["ai", "robotics", "ai-2"], "people"),
                capture("capture-research", "person", RESEARCH, ["ai", "robotics", "ai-2"], "people"),
                capture(
                    "capture-investors",
                    "company",
                    INVESTORS,
                    ["semiconductor", "track-1ccjq49"],
                    "sampleCompanies",
                ),
            ],
        }

        decisions = load_json(DECISIONS_PATH)
        next_config, next_inbox, stats = reconcile_payloads(
            config,
            inbox,
            decisions_payload=decisions,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
        )

        self.assertEqual(find_compound_tracking_entities(next_config), [])
        self.assertEqual(stats["review"], 4)
        for record in next_inbox["records"]:
            self.assertEqual(record["status"], "queued")
            self.assertEqual(record["appliedTo"], [])
            self.assertEqual(record["resolution"]["source"], "human-decision")

        by_slug = {row["slug"]: row for row in next_config["tracks"]}
        self.assertTrue({"王慧文", "陈天桥"}.issubset(by_slug["ai"]["people"]))
        self.assertTrue({"王慧文", "陈天桥"}.issubset(by_slug["track-1ccjq49"]["people"]))
        for slug in ("ai", "robotics", "ai-2"):
            self.assertTrue(set(google_atoms).issubset(by_slug[slug]["people"]))
            self.assertTrue(set(research_atoms).issubset(by_slug[slug]["people"]))
        for slug in ("semiconductor", "track-1ccjq49"):
            self.assertTrue(set(investor_atoms).issubset(by_slug[slug]["sampleCompanies"]))

        fixed_config, fixed_inbox, fixed_stats = reconcile_payloads(
            next_config,
            next_inbox,
            decisions_payload=decisions,
            company_registry_payload={"companies": []},
            people_payload={"people": []},
        )
        self.assertEqual(fixed_config, next_config)
        self.assertEqual(fixed_inbox, next_inbox)
        self.assertEqual(fixed_stats["review"], 4)


if __name__ == "__main__":
    unittest.main()
