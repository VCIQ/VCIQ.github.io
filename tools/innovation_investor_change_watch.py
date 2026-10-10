"""Compare consecutive bounded official-source scouting windows for editorial review.

Never equate a new *link* with a new investment or publication date.
Do not equate a missing link in a capped navigation window with a withdrawal,
negative business outcome or deleted source. No network calls or public writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from tools.innovation_investor_coverage import audit_coverage
from tools.innovation_investor_review_queue import build_review_queue, classify_link

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "config" / "innovation_global_investors.json"
EVIDENCE = ROOT / "config" / "innovation_investor_evidence.json"
IDENTITIES = ROOT / "config" / "innovation_investor_project_identities.json"

# Conservative title/path flags. A match is only a reason to OPEN the source.
NEGATIVE_PATTERNS = {
    "possible-insolvency": re.compile(r"\b(?:bankrupt(?:cy)?|insolven\w*|liquidat\w*)\b|破产|清算", re.I),
    "possible-shutdown": re.compile(r"\b(?:shutting down|shutdown|shut down|ceased operations|ceases operations|winding down)\b|停业|停产|终止运营", re.I),
    "possible-clinical-setback": re.compile(r"\b(?:clinical hold|trial halted|trial failed|phase [1-4] failure)\b|临床暂停|临床失败", re.I),
    "possible-regulatory-or-litigation": re.compile(r"\b(?:lawsuit|litigation|regulatory action|product recall)\b|监管处罚|产品召回|诉讼", re.I),
    "possible-layoffs": re.compile(r"\b(?:layoffs?|workforce reduction)\b|裁员", re.I),
}

def normalize_url(value: str) -> str:
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("Expected an HTTPS public evidence URL")
    return "https://" + p.netloc.casefold().removeprefix("www.") + (p.path.rstrip("/") or "/")

def _mentions_project(title: str, url: str, identities: dict) -> list[str]:
    # This is exact-token candidate matching, not identity resolution.
    text = (title + " " + urlsplit(url).path.replace("-", " ").replace("_", " ")).casefold()
    matches = []
    for project in identities["projects"]:
        for alias in project["observedNames"]:
            pattern = r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)"
            if re.search(pattern, text, re.UNICODE):
                matches.append(project["id"])
                break
    return sorted(set(matches))

def _signals(title: str, url: str) -> list[str]:
    value = title + " " + urlsplit(url).path.replace("-", " ").replace("_", " ")
    return [name for name, pattern in NEGATIVE_PATTERNS.items() if pattern.search(value)]

def compare_scout_runs(
    current: dict, previous: dict | None, roster: dict, evidence: dict, identities: dict,
) -> dict:
    # Fail closed on malformed or misattributed / unofficial candidates.
    audit_coverage(roster, current)
    build_review_queue(current, roster, evidence)
    if previous is not None:
        audit_coverage(roster, previous)
        build_review_queue(previous, roster, evidence)
    if len(identities.get("projects", [])) < 1:
        raise ValueError("Expected a reviewed project identity registry")
    ident_ids = [x.get("id") for x in identities["projects"]]
    if not all(isinstance(x, str) and x for x in ident_ids) or len(set(ident_ids)) != len(ident_ids):
        raise ValueError("Duplicate canonical research project IDs")

    evidence_urls: dict[str, set[str]] = {}
    for row in evidence["records"]:
        if row["kind"] == "fund-announcement" or not row["project"]:
            continue
        evidence_urls.setdefault(normalize_url(row["source"]["url"]), set()).add(row["institutionId"])
    by_current = {x["institutionId"]: x for x in current["results"]}
    by_previous = {x["institutionId"]: x for x in previous["results"]} if previous is not None else {}

    new_links: list[dict] = []
    no_longer_listed: list[dict] = []
    changes: list[dict] = []
    sites = []
    for firm in roster["institutions"]:
        key = firm["id"]
        now = by_current[key]
        old = by_previous.get(key)
        current_ok = now["status"] != "unavailable"
        prior_ok = old is not None and old["status"] != "unavailable"
        current_urls = {normalize_url(r["url"]): r for r in now["candidates"]}
        prior_urls = {normalize_url(r["url"]): r for r in old["candidates"]} if old else {}
        comparable = old is not None and current_ok and prior_ok
        if old is None:
            state = "no-prior-baseline"
        elif not prior_ok and current_ok:
            state = "site-recovered-baseline-unavailable"
        elif prior_ok and not current_ok:
            state = "site-newly-unavailable"
        elif not prior_ok and not current_ok:
            state = "site-still-unavailable"
        else:
            state = "comparable"
        if old and old["status"] != now["status"]:
            changes.append({
                "institutionId": key,
                "from": old["status"], "to": now["status"],
                "changeType": "availability-or-discovery-state",
                "notAnInvestmentEvent": True,
            })
        sites.append({
            "institutionId": key, "name": firm["name"], "status": now["status"],
            "priorStatus": old["status"] if old else None, "comparisonState": state,
            "candidateWindow": len(current_urls),
            "newlySeenInComparableWindow": len(current_urls.keys() - prior_urls.keys()) if comparable else None,
            "noLongerInLimitedWindow": len(prior_urls.keys() - current_urls.keys()) if comparable else None,
            "sourceErrorCategory": now.get("reason") if not current_ok else None,
            "pageDigestChanged": (old.get("contentSha256") != now.get("contentSha256"))
                if comparable and old.get("contentSha256") and now.get("contentSha256") else None,
        })
        if not comparable:
            # Most importantly: recovery does NOT imply each link was just published,
            # and failed retrieval does NOT imply any project has disappeared.
            continue
        for url, candidate in current_urls.items():
            if url in prior_urls:
                continue
            kind = classify_link(candidate["title"], candidate["url"])
            project_ids = _mentions_project(candidate["title"], candidate["url"], identities)
            source_reviewed = key in evidence_urls.get(url, set())
            new_links.append({
                "candidateId": candidate["id"], "institutionId": key,
                "institutionName": firm["name"], "title": candidate["title"][:320],
                "url": candidate["url"], "firstSeenInThisComparisonAt": current["generatedAt"],
                "publishedAt": None, "reviewRoute": kind,
                "possibleProjectIdsByTitleOrPath": project_ids,
                "alreadyReviewedAsSourceForInstitution": source_reviewed,
                "negativeEventTitleSignals": _signals(candidate["title"], candidate["url"]),
                "claimStatus": "navigation-change-only-unverified",
                "verifiedInvestmentEvent": False, "verifiedInvestorSpeech": False,
                "verifiedNegativeOutcome": False,
            })
        for url, candidate in prior_urls.items():
            if url not in current_urls:
                no_longer_listed.append({
                    "institutionId": key, "url": candidate["url"],
                    "status": "not-in-limited-navigation-window",
                    "confirmedDeleted": False, "confirmedExitOrShutdown": False,
                })
    new_links.sort(key=lambda x: (
        0 if x["negativeEventTitleSignals"] else 1,
        0 if x["possibleProjectIdsByTitleOrPath"] else 1,
        0 if x["reviewRoute"] in ("investment-lead", "outcome-lead") else 1,
        x["institutionId"], x["url"],
    ))
    state_count = Counter(s["comparisonState"] for s in sites)
    result = {
        "schemaVersion": 1,
        "measurement": "two-consecutive-bounded-homepage-navigation-windows",
        "currentGeneratedAt": current["generatedAt"],
        "previousGeneratedAt": previous.get("generatedAt") if previous else None,
        "baselineAvailable": previous is not None,
        "mode": "human-review-only-no-automatic-fact-promotion",
        "autoPublication": False,
        "registeredInstitutions": 30,
        "comparableInstitutions": state_count["comparable"],
        "sourceRecoveredInstitutions": state_count["site-recovered-baseline-unavailable"],
        "sourceNewlyUnavailableInstitutions": state_count["site-newly-unavailable"],
        "sourceStillUnavailableInstitutions": state_count["site-still-unavailable"],
        "newlySeenLinksInComparableWindows": len(new_links) if previous else None,
        "noLongerInCappedNavigationWindow": len(no_longer_listed) if previous else None,
        "newLinkNegativeTitleSignals": sum(bool(row["negativeEventTitleSignals"]) for row in new_links),
        "newLinksMatchingExistingProjectName": sum(bool(row["possibleProjectIdsByTitleOrPath"]) for row in new_links),
        "newLinksAlreadyUsingReviewedSource": sum(row["alreadyReviewedAsSourceForInstitution"] for row in new_links),
        "verifiedNewDealsByThisMonitor": 0,
        "verifiedNewFailuresByThisMonitor": 0,
        "sourceStatusChanges": changes,
        "institutions": sites,
        "newlySeenLinks": new_links,
        "noLongerListedLinks": no_longer_listed,
        "limitations": [
            "Each institution source is capped at 12 navigation candidates; order changes can replace links.",
            "firstSeenInThisComparisonAt is a crawler observation time, never an article or deal date.",
            "A source failure means unknown observation, not a company shutdown or zero new investments.",
            "A missing link does not prove deletion, a portfolio exit or a negative business outcome.",
            "Negative-title keywords, company-name matches and official co-mentions require original-page and independent evidence review.",
            "This monitor does not fetch project detail pages, verify company results, infer partner responsibility or compute financial returns.",
        ],
    }
    return result

def markdown(report: dict) -> str:
    s = [
        "## 全球机构官网变化观察（仅供人工核验）", "",
        f"当前扫描：{report['currentGeneratedAt']}",
        f"前次扫描：{report['previousGeneratedAt'] or '不可用（未形成变化基线）'}", "",
        "此处新链接只是**有限导航窗口首次看见**，不表示当日发布的新文章或真实交易。",
    ]
    if not report["baselineAvailable"]:
        s += ["", "**没有可比的成功生产基线，本次不能报告0条变化，也不能推出增量事件数。**"]
    else:
        s += [
            "", f"- 两轮均可访问的机构：{report['comparableInstitutions']}/30",
            f"- 从不可访问恢复：{report['sourceRecoveredInstitutions']}家；本次变为不可访问：{report['sourceNewlyUnavailableInstitutions']}家",
            f"- 新进入12条导航窗口：{report['newlySeenLinksInComparableWindows']}条",
            f"- 不再出现于有限窗口：{report['noLongerInCappedNavigationWindow']}条（**不等于删除或退出**）",
            f"- 新链接中的负面词汇线索：{report['newLinkNegativeTitleSignals']}条（**尚无已核验负面事件**）",
            f"- 新链接与既有规范项目标题/路径相符：{report['newLinksMatchingExistingProjectName']}条（尚待核实）",
            f"- 新链接已被独立人工证据台账覆盖：{report['newLinksAlreadyUsingReviewedSource']}条",
        ]
    s.extend(["", "| 机构 | 变化 | 说明 |", "| --- | --- | --- |"])
    for x in report["institutions"]:
        if x["comparisonState"] == "comparable" and not (x["newlySeenInComparableWindow"] or x["noLongerInLimitedWindow"]):
            continue
        safe = lambda t: str(t or "").replace("|", "\\|").replace("\n", " ")[:140]
        details = (
            f"新见{x['newlySeenInComparableWindow']} / 暂未列出{x['noLongerInLimitedWindow']}"
            if x["comparisonState"] == "comparable"
            else x["sourceErrorCategory"] or "本次没有可比导航窗口"
        )
        s.append(f"| {safe(x['name'])} | {x['comparisonState']} | {safe(details)} |")
    s.extend(["", "### 待查新导航入口（最多20条）", "",
              "| 机构 | 官网导航链接 | 初步路线 | 校验状态 |",
              "| --- | --- | --- | --- |"])
    for row in report["newlySeenLinks"][:20]:
        title = str(row["title"]).replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")[:140]
        route = row["reviewRoute"]
        status = "官网出处已另行入库" if row["alreadyReviewedAsSourceForInstitution"] else "必须打开原文核验"
        s.append(f"| {row['institutionName']} | [{title}]({row['url']}) | {route} | {status} |")
    s.extend(["", "**禁止自动推断：** 投资轮次、负责人、退出、违约、临床失败、基金收益。所有变化报告只留在14天Actions审核产物，不自动发布。", ""])
    return "\n".join(s)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--roster", type=Path, default=ROSTER)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--identities", type=Path, default=IDENTITIES)
    args = parser.parse_args()
    for destination in (args.output, args.markdown):
        if any(destination.resolve().is_relative_to(ROOT / path) for path in ("config", "public")):
            parser.error("Unverified link comparison must not modify public or reviewed records")
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = compare_scout_runs(
        read(args.current), read(args.previous) if args.previous and args.previous.is_file() else None,
        read(args.roster), read(args.evidence), read(args.identities),
    )
    for dest in (args.output, args.markdown):
        dest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    note = markdown(report)
    args.markdown.write_text(note, encoding="utf-8")
    print(json.dumps({
        "baselineAvailable": report["baselineAvailable"],
        "comparableInstitutions": report["comparableInstitutions"],
        "newlySeenLinks": report["newlySeenLinksInComparableWindows"],
        "reportedNewDeals": 0, "reportedNegativeEvents": 0,
    }, ensure_ascii=False))
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(note + "\n")
    if not report["baselineAvailable"]:
        print("::warning title=Investor change baseline::No comparable previous successful production artifact")
    for x in report["institutions"]:
        if x["comparisonState"] == "site-newly-unavailable":
            print(f"::warning title=Investor source unavailable::{x['institutionId']} unavailable; not a zero-investment observation")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
