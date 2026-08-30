#!/usr/bin/env python3
"""Strict evidence normalization and observability policy for Research Agent.

This module deliberately does not relax the Research Agent evidence gate. It only
recovers metadata that is already present in well-defined structured source
contexts (currently market quotes and news), then exposes rejection diagnostics
and research-object coverage in the published report.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


QUALITY_ISSUE_LABELS: dict[str, str] = {
    "missing_or_invalid_url": "缺少有效 URL",
    "missing_title": "缺少标题",
    "ungraded": "证据未分级",
    "missing_published_at": "缺少发布时间",
    "future_published_at": "发布时间晚于本轮截止时间",
    "no_external_evidence": "缺少外部证据",
    "discovery_only": "仅为发现线索，不能支持正式主张",
    "entity_mismatch": "标题未直接匹配研究对象",
}

_ORIGINAL_BUILD_EVIDENCE_PACKAGE: Any = None
_ORIGINAL_GENERATE_REPORT: Any = None
_AGENT: Any = None
_LAST_QUALITY_DIAGNOSTICS: dict[str, Any] = {}
_INSTALLED_AGENT_ID: int | None = None


def _source_name(value: Mapping[str, Any]) -> str:
    source = value.get("source")
    if isinstance(source, Mapping):
        source = (
            source.get("name")
            or source.get("publisher")
            or source.get("platform")
            or ""
        )
    return str(
        value.get("name")
        or source
        or value.get("publisher")
        or value.get("platform")
        or "原始信源"
    ).strip()


def _explicit_source_metadata(value: Mapping[str, Any]) -> dict[str, str]:
    """Copy explicit attribution fields without guessing from the page host."""

    def text(*keys: str) -> str:
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, Mapping):
                candidate = candidate.get("name") or candidate.get("publisher")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    fields = {
        "publisherName": text("publisherName", "publisher"),
        "originalPublisherName": text(
            "originalPublisherName", "originalPublisher"
        ),
        "platformName": text("platformName", "platform", "hostPlatform"),
        "sourceType": text("sourceType"),
        "sourceRole": text("sourceRole"),
    }
    return {key: item for key, item in fields.items() if item}


def _context_grade(path: tuple[str, ...], explicit: str, inherited: str) -> str:
    if explicit:
        return explicit
    path_set = set(path)
    # These labels describe the source *type*, not an inferred reliability score.
    # They are only assigned when the repository structure already identifies the
    # row unambiguously as a quote or a dated news item.
    if "quote" in path_set:
        return "市场数据"
    if "news" in path_set:
        return "媒体报道"
    return inherited or "未分级"


def walk_source_candidates(
    value: Any,
    path: tuple[str, ...] = (),
    inherited_title: str = "",
    inherited_date: str = "",
    inherited_grade: str = "",
) -> Iterable[dict[str, Any]]:
    """Yield source rows while inheriting metadata from explicit source context.

    The base implementation already enforces URL/title/grade/date checks. The
    missing piece is that structured market quote sources store their timestamp
    on the parent ``quote.asOf`` object, while news rows identify their source
    class by being inside ``news`` rather than by carrying ``evidenceGrade``.
    """

    if isinstance(value, Mapping):
        title = str(value.get("title") or inherited_title or "").strip()
        published_at = str(
            value.get("publishedAt")
            or value.get("date")
            or value.get("asOf")
            or inherited_date
            or ""
        ).strip()
        explicit_grade = str(
            value.get("evidenceGrade")
            or value.get("level")
            or value.get("evidenceLabel")
            or ""
        ).strip()
        grade = _context_grade(path, explicit_grade, inherited_grade)
        has_url_key = any(
            key in value for key in ("url", "sourceUrl", "originalPdfUrl")
        )
        source_container = any(
            part in {"source", "sources", "evidence"} for part in path
        )
        if has_url_key or source_container:
            raw_url = (
                value.get("url")
                or value.get("sourceUrl")
                or value.get("originalPdfUrl")
                or ""
            )
            source_name = _source_name(value)
            candidate_title = title
            if not candidate_title and "quote" in set(path):
                candidate_title = f"{source_name} 行情数据"
            yield {
                "sourceName": source_name,
                "title": candidate_title,
                "url": str(raw_url).strip(),
                "publishedAt": published_at,
                "evidenceGrade": grade,
                **_explicit_source_metadata(value),
                "_path": list(path),
                "_section": str(value.get("section") or "").strip(),
            }
        for key, item in value.items():
            yield from walk_source_candidates(
                item,
                (*path, str(key)),
                title,
                published_at,
                grade if grade != "未分级" else inherited_grade,
            )
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_source_candidates(
                item,
                (*path, str(index)),
                inherited_title,
                inherited_date,
                inherited_grade,
            )
        return

    if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
        grade = _context_grade(path, "", inherited_grade)
        source_name = "原始信源"
        title = inherited_title
        if not title and "quote" in set(path):
            title = "市场行情数据"
        yield {
            "sourceName": source_name,
            "title": title,
            "url": value.strip(),
            "publishedAt": inherited_date,
            "evidenceGrade": grade,
            "_path": list(path),
            "_section": "",
        }


def _quality_diagnostics(
    public_changes: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    rejected_by_dataset: Counter[str] = Counter()
    supporting = 0
    rejected_evidence = 0
    passed_but_unbound = 0

    for row in evidence:
        if row.get("supportStatus") == "supports":
            supporting += 1
        if row.get("qualityStatus") == "rejected":
            rejected_evidence += 1
            issues = row.get("qualityIssues")
            if isinstance(issues, list):
                reason_counts.update(str(issue) for issue in issues if issue)
        elif (
            row.get("qualityStatus") == "passed"
            and row.get("supportStatus") == "insufficient"
        ):
            passed_but_unbound += 1

    for change in public_changes:
        if change.get("eligibleForKeyDevelopment") is not True:
            rejected_by_dataset[str(change.get("dataset") or "unknown")] += 1

    eligible = sum(
        change.get("eligibleForKeyDevelopment") is True for change in public_changes
    )
    return {
        "candidateCount": len(public_changes),
        "eligibleCandidateCount": eligible,
        "rejectedCandidateCount": len(public_changes) - eligible,
        "rejectedByDataset": dict(sorted(rejected_by_dataset.items())),
        "evidenceCount": len(evidence),
        "supportingEvidenceCount": supporting,
        "rejectedEvidenceCount": rejected_evidence,
        "passedButUnboundEvidenceCount": passed_but_unbound,
        "rejectionReasons": dict(
            sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "sourceClassificationWarnings": _source_classification_warnings(evidence),
    }


def _source_classification_warnings(
    evidence: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Report contradictions in explicit source metadata without filling blanks."""

    warnings: list[dict[str, str]] = []
    for row in evidence:
        source_type = str(row.get("sourceType") or "").strip()
        if not source_type:
            continue
        folded_type = source_type.casefold()
        role = str(row.get("sourceRole") or "").strip().casefold()
        grade = str(row.get("evidenceGrade") or "").strip()
        folded_grade = grade.casefold()
        is_media_type = any(
            marker in folded_type
            for marker in ("media", "news", "publisher", "aggregation")
        )
        is_official_type = any(
            marker in folded_type
            for marker in ("company", "official", "regulatory", "exchange")
        )
        is_official_grade = any(
            marker in folded_grade
            for marker in ("官方", "监管", "交易所", "原始材料", "法定披露")
        )
        is_media_grade = any(
            marker in folded_grade for marker in ("媒体", "新闻聚合", "转载")
        )

        reason = ""
        if is_media_type and (role == "primary" or is_official_grade):
            reason = "media_source_marked_primary"
        elif is_official_type and (
            role in {"corroboration", "discovery"} or is_media_grade
        ):
            reason = "official_source_marked_secondary"
        if not reason:
            continue
        warnings.append(
            {
                "evidenceId": str(row.get("id") or ""),
                "reason": reason,
                "sourceName": str(row.get("sourceName") or ""),
                "sourceType": source_type,
                "sourceRole": str(row.get("sourceRole") or ""),
                "evidenceGrade": grade,
            }
        )
    return warnings


def build_evidence_package(
    changes: list[dict[str, Any]], *, as_of: Any = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    global _LAST_QUALITY_DIAGNOSTICS
    public_changes, evidence = _ORIGINAL_BUILD_EVIDENCE_PACKAGE(
        changes, as_of=as_of
    )
    _LAST_QUALITY_DIAGNOSTICS = _quality_diagnostics(public_changes, evidence)
    return public_changes, evidence


def _scope_entry(
    label: str, *, status: str, count: int | None, note: str
) -> dict[str, Any]:
    return {"label": label, "status": status, "count": count, "note": note}


def _research_scope(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    datasets = snapshot.get("datasets")
    if not isinstance(datasets, Mapping):
        datasets = {}

    def row_count(key: str) -> int:
        rows = datasets.get(key)
        return len(rows) if isinstance(rows, Mapping) else 0

    return {
        "technology": _scope_entry(
            "核心技术",
            status="pending-artifact",
            count=None,
            note="尚未进入 Research Agent 稳定快照；技术频道继续独立发布。",
        ),
        "track": _scope_entry(
            "核心赛道",
            status="pending-artifact",
            count=None,
            note="尚未进入 Research Agent 稳定快照；赛道频道继续独立发布。",
        ),
        "person": _scope_entry(
            "核心人物",
            status="active",
            count=row_count("person"),
            note="已进入每日实体快照与变化检测。",
        ),
        "ventureCompany": _scope_entry(
            "核心公司",
            status="active",
            count=row_count("ventureCompany"),
            note="已进入每日实体快照与变化检测。",
        ),
    }


def _read_pipeline_health(root: Path | None) -> dict[str, Any] | None:
    if root is None:
        return None
    path = root / "public" / "data" / "pipeline_health.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    jobs = payload.get("jobs")
    issue_jobs: list[dict[str, Any]] = []
    if isinstance(jobs, list):
        for job in jobs:
            if not isinstance(job, dict):
                continue
            status = str(job.get("status") or "unknown")
            if status == "healthy":
                continue
            issue_jobs.append(
                {
                    "jobId": str(job.get("jobId") or ""),
                    "name": str(job.get("name") or job.get("jobId") or "未知任务"),
                    "status": status,
                    "lastCompletedAt": job.get("lastCompletedAt"),
                }
            )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "overallStatus": str(payload.get("overallStatus") or "unknown"),
        "healthyJobs": int(summary.get("healthyJobs") or 0),
        "jobCount": int(summary.get("jobCount") or len(jobs or [])),
        "issueJobs": issue_jobs,
    }


def _diagnostic_text(diagnostics: Mapping[str, Any]) -> str:
    reasons = diagnostics.get("rejectionReasons")
    pieces: list[str] = []
    if isinstance(reasons, Mapping):
        ordered = sorted(
            ((str(key), int(value)) for key, value in reasons.items()),
            key=lambda item: (-item[1], item[0]),
        )
        for reason, count in ordered[:4]:
            pieces.append(f"{QUALITY_ISSUE_LABELS.get(reason, reason)} {count}")
    unbound = int(diagnostics.get("passedButUnboundEvidenceCount") or 0)
    if unbound:
        pieces.append(f"证据合格但未绑定变化字段 {unbound}")
    return "、".join(pieces)


def generate_report(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    global _LAST_QUALITY_DIAGNOSTICS
    _LAST_QUALITY_DIAGNOSTICS = {}
    report, snapshot = _ORIGINAL_GENERATE_REPORT(*args, **kwargs)

    diagnostics = dict(_LAST_QUALITY_DIAGNOSTICS)
    report["qualityDiagnostics"] = diagnostics
    warnings = diagnostics.get("sourceClassificationWarnings")
    report["sourceClassificationWarnings"] = (
        list(warnings) if isinstance(warnings, list) else []
    )
    report["researchScope"] = _research_scope(snapshot)

    root_value = kwargs.get("root")
    root = Path(root_value) if root_value is not None else None
    pipeline_health = _read_pipeline_health(root)
    if pipeline_health is not None:
        report["pipelineHealth"] = pipeline_health

    analysis = report.get("analysis")
    if isinstance(analysis, dict):
        rejected = int(diagnostics.get("rejectedCandidateCount") or 0)
        if rejected:
            details = _diagnostic_text(diagnostics)
            suffix = f"质量门诊断：{details}。" if details else "质量门诊断已写入结构化工件。"
            summary = str(analysis.get("executiveSummary") or "").rstrip()
            if "质量门诊断" not in summary:
                analysis["executiveSummary"] = f"{summary} {suffix}".strip()

        if pipeline_health and pipeline_health.get("issueJobs"):
            issue_text = "、".join(
                f"{job['name']}={job['status']}"
                for job in pipeline_health["issueJobs"][:4]
            )
            note = str(analysis.get("methodologyNote") or "").rstrip()
            pipeline_note = f"数据管线提示：{issue_text}。"
            if "数据管线提示" not in note:
                analysis["methodologyNote"] = f"{note} {pipeline_note}".strip()

    return report, snapshot


def install_evidence_policy(agent: Any) -> None:
    """Install strict evidence recovery/diagnostics hooks exactly once."""

    global _AGENT, _ORIGINAL_BUILD_EVIDENCE_PACKAGE, _ORIGINAL_GENERATE_REPORT
    global _INSTALLED_AGENT_ID

    if _INSTALLED_AGENT_ID == id(agent):
        return
    _AGENT = agent
    _ORIGINAL_BUILD_EVIDENCE_PACKAGE = agent.build_evidence_package
    _ORIGINAL_GENERATE_REPORT = agent.generate_report
    agent._walk_source_candidates = walk_source_candidates
    agent.build_evidence_package = build_evidence_package
    agent.generate_report = generate_report
    _INSTALLED_AGENT_ID = id(agent)
