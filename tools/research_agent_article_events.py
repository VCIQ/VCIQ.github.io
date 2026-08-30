#!/usr/bin/env python3
"""Bridge validated public intelligence events into Research Agent.

The public article snapshot is already protected by the crawler publication and
quality gates. Research Agent historically ignored that event stream and only
compared entity/profile snapshots, so a day with many new articles could still
produce ``externalCandidates=0`` when profile fields did not change.

This policy adds a bounded, event-level view of ``public/data/articles.json`` to
the stable Research Agent snapshot. It deliberately keeps the existing Research
Agent evidence gate in charge of final eligibility: this module selects recent
high-value, already-published events and preserves their source metadata, but it
does not weaken evidence validation or invent missing evidence grades.
"""

from __future__ import annotations

import copy
import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DATASET = "intelligenceEvent"
DATASET_LABEL = "高价值情报事件"
MIN_IMPORTANCE = 80
EVENT_WINDOW_DAYS = 7
MAX_EVENT_ROWS = 160
MAX_EVENT_SOURCES = 4

TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "spm",
}
LOW_TRUST_STATUSES = {"低可信", "low", "rejected", "invalid"}
UNUSABLE_EVIDENCE_GRADES = {
    "",
    "未分级",
    "unknown",
    "ungraded",
    "none",
    "n/a",
}
RESEARCH_EVENT_TYPES = {
    "融资",
    "产业投资",
    "产品发布",
    "技术突破",
    "商业进展",
    "公司动态",
    "并购",
    "财报",
    "政策",
    "监管文件",
    "IPO",
    "论文",
    "人物观点",
}

_AGENT: Any = None
_ORIGINAL_LOAD_INPUT_PAYLOADS: Any = None
_ORIGINAL_BUILD_SNAPSHOT: Any = None
_ORIGINAL_BUILD_SNAPSHOT_FROM_GIT: Any = None
_ORIGINAL_DIFF_SNAPSHOTS: Any = None
_ORIGINAL_GENERATE_REPORT: Any = None
_INSTALLED_AGENT_ID: int | None = None
_BOOTSTRAP_EVENT_ROWS: dict[str, dict[str, Any]] | None = None


class ArticleAwarePayloads:
    """Proxy the core InputPayloads object while carrying article metadata."""

    def __init__(self, base: Any, articles: Mapping[str, Any]) -> None:
        self._base = base
        self.articles = articles

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_url(value: Any) -> str:
    text = _clean(value)
    if not text.startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMETERS
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), path, query, "")
    )


def _normalized_title(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", _clean(value).casefold())


def _source(article: Mapping[str, Any]) -> Mapping[str, Any]:
    value = article.get("source")
    return value if isinstance(value, Mapping) else {}


def _source_role(article: Mapping[str, Any]) -> str:
    source = _source(article)
    return _clean(source.get("sourceRole") or article.get("sourceRole")).casefold()


def _evidence_grade(article: Mapping[str, Any]) -> str:
    source = _source(article)
    explicit = _clean(
        source.get("evidenceGrade")
        or source.get("level")
        or article.get("evidenceGrade")
    )
    if explicit:
        return explicit
    role = _source_role(article)
    if role == "primary":
        return "原始材料"
    if role == "corroboration":
        return "媒体报道"
    return "未分级"


def _article_url(article: Mapping[str, Any]) -> str:
    source = _source(article)
    return _canonical_url(article.get("url") or source.get("url"))


def _article_key(article: Mapping[str, Any]) -> str:
    cluster_id = _clean(article.get("eventClusterId"))
    if cluster_id:
        return f"cluster:{cluster_id.casefold()}"
    url = _article_url(article)
    if url:
        return f"url:{url}"
    title = _normalized_title(article.get("title"))
    published = _clean(article.get("publishedAt"))[:10]
    company = _normalized_title(article.get("company"))
    event_type = _clean(article.get("type"))
    return f"title:{published}:{event_type}:{company}:{title}"


def _representative_score(article: Mapping[str, Any]) -> tuple[Any, ...]:
    role_score = {"primary": 3, "corroboration": 2, "discovery": 1}.get(
        _source_role(article), 0
    )
    quality_status = _clean(article.get("qualityStatus"))
    quality_score = {"高可信": 3, "中可信": 2, "待交叉验证": 1}.get(
        quality_status, 0
    )
    return (
        role_score,
        quality_score,
        _as_int(article.get("qualityScore")),
        _as_int(article.get("importance")),
        _clean(article.get("publishedAt")),
        _article_url(article),
        _clean(article.get("title")),
    )


def _eligible_article(article: Mapping[str, Any], generated_at: str) -> bool:
    if _as_int(article.get("importance")) < MIN_IMPORTANCE:
        return False
    if _clean(article.get("qualityStatus")).casefold() in LOW_TRUST_STATUSES:
        return False
    if _clean(article.get("type")) not in RESEARCH_EVENT_TYPES:
        return False
    if not _clean(article.get("title")) or not _article_url(article):
        return False
    published = _parse_datetime(article.get("publishedAt"))
    generated = _parse_datetime(generated_at)
    if published is None or generated is None:
        return False
    earliest_date = generated.date() - timedelta(days=EVENT_WINDOW_DAYS - 1)
    return earliest_date <= published.date() <= generated.date()


def _source_row(article: Mapping[str, Any]) -> dict[str, Any]:
    source = _source(article)

    def explicit_text(*keys: str) -> str:
        for key in keys:
            value = source.get(key)
            if isinstance(value, Mapping):
                value = value.get("name") or value.get("publisher")
            text = _clean(value)
            if text:
                return text
        return ""

    row = {
        "name": _clean(
            source.get("name")
            or source.get("publisher")
            or article.get("sourceName")
            or article.get("company")
            or "原始信源"
        ),
        # The article URL, not a publisher homepage, is the evidence locator.
        "url": _article_url(article),
        "title": _clean(article.get("title")),
        "publishedAt": _clean(article.get("publishedAt")),
        "level": _evidence_grade(article),
        "sourceRole": _source_role(article),
        # Bind the source to the factual event summary under the existing field
        # evidence contract. Other fields remain context, not separate claims.
        "section": "summary",
    }
    explicit_fields = {
        "publisherName": explicit_text("publisherName", "publisher"),
        "originalPublisherName": explicit_text(
            "originalPublisherName", "originalPublisher"
        ),
        "platformName": explicit_text(
            "platformName", "platform", "hostPlatform"
        ),
        "sourceType": explicit_text("sourceType"),
    }
    row.update(
        {key: value for key, value in explicit_fields.items() if value}
    )
    return row


def _event_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:18]
    return f"intelligence-event-{digest}"


def build_event_rows(
    payload: Mapping[str, Any], generated_at: str
) -> dict[str, dict[str, Any]]:
    """Return a bounded, event-deduplicated view of the committed article stream."""

    gate = payload.get("qualityGate")
    if not isinstance(gate, Mapping) or gate.get("passed") is not True:
        return {}
    raw_articles = payload.get("articles")
    if not isinstance(raw_articles, list):
        return {}

    groups: dict[str, list[Mapping[str, Any]]] = {}
    for value in raw_articles:
        if not isinstance(value, Mapping) or not _eligible_article(value, generated_at):
            continue
        groups.setdefault(_article_key(value), []).append(value)

    ranked_groups = sorted(
        groups.items(),
        key=lambda item: max(_representative_score(row) for row in item[1]),
        reverse=True,
    )[:MAX_EVENT_ROWS]

    result: dict[str, dict[str, Any]] = {}
    for key, rows in ranked_groups:
        representative = max(rows, key=_representative_score)
        source_rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for article in sorted(rows, key=_representative_score, reverse=True):
            source_row = _source_row(article)
            url = source_row["url"]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            source_rows.append(source_row)
            if len(source_rows) >= MAX_EVENT_SOURCES:
                break
        if not source_rows:
            continue

        mentioned_companies = representative.get("mentionedCompanies")
        mentioned_people = representative.get("mentionedPeople")
        record = {
            "title": _clean(representative.get("title")),
            "summary": _clean(
                representative.get("summary") or representative.get("title")
            )[:1200],
            "type": _clean(representative.get("type")),
            "publishedAt": _clean(representative.get("publishedAt")),
            "company": _clean(representative.get("company")),
            "companySlug": _clean(representative.get("companySlug")),
            "sector": _clean(representative.get("sector")),
            "region": _clean(representative.get("region")),
            "mentionedCompanies": [
                _clean(value)
                for value in mentioned_companies[:12]
                if _clean(value)
            ]
            if isinstance(mentioned_companies, list)
            else [],
            "mentionedPeople": [
                _clean(value) for value in mentioned_people[:12] if _clean(value)
            ]
            if isinstance(mentioned_people, list)
            else [],
            "importance": max(_as_int(row.get("importance")) for row in rows),
            "qualityScore": max(_as_int(row.get("qualityScore")) for row in rows),
            "qualityStatus": _clean(representative.get("qualityStatus")),
            "eventClusterId": _clean(representative.get("eventClusterId")),
            "sources": source_rows,
        }
        # Remove empty optional values so stable hashing is not affected by
        # absent-vs-empty representation differences.
        compact = {
            field: value
            for field, value in record.items()
            if value not in (None, "", [], {})
        }
        result[_event_id(key)] = compact
    return result


def _with_event_dataset(
    snapshot: Mapping[str, Any], article_payload: Mapping[str, Any], generated_at: str
) -> dict[str, Any]:
    value = copy.deepcopy(dict(snapshot))
    datasets = value.get("datasets")
    datasets = copy.deepcopy(datasets) if isinstance(datasets, Mapping) else {}
    datasets[DATASET] = build_event_rows(article_payload, generated_at)
    value["datasets"] = datasets
    value["stats"] = {
        str(name): len(rows) if isinstance(rows, Mapping) else 0
        for name, rows in datasets.items()
    }
    value["contentHash"] = _AGENT.stable_hash(datasets)
    return value


def load_input_payloads(root: Path) -> ArticleAwarePayloads:
    base = _ORIGINAL_LOAD_INPUT_PAYLOADS(root)
    articles = _AGENT.load_json(
        root / "public" / "data" / "articles.json", required=False
    )
    return ArticleAwarePayloads(base, articles)


def build_snapshot(payloads: Any, generated_at: str) -> dict[str, Any]:
    snapshot = _ORIGINAL_BUILD_SNAPSHOT(payloads, generated_at)
    articles = getattr(payloads, "articles", {})
    if not isinstance(articles, Mapping):
        articles = {}
    return _with_event_dataset(snapshot, articles, generated_at)


def build_snapshot_from_git(
    root: Path, git_ref: str, generated_at: str
) -> dict[str, Any]:
    snapshot = _ORIGINAL_BUILD_SNAPSHOT_FROM_GIT(root, git_ref, generated_at)
    try:
        articles = _AGENT._git_json(
            root, git_ref, "public/data/articles.json"
        )
    except (RuntimeError, ValueError, FileNotFoundError):
        articles = {}
    return _with_event_dataset(snapshot, articles, generated_at)


def _effective_previous_snapshot(previous: Mapping[str, Any]) -> Mapping[str, Any]:
    datasets = previous.get("datasets")
    if (
        _BOOTSTRAP_EVENT_ROWS is None
        or not isinstance(datasets, Mapping)
        or DATASET in datasets
    ):
        return previous
    value = copy.deepcopy(dict(previous))
    copied_datasets = copy.deepcopy(dict(datasets))
    copied_datasets[DATASET] = copy.deepcopy(_BOOTSTRAP_EVENT_ROWS)
    value["datasets"] = copied_datasets
    return value


def _normalize_event_changes(changes: list[dict[str, Any]]) -> None:
    for change in changes:
        if change.get("dataset") != DATASET:
            continue
        record = change.get("record")
        if isinstance(record, Mapping):
            change["importance"] = max(
                MIN_IMPORTANCE, _as_int(record.get("importance"), MIN_IMPORTANCE)
            )
        if change.get("action") == "added":
            change["changeType"] = "external_event"
            change["classificationReason"] = (
                "公开文章快照已通过质量门，高价值事件完成事件级去重"
            )
            change["isResearchCandidate"] = True
        else:
            change["changeType"] = "data_maintenance"
            change["classificationReason"] = "既有情报事件的来源或元数据更新"
            change["isResearchCandidate"] = False


def diff_snapshots(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> list[dict[str, Any]]:
    changes = _ORIGINAL_DIFF_SNAPSHOTS(
        _effective_previous_snapshot(previous), current
    )
    _normalize_event_changes(changes)
    changes.sort(
        key=lambda item: (
            item.get("changeType") == "external_event",
            _as_int(item.get("importance")),
            str(item.get("dataset", "")),
            str(item.get("entityName", "")),
        ),
        reverse=True,
    )
    return changes


def normalize_report_summary(report: dict[str, Any]) -> None:
    """Distinguish zero candidates from candidates rejected by evidence quality."""

    change_summary = report.get("changeSummary")
    analysis = report.get("analysis")
    if not isinstance(change_summary, Mapping) or not isinstance(analysis, dict):
        return
    external_candidates = _as_int(change_summary.get("externalCandidates"))
    quality_rejected = _as_int(change_summary.get("qualityRejected"))
    visible_changes = _as_int(change_summary.get("total"))

    replacement = ""
    if external_candidates == 0:
        replacement = "本轮未检测到新的外部事实候选。"
    elif quality_rejected >= external_candidates and visible_changes == 0:
        replacement = (
            f"本轮检测到 {external_candidates} 个外部事实候选，"
            "但全部未通过证据质量门。"
        )
    if not replacement:
        return

    analysis["executiveSummary"] = replacement
    history = report.get("history")
    if isinstance(history, list) and history:
        current_generated_at = str(report.get("generatedAt") or "")
        for row in reversed(history):
            if not isinstance(row, dict):
                continue
            if str(row.get("generatedAt") or "") == current_generated_at:
                row["executiveSummary"] = replacement
                break


def generate_report(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    global _BOOTSTRAP_EVENT_ROWS
    now = kwargs.get("now")
    root_value = kwargs.get("root")
    bootstrap_git_ref = str(kwargs.get("bootstrap_git_ref") or "HEAD^")
    generated_at = _AGENT.isoformat(now) if isinstance(now, datetime) else ""
    baseline: dict[str, dict[str, Any]] | None = None
    if generated_at and root_value is not None:
        try:
            article_payload = _AGENT._git_json(
                Path(root_value), bootstrap_git_ref, "public/data/articles.json"
            )
            baseline = build_event_rows(article_payload, generated_at)
        except (RuntimeError, ValueError, FileNotFoundError):
            baseline = {}
    _BOOTSTRAP_EVENT_ROWS = baseline
    try:
        report, snapshot = _ORIGINAL_GENERATE_REPORT(*args, **kwargs)
    finally:
        _BOOTSTRAP_EVENT_ROWS = None
    normalize_report_summary(report)
    return report, snapshot


def install_article_event_policy(agent: Any) -> None:
    """Install article-event snapshot and report hooks exactly once."""

    global _AGENT, _ORIGINAL_LOAD_INPUT_PAYLOADS, _ORIGINAL_BUILD_SNAPSHOT
    global _ORIGINAL_BUILD_SNAPSHOT_FROM_GIT, _ORIGINAL_DIFF_SNAPSHOTS
    global _ORIGINAL_GENERATE_REPORT, _INSTALLED_AGENT_ID

    if _INSTALLED_AGENT_ID == id(agent):
        return
    _AGENT = agent
    _ORIGINAL_LOAD_INPUT_PAYLOADS = agent.load_input_payloads
    _ORIGINAL_BUILD_SNAPSHOT = agent.build_snapshot
    _ORIGINAL_BUILD_SNAPSHOT_FROM_GIT = agent.build_snapshot_from_git
    _ORIGINAL_DIFF_SNAPSHOTS = agent.diff_snapshots
    _ORIGINAL_GENERATE_REPORT = agent.generate_report

    # Reuse the core event semantics so removals caused by the rolling event
    # window are ignored and added events bind their dated evidence fields.
    agent.EVENT_DATASETS.add(DATASET)
    agent.ENTITY_LABELS[DATASET] = DATASET_LABEL
    agent.load_input_payloads = load_input_payloads
    agent.build_snapshot = build_snapshot
    agent.build_snapshot_from_git = build_snapshot_from_git
    agent.diff_snapshots = diff_snapshots
    agent.generate_report = generate_report
    _INSTALLED_AGENT_ID = id(agent)
