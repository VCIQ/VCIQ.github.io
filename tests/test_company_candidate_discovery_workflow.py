from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'company-candidate-discovery.yml'


class CompanyCandidateDiscoveryWorkflowTests(unittest.TestCase):
    def test_semantic_modes_compact_independently_and_writer_job_stays_serialized(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        top = text.split('jobs:', 1)[0]
        self.assertIn("group: vciq-candidate-discovery-${{ github.ref }}-${{ inputs.publish_after_reconciliation || 'false' }}", top)
        self.assertIn('queue: single', top)
        discover = text.split('  discover:\n', 1)[1]
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", discover)
        self.assertIn('queue: max', discover)
        self.assertNotIn('cancel-in-progress:', text)

    def test_refresh_and_terminal_publication_handoffs_remain_distinct(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('publish_after_reconciliation:', text)
        self.assertIn('post_onboarding_handoff=refresh', text)
        self.assertIn('post_onboarding_handoff=publish-with-research', text)
        self.assertIn('gh workflow run scheduled-sync.yml --ref main', text)


if __name__ == '__main__':
    unittest.main()
