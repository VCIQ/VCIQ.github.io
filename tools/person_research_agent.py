#!/usr/bin/env python3
"""Build a public-safe active research agenda for tracked people.

The planner is deliberately deterministic. It turns evidence gaps and conservative
viewpoint/execution questions into bounded research tasks, but it never asks a model
to decide whether a claim is verified. Third-party evidence can create a candidate;
only direct/official evidence may satisfy a task automatically.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = ROOT / "public" / "data" / "people.json"
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
OUTPUT_PATH = ROOT / "public" / "data" / "person_research_agenda.json"

FIRST_PARTY_TYPES = {
    "official_profile",
    "authored_work",
    "research_paper",
    "shareholder_letter",
    "public_post",
    "public_document",
    "speech",
    "qa",
}
DIRECT_EXPRESSION_TYPES = {
    "authored_work",
    "research_paper",
    "shareholder_letter",
    "public_post",
    "speech",
    "qa",
    "interview",
}
OFFICIAL_SOURCE_LEVELS = {"官方披露", "原始材料", "监管文件"}
PLACEHOLDER_ROLE = re.compile(r"待补充|待抓取|待完善|人物档案待补充", re.I)
SHIFT_MARKERS = re.compile(r"转向|转而|改为|重新聚焦|重心转|pivot|shift(?:ed|ing)?|move(?:d)? from|instead of", re.I)
REVERSAL_MARKERS = re.compile(r"改口|推翻|撤回|承认.{0,12}错|不再认为|changed my mind|was wrong|no longer believe|retract|reverse(?:d)?", re.I)
DAY = 24 * 60 * 60
MAX_TASKS_PER_PERSON = 5
MAX_SEARCH_QUERIES = 3
MAX_CANDIDATE_EVIDENCE = 4


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def clean(value: Any, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean(value, 1200).casefold())


def unique(values: Iterable[Any], *, limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean(value, 220)
        key = normalize(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return result


def parse_date(value: Any) -> int:
    raw = clean(value, 80)
    if not raw or raw in {"持续更新", "日期待核验"}:
        return 0
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        pass
    match = re.search(r"(20\d{2})[-年/]?(\d{1,2})?[-月/]?(\d{1,2})?", raw)
    if not match:
        return 0
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    try:
        return int(dt.datetime(year, month, day, tzinfo=dt.timezone.utc).timestamp())
    except ValueError:
        return 0


def stable_task_id(slug: str, task_type: str, target: str) -> str:
    digest = hashlib.sha1(f"{slug}|{task_type}|{normalize(target)}".encode("utf-8")).hexdigest()[:12]
    return f"person-research-{digest}"


def material_is_first_party(material: dict[str, Any]) -> bool:
    if clean(material.get("type")) in FIRST_PARTY_TYPES:
        return True
    source = clean(material.get("source")).casefold()
    return any(marker in source for marker in ("官方", "本人", "arxiv", "sec", "github", "大学", "研究院", "实验室"))


def focus_terms(person: dict[str, Any]) -> list[str]:
    return unique([
        *(person.get("products") or []),
        *(person.get("concepts") or []),
        *(person.get("sectors") or []),
    ], limit=6)


def first_party_materials(person: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in person.get("materials") or [] if isinstance(item, dict) and material_is_first_party(item)]


def direct_expression_materials(person: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in person.get("materials") or []
        if isinstance(item, dict) and clean(item.get("type")) in DIRECT_EXPRESSION_TYPES and parse_date(item.get("date"))
    ]


def latest_material(person: dict[str, Any]) -> dict[str, Any] | None:
    materials = [item for item in person.get("materials") or [] if isinstance(item, dict)]
    if not materials:
        return None
    return max(materials, key=lambda item: parse_date(item.get("date")))


def latest_age_days(person: dict[str, Any], generated_at: str) -> int | None:
    latest = latest_material(person)
    latest_ts = parse_date((latest or {}).get("date"))
    reference_ts = parse_date(generated_at)
    if not latest_ts or not reference_ts:
        return None
    return max(0, int((reference_ts - latest_ts) / DAY))


def query_with_person(person: dict[str, Any], hint: str) -> str:
    name = clean(person.get("name") or person.get("englishName"), 80)
    return clean(f"{name} {hint}", 180)


def bounded_queries(person: dict[str, Any], hints: Iterable[str]) -> list[str]:
    name_keys = [normalize(person.get("name")), normalize(person.get("englishName"))]
    result: list[str] = []
    for hint in hints:
        query = query_with_person(person, clean(hint, 100))
        query_norm = normalize(query)
        if not query_norm or not any(key and key in query_norm for key in name_keys):
            continue
        if query not in result:
            result.append(query)
        if len(result) >= MAX_SEARCH_QUERIES:
            break
    return result


def task(
    person: dict[str, Any],
    task_type: str,
    priority: str,
    target: str,
    question: str,
    objective: str,
    preferred_evidence: list[str],
    search_queries: list[str],
    success_criteria: str,
    evidence_basis: list[dict[str, Any]] | None = None,
    candidate_evidence: list[dict[str, Any]] | None = None,
    status: str = "open",
) -> dict[str, Any]:
    return {
        "id": stable_task_id(clean(person.get("slug")), task_type, target),
        "taskType": task_type,
        "priority": priority,
        "target": clean(target, 160),
        "question": clean(question, 420),
        "objective": clean(objective, 520),
        "preferredEvidence": unique(preferred_evidence, limit=5),
        "searchQueries": unique(search_queries, limit=MAX_SEARCH_QUERIES),
        "successCriteria": clean(success_criteria, 520),
        "evidenceBasis": [
            {
                "title": clean(item.get("title"), 260),
                "url": clean(item.get("url"), 1000),
                "source": clean(item.get("source"), 160),
                "date": clean(item.get("date"), 60),
            }
            for item in (evidence_basis or [])[:3]
            if clean(item.get("url"))
        ],
        "candidateEvidence": (candidate_evidence or [])[:MAX_CANDIDATE_EVIDENCE],
        "status": status if status in {"open", "candidate_found", "supported", "blocked"} else "open",
    }


def detect_viewpoint_candidate(person: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str] | None:
    direct = sorted(direct_expression_materials(person), key=lambda item: parse_date(item.get("date")), reverse=True)
    focuses = [normalize(item) for item in focus_terms(person) if len(normalize(item)) >= 2]
    for newer_index, newer in enumerate(direct):
        newer_title = clean(newer.get("title"), 320)
        marker = "reversal" if REVERSAL_MARKERS.search(newer_title) else "shift" if SHIFT_MARKERS.search(newer_title) else ""
        if not marker:
            continue
        newer_ts = parse_date(newer.get("date"))
        newer_norm = normalize(newer_title)
        for older in direct[newer_index + 1:]:
            older_ts = parse_date(older.get("date"))
            if not older_ts or not newer_ts or newer_ts - older_ts < 30 * DAY:
                continue
            older_norm = normalize(older.get("title"))
            shared = any(term in newer_norm and term in older_norm for term in focuses)
            if not shared:
                continue
            topic = next((raw for raw in focus_terms(person) if normalize(raw) in newer_norm and normalize(raw) in older_norm), "同一研究主题")
            return marker, [newer, older], topic
    return None


def article_candidate(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source") or {}
    return {
        "title": clean(article.get("title"), 280),
        "url": clean(source.get("url"), 1000),
        "source": clean(source.get("name"), 160),
        "sourceLevel": clean(source.get("level"), 80),
        "date": clean(article.get("publishedAt"), 60),
    }


def execution_candidates(
    person: dict[str, Any],
    articles: list[dict[str, Any]],
    organization: str,
    target: str,
) -> tuple[list[dict[str, Any]], bool]:
    org_norm = normalize(organization)
    target_norm = normalize(target)
    matches: list[tuple[int, dict[str, Any], bool]] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        source = article.get("source") or {}
        text = normalize(f"{article.get('title', '')} {article.get('summary', '')} {article.get('company', '')}")
        company_match = bool(org_norm and (org_norm in text or normalize(article.get("company")) == org_norm))
        target_match = bool(target_norm and target_norm in text)
        if not company_match or (target_norm and not target_match):
            continue
        source_level = clean(source.get("level"))
        official = source_level in OFFICIAL_SOURCE_LEVELS
        score = (40 if official else 10) + (20 if target_match else 0) + min(20, int(article.get("importance") or 0))
        matches.append((score, article_candidate(article), official and target_match))
    matches.sort(key=lambda item: (item[0], item[1].get("date", "")), reverse=True)
    candidates = [item[1] for item in matches[:MAX_CANDIDATE_EVIDENCE]]
    supported = any(item[2] for item in matches)
    return candidates, supported


def build_person_tasks(person: dict[str, Any], articles: list[dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    name = clean(person.get("name"))
    slug = clean(person.get("slug"))
    if not name or not slug:
        return tasks

    role = clean(person.get("role"))
    organizations = unique(person.get("organizations") or [], limit=4)
    focuses = focus_terms(person)
    first_party = first_party_materials(person)
    age_days = latest_age_days(person, generated_at)

    if not role or PLACEHOLDER_ROLE.search(role) or not organizations:
        tasks.append(task(
            person,
            "identity_verification",
            "P0",
            "身份与任职",
            f"{name} 当前公开身份、任职机构和角色能否由本人、机构官网或监管/学术档案独立核验？",
            "补齐人物身份与任职证据；在验证完成前，不把网页标题、媒体称谓或自动抽取角色当作正式任职。",
            ["机构官方人物页", "个人学术主页", "监管文件", "官方任命/团队页面"],
            bounded_queries(person, ["official profile", "个人主页", "任职 官方"]),
            "至少取得 1 条可直接归因于本人或任职机构的公开来源，同时明确姓名与当前角色。",
        ))

    if len(first_party) < 2:
        topic = focuses[0] if focuses else "核心研究与业务主线"
        tasks.append(task(
            person,
            "first_party_evidence",
            "P0" if len(first_party) == 0 else "P1",
            topic,
            f"能否找到 {name} 围绕“{topic}”的本人演讲、访谈、论文、公开发文或官方文件？",
            "增加可归因于人物本人的一手材料，避免人物研究长期依赖第三方报道。",
            ["本人论文/著作", "个人或机构官方主页", "官方 YouTube/视频号", "公开演讲/问答原始视频"],
            bounded_queries(person, [topic, f"{topic} 演讲", f"{topic} 访谈"]),
            "至少新增 1 条直接可归因于本人的公开材料；若用于观点演进，仍需第二个跨时间证据点。",
            evidence_basis=first_party[-1:] if first_party else [],
        ))

    viewpoint = detect_viewpoint_candidate(person)
    if viewpoint:
        kind, evidence, topic = viewpoint
        label = "观点反转" if kind == "reversal" else "观点转向"
        tasks.append(task(
            person,
            "viewpoint_verification",
            "P0",
            topic,
            f"{name} 在“{topic}”上的{label}是否真实存在，还是标题措辞/上下文截取造成的表面变化？",
            "回到原始视频、全文、论文或本人发文核验前后语境；任务关闭前不把候选变化升级为确定结论。",
            ["原始演讲/访谈视频", "完整文字稿", "本人论文/发文", "机构发布的完整问答"],
            bounded_queries(person, [topic, f"{topic} 完整访谈", f"{topic} full interview"]),
            "必须取得包含相关表述上下文的一手材料，并能与较早同主题一手材料直接比较；仅有媒体标题不得标记 supported。",
            evidence_basis=evidence,
        ))

    latest = latest_material(person)
    if latest and organizations:
        latest_text = normalize(latest.get("title"))
        target = next((focus for focus in focuses if normalize(focus) and normalize(focus) in latest_text), "")
        if target:
            organization = next((org for org in organizations if normalize(org) in latest_text), organizations[0])
            candidates, supported = execution_candidates(person, articles, organization, target)
            tasks.append(task(
                person,
                "execution_verification",
                "P1",
                f"{organization} · {target}",
                f"{name} 的最新公开事件涉及“{target}”后，{organization} 是否出现独立的产品、技术、组织或商业执行证据？",
                "把“人物表达”与“组织执行”分开验证；人物观点本身不自动等同于公司战略或产品落地。",
                ["公司官方公告/博客", "产品或技术官方发布", "监管文件", "公司官方开发者/研究页面"],
                [],
                "至少存在 1 条独立于人物表述的一手/官方组织来源，同时直接命中组织与目标技术/产品；第三方报道只能形成 candidate_found。",
                evidence_basis=[latest],
                candidate_evidence=candidates,
                status="supported" if supported else "candidate_found" if candidates else "open",
            ))

    if age_days is None or age_days > 180:
        topic = focuses[0] if focuses else "近期公开活动"
        tasks.append(task(
            person,
            "freshness_update",
            "P2",
            topic,
            f"{name} 最近 180 天是否有新的本人公开表达、论文、产品/项目动作或任职变化？",
            "补齐近期时间窗口，避免用多年以前的材料代表人物当前判断。",
            ["本人/机构官方更新", "近期演讲或采访", "近期论文/公开文件"],
            bounded_queries(person, [topic, f"{topic} 2026", "最新演讲 访谈"]),
            "找到至少 1 条最近 180 天的一手或机构官方材料；否则保持 open 并明确近期证据空窗。",
        ))

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    tasks.sort(key=lambda item: (priority_order.get(item["priority"], 9), item["taskType"], item["id"]))
    return tasks[:MAX_TASKS_PER_PERSON]


def build_agenda(people_payload: dict[str, Any], article_payload: dict[str, Any]) -> dict[str, Any]:
    people = [item for item in people_payload.get("people") or [] if isinstance(item, dict)]
    articles = [item for item in article_payload.get("articles") or [] if isinstance(item, dict)]
    generated_at = clean(people_payload.get("generatedAt") or article_payload.get("generatedAt") or dt.datetime.now(dt.timezone.utc).isoformat())
    records: dict[str, Any] = {}
    task_count = 0
    open_count = 0
    for person in people:
        slug = clean(person.get("slug"))
        if not slug:
            continue
        tasks = build_person_tasks(person, articles, generated_at)
        if not tasks:
            continue
        task_count += len(tasks)
        open_count += sum(1 for item in tasks if item.get("status") != "supported")
        records[slug] = {
            "personName": clean(person.get("name"), 120),
            "tasks": tasks,
            "openCount": sum(1 for item in tasks if item.get("status") != "supported"),
        }
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "personCount": len(records),
        "taskCount": task_count,
        "openTaskCount": open_count,
        "people": records,
        "methodology": "规则引擎仅提出研究问题和证据任务；第三方材料最多形成候选，只有满足 successCriteria 的一手/官方证据才能自动标记 supported。",
    }


def research_queries_by_slug(agenda: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for slug, record in (agenda.get("people") or {}).items():
        queries: list[str] = []
        for item in record.get("tasks") or []:
            if item.get("status") == "supported":
                continue
            if item.get("taskType") not in {"first_party_evidence", "viewpoint_verification", "freshness_update"}:
                continue
            queries.extend(item.get("searchQueries") or [])
        result[str(slug)] = unique(queries, limit=MAX_SEARCH_QUERIES)
    return result


def write_agenda(people_path: Path = PEOPLE_PATH, articles_path: Path = ARTICLES_PATH, output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    agenda = build_agenda(
        load_json(people_path, {"people": []}),
        load_json(articles_path, {"articles": []}),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(agenda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return agenda


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    parser.add_argument("--articles", type=Path, default=ARTICLES_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    agenda = build_agenda(
        load_json(args.people, {"people": []}),
        load_json(args.articles, {"articles": []}),
    )
    if args.check:
        invalid = [
            task.get("id") or "unknown"
            for record in (agenda.get("people") or {}).values()
            for task in record.get("tasks") or []
            if not task.get("question") or not task.get("successCriteria") or len(task.get("searchQueries") or []) > MAX_SEARCH_QUERIES
        ]
        if invalid:
            print(f"Invalid person research tasks: {invalid}")
            return 1
        print(f"Validated {agenda['taskCount']} active person research tasks.")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(agenda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {agenda['taskCount']} person research tasks to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
