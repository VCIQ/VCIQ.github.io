"""Manual-session entrypoint regression across all registered collectors."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_social_contracts import fixture
from tests.test_social_zhihu import PATCHES
from tools.social import worker
from tools.social.contracts import ContractError
from workers.mediacrawler.upstream import PIN


class SessionEntrypointTests(unittest.TestCase):
    def test_explicit_setup_uses_guarded_profile_without_claiming_auth(self):
        for platform in sorted(worker.ENTRYPOINTS):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory:
                state, upstream = Path(directory) / "state", Path(directory) / "upstream"
                state.mkdir(mode=0o700); upstream.mkdir()
                runtime = fixture("runtime_config"); runtime["interactiveAuthAllowed"] = True
                def child(python, path, **kwargs):
                    request = json.loads(path.read_text())
                    self.assertEqual(request["action"], "session")
                    self.assertIsNone(request["job"])
                    self.assertEqual(request["profile"], str(state / "profiles" / platform))
                    self.assertEqual(kwargs["platform"], platform)
                    Path(request["output"]).write_text(json.dumps({"sessionPrepared": True, "authenticationVerified": False, "liveQueryExecuted": False}))
                    return False, 0
                with patch.object(worker, "preflight", return_value=(state, upstream, Path("/python"), {"commit": PIN, "patchsetHash": PATCHES})), patch.object(worker, "run_child", side_effect=child):
                    result = worker.bootstrap_session(runtime=runtime, policy={}, runtime_file=state / "runtime.json", live=True, interactive=True, platform=platform)
                self.assertTrue(result["ok"])
                self.assertFalse(result["authenticationVerified"])
                self.assertFalse(result["liveQueryExecuted"])

    def test_session_never_runs_without_interactive_opt_in(self):
        runtime = fixture("runtime_config")
        with patch.object(worker, "preflight", side_effect=AssertionError("started")):
            with self.assertRaisesRegex(ContractError, "interactive_auth_opt_in_required"):
                worker.bootstrap_session(runtime=runtime, policy={}, runtime_file=Path("/missing"), live=True, interactive=True, platform="zhihu")


if __name__ == "__main__": unittest.main()
