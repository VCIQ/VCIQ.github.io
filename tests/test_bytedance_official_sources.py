from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tools import bytedance_official_sources as target
from tools import crawl_official_companies as official


def spec(slug: str, name: str) -> official.CompanySpec:
    homepage = {
        "bytedance": "https://www.bytedance.com/zh/",
        "doubao": "https://www.doubao.com/about",
        "volcengine": "https://www.volcengine.com/",
    }[slug]
    return official.CompanySpec(
        slug=slug,
        name=name,
        region="中国",
        sector="AI / AGI",
        homepage=homepage,
        news_urls=(homepage,),
        sitemap_urls=(),
        aliases=(),
        entity_aliases=(name,),
        article_url_patterns=(),
        require_entity_match=False,
        max_items=8,
        max_candidate_links=12,
        max_age_days=3650,
        request_timeout=10,
    )


def router_page(loader_data: dict) -> str:
    return (
        "<html><script>window._ROUTER_DATA = "
        + json.dumps({"loaderData": loader_data}, ensure_ascii=False)
        + ";</script></html>"
    )


class ByteDanceOfficialSourcesTests(unittest.TestCase):
    def test_parse_bytedance_public_article_api(self) -> None:
        body = json.dumps(
            {
                "statusCode": 0,
                "data": {
                    "data": [
                        {
                            "_id": "article-1",
                            "published": 1752969600000,
                            "title": "字节跳动发布企业社会责任报告",
                            "abstract": "报告披露年度社会责任实践。",
                        }
                    ],
                    "total": 1,
                },
            },
            ensure_ascii=False,
        )

        articles = target.parse_bytedance_payload(
            body, spec("bytedance", "字节跳动"), official
        )

        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article["sourceId"], "official-bytedance")
        self.assertEqual(article["companySlug"], "bytedance")
        self.assertEqual(article["source"]["platform"], "字节跳动官网")
        self.assertEqual(
            article["source"]["url"],
            "https://www.bytedance.com/zh/news/article-1",
        )

    def test_parse_doubao_seed_router_data(self) -> None:
        body = router_page(
            {
                "(locale$)/blog/page": {
                    "article_list": [
                        {
                            "ArticleMeta": {
                                "PublishDate": 1752969600000,
                                "ResearchArea": [
                                    {"ResearchAreaNameZh": "模型发布"}
                                ],
                            },
                            "ArticleSubContentZh": {
                                "Title": "豆包 Seed 新模型发布",
                                "Abstract": "面向多模态理解与生成。",
                                "TitleKey": "豆包-seed-新模型发布",
                            },
                        }
                    ]
                }
            }
        )

        articles = target.parse_doubao_seed_page(
            body, spec("doubao", "豆包"), official
        )

        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article["type"], "产品发布")
        self.assertEqual(article["source"]["platform"], "豆包 Seed")
        self.assertTrue(
            article["source"]["url"].startswith(
                "https://seed.bytedance.com/zh/blog/"
            )
        )

    def test_parse_volcengine_router_data_and_deduplicate_banner(self) -> None:
        body = router_page(
            {
                "__ssr_without_user/news/page": {
                    "banner": [
                        {
                            "title": "火山引擎方舟发布新能力",
                            "category": "产品迭代",
                            "tag": "机器学习",
                            "date": "2025-10-16",
                            "link": "https://www.volcengine.com/news/detail/23",
                        }
                    ],
                    "listOnlineArticle": {
                        "List": [
                            {
                                "DocumentID": 23,
                                "Title": "火山引擎方舟发布新能力",
                                "VersionTitle": "火山引擎方舟发布新能力",
                                "CreatedTime": "2025-10-16T09:00:00+08:00",
                                "TagName": "产品迭代",
                                "CategoryCodeName": "机器学习",
                            },
                            {
                                "DocumentID": 24,
                                "Title": "豆包大模型服务升级",
                                "CreatedTime": "2025-10-17T09:00:00+08:00",
                                "TagName": "新功能",
                                "CategoryCodeName": "机器学习",
                            },
                        ]
                    },
                }
            }
        )

        articles = target.parse_volcengine_page(
            body, spec("volcengine", "火山引擎"), official
        )

        self.assertEqual(len(articles), 2)
        self.assertEqual(target._structured_record_count("volcengine", body), 3)
        self.assertEqual(
            {article["source"]["url"] for article in articles},
            {
                "https://www.volcengine.com/news/detail/23",
                "https://www.volcengine.com/news/detail/24",
            },
        )
        self.assertTrue(
            all(
                article["source"]["platform"] == "火山引擎发布中心"
                for article in articles
            )
        )

    def test_status_keeps_transport_requests_separate_from_record_scan_counts(self) -> None:
        status = target._status(
            spec("volcengine", "火山引擎"),
            accepted=8,
            scanned=1,
            failed=0,
            platform="火山引擎发布中心",
            transport_requests=1,
        )

        self.assertEqual(status["accepted"], 8)
        self.assertEqual(status["scanned"], 8)
        self.assertEqual(status["transportRequests"], 1)
        self.assertLessEqual(status["accepted"], status["scanned"])

    def test_install_routes_only_supported_slugs(self) -> None:
        original = Mock(return_value=([{"id": "generic"}], {"status": "ok"}))
        original._bytedance_structured_sources = False
        module = SimpleNamespace(crawl_company=original)
        structured = Mock(return_value=([{"id": "structured"}], {"status": "ok"}))

        target.install(module)
        with unittest.mock.patch.object(
            target, "crawl_structured_company", structured
        ):
            supported = module.crawl_company(spec("doubao", "豆包"), "ua")
            generic_spec = spec("bytedance", "字节跳动")
            object.__setattr__(generic_spec, "slug", "other")
            generic = module.crawl_company(generic_spec, "ua")

        self.assertEqual(supported[0][0]["id"], "structured")
        self.assertEqual(generic[0][0]["id"], "generic")
        structured.assert_called_once()
        original.assert_called_once()


if __name__ == "__main__":
    unittest.main()
