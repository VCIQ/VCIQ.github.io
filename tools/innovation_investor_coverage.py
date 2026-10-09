"""Audit the 30-firm official-homepage scout without promoting discovery to facts.

This reports retrieval and navigation-link extraction only. It does not infer
portfolio completeness, investment relationships, project leads or returns.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "config" / "innovation_global_investors.json"
VALID_STATES = {"candidates-found", "no-candidates-adapter-review", "unavailable"}
STATE_LABEL = {
    "candidates-found": "官网可访问，有待审核导航链接",
    "no-candidates-adapter-review": "官网可访问，未提取到导航链接",
    "unavailable": "本次访问失败或受限",
}


def audit_coverage(roster: dict, scout: dict) -> dict:
    firms = roster.get("institutions")
    if not isinstance(firms, list) or len(firms) != 30:
        raise ValueError("Expected exactly 30 registered institutions")
    ids = [firm.get("id") for firm in firms]
    if not all(isinstance(item, str) and item for item in ids) or len(set(ids)) != 30:
        raise ValueError("Invalid or duplicate institution IDs")
    if scout.get("mode") != "official-page-navigation-discovery-only" or scout.get("autoPublication") is not False:
        raise ValueError("Unexpected scout mode or publication setting")
    results = scout.get("results")
    if not isinstance(results, list) or len(results) != 30:
        raise ValueError("Scout did not report exactly 30 institution attempts")
    by_id = {}
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Invalid institution result")
        identity = result.get("institutionId")
        status = result.get("status")
        candidates = result.get("candidates")
        if identity not in ids or identity in by_id or status not in VALID_STATES:
            raise ValueError("Unexpected, duplicated or invalid institution result")
        if not isinstance(candidates, list):
            raise ValueError("Invalid candidate list")
        if (status == "candidates-found") != bool(candidates):
            raise ValueError("Candidate list disagrees with source status")
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("institutionId") != identity:
                raise ValueError("Candidate is not attributed to its source institution")
            if candidate.get("investmentRelationConfirmed") is not False or candidate.get("claimStatus") != "unreviewed-navigation-candidate":
                raise ValueError("Unreviewed navigation link was promoted to an investment fact")
        by_id[identity] = result
    candidate_total = sum(len(row["candidates"]) for row in results)
    if candidate_total != scout.get("candidateCount") or scout.get("institutionsExamined") != 30:
        raise ValueError("Scout headline counts disagree with its detailed results")
    statuses = [by_id[identity]["status"] for identity in ids]
    breakdown = [
        {
            "institutionId": identity,
            "name": firm["name"],
            "status": by_id[identity]["status"],
            "navigationCandidateCount": len(by_id[identity]["candidates"]),
            "reason": by_id[identity].get("reason") if by_id[identity]["status"] == "unavailable" else None,
        }
        for firm, identity in zip(firms, ids)
    ]
    available = 30 - statuses.count("unavailable")
    return {
        "schemaVersion": 1,
        "generatedAt": scout.get("generatedAt"),
        "measurement": "official-homepage-retrieval-and-navigation-only",
        "verifiedInvestmentEvents": None,
        "registeredInstitutions": 30,
        "attemptedInstitutions": 30,
        "reachableOfficialHomepages": available,
        "homepagesWithNavigationCandidates": statuses.count("candidates-found"),
        "reachableHomepagesWithoutCandidates": statuses.count("no-candidates-adapter-review"),
        "unavailableOfficialHomepages": statuses.count("unavailable"),
        "unreviewedNavigationCandidates": candidate_total,
        "retrievalCoveragePercent": round(100 * available / 30, 1),
        "institutions": breakdown,
    }


def markdown_summary(report: dict) -> str:
    lines = [
        "## 全球30家科技投资机构：官网发现覆盖审计",
        "",
        f"审计时间：{report['generatedAt'] or '未记录'}",
        "",
        f"- 官网访问成功：**{report['reachableOfficialHomepages']}/30**（{report['retrievalCoveragePercent']}%）",
        f"- 有导航发现候选：**{report['homepagesWithNavigationCandidates']}家**，共 **{report['unreviewedNavigationCandidates']}条** 待审链接",
        f"- 可访问但没有候选：**{report['reachableHomepagesWithoutCandidates']}家**",
        f"- 访问失败或受限：**{report['unavailableOfficialHomepages']}家**",
        "",
        "**口径：仅检测官网首页访问与导航发现；不代表投资组合、实际投资、投资人发言或收益已经核验。**",
        "",
        "| 机构 | 官网采集状态 | 待审导航候选 | 失败原因 |",
        "| --- | --- | ---: | --- |",
    ]
    for item in report["institutions"]:
        safe = lambda value: str(value or "").replace("|", "\\|").replace("\n", " ")[:160]
        lines.append(
            f"| {safe(item['name'])} | {STATE_LABEL[item['status']]} "
            f"| {item['navigationCandidateCount']} | {safe(item['reason']) or '—'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--roster", type=Path, default=ROSTER)
    args = parser.parse_args()
    if any(args.output.resolve().is_relative_to(ROOT / path) for path in ("public", "config")):
        parser.error("Unreviewed coverage reports cannot overwrite public/ or config/")
    roster = json.loads(args.roster.read_text(encoding="utf-8"))
    scout = json.loads(args.input.read_text(encoding="utf-8"))
    report = audit_coverage(roster, scout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = markdown_summary(report)
    print(summary)
    if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a", encoding="utf-8") as stream:
            stream.write(summary)
    if report["unavailableOfficialHomepages"]:
        print(f"::warning title=Institution homepage scout::{report['unavailableOfficialHomepages']} of 30 homepage checks unavailable or restricted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
