from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StandaloneCapitalSemanticTests(unittest.TestCase):
    def test_cold_process_rejects_recruiting_and_preserves_real_acquisitions(self) -> None:
        # A fresh interpreter prevents other suites' shared-pattern installation
        # from hiding a broken standalone semantic gate.
        script = textwrap.dedent('''
            import copy
            from tools import enforce_venture_entity_semantics as semantics
            from tests.test_venture_entity_semantics import CATALOG

            def check():
                for phrase in (
                    "talent acquisition", "Talent Acquisition", "talent-acquisition",
                    "talent   acquisition", "talent\\nacquisition",
                ):
                    hr = {
                        "date": "", "type": "并购/退出", "title": "Leadership at Anthropic",
                        "summary": "Hannah leads Anthropic's " + phrase + " and organizational development.",
                        "sourceUrl": "https://www.anthropic.com/company/leadership",
                    }
                    transaction = {
                        "date": "2026-09-18", "type": "并购/退出",
                        "title": "Anthropic completed the acquisition of Acme",
                        "summary": "Anthropic completed the acquisition and expanded its " + phrase + " team.",
                        "sourceUrl": "https://www.anthropic.com/news/acquisition",
                    }
                    for events, expected in (([hr], []), ([hr, transaction], [transaction])):
                        payload = {
                            "companies": {"anthropic": {
                                "slug": "anthropic", "name": "Anthropic",
                                "background": "Anthropic builds reliable AI systems.",
                                "technology": "Anthropic develops Claude Platform.",
                                "products": ["Claude Platform"], "team": [], "financing": [],
                                "capitalMarkets": events, "technologyProducts": [], "sources": [],
                            }},
                            "institutions": {}, "qualityGate": {"passed": True, "checks": {}},
                        }
                        before = copy.deepcopy(payload)
                        cleaned, _ = semantics.enforce_snapshot(payload, CATALOG)
                        assert cleaned["companies"]["anthropic"]["capitalMarkets"] == expected, phrase
                        if not expected:
                            assert cleaned["companies"]["anthropic"]["exitPerformance"]["status"] == "暂无公开退出信息"
                        assert payload == before
                        assert semantics.enforce_snapshot(cleaned, CATALOG)[0] == cleaned

            check()
            from tools.stabilize_venture_publication_pipeline import align_capital_event_patterns
            align_capital_event_patterns()
            check()
            print("Cold and aligned semantic gates passed")
        ''')
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=ROOT, text=True,
            capture_output=True, timeout=45, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Cold and aligned semantic gates passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
