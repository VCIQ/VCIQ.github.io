from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_wechat_signed_links import audit


class AuditSignedWeChatLinksTests(unittest.TestCase):
    def test_counts_references_without_returning_sensitive_urls(self) -> None:
        signed = "https://mp.weixin.qq.com/s?new=1&signature=SECRET&timestamp=1794138303&ver=7076"
        share = "https://mp.weixin.qq.com/s/shortcode"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.json").write_text(json.dumps({
                "items": [{"url": signed}, {"source": {"url": share}}, {"url": signed}],
            }))
            (root / "b.json").write_text(json.dumps({"url": "https://example.com/a"}))
            result = audit(root)
        self.assertEqual(result["linkReferences"]["temporary"], 2)
        self.assertEqual(result["linkReferences"]["durable"], 1)
        self.assertEqual(result["nonDurableUniqueUrls"], 1)
        self.assertEqual(len(result["files"]), 1)
        self.assertNotIn("SECRET", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
