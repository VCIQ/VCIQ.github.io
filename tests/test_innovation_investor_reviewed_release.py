import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from tools.innovation_investor_reviewed_release import prepare_release, append_canonical_json


def fixture():
    firms = [{"id": f"firm-{i}", "officialUrl": f"https://firm-{i}.example.org/"} for i in range(30)]
    original = "https://firm-0.example.org/stories/investing-in-chipco"
    queue = {"mode": "offline-human-review-queue", "autoPublication": False, "reviewLeads": [{
        "candidateId": "candidate-1", "institutionId": "firm-0", "type": "investment-lead",
        "originalUrl": original, "publicationAllowed": False,
    }]}
    record = {
        "id": "firm-0-chipco-20261010", "institutionId": "firm-0", "project": "ChipCo",
        "kind": "investment", "date": "2026-10-10", "datePrecision": "day",
        "title": "Firm 0 invests in ChipCo", "summary": "Firm 0 discloses its investment.",
        "round": None, "participation": "disclosed-investor", "roundAmount": None,
        "investorAmount": None, "speakers": [], "linkedPerson": None,
        "resultStatus": None, "realizedProceeds": None,
        "source": {"url": original, "title": "Investing in ChipCo", "publisher": "Firm 0",
                   "kind": "investor-official", "publishedAt": "2026-10-10",
                   "locator": "Final paragraph confirms investment."},
        "nextCheck": "Verify financing round and customer adoption.",
    }
    batch = {"schemaVersion": 1, "reviews": [{"candidateId": "candidate-1", "decision": "approved",
        "originalArticleVerified": True, "records": [record],
        "newProjectIdentity": {"id": "chipco", "name": "ChipCo", "observedNames": ["ChipCo"],
                               "identityEvidenceUrls": [original]}}]}
    return batch, queue, {"institutions": firms}, {"schemaVersion": 1, "records": []}, {"schemaVersion": 1, "projects": []}


class ReviewedReleaseTests(unittest.TestCase):
    def run_release(self, args):
        return prepare_release(*args, today=date(2026, 10, 10))

    def test_approved_source_appends_both_canonical_ledgers(self):
        evidence, identities, report = self.run_release(fixture())
        self.assertEqual(len(evidence["records"]), 1)
        self.assertEqual(identities["projects"][0]["id"], "chipco")
        self.assertEqual(report["newEvidenceRecords"], 1)
        self.assertEqual(report["status"], "reviewed-not-yet-deployed")

    def test_rejects_without_human_verification(self):
        args = list(copy.deepcopy(fixture()))
        args[0]["reviews"][0]["originalArticleVerified"] = False
        with self.assertRaisesRegex(ValueError, "human original-article approval"):
            self.run_release(args)

    def test_rejects_cross_source_forged_day_and_secondary_material(self):
        for change in ("source", "future-date", "media", "fake-amount"):
            with self.subTest(change=change):
                args = list(copy.deepcopy(fixture()))
                row = args[0]["reviews"][0]["records"][0]
                if change == "source":
                    row["source"]["url"] = "https://other.example.org/investing-in-chipco"
                elif change == "future-date":
                    row["date"] = row["source"]["publishedAt"] = "2026-10-11"
                elif change == "media":
                    row["source"]["kind"] = "investor-hosted-media-report"
                else:
                    row["investorAmount"] = {"value": -1, "currency": "USD"}
                with self.assertRaises(ValueError):
                    self.run_release(args)

    def test_duplicate_article_kind_and_duplicate_round_fail(self):
        args = list(copy.deepcopy(fixture()))
        existing = copy.deepcopy(args[0]["reviews"][0]["records"][0])
        existing["id"] = "old-investment"
        args[3]["records"] = [existing]
        with self.assertRaisesRegex(ValueError, "already present"):
            self.run_release(args)

    def test_existing_project_requires_exact_reuse(self):
        args = list(copy.deepcopy(fixture()))
        identity = args[0]["reviews"][0]["newProjectIdentity"]
        args[4]["projects"].append(identity)
        with self.assertRaisesRegex(ValueError, "duplicate project ID"):
            self.run_release(args)
        args[0]["reviews"][0]["newProjectIdentity"] = None
        evidence, identities, _ = self.run_release(args)
        self.assertEqual(len(identities["projects"]), 1)
        self.assertEqual(len(evidence["records"]), 1)

    def test_review_does_not_upgrade_scout_into_auto_publication(self):
        args = list(copy.deepcopy(fixture()))
        args[1]["autoPublication"] = True
        with self.assertRaisesRegex(ValueError, "unpromoted"):
            self.run_release(args)

    def test_canonical_append_keeps_old_line_stable_for_pr_review(self):
        # The actual manifest keeps one original source per compact line.
        prior = '{\n  "schemaVersion": 1,\n  "reviewedAt": "2026-10-01T00:00:00Z",\n' + (
            '  "records": [\n    {"id":"old","source":{"url":"https://firm-0.example.org/x"}}\n  ]\n}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            evidence_file = Path(directory) / "evidence.json"
            evidence_file.write_text(prior, encoding="utf-8")
            item = fixture()[0]["reviews"][0]["records"][0]
            append_canonical_json(evidence_file, "records", [item],
                                  reviewed_at="2026-10-10T10:30:00Z")
            result = evidence_file.read_text(encoding="utf-8")
            self.assertIn('    {"id":"old","source":{"url":"https://firm-0.example.org/x"}},\n', result)
            self.assertEqual(len(json.loads(result)["records"]), 2)
            self.assertIn('"reviewedAt": "2026-10-10T10:30:00Z"', result)

    def test_rejects_noncanonical_mutation_of_the_public_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text('{"reviewedAt":"2026-10-09","records":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected canonical"):
                append_canonical_json(path, "records", [{"id": "x"}],
                                      reviewed_at="2026-10-10T10:30:00Z")
            self.assertEqual(json.loads(path.read_text())["records"], [])

if __name__ == "__main__":
    unittest.main()
