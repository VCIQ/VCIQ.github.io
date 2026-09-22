import unittest

from tools.enrich_tracking_people_from_sample_companies import (
    PublicWikidataClient,
    SocialAccount,
    apply_candidates,
    choose_core_team,
    empty_ledger,
    enrich_config,
    is_likely_person_name,
    profile_index,
)


class SampleCompanyPeopleDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "robotics",
                    "name": "机器人",
                    "enabled": True,
                    "custom": False,
                    "keywords": ["具身智能"],
                    "people": [],
                    "sampleCompanies": ["Example Robotics"],
                }
            ],
            "listedCompanies": [],
            "sources": [],
        }
        self.venture = {
            "companies": {
                "example-robotics": {
                    "slug": "example-robotics",
                    "name": "Example Robotics",
                    "team": [
                        {
                            "name": "Alice Chen",
                            "role": "联合创始人兼 CEO",
                            "sourceUrl": "https://example.com/team",
                        },
                        {
                            "name": "Bob Li",
                            "role": "CTO",
                            "sourceUrl": "https://example.com/team",
                        },
                        {
                            "name": "Carol Wu",
                            "role": "联合创始人",
                            "sourceUrl": "https://example.com/team",
                        },
                        {
                            "name": "Investor Relations",
                            "role": "团队",
                            "sourceUrl": "https://example.com/team",
                        },
                    ],
                }
            }
        }

    def test_core_team_prefers_founders_and_executives(self):
        profile = profile_index(self.venture)["examplerobotics"]
        candidates = choose_core_team(profile, "Example Robotics")
        self.assertEqual([item.name for item in candidates], ["Alice Chen", "Carol Wu", "Bob Li"])
        self.assertTrue(all(item.source_url == "https://example.com/team" for item in candidates))

    def test_rejects_role_and_sentence_fragments_as_people(self):
        for value in (
            "Company Development",
            "Business Development",
            "Autonomous Vehicles Senior Vice",
            "Class Presiden Thomas Sonderman",
            "Massachusetts Governo Chris Ballance",
            "作为自动驾",
            "主题演讲全",
            "杨永旺共同",
        ):
            self.assertFalse(is_likely_person_name(value), value)
        self.assertTrue(is_likely_person_name("Alice Chen"))
        self.assertTrue(is_likely_person_name("彭志辉"))

    def test_local_social_accounts_add_x_label_and_person_sources(self):
        people = {
            "people": [
                {
                    "name": "Alice Chen",
                    "aliases": [],
                    "handles": ["alicechen"],
                    "socialAccounts": [
                        {"url": "https://github.com/alicechen"},
                        {"url": "https://www.linkedin.com/in/alicechen"},
                    ],
                }
            ]
        }
        client = PublicWikidataClient(max_requests=0)
        ledger = empty_ledger()
        result = enrich_config(self.config, self.venture, people, ledger, client, 10)

        self.assertTrue(result["changed"])
        track = self.config["tracks"][0]
        self.assertIn("Alice Chen @alicechen", track["people"])
        self.assertIn("Carol Wu", track["people"])
        urls = {source["url"] for source in self.config["sources"]}
        self.assertIn("https://github.com/alicechen", urls)
        self.assertIn("https://www.linkedin.com/in/alicechen", urls)
        self.assertTrue(all(source["sourceCategory"] == "person" for source in self.config["sources"]))

    def test_existing_name_is_upgraded_instead_of_duplicated(self):
        track = self.config["tracks"][0]
        track["people"] = ["Alice Chen"]
        candidate = choose_core_team(profile_index(self.venture)["examplerobotics"], "Example Robotics")[0]
        candidate.socials = [SocialAccount("X", "alicechen", "https://x.com/alicechen")]
        ledger = empty_ledger()

        summary = apply_candidates(self.config, ledger, track, [candidate])

        self.assertEqual(track["people"], ["Alice Chen @alicechen"])
        self.assertEqual(summary["added"]["people"], ["Alice Chen @alicechen"])
        self.assertEqual(len([row for row in ledger["added"] if row["kind"] == "people"]), 1)

    def test_removed_auto_person_is_not_added_again(self):
        ledger = empty_ledger()
        ledger["removed"].append(
            {
                "track": "robotics",
                "kind": "people",
                "value": "Alice Chen @alicechen",
                "removedAt": "2026-07-27T00:00:00+00:00",
            }
        )
        candidate = choose_core_team(profile_index(self.venture)["examplerobotics"], "Example Robotics")[0]
        candidate.socials = [SocialAccount("X", "alicechen", "https://x.com/alicechen")]

        summary = apply_candidates(self.config, ledger, self.config["tracks"][0], [candidate])

        self.assertNotIn("Alice Chen @alicechen", self.config["tracks"][0]["people"])
        self.assertEqual(summary["added"]["people"], [])

    def test_social_source_is_deduplicated_by_url(self):
        self.config["sources"].append(
            {
                "id": "existing-alice-github",
                "name": "Alice Chen · GitHub",
                "url": "https://github.com/alicechen",
                "sourceType": "listing-search",
                "sourceCategory": "person",
                "region": "全球",
                "sector": "机器人",
                "company": "",
                "ticker": "",
                "keywords": ["Alice Chen"],
                "enabled": True,
            }
        )
        candidate = choose_core_team(profile_index(self.venture)["examplerobotics"], "Example Robotics")[0]
        candidate.socials = [SocialAccount("GitHub", "alicechen", "https://github.com/alicechen")]

        apply_candidates(self.config, empty_ledger(), self.config["tracks"][0], [candidate])

        self.assertEqual(
            [source["url"] for source in self.config["sources"]].count("https://github.com/alicechen"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
