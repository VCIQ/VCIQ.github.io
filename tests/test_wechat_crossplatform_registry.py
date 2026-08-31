from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


class WeChatCrossPlatformRegistryTests(unittest.TestCase):
    def test_every_active_wechat_entity_has_a_whitelisted_cross_platform_index(self) -> None:
        registry = json.loads(
            (ROOT / "config" / "wechat_sources.json").read_text(encoding="utf-8")
        )
        indexes = json.loads(
            (ROOT / "config" / "wechat_public_indexes.json").read_text(
                encoding="utf-8"
            )
        ).get("accounts", {})
        active = [
            row
            for row in registry.get("accounts", [])
            if isinstance(row, dict) and row.get("enabled", True) is not False
        ]

        self.assertEqual(len(active), 13)
        self.assertNotIn("robospeak", {row.get("id") for row in active})

        for row in active:
            source_id = str(row.get("id") or "")
            self.assertTrue(row.get("publisherEntity"), source_id)
            self.assertTrue(row.get("acceptedSourceKinds"), source_id)
            allowed_hosts = {
                str(host).lower().removeprefix("www.")
                for host in row.get("officialCrosspostHosts", [])
            }
            self.assertTrue(allowed_hosts, source_id)
            official_indexes = [
                url
                for url in indexes.get(source_id, [])
                if (urlsplit(url).hostname or "")
                .lower()
                .removeprefix("www.")
                in allowed_hosts
            ]
            self.assertTrue(
                official_indexes,
                f"{source_id} has no index on an explicitly allowed publisher host",
            )

    def test_ai_technology_review_uses_certified_crosspost_semantics(self) -> None:
        registry = json.loads(
            (ROOT / "config" / "wechat_sources.json").read_text(encoding="utf-8")
        )
        account = next(
            row for row in registry["accounts"] if row.get("id") == "aitechuang"
        )
        self.assertIn("official-crosspost", account["acceptedSourceKinds"])
        self.assertNotIn("official-website", account["acceptedSourceKinds"])
        self.assertEqual(
            account["officialPlatformLabels"]["leiphone.com"],
            "雷峰网认证作者页",
        )


if __name__ == "__main__":
    unittest.main()
