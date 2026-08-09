from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools import full_refresh_input_guard as guard


class FullRefreshInputGuardTests(unittest.TestCase):
    def test_live_inputs_cover_runtime_and_configuration_not_public_outputs(self) -> None:
        expected = {
            ".github/workflows/scheduled-sync.yml",
            "tools/crawl_with_wechat_registry.py",
            "tools/article_publication_gate.py",
            "tools/core_official_adapters.py",
            "tools/source_portfolio.py",
            "tools/full_refresh_input_guard.py",
            "config/user_tracking.json",
            "config/official_company_sources.json",
            "config/professional_technology_media_sources.json",
        }
        self.assertTrue(expected.issubset(set(guard.LIVE_REFRESH_INPUTS)))
        self.assertFalse(any(path.startswith("public/data/") for path in guard.LIVE_REFRESH_INPUTS))
        self.assertEqual(len(guard.LIVE_REFRESH_INPUTS), len(set(guard.LIVE_REFRESH_INPUTS)))

    def _git(self, cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    def _commit(self, cwd: Path, message: str) -> str:
        self._git(cwd, "add", ".")
        self._git(cwd, "commit", "-m", message)
        return self._git(cwd, "rev-parse", "HEAD")

    def test_data_only_change_does_not_make_refresh_stale(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "VCIQ Tests")
            (root / "config").mkdir()
            (root / "public" / "data").mkdir(parents=True)
            (root / "config" / "user_tracking.json").write_text("{}\n", encoding="utf-8")
            (root / "public" / "data" / "articles.json").write_text("{}\n", encoding="utf-8")
            base = self._commit(root, "base")

            (root / "public" / "data" / "articles.json").write_text('{"changed":true}\n', encoding="utf-8")
            target = self._commit(root, "data only")

            result = guard.evaluate_currentness(base, target, cwd=root)
            self.assertTrue(result["current"])
            self.assertEqual(result["changedPaths"], [])

    def test_runtime_or_tracking_change_makes_refresh_stale(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            self._git(root, "init")
            self._git(root, "config", "user.email", "tests@example.com")
            self._git(root, "config", "user.name", "VCIQ Tests")
            (root / "config").mkdir()
            (root / "tools").mkdir()
            (root / "config" / "user_tracking.json").write_text("{}\n", encoding="utf-8")
            (root / "tools" / "source_portfolio.py").write_text("VALUE = 1\n", encoding="utf-8")
            base = self._commit(root, "base")

            (root / "config" / "user_tracking.json").write_text('{"version":2}\n', encoding="utf-8")
            (root / "tools" / "source_portfolio.py").write_text("VALUE = 2\n", encoding="utf-8")
            target = self._commit(root, "live inputs")

            result = guard.evaluate_currentness(base, target, cwd=root)
            self.assertFalse(result["current"])
            self.assertEqual(
                set(result["changedPaths"]),
                {"config/user_tracking.json", "tools/source_portfolio.py"},
            )


if __name__ == "__main__":
    unittest.main()
