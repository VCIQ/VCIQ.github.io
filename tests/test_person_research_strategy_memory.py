import unittest

from tools.person_research_cost_model import choose_cost_aware_query_strategy
from tools.person_research_strategy_memory import (
    build_strategy_stats,
    choose_query_strategy,
    classify_query_strategy,
    classify_source_type,
)


class PersonResearchStrategyMemoryTests(unittest.TestCase):
    def test_query_and_source_strategies_are_explainable(self):
        self.assertEqual(
            classify_query_strategy("Alice 世界模型 完整访谈", "viewpoint_verification"),
            "full_context_interview",
        )
        self.assertEqual(
            classify_query_strategy("Alice 世界模型 演讲", "first_party_evidence"),
            "topic_speech",
        )
        self.assertEqual(classify_source_type("https://www.youtube.com/watch?v=1"), "video_platform")
        self.assertEqual(classify_source_type("https://arxiv.org/abs/1234"), "academic")
        self.assertEqual(classify_source_type("https://example.com/a", "机构官方来源"), "official")

    def test_task_source_matrix_uses_all_attempts_as_denominator(self):
        attempts = [
            {
                "taskType": "first_party_evidence",
                "query": "Alice topic 访谈",
                "queryStrategy": "topic_interview",
                "outcome": "candidate_found",
                "candidateCount": 2,
                "sourceTypeCounts": {"video_platform": 2},
            },
            {
                "taskType": "first_party_evidence",
                "query": "Alice topic 访谈",
                "queryStrategy": "topic_interview",
                "outcome": "no_evidence",
                "candidateCount": 0,
                "sourceTypeCounts": {},
            },
        ]
        stats = build_strategy_stats(attempts)
        self.assertEqual(stats["queryStrategyStats"]["topic_interview"]["attempts"], 2)
        self.assertEqual(stats["queryStrategyStats"]["topic_interview"]["successRate"], 0.5)
        matrix = stats["taskSourceMatrix"]["first_party_evidence"]["video_platform"]
        self.assertEqual(matrix["attempts"], 2)
        self.assertEqual(matrix["yieldAttempts"], 1)
        self.assertEqual(matrix["yieldRate"], 0.5)
        self.assertEqual(matrix["candidates"], 2)

    def test_higher_yield_strategy_wins_without_changing_fact_state(self):
        memory = {
            "attempts": [
                *[
                    {
                        "taskType": "first_party_evidence",
                        "query": "Alice 世界模型",
                        "queryStrategy": "topic_direct",
                        "outcome": "no_evidence",
                        "candidateCount": 0,
                        "sourceTypes": [],
                    }
                    for _ in range(3)
                ],
                *[
                    {
                        "taskType": "first_party_evidence",
                        "query": "Alice 世界模型 演讲",
                        "queryStrategy": "topic_speech",
                        "outcome": "candidate_found",
                        "candidateCount": 2,
                        "sourceTypes": ["video_platform"],
                        "sourceTypeCounts": {"video_platform": 2},
                    }
                    for _ in range(3)
                ],
            ]
        }
        choice = choose_query_strategy(
            memory,
            "first_party_evidence",
            ["Alice 世界模型", "Alice 世界模型 演讲"],
        )
        self.assertEqual(choice["query"], "Alice 世界模型 演讲")
        self.assertEqual(choice["strategy"], "topic_speech")
        self.assertGreater(choice["historyAdjustment"], 0)
        self.assertGreater(choice["expectedSuccessRate"], 0.5)
        self.assertEqual(choice["topSourceType"], "video_platform")
        self.assertNotIn("supported", choice)

    def test_cost_aware_choice_prefers_same_yield_at_lower_measured_cost(self):
        memory = {
            "attempts": [
                *[
                    {
                        "taskType": "viewpoint_verification",
                        "query": "Alice 世界模型 演讲",
                        "queryStrategy": "topic_speech",
                        "outcome": "candidate_found",
                        "candidateCount": 1,
                        "durationMs": 40_000,
                        "queryCostUnits": 4,
                    }
                    for _ in range(3)
                ],
                *[
                    {
                        "taskType": "viewpoint_verification",
                        "query": "Alice 世界模型 访谈",
                        "queryStrategy": "topic_interview",
                        "outcome": "candidate_found",
                        "candidateCount": 1,
                        "durationMs": 10_000,
                        "queryCostUnits": 1,
                    }
                    for _ in range(3)
                ],
            ]
        }
        choice = choose_cost_aware_query_strategy(
            memory,
            "viewpoint_verification",
            ["Alice 世界模型 演讲", "Alice 世界模型 访谈"],
        )
        self.assertEqual(choice["strategy"], "topic_interview")
        self.assertEqual(choice["expectedCostUnits"], 1)
        self.assertGreater(choice["expectedYieldPerCost"], 0.5)
        self.assertGreater(choice["costEfficiencyAdjustment"], 0)
        self.assertNotIn("supported", choice)

    def test_unseen_strategy_uses_small_prior_not_fake_history(self):
        choice = choose_query_strategy(
            {},
            "viewpoint_verification",
            ["Alice 世界模型", "Alice 世界模型 完整访谈"],
        )
        self.assertEqual(choice["query"], "Alice 世界模型 完整访谈")
        self.assertEqual(choice["sampleSize"], 0)
        self.assertEqual(choice["historyAdjustment"], 0)


if __name__ == "__main__":
    unittest.main()
