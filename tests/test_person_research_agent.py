from __future__ import annotations

import unittest

from tools.person_research_agent import (
    build_agenda,
    build_person_tasks,
    research_queries_by_slug,
)


def person(**overrides):
    value = {
        "slug": "test-person",
        "name": "测试人物",
        "englishName": "Test Person",
        "role": "Example Labs 创始人",
        "aliases": ["测试人物", "Test Person"],
        "sectors": ["AI / AGI"],
        "organizations": ["Example Labs"],
        "products": ["Atlas"],
        "concepts": ["世界模型"],
        "materials": [],
        "updatedAt": "2026-08-22T00:00:00Z",
    }
    value.update(overrides)
    return value


class PersonResearchAgentTests(unittest.TestCase):
    def test_missing_first_party_evidence_creates_bounded_identity_queries(self):
        tasks = build_person_tasks(person(), [], "2026-08-22T00:00:00Z")
        evidence_task = next(item for item in tasks if item["taskType"] == "first_party_evidence")
        self.assertIn(evidence_task["priority"], {"P0", "P1"})
        self.assertLessEqual(len(evidence_task["searchQueries"]), 3)
        self.assertTrue(evidence_task["searchQueries"])
        self.assertTrue(all("测试人物" in query for query in evidence_task["searchQueries"]))
        self.assertIn("至少补齐到 2 条", evidence_task["successCriteria"])
        self.assertEqual(evidence_task["status"], "open")

    def test_viewpoint_shift_only_creates_verification_task(self):
        profile = person(materials=[
            {
                "title": "世界模型：长期研究方向",
                "date": "2025-01-10",
                "type": "speech",
                "url": "https://example.com/old",
                "source": "Example Labs",
            },
            {
                "title": "从世界模型转向端到端智能体：新的研究重心",
                "date": "2026-08-01",
                "type": "interview",
                "url": "https://example.com/new",
                "source": "Example Interview",
            },
        ])
        tasks = build_person_tasks(profile, [], "2026-08-22T00:00:00Z")
        task = next(item for item in tasks if item["taskType"] == "viewpoint_verification")
        self.assertEqual(task["priority"], "P0")
        self.assertEqual(task["status"], "open")
        self.assertIn("仅有媒体标题不得标记 supported", task["successCriteria"])
        self.assertEqual(len(task["evidenceBasis"]), 2)

    def test_third_party_execution_evidence_stays_candidate(self):
        profile = person(materials=[
            {
                "title": "测试人物谈 Example Labs Atlas 世界模型",
                "date": "2026-08-20",
                "type": "interview",
                "url": "https://example.com/person",
                "source": "Media Interview",
            }
        ])
        articles = [{
            "title": "Example Labs 推进 Atlas 世界模型产品",
            "summary": "Example Labs Atlas 世界模型进入新阶段",
            "company": "Example Labs",
            "publishedAt": "2026-08-21",
            "importance": 8,
            "source": {
                "name": "Media A",
                "url": "https://media.example.com/a",
                "level": "媒体报道",
            },
        }]
        tasks = build_person_tasks(profile, articles, "2026-08-22T00:00:00Z")
        task = next(item for item in tasks if item["taskType"] == "execution_verification")
        self.assertEqual(task["status"], "candidate_found")
        self.assertEqual(task["candidateEvidence"][0]["sourceLevel"], "媒体报道")

    def test_official_independent_execution_evidence_can_satisfy_task(self):
        profile = person(materials=[
            {
                "title": "测试人物谈 Example Labs Atlas 世界模型",
                "date": "2026-08-20",
                "type": "interview",
                "url": "https://example.com/person",
                "source": "Media Interview",
            }
        ])
        articles = [{
            "title": "Example Labs 发布 Atlas 世界模型产品更新",
            "summary": "官方发布 Atlas 世界模型产品与部署信息",
            "company": "Example Labs",
            "publishedAt": "2026-08-21",
            "importance": 9,
            "source": {
                "name": "Example Labs",
                "url": "https://example.com/official-atlas",
                "level": "官方披露",
            },
        }]
        tasks = build_person_tasks(profile, articles, "2026-08-22T00:00:00Z")
        task = next(item for item in tasks if item["taskType"] == "execution_verification")
        self.assertEqual(task["status"], "supported")
        self.assertEqual(task["candidateEvidence"][0]["sourceLevel"], "官方披露")

    def test_same_url_official_evidence_cannot_close_execution_task(self):
        profile = person(materials=[
            {
                "title": "测试人物谈 Example Labs Atlas 世界模型",
                "date": "2026-08-20",
                "type": "interview",
                "url": "https://example.com/shared?utm_source=person",
                "source": "Example Labs",
            }
        ])
        articles = [{
            "title": "Example Labs 发布 Atlas 世界模型产品更新",
            "summary": "官方发布 Atlas 世界模型产品与部署信息",
            "company": "Example Labs",
            "publishedAt": "2026-08-21",
            "importance": 9,
            "source": {
                "name": "Example Labs",
                "url": "https://example.com/shared?utm_source=company",
                "level": "官方披露",
            },
        }]
        tasks = build_person_tasks(profile, articles, "2026-08-22T00:00:00Z")
        task = next(item for item in tasks if item["taskType"] == "execution_verification")
        self.assertEqual(task["status"], "candidate_found")
        self.assertIn("URL 不与人物证据重合", task["successCriteria"])

    def test_query_execution_uses_only_open_video_compatible_tasks(self):
        payload = {
            "generatedAt": "2026-08-22T00:00:00Z",
            "people": [person()],
        }
        agenda = build_agenda(payload, {"articles": []})
        queries = research_queries_by_slug(agenda)["test-person"]
        self.assertGreaterEqual(len(queries), 1)
        self.assertLessEqual(len(queries), 3)
        self.assertTrue(all("测试人物" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
