#!/usr/bin/env python3
"""One-time source migration for automatic-only all-skipped batches."""

from pathlib import Path


def replace_once(path: str, before: str, after: str) -> None:
    target = Path(path)
    source = target.read_text(encoding="utf-8")
    if source.count(before) != 1:
        raise SystemExit(f"expected exactly one source fragment in {path}")
    target.write_text(source.replace(before, after), encoding="utf-8")


replace_once(
    "tools/manual_tracking_batch.py",
    '''    if invalid_policy == "skip" and not results:
        details = "；".join(
            f"第 {item['index']} 个对象 {item['name'] or item['objectType']}：{item['error']}"
            for item in skipped[:3]
        )
        suffix = f"（{details}）" if details else ""
        raise manual.ManualTrackingError(f"整批对象均未通过验证，没有可安全写入的对象。{suffix}")
''',
    '''    # An automatic-only batch may legitimately collapse to a no-op after
    # canonical validation. Return the skipped outcomes as a successful,
    # unchanged transaction so the control plane can report each rejection
    # without presenting an expected safety decision as an infrastructure error.
''',
)

replace_once(
    "tests/test_manual_tracking_batch.py",
    '''    def test_skip_policy_fails_when_every_automatic_candidate_is_invalid(self) -> None:
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run([self.invalid_person()], "apply", expected=2, invalid_policy="skip")
        self.assertFalse(report["ok"])
        self.assertIn("均未通过验证", report["error"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})
''',
    '''    def test_skip_policy_all_invalid_automatic_candidates_is_successful_noop(self) -> None:
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        report = self._run([self.invalid_person()], "apply", invalid_policy="skip")

        self.assertTrue(report["ok"])
        self.assertFalse(report["changed"])
        self.assertFalse(report["configChanged"])
        self.assertFalse(report["inboxChanged"])
        self.assertFalse(report["intentsChanged"])
        self.assertEqual(report["acceptedCount"], 0)
        self.assertEqual(report["skippedCount"], 1)
        self.assertEqual(report["appliedCount"], 0)
        self.assertEqual(report["reviewQueuedCount"], 0)
        self.assertEqual(report["recordedCount"], 0)
        self.assertEqual(report["unchangedCount"], 0)
        self.assertEqual(len(report["outcomes"]), 1)
        self.assertEqual(report["outcomes"][0]["outcome"], "skipped")
        self.assertEqual(report["outcomes"][0]["origin"], "automatic")
        self.assertIn("完整姓名", report["outcomes"][0]["reason"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})
''',
)

Path("scripts/bootstrap-automatic-all-skipped-noop.py").unlink(missing_ok=True)
Path(".github/workflows/bootstrap-automatic-all-skipped-noop.yml").unlink(missing_ok=True)
