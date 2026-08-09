from __future__ import annotations

import unittest
from pathlib import Path

from tools import apply_manual_company_trust
from tools import build_company_candidates
from tools import onboard_company_candidates
from tools import prepare_company_candidate_onboarding


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_QUEUE = ROOT / "config" / "company_candidate_review_queue.json"
PRIVATE_ONBOARDING = ROOT / "config" / "company_candidate_onboarding_state.json"


class CompanyReviewPathDefaultsTest(unittest.TestCase):
    def test_candidate_cli_defaults_use_private_review_queue(self) -> None:
        self.assertEqual(build_company_candidates.OUTPUT_PATH, PRIVATE_QUEUE)
        self.assertEqual(apply_manual_company_trust.CANDIDATES_PATH, PRIVATE_QUEUE)
        self.assertEqual(prepare_company_candidate_onboarding.CANDIDATES_PATH, PRIVATE_QUEUE)
        self.assertEqual(onboard_company_candidates.CANDIDATES_PATH, PRIVATE_QUEUE)

    def test_onboarding_cli_default_uses_private_state(self) -> None:
        self.assertEqual(onboard_company_candidates.REPORT_PATH, PRIVATE_ONBOARDING)

    def test_private_defaults_cannot_recreate_retired_public_review_files(self) -> None:
        retired = {
            ROOT / "public" / "data" / "company_candidates.json",
            ROOT / "public" / "data" / "company_candidate_onboarding.json",
        }
        defaults = {
            build_company_candidates.OUTPUT_PATH,
            apply_manual_company_trust.CANDIDATES_PATH,
            prepare_company_candidate_onboarding.CANDIDATES_PATH,
            onboard_company_candidates.CANDIDATES_PATH,
            onboard_company_candidates.REPORT_PATH,
        }
        self.assertTrue(defaults.isdisjoint(retired))
        for path in defaults:
            self.assertTrue(path.is_relative_to(ROOT / "config"), path)


if __name__ == "__main__":
    unittest.main()
