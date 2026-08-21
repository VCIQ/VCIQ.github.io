from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "config" / "user_tracking.json"


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


class TrackingWorktreeCleanAfterCrawlerTests(unittest.TestCase):
    def test_crawler_suite_leaves_user_tracking_identical_to_checked_out_head(self) -> None:
        raw = TRACKING.read_bytes()
        worktree_blob = git("hash-object", "config/user_tracking.json")
        head_blob = git("rev-parse", "HEAD:config/user_tracking.json")
        status = git("status", "--porcelain", "--", "config/user_tracking.json")

        print(
            "TRACKING_WORKTREE_AFTER_CRAWLER="
            + json.dumps(
                {
                    "rawSha256": hashlib.sha256(raw).hexdigest(),
                    "worktreeBlob": worktree_blob,
                    "headBlob": head_blob,
                    "status": status,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        if worktree_blob != head_blob or status:
            diff = subprocess.run(
                ["git", "diff", "--", "config/user_tracking.json"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            ).stdout
            self.fail(
                "crawler tests mutated config/user_tracking.json; "
                f"worktree_blob={worktree_blob} head_blob={head_blob} status={status!r}\n"
                f"diff:\n{diff[:12000]}"
            )


if __name__ == "__main__":
    unittest.main()
