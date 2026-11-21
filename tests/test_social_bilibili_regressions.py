"""Identity conflicts must not be hidden as ordinary duplicate rows."""
import copy
import unittest

from tools.social.adapters.bilibili import finalize
from tests.test_social_bilibili import inputs, captured, PATCHES


class BilibiliConflictTests(unittest.TestCase):
    def test_same_aid_conflicting_bvid_is_rejected_not_deduplicated(self):
        job, context, row = inputs()
        cap = captured(job, row)
        second = copy.deepcopy(cap["records"][0])
        second["record"]["bvid"] = "BV1d54y1g7dc"
        cap["records"].append(second)
        cap["pages"][0]["contentItems"] = 2
        result = finalize(job, cap, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(result["receipt"]["counts"]["rejectedRows"], 1)
        self.assertEqual(result["receipt"]["counts"]["duplicateRows"], 0)

    def test_same_bvid_conflicting_aid_is_rejected(self):
        job, context, row = inputs()
        cap = captured(job, row)
        second = copy.deepcopy(cap["records"][0])
        second["record"]["video_id"] = "124"
        cap["records"].append(second)
        cap["pages"][0]["contentItems"] = 2
        result = finalize(job, cap, context, patchset_hash=PATCHES)
        self.assertEqual(result["receipt"]["status"], "partial")
        self.assertEqual(len(result["observations"]), 1)


if __name__ == "__main__": unittest.main()
