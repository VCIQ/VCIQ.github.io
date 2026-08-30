from __future__ import annotations

import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlsplit

from tools import wechat_sogou_redirect_compat as compat
from tools import wechat_sogou_index


class WeChatSogouRedirectCompatTests(unittest.TestCase):
    def assertSignedTimestamp(self, resolved: str) -> None:  # noqa: N802
        query = parse_qs(urlsplit(resolved).query, keep_blank_values=True)
        self.assertEqual(query["src"], ["11"])
        self.assertEqual(query["timestamp"], ["1788018564"])
        self.assertEqual(query["ver"], ["6934"])
        self.assertEqual(query["signature"], ["a*b"])

    def test_escaped_original_url_is_resolved(self) -> None:
        body = (
            r'<script>window.location.href="https:\/\/mp.weixin.qq.com\/s?'
            r'__biz=MzA1&amp;mid=123&amp;idx=1&amp;sn=abc";</script>'
        )
        resolved = compat.resolve_current_redirect(body)
        self.assertTrue(resolved.startswith("https://mp.weixin.qq.com/s?"))
        self.assertIn("&mid=123", resolved)

    def test_location_replace_is_resolved(self) -> None:
        body = (
            '<script>location.replace("https://mp.weixin.qq.com/s/'
            'AbCdEfGhIjKlMn");</script>'
        )
        self.assertEqual(
            compat.resolve_current_redirect(body),
            "https://mp.weixin.qq.com/s/AbCdEfGhIjKlMn",
        )

    def test_meta_refresh_is_resolved(self) -> None:
        body = (
            '<meta http-equiv="refresh" content="0; url='
            'https://mp.weixin.qq.com/s?__biz=abc&amp;mid=1">'
        )
        self.assertEqual(
            compat.resolve_current_redirect(body),
            "https://mp.weixin.qq.com/s?__biz=abc&mid=1",
        )

    def test_non_article_wechat_url_is_rejected(self) -> None:
        body = '<script>location.href="https://mp.weixin.qq.com/mp/profile_ext?action=home"</script>'
        self.assertEqual(compat.resolve_current_redirect(body), "")

    def test_insecure_wechat_url_is_rejected(self) -> None:
        body = '<script>location.href="http://mp.weixin.qq.com/s/insecure"</script>'
        self.assertEqual(compat.resolve_current_redirect(body), "")

    def test_timestamp_artifacts_are_repaired(self) -> None:
        variants = (
            "&timestamp=1788018564",
            "&amp;timestamp=1788018564",
            "&times;tamp=1788018564",
            "×tamp=1788018564",
            "%C3%97tamp%3D1788018564",
        )
        for timestamp in variants:
            with self.subTest(timestamp=timestamp):
                body = (
                    '<script>location.href="https://mp.weixin.qq.com/s?src=11'
                    f'{timestamp}&ver=6934&signature=a%2Ab"</script>'
                )
                self.assertSignedTimestamp(compat.resolve_current_redirect(body))

    def test_reserved_query_escapes_are_preserved(self) -> None:
        expected = (
            "https://mp.weixin.qq.com/s?signature=a%26b%23c"
            "&payload=double%2526encoded&mid=1"
        )
        body = f'<script>location.href="{expected}"</script>'
        self.assertEqual(compat.resolve_current_redirect(body), expected)

    def test_fully_encoded_url_decodes_only_the_outer_layer(self) -> None:
        expected = "https://mp.weixin.qq.com/s?signature=a%26b%23c&mid=1"
        encoded = quote(expected, safe="")
        body = f'<script>location.href="{encoded}"</script>'
        self.assertEqual(compat.resolve_current_redirect(body), expected)

    def test_timestamp_artifact_inside_value_is_not_rewritten(self) -> None:
        expected = (
            "https://mp.weixin.qq.com/s?signature=abc%C3%97tamp%3Ddef&mid=1"
        )
        body = f'<script>location.href="{expected}"</script>'
        self.assertEqual(compat.resolve_current_redirect(body), expected)

    def test_explicit_entity_spellings_are_decoded(self) -> None:
        variants = ("&AMP;", "&#038;", "&#x00026;")
        for separator in variants:
            with self.subTest(separator=separator):
                body = (
                    '<script>location.href="https://mp.weixin.qq.com/s?src=11'
                    f'{separator}timestamp=1788018564&amp;ver=6934'
                    '&amp;signature=a%2Ab"</script>'
                )
                self.assertSignedTimestamp(compat.resolve_current_redirect(body))

    def test_install_falls_back_to_legacy_parser(self) -> None:
        index = SimpleNamespace(resolve_script_url=lambda _body: "https://mp.weixin.qq.com/s/legacy")
        compat.install(index)
        self.assertEqual(index.resolve_script_url("ignored"), "https://mp.weixin.qq.com/s/legacy")

    def test_install_rejects_insecure_legacy_result(self) -> None:
        index = SimpleNamespace(
            resolve_script_url=lambda _body: "http://mp.weixin.qq.com/s/insecure"
        )
        compat.install(index)
        self.assertEqual(index.resolve_script_url("legacy response"), "")

    def test_install_prefers_safe_timestamp_parser(self) -> None:
        index = SimpleNamespace(
            resolve_script_url=lambda _body: "https://mp.weixin.qq.com/s/corrupt",
            _normalized_url=lambda value: value,
        )
        compat.install(index)
        body = (
            '<script>location.href="https://mp.weixin.qq.com/s?src=11'
            '&timestamp=1788018564&ver=6934&signature=a%2Ab"</script>'
        )
        self.assertSignedTimestamp(index.resolve_script_url(body))

    def test_install_preserves_complete_legacy_chunked_url(self) -> None:
        index = SimpleNamespace(
            resolve_script_url=wechat_sogou_index.resolve_script_url,
            _normalized_url=wechat_sogou_index._normalized_url,
        )
        compat.install(index)
        body = """
        <script>
          var url = '';
          url += 'https://mp.weixin.qq.com/s?src=11';
          url += '&timestamp=1788018564';
          url += '&ver=6934';
          url += '&signature=a%2Ab';
        </script>
        """
        resolved = index.resolve_script_url(body)
        self.assertSignedTimestamp(resolved)
        self.assertNotEqual(resolved, "https://mp.weixin.qq.com/s?src=11")

    def test_install_does_not_accept_partial_legacy_chunk(self) -> None:
        index = SimpleNamespace(
            resolve_script_url=lambda _body: "",
            _normalized_url=wechat_sogou_index._normalized_url,
        )
        compat.install(index)
        body = """
        <script>
          var url = '';
          url += 'https://mp.weixin.qq.com/s?src=11';
          url += malformed;
        </script>
        """
        self.assertEqual(index.resolve_script_url(body), "")

    def test_install_repairs_encoded_legacy_timestamp_artifact(self) -> None:
        corrupted = (
            "https://mp.weixin.qq.com/s?src=11%C3%97tamp%3D1788018564"
            "&ver=6934&signature=a%2Ab"
        )
        index = SimpleNamespace(
            resolve_script_url=lambda _body: corrupted,
            _normalized_url=wechat_sogou_index._normalized_url,
        )
        compat.install(index)
        self.assertSignedTimestamp(index.resolve_script_url("legacy response"))


if __name__ == "__main__":
    unittest.main()
