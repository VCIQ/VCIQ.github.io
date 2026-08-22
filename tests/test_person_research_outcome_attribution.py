import unittest

import tools.refresh_people_profiles_with_video as refresh


class PersonResearchOutcomeAttributionTests(unittest.TestCase):
    def setUp(self):
        self.previous = dict(refresh._RESEARCH_ATTEMPT_MAP)

    def tearDown(self):
        refresh._RESEARCH_ATTEMPT_MAP = self.previous

    def test_scheduler_query_overrides_curated_query_for_measured_attempt(self):
        refresh._RESEARCH_ATTEMPT_MAP = {
            "alice": {"taskId": "task-a", "query": "Alice scheduled research query"}
        }
        candidate = {
            "slug": "alice",
            "name": "Alice",
            "override": {"videoQueries": ["Alice old curated query"], "roleHint": "CEO"},
        }
        measured = refresh._candidate_with_research_query(candidate)
        self.assertEqual(measured["override"]["videoQueries"], ["Alice scheduled research query"])
        self.assertEqual(measured["override"]["roleHint"], "CEO")
        self.assertEqual(candidate["override"]["videoQueries"], ["Alice old curated query"])


if __name__ == "__main__":
    unittest.main()
