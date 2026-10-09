"""Build an offline, human-only evidence queue from official navigation candidates.

Never treats a title or homepage link as a verified investment, speaker, or exit.
No further network requests and no writes to reviewed/public data.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "config" / "innovation_global_investors.json"
EVIDENCE = ROOT / "config" / "innovation_investor_evidence.json"

SECTIONS = {
    "team", "our-team", "our_team", "people", "portfolio", "companies",
    "our-portfolio", "news", "newsroom", "blog", "articles", "insights",
    "perspectives", "research", "research-ai", "podcasts", "podcast",
    "stories", "media", "press", "investments", "investment", "about",
    "about-us", "events", "atlas", "category", "newsletter", "newsletters",
    "service", "investment_policy", "startup-growth-funding",
}
ARTICLES = {
    "news", "newsroom", "blog", "article", "articles", "story", "stories",
    "insight", "insights", "perspectives", "podcast", "atlas",
    "announcement", "press", "research", "interview", "viewpoint",
}
BIO = {"team", "our-team", "our_team", "team-members", "people", "person"}
PORTFOLIO = {"company", "companies", "portfolio", "investments", "investment"}

INVESTMENT = re.compile(
    r"\b(investing in|investment in|our investment|we invested|backing|we're backing|"
    r"co-led|co-lead|led the (?:series|round)|funding round|series [a-f]\b|"
    r"portfolio announcement)\b|领投|共同领投|投资于|宣布投资|参投|完成.{0,20}融资",
    re.I,
)
OUTCOME = re.compile(
    r"\b(acquire[ds]?|acquisition|goes public|went public|ipo|"
    r"clinical (?:data|trial|results)|phase [1-4] (?:trial|results)|"
    r"commercial launch|bankrupt|liquidat(?:ed|ion)|exit)\b|"
    r"被收购|完成收购|上市|临床试验|破产|清算",
    re.I,
)
SPEECH = re.compile(
    r"\b(podcast|interview|in conversation|fireside|perspective|insight|"
    r"thesis|viewpoint|why we|our view|Q&A)\b|访谈|专访|观点|对话|洞察|演讲",
    re.I,
)

CHECKLISTS = {
    "investment-lead": [
        "核验项目身份、实际机构/基金及领投或跟投角色；不能从同篇提及推定投资",
        "区分整轮融资总额与单家出资额，核验交易轮次和日期",
        "保存准确的官方原文、原始发布日期、证据段落；必要时查公司公告",
    ],
    "outcome-lead": [
        "核验项目身份、具体结果和原文发生日期",
        "区分技术/商业化/下一轮融资与收购或上市",
        "IPO、并购或估值上升不证明任何基金现金回报",
    ],
    "viewpoint-lead": [
        "确认作者/发言人、当时职务、原文或视频时间码、发表日期",
        "区分直接引述与转述；观点不是已被证实的事实",
        "项目责任必须另外核验，不能由署名文章推断领投",
    ],
    "portfolio-lead": [
        "核验项目规范身份与页面列示的组合关系",
        "组合页Partner不证明特定轮次领投或出资额",
        "保存来源定位；缺少的轮次与交易金额保持未知",
    ],
    "person-lead": [
        "核验人物身份、任职时点与机构关系",
        "人物介绍不证明此人主导某轮投资",
        "另查确实署名或出镜的原始采访以核验观点",
    ],
    "article-lead": [
        "核验原文标题和发布时间，排除营销页面",
        "核验公司、发言人、行为类别、证据位置",
        "未完成事实核验不得发布投资或退出断言",
    ],
}
PRIORITY = {
    "investment-lead": 0, "outcome-lead": 1, "viewpoint-lead": 2,
    "portfolio-lead": 3, "person-lead": 4, "article-lead": 5,
}


def _host(value: str) -> str:
    return (urlsplit(value).hostname or "").casefold().removeprefix("www.")


def _same_official_domain(url: str, official: str) -> bool:
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return bool(host) and p.scheme == "https" and p.port in (None, 443) and not p.username and not p.password and _host(url) == _host(official) and not host.endswith((".local", ".internal"))
    except ValueError:
        return False


def _normalized_url(value: str) -> str:
    p = urlsplit(value)
    return f"https://{_host(value)}{p.path.rstrip('/') or '/'}"


def classify_link(title: str, url: str) -> str:
    """A routing suggestion, not a claim that the linked page verifies anything."""
    segments = [s.casefold() for s in urlsplit(url).path.split("/") if s]
    if not segments or re.search(r"/category/|/(?:login|jobs|careers)(?:/|$)", url, re.I):
        return "navigation"
    if segments[-1] in SECTIONS or (len(segments) == 2 and segments[0] in {"cn", "en", "english"} and segments[-1] in SECTIONS):
        return "navigation"
    text = " ".join(title.split())
    if re.fullmatch(r"read more|learn more|view more|subscribe|newsletter|all stories", text, re.I) and not any(s in ARTICLES for s in segments[:-1]):
        return "navigation"
    if len(segments) >= 2 and segments[-2] in BIO:
        return "person-lead"
    if len(segments) >= 2 and segments[-2] in PORTFOLIO:
        return "portfolio-lead"
    slug = segments[-1].replace("-", " ")
    if OUTCOME.search(text) or OUTCOME.search(slug):
        return "outcome-lead"
    if INVESTMENT.search(text) or INVESTMENT.search(slug):
        return "investment-lead"
    if "podcast" in segments or SPEECH.search(text):
        return "viewpoint-lead"
    if any(s in ARTICLES for s in segments[:-1]):
        return "article-lead"
    return "navigation"


def build_review_queue(scout: dict, roster: dict, evidence: dict) -> dict:
    if scout.get("mode") != "official-page-navigation-discovery-only" or scout.get("autoPublication") is not False:
        raise ValueError("Only unreviewed official scout candidates are allowed")
    firms = roster.get("institutions")
    if not isinstance(firms, list) or len(firms) != 30:
        raise ValueError("Expected 30 registered institutions")
    by_firm = {f["id"]: f for f in firms}
    if len(by_firm) != 30:
        raise ValueError("Duplicate institution identifiers")
    rows = scout.get("results")
    if not isinstance(rows, list) or len(rows) != 30 or scout.get("institutionsExamined") != 30:
        raise ValueError("Incomplete scout run")
    reviewed_records = evidence.get("records", [])
    if not isinstance(reviewed_records, list):
        raise ValueError("Invalid reviewed evidence manifest")
    reviewed_urls = {
        _normalized_url(r["source"]["url"]) for r in reviewed_records
        if isinstance(r, dict) and isinstance(r.get("source"), dict) and isinstance(r["source"].get("url"), str)
    }
    examined, seen, links, directories, failures = set(), set(), [], [], []
    count = 0
    for source in rows:
        if not isinstance(source, dict):
            raise ValueError("Invalid institution result")
        institution_id = source.get("institutionId")
        if institution_id not in by_firm or institution_id in examined:
            raise ValueError("Foreign or duplicate institution")
        examined.add(institution_id)
        firm = by_firm[institution_id]
        official = firm["officialUrl"]
        if not _same_official_domain(source.get("sourceUrl", ""), official):
            raise ValueError("Non-official source")
        candidates = source.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Invalid candidate list")
        state = source.get("status")
        if state not in ("candidates-found", "no-candidates-adapter-review", "unavailable"):
            raise ValueError("Unexpected discovery state")
        if (state == "candidates-found") != bool(candidates):
            raise ValueError("Inconsistent source results")
        if state == "unavailable":
            failures.append({"institutionId": institution_id, "name": firm["name"], "reason": source.get("reason") or "unknown"})
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("institutionId") != institution_id:
                raise ValueError("Misattributed candidate")
            if candidate.get("claimStatus") != "unreviewed-navigation-candidate" or candidate.get("investmentRelationConfirmed") is not False:
                raise ValueError("Unreviewed evidence incorrectly promoted")
            url, origin = candidate.get("url"), candidate.get("discoveredOn")
            title, candidate_id = candidate.get("title"), candidate.get("id")
            if not all(isinstance(x, str) and x for x in (url, origin, title, candidate_id)):
                raise ValueError("Incomplete candidate")
            if not _same_official_domain(url, official) or not _same_official_domain(origin, official) or urlsplit(url).query or urlsplit(url).fragment:
                raise ValueError("Unsafe URL or provenance")
            if candidate_id in seen:
                raise ValueError("Duplicate candidate ID")
            seen.add(candidate_id)
            count += 1
            kind = classify_link(title, url)
            core = {
                "candidateId": candidate_id, "institutionId": institution_id, "institutionName": firm["name"],
                "title": " ".join(title.split())[:320], "originalUrl": url,
                "discoveredOn": origin, "publishedAt": None, "verifiedProjectId": None,
                "verifiedPersonId": None, "verifiedTransactionId": None, "publicationAllowed": False,
            }
            if kind == "navigation":
                directories.append({**core, "type": "source-navigation-only"})
            else:
                links.append({
                    **core, "type": kind,
                    "reviewState": "source-in-reviewed-sample" if _normalized_url(url) in reviewed_urls else "awaiting-original-evidence",
                    "classificationBasis": "heuristic-from-url-and-anchor-only",
                    "requiredEvidenceChecks": CHECKLISTS[kind],
                    "needsOriginalArticleAndDate": True,
                    "investmentRelationConfirmed": False, "investorSpeechVerified": False,
                    "realizedReturnVerified": False,
                })
    if len(examined) != 30 or count != scout.get("candidateCount"):
        raise ValueError("Scout totals disagree with candidate details")
    links.sort(key=lambda x: (PRIORITY[x["type"]], x["institutionId"], x["candidateId"]))
    buckets = defaultdict(list)
    for item in links:
        if item["reviewState"] != "source-in-reviewed-sample":
            buckets[item["institutionId"]].append(item)
    selected = []
    for _ in range(3):
        for firm in firms:
            if buckets[firm["id"]]:
                selected.append(buckets[firm["id"]].pop(0)["candidateId"])
            if len(selected) >= 60:
                break
        if len(selected) >= 60:
            break
    return {
        "schemaVersion": 1, "generatedAt": scout.get("generatedAt"),
        "mode": "offline-human-review-queue", "autoPublication": False,
        "verifiedInvestmentEvents": None, "registeredInstitutions": 30,
        "attemptedInstitutions": 30, "navigationCandidateCount": count,
        "actionableReviewLeads": len(links), "navigationOnlyCount": len(directories),
        "reviewTypeCounts": dict(sorted(Counter(r["type"] for r in links).items())),
        "priorityReviewCandidateIds": selected, "reviewLeads": links,
        "navigationSources": directories, "unavailableInstitutions": failures,
        "limitations": "仅用官网URL和导航标题分流，不含正文核验；未确认投资交易、主要项目投资人、发言原文、日期或收益。",
    }


def _md(value: object) -> str:
    return " ".join(str(value or "").replace("|", "\\|").split())[:320]


def render_markdown(queue: dict) -> str:
    by_id = {r["candidateId"]: r for r in queue["reviewLeads"]}
    labels = {
        "investment-lead": "潜在投资公告", "outcome-lead": "潜在项目结果",
        "viewpoint-lead": "观点/访谈候选", "portfolio-lead": "组合项目页面",
        "person-lead": "团队人物", "article-lead": "其他待核验文章",
    }
    lines = [
        "# 全球科技投资机构：待核验研究线索", "",
        f"来源扫描：{_md(queue['generatedAt'])}", "",
        f"- 已检查机构：{queue['attemptedInstitutions']}/30；导航候选：{queue['navigationCandidateCount']}",
        f"- 待查阅原文链接：{queue['actionableReviewLeads']}；仅作栏目导航：{queue['navigationOnlyCount']}",
        f"- 首页审核精选：{len(queue['priorityReviewCandidateIds'])}；来源访问失败：{len(queue['unavailableInstitutions'])}", "",
        "**仅为审核入口，不是已核验的投资关系、人物发言或现金回报。**", "",
        "| 机构 | 类型 | 待审核官方页面 | 首要核验 |",
        "| --- | --- | --- | --- |",
    ]
    for key in queue["priorityReviewCandidateIds"]:
        r = by_id[key]
        title = _md(r["title"]).replace("[", "\\[").replace("]", "\\]")
        lines.append(f"| {_md(r['institutionName'])} | {labels[r['type']]} | [{title}]({r['originalUrl']}) | {_md(r['requiredEvidenceChecks'][0])} |")
    lines.extend(["", "正式证据入库前需核对原文发布日期、段落定位、公司/人物规范身份、交易轮次和角色。不能由组合页推断领投，也不能由上市/收购推断基金回报。新增候选不会自动写入正式投资证据或公开站点。", ""])
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scout", required=True, type=Path)
    p.add_argument("--roster", type=Path, default=ROSTER)
    p.add_argument("--evidence", type=Path, default=EVIDENCE)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--markdown", required=True, type=Path)
    args = p.parse_args()
    if any(
        path.resolve().is_relative_to(ROOT / dirname)
        for path in (args.output, args.markdown)
        for dirname in ("config", "public")
    ):
        p.error("Unreviewed candidate output must not overwrite formal config/public data")
    queue = build_review_queue(
        json.loads(args.scout.read_text(encoding="utf-8")),
        json.loads(args.roster.read_text(encoding="utf-8")),
        json.loads(args.evidence.read_text(encoding="utf-8")),
    )
    for path in (args.output, args.markdown):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(queue), encoding="utf-8")
    print(json.dumps({
        "navigationCandidates": queue["navigationCandidateCount"],
        "humanReviewLeads": queue["actionableReviewLeads"],
        "navigationOnly": queue["navigationOnlyCount"],
        "priorityReview": len(queue["priorityReviewCandidateIds"]),
        "newVerifiedDeals": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
