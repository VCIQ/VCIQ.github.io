"""Directory drift fails closed; stop is one-way and never relaxes privacy."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_social_contracts import fixture
from tools.social.batch import ROOT, private_root, read_private, write_private
from tools.social.guard import GuardError
from tools.social.shadow_state import clear_stop, request_stop, stopped
from workers.mediacrawler import observer, request_control


@unittest.skipUnless(os.name == "posix", "POSIX worker boundary")
class PermissionDriftTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name).resolve()
        self.root = self.parent / "state"; self.root.mkdir(mode=0o700)
        self.roots = (ROOT,)
        value = fixture("runtime_config")
        value.update(enabled=True, stateDir=str(self.root), profileRoot=str(self.root / "profiles"), mediacrawlerDir=None)
        value["platforms"]["xhs"]["enabled"] = True
        self.runtime = self.root / "runtime.json"
        self.runtime.write_text(json.dumps(value)); self.runtime.chmod(0o600)
        self.original = self.runtime.read_bytes()

    def check(self):
        request_control.check(observer, platform="xhs", state_dir=str(self.root), runtime_file=str(self.runtime))

    def test_private_directory_allows_control(self):
        self.check()

    def test_directory_drift_refuses_even_private_runtime_before_read(self):
        for mode in (0o750, 0o755, 0o770, 0o777):
            with self.subTest(mode=oct(mode)):
                self.root.chmod(mode)
                with patch.object(request_control.os, "open", side_effect=AssertionError("runtime read")):
                    with self.assertRaisesRegex(observer.CollectorError, "SHADOW_CONTROL_PERMISSIONS"):
                        self.check()

    def test_stop_can_only_add_latch_in_owner_readable_directory(self):
        self.root.chmod(0o755)
        self.assertTrue(request_stop(self.root, self.roots))
        self.assertEqual((self.root / "shadow.stop").read_bytes(), b'{"stop":true}\n')
        self.assertEqual(stat.S_IMODE((self.root / "shadow.stop").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o755)
        self.assertEqual(self.runtime.read_bytes(), self.original)
        self.assertTrue(stopped(self.root, self.roots))

    def test_latch_idempotent_does_not_replace_or_read_existing_file(self):
        self.root.chmod(0o755)
        path = self.root / "shadow.stop"; path.write_bytes(b"incomplete-stop")
        inode = path.stat().st_ino
        self.assertFalse(request_stop(self.root, self.roots))
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"incomplete-stop")

    def test_group_or_world_writable_root_rejected_without_writes(self):
        for mode in (0o720, 0o702, 0o770, 0o777):
            with self.subTest(mode=oct(mode)):
                self.root.chmod(mode)
                with self.assertRaisesRegex(GuardError, "shadow_stop_directory_permissions"):
                    request_stop(self.root, self.roots)
                self.assertFalse((self.root / "shadow.stop").exists())

    def test_owner_mismatch_refuses_stop_and_worker(self):
        with patch("os.geteuid", return_value=self.root.stat().st_uid + 1):
            with self.assertRaisesRegex(GuardError, "shadow_stop_directory_permissions"):
                request_stop(self.root, self.roots)
            with self.assertRaisesRegex(observer.CollectorError, "SHADOW_CONTROL_PERMISSIONS"):
                self.check()

    def test_stop_does_not_authorize_resume_or_private_writes(self):
        self.root.chmod(0o755); request_stop(self.root, self.roots)
        with self.assertRaises(GuardError): clear_stop(self.root, self.roots)
        with self.assertRaises(GuardError): private_root(self.root, self.roots)
        with self.assertRaises(GuardError): read_private(self.root, "runtime.json", self.roots)
        with self.assertRaises(GuardError): write_private(self.root, "secret.json", b"{}", self.roots)
        self.assertFalse((self.root / "secret.json").exists())

    def test_root_symlink_rejected_without_touching_target(self):
        alias = self.parent / "alias"; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(GuardError): request_stop(alias, self.roots)
        self.assertFalse((self.root / "shadow.stop").exists())

    def test_linked_marker_is_not_followed_or_replaced(self):
        target = self.parent / "outside"; target.write_text("unchanged")
        marker = self.root / "shadow.stop"; marker.symlink_to(target)
        self.assertFalse(request_stop(self.root, self.roots))
        self.assertTrue(marker.is_symlink()); self.assertEqual(target.read_text(), "unchanged")

    def test_missing_root_not_created(self):
        missing = self.parent / "missing"
        with self.assertRaises(OSError): request_stop(missing, self.roots)
        self.assertFalse(missing.exists())

    def test_restoring_permissions_still_requires_explicit_resume(self):
        self.root.chmod(0o755); request_stop(self.root, self.roots)
        self.root.chmod(0o700)
        with self.assertRaisesRegex(observer.CollectorError, "SHADOW_STOP_REQUESTED"): self.check()
        clear_stop(self.root, self.roots); self.check()

    def test_fsync_failure_leaves_fail_closed_marker(self):
        with patch("tools.social.shadow_state.os.fsync", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError): request_stop(self.root, self.roots)
        self.assertTrue(stopped(self.root, self.roots))

    def test_repository_cannot_be_stop_destination(self):
        with self.assertRaises(GuardError): request_stop(ROOT, self.roots)

    def test_directory_marker_already_means_stop(self):
        (self.root / "shadow.stop").mkdir()
        self.assertFalse(request_stop(self.root, self.roots))
        self.assertTrue(stopped(self.root, self.roots))


if __name__ == "__main__": unittest.main()
