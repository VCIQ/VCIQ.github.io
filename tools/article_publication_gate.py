"""Publication gate for low-authority discovery sources.

Collection and publication are separate privileges.  Discovery sources may scan
broadly, but their rows enter the committed public snapshot only when they carry
a concrete entity, a concrete event and strong relevance, or when an independent
primary/corroborating source confirms the same entity/event in the same window.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable
from urllib.parse import urlsplit


VALID_SOURCE_ROLES = {"primary", "corroboration", "discovery"}
EXPLICIT_EVENT_TYPES = {
    "融资",
    "产业投资",
    "产品发布",
    "技术突破",
    "商业进展",
    "并购",
    "财报",
    "政策",
    "监管文件",
    "IPO",
    "论文",
}
GENERIC_COMPANIES = {
    "",
    "科技产业",
    "持续更新",
    "未识别",
    "未分类",
    "unknown",
    "公司",
    "行业",
    "产业",
    "资本动态",
}

# ``融资`` is also used for debt facilities, margin trading, fund raising and
# forward-looking plans.  Those topic mentions must not become claims that a
# company completed an equity/venture financing round.
_FINANCING_EXCLUSIONS = (
    r"\b(?:debt financing|debt facility|credit facility|loan financing|bond financing|venture debt|term loan)\b",
    r"\b(?:financing|funding)\s+(?:plan|plans|proposal|strategy|options?|needs?|costs?|environment|cuts?)\b",
    r"\b(?:plans?|planning|considers?|considering|seeks?|seeking|aims?|targeting|eyes?|explores?|exploring|may|might|could|expected)\b.{0,32}\b(?:raise|raising|funding|financing|round)\b",
    r"\b(?:abandons?|cancels?|drops?|shelves?|pauses?)\b.{0,28}\b(?:raise|raising|funding|financing|round)\b",
    r"\braises?\b.{0,36}\bacross\b.{0,20}\bfunds?\b",
    r"\b(?:raises?|closes?|launches?)\b.{0,36}\b(?:venture|investment|buyout|growth)\s+funds?\b",
    r"\b(?:grant funding|research grant|government grant)\b",
    r"\braises?\s+(?:concerns?|questions?|doubts?)\b",
    r"\b(?:not|no|never|without|has not|hasn't)\b.{0,24}\b(?:raised|secured|closed|completed)\b.{0,24}\b(?:funding|financing|round)\b",
    r"(?:债务融资|贷款融资|信贷融资|债券融资|发债融资|融资租赁|银行授信)",
    r"(?:融资客|融资融券|融资余额|融资买入|融资偿还|保证金交易)",
    r"(?:融资计划|融资方案|融资安排|融资需求|融资渠道|融资成本|融资环境|融资协议)",
    r"(?:拟|计划|考虑|寻求|探索|可能|或将|有望|意向|筹备).{0,16}(?:融资|募资|筹资)",
    r"(?:放弃|取消|终止|搁置|暂停).{0,16}(?:融资|募资|筹资)",
    r"(?:尚未|未能|没有).{0,16}(?:完成|获得|获).{0,12}(?:融资|募资)",
    r"(?:基金|创投|资本).{0,16}(?:完成|宣布|启动|计划).{0,12}(?:募资|募集)",
    r"(?:基金).{0,12}(?:募资|募集).{0,8}(?:完成|计划|目标)",
)
_FINANCING_POSITIVE = (
    r"\b(?:raises?|raised)\b.{0,44}(?:\$|€|£|¥|\busd\b|\beur\b|\brmb\b|\bfunding\b|\bfinancing\b|\bseries\b|\bseed\b|\bround\b|\bmillion\b|\bbillion\b)",
    r"\b(?:secures?|secured|closes?|closed|lands?|landed|nabs?|nabbed|bags?|bagged|gets?|got|receives?|received|completes?|completed)\b.{0,44}(?:\bfunding\b|\bfinancing\b|\bseries\s+[a-z]|\bpre-?seed\b|\bseed\b|\bround\b)",
    r"\bannounc(?:e|es|ed)\b.{0,36}(?:\$|€|£|¥|\busd\b|\beur\b|\brmb\b|\bfunding\b|\bfinancing\b|\bseries\s+[a-z]|\bpre-?seed\b|\bseed\b|\bround\b)",
    r"\bemerges?\s+from\s+stealth\s+with\b.{0,36}(?:\$|€|£|¥|\bfunding\b|\bfinancing\b|\bseries\b|\bseed\b)",
    r"(?:\$|€|£|¥)\s?\d[\d,.]*\s*(?:m|bn|million|billion)?\b.{0,24}\b(?:series\s+[a-z](?:\+)?|pre-?[a-z]|pre-?seed|seed\s+round)\b",
    r"(?:完成|获得|获|拿下|宣布|成功完成|募集到|募得|再获).{0,24}(?:融资|天使轮|种子轮|pre-?[a-z]\+?轮|[a-z]\+?轮)",
    r"(?:融资|天使轮|种子轮|pre-?[a-z]\+?轮|[a-z]\+?轮).{0,12}(?:完成|交割|到账)",
    r"(?:天使轮|种子轮|pre-?[a-z]\+?轮|[a-z]\+?轮)融资.{0,10}(?:超|达|近|逾|数|亿元|万元|美元|人民币|\d)",
    r"(?:领投|跟投).{0,12}(?:天使|种子|pre-?[a-z]|[a-z]\+?轮)",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: Any) -> str:
    return _clean(value).casefold()


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def financing_event_supported(title: Any, summary: Any = "") -> bool:
    """Return whether text states a completed company financing event."""

    title_text = _fold(title)
    combined = _fold(f"{title} {summary}")
    if not title_text:
        return False
    if _matches_any(title_text, _FINANCING_EXCLUSIONS):
        return False
    if _matches_any(title_text, _FINANCING_POSITIVE):
        return True
    if _matches_any(combined, _FINANCING_EXCLUSIONS):
        return False
    return _matches_any(combined, _FINANCING_POSITIVE)


def _source(article: dict[str, Any]) -> dict[str, Any]:
    value = article.get("source")
    return value if isinstance(value, dict) else {}


def _role(article: dict[str, Any]) -> str:
    source = _source(article)
    explicit = _fold(source.get("sourceRole") or article.get("sourceRole"))
    if explicit in VALID_SOURCE_ROLES:
        return explicit
    grade = _clean(source.get("evidenceGrade")).upper()
    if grade in {"A", "B"}:
        return "primary"
    if grade == "C":
        return "corroboration"
    return "discovery"


def _source_identity(article: dict[str, Any]) -> tuple[str, str]:
    source = _source(article)
    source_id = _fold(article.get("sourceId"))
    try:
        host = (urlsplit(_clean(source.get("url"))).hostname or "").casefold()
    except ValueError:
        host = ""
    return source_id, host


def _entity_keys(article: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    company_slug = _fold(article.get("companySlug"))
    person_slug = _fold(article.get("personSlug"))
    if company_slug:
        keys.add(f"company-slug:{company_slug}")
    if person_slug:
        keys.add(f"person-slug:{person_slug}")

    company = _clean(article.get("company"))
    if _fold(company) not in GENERIC_COMPANIES:
        keys.add(f"company:{_fold(company)}")

    for field, prefix in (
        ("mentionedCompanies", "company"),
        ("mentionedPeople", "person"),
    ):
        values = article.get(field)
        if not isinstance(values, list):
            continue
        for value in values[:12]:
            normalized = _fold(value)
            if normalized and normalized not in GENERIC_COMPANIES:
                keys.add(f"{prefix}:{normalized}")
    return keys


def _published_day(article: dict[str, Any]) -> int | None:
    raw = _clean(article.get("publishedAt"))[:10]
    try:
        return date.fromisoformat(raw).toordinal()
    except ValueError:
        return None


def _explicit_event(article: dict[str, Any]) -> bool:
    event_type = _clean(article.get("type"))
    if event_type not in EXPLICIT_EVENT_TYPES:
        return False
    if event_type == "融资":
        return financing_event_supported(
            article.get("title"), article.get("summary")
        )
    return True


def _title_mentions_entity(article: dict[str, Any]) -> bool:
    """Require a literal entity cue in the title, not merely a resolved slug.

    Entity resolution is valuable for joining records, but allowing a formal slug
    alone to satisfy relevance would let a broad search result self-authorize its
    own publication.  Discovery-tier material therefore needs the company/person
    name in the title unless an independent stronger source corroborates it.
    """

    title = _fold(article.get("title"))
    if not title:
        return False
    company = _fold(article.get("company"))
    if company and company not in GENERIC_COMPANIES and company in title:
        return True
    for field in ("mentionedCompanies", "mentionedPeople"):
        values = article.get(field)
        if not isinstance(values, list):
            continue
        if any(_fold(value) and _fold(value) in title for value in values[:12]):
            return True
    return False


def _strong_relevance(article: dict[str, Any]) -> bool:
    try:
        score = int(article.get("qualityScore", -1))
    except (TypeError, ValueError):
        score = -1
    if score >= 45:
        return True
    return _explicit_event(article) and _title_mentions_entity(article)


def _independent(
    left: dict[str, Any], right: dict[str, Any]
) -> bool:
    left_id, left_host = _source_identity(left)
    right_id, right_host = _source_identity(right)
    if left_id and right_id and left_id == right_id:
        return False
    if left_host and right_host and left_host == right_host:
        return False
    return True


def _same_event(
    discovery: dict[str, Any], stronger: dict[str, Any]
) -> bool:
    if _clean(discovery.get("type")) == "融资" and not (
        financing_event_supported(
            discovery.get("title"), discovery.get("summary")
        )
        and financing_event_supported(
            stronger.get("title"), stronger.get("summary")
        )
    ):
        return False
    left_cluster = _fold(discovery.get("eventClusterId"))
    right_cluster = _fold(stronger.get("eventClusterId"))
    if left_cluster and right_cluster and left_cluster == right_cluster:
        return _independent(discovery, stronger)
    if _clean(discovery.get("type")) != _clean(stronger.get("type")):
        return False
    if not (_entity_keys(discovery) & _entity_keys(stronger)):
        return False
    left_day = _published_day(discovery)
    right_day = _published_day(stronger)
    if left_day is not None and right_day is not None and abs(left_day - right_day) > 3:
        return False
    return _independent(discovery, stronger)


def _corroborated(
    article: dict[str, Any], stronger_articles: Iterable[dict[str, Any]]
) -> bool:
    return any(_same_event(article, stronger) for stronger in stronger_articles)


def filter_publishable_articles(
    articles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stronger = [article for article in articles if _role(article) != "discovery"]
    published: list[dict[str, Any]] = []
    report = {
        "total": len(articles),
        "primary": 0,
        "corroboration": 0,
        "discoverySeen": 0,
        "discoveryPublished": 0,
        "discoveryHeld": 0,
    }

    for article in articles:
        role = _role(article)
        if role == "primary":
            report["primary"] += 1
            published.append(article)
            continue
        if role == "corroboration":
            report["corroboration"] += 1
            published.append(article)
            continue

        report["discoverySeen"] += 1
        has_entity = bool(_entity_keys(article))
        has_event = _explicit_event(article)
        allowed = has_entity and has_event and (
            _strong_relevance(article) or _corroborated(article, stronger)
        )
        if allowed:
            report["discoveryPublished"] += 1
            published.append(article)
        else:
            report["discoveryHeld"] += 1

    return published, report
