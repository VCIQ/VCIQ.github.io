#!/usr/bin/env python3
"""Generate deterministic record-level samples for manual source-quality review.

The existing ``source_quality_reviews.json`` manifest intentionally stores only
aggregate human judgements.  This queue supplies the missing traceability layer:
exact article/disclosure records that a reviewer can inspect before writing the
aggregate counts back to the existing manifest.

Sampling is deliberately conservative.  Normal articles are matched only by an
exact runtime ``sourceId``.  Regulatory disclosures are matched only by hosts
explicitly configured for the corresponding ``regulatory:<id>`` entity.  No
fuzzy source-name matching is used because that would contaminate a
misattribution audit with another source of inferred attribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

try:
    from .source_quality_reviews import load_review_manifest, review_index
except ImportError:
    from source_quality_reviews import load_review_manifest, review_index

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "public" / "data" / "source_health.json"
DEFAULT_ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
DEFAULT_DISCLOSURES_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
DEFAULT_REVIEWS_PATH = ROOT / "config" / "source_quality_reviews.json"
DEFAULT_DISCLOSURE_CONFIG_PATH = ROOT / "config" / "listed_company_disclosure_sources.json"
DEFAULT_JSON_PATH = ROOT / "public" / "data" / "source_quality_review_queue.json"
DEFAULT_MARKDOWN_PATH = ROOT / "docs" / "source-quality-review-queue.md"
DEFAULT_TARGET_RECORDS = 20
DEFAULT_SAMPLE_LIMIT = 20


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").split())[:limit]


def _host(value: Any) -> str:
    try:
        return (urlsplit(str(value or "")).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _matches_host(host: str, configured_host: str) -> bool:
    candidate = configured_host.casefold().strip().removeprefix("www.")
    return bool(candidate) and (host == candidate or host.endswith(f".{candidate}"))


def _source_url(record: dict[str, Any]) -> str:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    return _text(source.get("url"), 2400)


def _source_name(record: dict[str, Any]) -> str:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    return _text(source.get("name"), 240)


def _record_id(record: dict[str, Any], *, record_type: str) -> str:
    explicit = _text(record.get("id"), 300)
    if explicit:
        return explicit
    url = _source_url(record)
    if url:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        return f"{record_type}:{digest}"
    return ""


def _article_records(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    articles = payload.get("articles", [])
    articles = articles if isinstance(articles, list) else []
    for raw in articles:
        if not isinstance(raw, dict):
            continue
        source_id = _text(raw.get("sourceId"), 300)
        record_id = _record_id(raw, record_type="article")
        if not source_id or not record_id:
            continue
        row = {
            "recordId": record_id,
            "recordType": "article",
            "sourceId": source_id,
            "title": _text(raw.get("title"), 600),
            "publishedAt": _text(raw.get("publishedAt"), 80),
            "url": _source_url(raw),
            "sourceName": _source_name(raw),
            "companySlug": _text(raw.get("companySlug"), 160),
            "companyName": _text(raw.get("company"), 200),
            "firstSeenAt": _text(raw.get("firstSeenAt"), 80),
        }
        result.setdefault(source_id, []).append(row)
    return result


def _regulatory_host_index(config: dict[str, Any]) -> list[tuple[str, tuple[str, ...]]]:
    official_sources = config.get("officialSources", {})
    official_sources = official_sources if isinstance(official_sources, dict) else {}
    result: list[tuple[str, tuple[str, ...]]] = []
    for source_key, raw in official_sources.items():
        if not isinstance(raw, dict):
            continue
        hosts = raw.get("hosts", [])
        hosts = hosts if isinstance(hosts, list) else []
        normalized = tuple(
            host
            for host in (_host(f"https://{value}") for value in hosts)
            if host
        )
        if normalized:
            result.append((f"regulatory:{source_key}", normalized))
    return result


def _disclosure_records(
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    host_index = _regulatory_host_index(config)
    companies = payload.get("companies", {})
    companies = companies if isinstance(companies, dict) else {}

    for company_slug, company_raw in companies.items():
        if not isinstance(company_raw, dict):
            continue
        events = company_raw.get("events", [])
        events = events if isinstance(events, list) else []
        for raw in events:
            if not isinstance(raw, dict):
                continue
            url = _source_url(raw)
            host = _host(url)
            record_id = _record_id(raw, record_type="regulatory-disclosure")
            if not host or not record_id:
                continue
            matched_ids = [
                source_id
                for source_id, hosts in host_index
                if any(_matches_host(host, configured_host) for configured_host in hosts)
            ]
            # Ambiguous host configuration is safer to omit than to duplicate
            # one record into multiple regulator review samples.
            if len(matched_ids) != 1:
                continue
            source_id = matched_ids[0]
            row = {
                "recordId": record_id,
                "recordType": "regulatory-disclosure",
                "sourceId": source_id,
                "title": _text(raw.get("title"), 600),
                "publishedAt": _text(raw.get("publishedAt"), 80),
                "url": url,
                "sourceName": _source_name(raw),
                "companySlug": _text(raw.get("companySlug") or company_slug, 160),
                "companyName": _text(raw.get("companyName") or company_raw.get("name"), 200),
                "discoveredVia": _text(raw.get("discoveredVia"), 160),
                "fallback": bool(raw.get("fallback")),
            }
            result.setdefault(source_id, []).append(row)
    return result


def _merge_record_indexes(*indexes: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for index in indexes:
        for source_id, rows in index.items():
            result.setdefault(source_id, []).extend(rows)
    return result


def _dedupe_and_sort(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        record_type = _text(row.get("recordType"), 80)
        record_id = _text(row.get("recordId"), 300)
        if record_type and record_id:
            by_key[(record_type, record_id)] = row
    return sorted(
        by_key.values(),
        key=lambda row: (
            _text(row.get("publishedAt"), 80),
            _text(row.get("recordId"), 300),
        ),
        reverse=True,
    )


def _sample_digest(source_id: str, records: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        [source_id]
        + [
            f"{_text(row.get('recordType'), 80)}:{_text(row.get('recordId'), 300)}"
            for row in records
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_queue(
    state: dict[str, Any],
    articles: dict[str, Any],
    disclosures: dict[str, Any],
    manual_reviews: dict[str, dict[str, Any]],
    disclosure_config: dict[str, Any],
    *,
    target_records: int = DEFAULT_TARGET_RECORDS,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> dict[str, Any]:
    target_records = max(1, int(target_records))
    sample_limit = max(1, int(sample_limit))
    sources = state.get("sources", {})
    sources = sources if isinstance(sources, dict) else {}
    records_by_source = _merge_record_indexes(
        _article_records(articles),
        _disclosure_records(disclosures, disclosure_config),
    )
    generated_at = _text(state.get("generatedAt"), 80)
    period = generated_at[:7] if len(generated_at) >= 7 else "unknown"
    rows: list[dict[str, Any]] = []

    for source_id, raw in sources.items():
        if not isinstance(raw, dict):
            continue
        performance = raw.get("performance")
        if not isinstance(performance, dict) or not performance:
            continue
        reviewed = _integer(manual_reviews.get(source_id, {}).get("reviewedRecords"))
        needed = max(0, target_records - reviewed)
        if needed <= 0:
            continue
        available = _dedupe_and_sort(records_by_source.get(source_id, []))
        sample = available[:sample_limit]
        digest = _sample_digest(source_id, sample)
        rows.append(
            {
                "sourceId": source_id,
                "name": _text(raw.get("name") or source_id, 240),
                "platform": _text(raw.get("platform"), 160),
                "evidenceGrade": _text(raw.get("evidenceGrade"), 8),
                "reviewState": _text(performance.get("reviewState") or "insufficient-data", 60),
                "reviewedRecords": reviewed,
                "targetReviewedRecords": target_records,
                "reviewNeeded": needed,
                "availableRecordCount": len(available),
                "sampleCandidateCount": len(sample),
                "sampleDigest": digest,
                "status": "ready" if len(sample) >= needed else "insufficient-records",
                "records": sample,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["status"] == "ready" else 1,
            -int(row["reviewNeeded"]),
            str(row["evidenceGrade"]),
            str(row["name"]).casefold(),
        )
    )
    return {
        "schemaVersion": 1,
        "period": period,
        "generatedAt": generated_at,
        "targetReviewedRecords": target_records,
        "sourceCount": len(rows),
        "readySourceCount": sum(row["status"] == "ready" for row in rows),
        "insufficientRecordSourceCount": sum(
            row["status"] == "insufficient-records" for row in rows
        ),
        "traceabilityNote": (
            "The review manifest stores aggregate counts only. For partial prior reviews, "
            "record-level exclusion cannot be automated; reviewers must avoid known repeats "
            "and copy this queue's sampleDigest into the existing notes field."
        ),
        "sources": rows,
    }


def validate_queue(queue: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if queue.get("schemaVersion") != 1:
        errors.append("invalid schemaVersion")
    sources = queue.get("sources")
    if not isinstance(sources, list):
        return [*errors, "sources must be an array"]
    if _integer(queue.get("sourceCount")) != len(sources):
        errors.append("sourceCount does not match sources")
    seen_sources: set[str] = set()
    for index, raw in enumerate(sources):
        if not isinstance(raw, dict):
            errors.append(f"invalid source row {index}")
            continue
        source_id = _text(raw.get("sourceId"), 300)
        if not source_id:
            errors.append(f"source row {index} is missing sourceId")
        elif source_id in seen_sources:
            errors.append(f"duplicate source row: {source_id}")
        else:
            seen_sources.add(source_id)
        records = raw.get("records")
        if not isinstance(records, list):
            errors.append(f"records must be an array for {source_id or index}")
            continue
        seen_records: set[tuple[str, str]] = set()
        for record in records:
            if not isinstance(record, dict):
                errors.append(f"invalid record for {source_id or index}")
                continue
            key = (
                _text(record.get("recordType"), 80),
                _text(record.get("recordId"), 300),
            )
            if not all(key):
                errors.append(f"record identity missing for {source_id or index}")
            elif key in seen_records:
                errors.append(f"duplicate record for {source_id}: {key[1]}")
            else:
                seen_records.add(key)
            if _text(record.get("sourceId"), 300) != source_id:
                errors.append(f"record sourceId mismatch for {source_id}: {key[1]}")
        expected_digest = _sample_digest(source_id, records) if source_id else ""
        if _text(raw.get("sampleDigest"), 40) != expected_digest:
            errors.append(f"sampleDigest mismatch for {source_id or index}")
    return errors


def render_markdown(queue: dict[str, Any], *, source_limit: int = 100) -> str:
    sources = queue.get("sources", [])
    sources = sources if isinstance(sources, list) else []
    lines = [
        "# 信源人工质量抽样队列",
        "",
        f"周期：`{queue.get('period', '')}`；信源健康快照：`{queue.get('generatedAt', '')}`。",
        "",
        (
            f"目标为每个来源累计 **{queue.get('targetReviewedRecords', 20)}** 条人工审查记录。"
            f"当前有 **{queue.get('readySourceCount', 0)}** 个来源已具备足量候选，"
            f"**{queue.get('insufficientRecordSourceCount', 0)}** 个来源仍缺少可审记录。"
        ),
        "",
        "## 审核规则",
        "",
        "1. 只按本页给出的 record ID 与原始 URL 审核，不用名称相似度自行补归属。",
        "2. 对每个来源最多审核 `reviewNeeded` 条；若已人工审核过某条，不要重复计数。",
        "3. 完成后仍将汇总结果写入现有 `config/source_quality_reviews.json`，不改 schema。",
        "4. 在该 review 的 `notes` 中记录 `sampleDigest=<值>`，以便从 Git 历史追溯本次具体样本。",
        "",
        "| 来源 | 等级 | 已审/目标 | 还需 | 可用记录 | 队列状态 | sampleDigest |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in sources[:source_limit]:
        lines.append(
            "| {name} | {grade} | {reviewed}/{target} | {needed} | {available} | {status} | `{digest}` |".format(
                name=_text(row.get("name") or row.get("sourceId"), 240).replace("|", "\\|"),
                grade=_text(row.get("evidenceGrade"), 8) or "—",
                reviewed=_integer(row.get("reviewedRecords")),
                target=_integer(row.get("targetReviewedRecords")),
                needed=_integer(row.get("reviewNeeded")),
                available=_integer(row.get("availableRecordCount")),
                status="可审核" if row.get("status") == "ready" else "记录不足",
                digest=_text(row.get("sampleDigest"), 40),
            )
        )
    if len(sources) > source_limit:
        lines.extend(["", f"这里只展示前 {source_limit} 个来源；完整队列见 JSON 文件。"])
    lines.append("")

    for row in sources[:source_limit]:
        lines.extend(
            [
                f"## {_text(row.get('name') or row.get('sourceId'), 240)}",
                "",
                f"`sourceId={_text(row.get('sourceId'), 300)}` · "
                f"还需审核 `{_integer(row.get('reviewNeeded'))}` 条 · "
                f"`sampleDigest={_text(row.get('sampleDigest'), 40)}`",
                "",
            ]
        )
        records = row.get("records", [])
        records = records if isinstance(records, list) else []
        if not records:
            lines.extend(["当前没有可追溯的精确匹配记录。", ""])
            continue
        for index, record in enumerate(records, 1):
            title = _text(record.get("title"), 600) or "（无标题）"
            record_type = _text(record.get("recordType"), 80)
            record_id = _text(record.get("recordId"), 300)
            published = _text(record.get("publishedAt"), 80) or "—"
            url = _text(record.get("url"), 2400) or "—"
            company = _text(record.get("companyName") or record.get("companySlug"), 200)
            suffix = f" · {company}" if company else ""
            lines.extend(
                [
                    f"{index}. **{title}**",
                    f"   - `{record_type}` · `{record_id}` · {published}{suffix}",
                    f"   - {url}",
                ]
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--articles", type=Path, default=DEFAULT_ARTICLES_PATH)
    parser.add_argument("--disclosures", type=Path, default=DEFAULT_DISCLOSURES_PATH)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS_PATH)
    parser.add_argument("--disclosure-config", type=Path, default=DEFAULT_DISCLOSURE_CONFIG_PATH)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--target-records", type=int, default=DEFAULT_TARGET_RECORDS)
    parser.add_argument("--sample-limit", type=int, default=DEFAULT_SAMPLE_LIMIT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        queue = _read_json(args.json, {})
        errors = validate_queue(queue if isinstance(queue, dict) else {})
        print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
        return 1 if errors else 0

    state = _read_json(args.state, {})
    articles = _read_json(args.articles, {})
    disclosures = _read_json(args.disclosures, {})
    config = _read_json(args.disclosure_config, {})
    manifest = load_review_manifest(args.reviews)
    queue = build_queue(
        state if isinstance(state, dict) else {},
        articles if isinstance(articles, dict) else {},
        disclosures if isinstance(disclosures, dict) else {},
        review_index(manifest),
        config if isinstance(config, dict) else {},
        target_records=args.target_records,
        sample_limit=args.sample_limit,
    )
    errors = validate_queue(queue)
    if errors:
        raise ValueError("; ".join(errors))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(queue), encoding="utf-8")
    print(
        json.dumps(
            {
                "period": queue["period"],
                "sourceCount": queue["sourceCount"],
                "readySourceCount": queue["readySourceCount"],
                "insufficientRecordSourceCount": queue["insufficientRecordSourceCount"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
