import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tools import refresh_people_profiles as core

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_ENRICH = core.enrich_candidate
SPEC = importlib.util.spec_from_file_location(
    "person_research_outcome_attribution_module",
    ROOT / "tools" / "refresh_people_profiles_with_video.py",
)
REFRESH = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
try:
    SPEC.loader.exec_module(REFRESH)
finally:
    # The production module intentionally installs its enriched entrypoint on import.
    # This test needs the helper only, so restore shared core state for later test modules.
    core.enrich_candidate = ORIGINAL_ENRICH


class PersonResearchOutcomeAttributionTests(unittest.TestCase):
    def setUp(self):
        self.previous = dict(REFRESH._RESEARCH_ATTEMPT_MAP)

    def tearDown(self):
        REFRESH._RESEARCH_ATTEMPT_MAP = self.previous

    def test_scheduler_query_overrides_curated_query_for_measured_attempt(self):
        REFRESH._RESEARCH_ATTEMPT_MAP = {
            "alice": {"taskId": "task-a", "query": "Alice scheduled research query"}
        }
        candidate = {
            "slug": "alice",
            "name": "Alice",
            "override": {"videoQueries": ["Alice old curated query"], "roleHint": "CEO"},
        }
        measured = REFRESH._candidate_with_research_query(candidate)
        self.assertEqual(measured["override"]["videoQueries"], ["Alice scheduled research query"])
        self.assertEqual(measured["override"]["roleHint"], "CEO")
        self.assertEqual(candidate["override"]["videoQueries"], ["Alice old curated query"])

    def test_refreshed_snapshot_publishes_nonempty_agenda_and_queue_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            people_path = root / "people.json"
            articles_path = root / "articles.json"
            agenda_path = root / "person_research_agenda.json"
            queue_path = root / "person_research_queue.json"
            people_path.write_text(json.dumps({
                "generatedAt": "2026-08-23T12:00:00Z",
                "people": [{
                    "slug": "alice",
                    "name": "Alice",
                    "role": "",
                    "organizations": [],
                    "materials": [],
                    "sectors": ["AI"],
                }],
            }), encoding="utf-8")
            articles_path.write_text('{"articles": []}\n', encoding="utf-8")

            agenda, queue = REFRESH.publish_research_plan(
                people_path=people_path,
                articles_path=articles_path,
                agenda_path=agenda_path,
                queue_path=queue_path,
                outcome_memory={"attempts": []},
            )

            self.assertGreater(agenda["taskCount"], 0)
            self.assertGreater(queue["selectedTaskCount"], 0)
            self.assertEqual(
                json.loads(agenda_path.read_text(encoding="utf-8"))["taskCount"],
                agenda["taskCount"],
            )
            self.assertEqual(
                json.loads(queue_path.read_text(encoding="utf-8"))["selectedTaskCount"],
                queue["selectedTaskCount"],
            )


if __name__ == "__main__":
    unittest.main()
