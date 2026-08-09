from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'company-candidate-onboarding.yml'


class CompanyCandidateOnboardingWorkflowTests(unittest.TestCase):
    def test_handoff_modes_compact_independently_and_writer_job_stays_serialized(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        top = text.split('jobs:', 1)[0]
        self.assertIn("group: vciq-candidate-onboarding-${{ github.ref }}-${{ inputs.post_onboarding_handoff || 'none' }}", top)
        self.assertIn('queue: single', top)
        onboard = text.split('  onboard:\n', 1)[1]
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", onboard)
        self.assertIn('queue: max', onboard)
        self.assertNotIn('cancel-in-progress:', text)

    def test_refresh_and_terminal_publication_handoffs_remain_distinct(self) -> None:
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('post_onboarding_handoff:', text)
        self.assertIn('refresh)', text)
        self.assertIn('publish-with-research)', text)
        self.assertIn('gh workflow run scheduled-sync.yml --ref main', text)
        self.assertIn('run_research_after_deploy=true', text)


if __name__ == '__main__':
    unittest.main()
