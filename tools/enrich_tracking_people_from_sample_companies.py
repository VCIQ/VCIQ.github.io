#!/usr/bin/env python3
"""Add verified founders/core team and public social accounts for sample companies.

The tracking admin stores sample companies and people in ``config/user_tracking.json``.
This tool joins each enabled track's sample companies to the already sourced company
profiles in ``public/data/venture_profiles.json``, selects founder/executive/technical
leadership entries, and adds them to the track's people list. It then enriches exact
person identities from the local people snapshot and public Wikidata claims.

Only public profile identifiers are retained. X usernames become ``Name @handle``
labels so the existing X crawler can read the public timeline. GitHub, YouTube,
LinkedIn, Weibo and Bilibili profile URLs are registered as person sources. No login,
private endpoint, page scraping, credential or inferred account is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
LEDGER_PATH = ROOT / "config" / "tracking_auto_discovery.json"
VENTURE_PROFILES_PATH = ROOT / "public" / "data" / "venture_profiles.json"
PEOPLE_PATH = ROOT / "public" / "data" / "people.json"

USER_AGENT = (
    "VCIQResearch/1.0 (+https://github.com/VCIQ/VCIQ.github.io; "
    "public sample-company team discovery)"
)
REQUEST_TIMEOUT = 18
REQUEST_SLEEP = 0.2
MAX_PEOPLE_PER_TRACK = 6
MAX_PEOPLE_PER_COMPANY = 3
MAX_SOCIAL_SOURCES_PER_PERSON = 4

CORE_ROLE_RULES: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"联合创始|共同创始|联席创始|co[-\s]?founder|founding", re.I), 110),
    (re.compile(r"创始|founder", re.I), 105),
    (re.compile(r"首席执行|chief executive|\bceo\b|董事长|chair(?:man|woman|person)?", re.I), 90),
    (re.compile(r"首席技术|chief technology|\bcto\b|首席科学|chief scientist", re.I), 82),
    (re.compile(r"总裁|president|首席产品|chief product|首席研究|head of research", re.I), 72),
)

SOCIAL_PROPERTIES: dict[str, tuple[str, Callable[[str], str]]] = {
    "P2002": ("X", lambda value: f"https://x.com/{value.lstrip('@')}"),
    "P2037": ("GitHub", lambda value: f"https://github.com/{value}"),
    "P2397": ("YouTube", lambda value: f"https://www.youtube.com/channel/{value}"),
    "P6634": ("LinkedIn", lambda value: f"https://www.linkedin.com/in/{value}"),
    "P3579": (
        "微博",
        lambda value: f"https://weibo.com/u/{value}" if value.isdigit() else f"https://weibo.com/{value}",
    ),
    "P6455": ("Bilibili", lambda value: f"https://space.bilibili.com/{value}"),
}

SOCIAL_HOST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("X", re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/|$)", re.I)),
    ("GitHub", re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})(?:/|$)", re.I)),
    ("YouTube", re.compile(r"https?://(?:www\.)?youtube\.com/(?:channel/|@)([A-Za-z0-9_.-]+)(?:/|$)", re.I)),
    ("LinkedIn", re.compile(r"https?://(?:(?:www|[a-z]{2})\.)?linkedin\.com/in/([^/?#]+)", re.I)),
    ("微博", re.compile(r"https?://(?:www\.)?weibo\.com/(?:u/)?([^/?#]+)", re.I)),
    ("Bilibili", re.compile(r"https?://space\.bilibili\.com/(\d+)(?:/|$)", re.I)),
)

GENERIC_PERSON_NAMES = {
    "",
    "创始人",
    "联合创始人",
    "首席执行官",
    "ceo",
    "cto",
    "团队",
    "管理团队",
    "核心团队",
    "leadership",
    "management",
    "team",
}


@dataclass
class SocialAccount:
    platform: str
    value: str
    url: str


@dataclass
class TeamCandidate:
    name: str
    role: str
    company: str
    source_url: str
    score: int
    socials: list[SocialAccount] = field(default_factory=list)


class PublicWikidataClient:
    def __init__(
        self,
        max_requests: int = 100,
        fetch_json: Callable[[str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_requests = max_requests
        self.used_requests = 0
        self.failed_requests = 0
        self._fetch_json = fetch_json
        self._sleep = sleep

    def json(self, url: str) -> Any:
        if self.used_requests >= self.max_requests:
            return None
        self.used_requests += 1
        try:
            if self._fetch_json is not None:
                payload = self._fetch_json(url)
            else:
                request = Request(url, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            self.failed_requests += 1
            return None
        self._sleep(REQUEST_SLEEP)
        return payload


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def clean_text(value: Any, limit: int = 160) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalized_key(value: Any) -> str:
    text = clean_text(value, 240).casefold()
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", text)


PERSON_NAME_SUFFIX_RE = re.compile(
    r"(?:博士后?|博士後|教授|院士|先生|女士|老师|老師)$",
    re.IGNORECASE,
)


def normalize_person_name(value: Any) -> str:
    text = re.sub(r"@\S+", "", clean_text(value, 120)).strip()
    previous = None
    while text and text != previous:
        previous = text
        text = PERSON_NAME_SUFFIX_RE.sub("", text).strip()
    words = text.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        left = [word.casefold() for word in words[:half]]
        right = [word.casefold() for word in words[half:]]
        if left == right:
            text = " ".join(words[:half])
    return text


def person_name_key(value: Any) -> str:
    return normalized_key(normalize_person_name(value))


def company_keys(value: Any) -> set[str]:
    raw = clean_text(value, 120)
    if not raw:
        return set()
    variants = {normalized_key(raw)}
    simplified = re.sub(
        r"(?:股份)?有限公司$|有限责任公司$|集团$|控股$|科技$|技术$|创新$|\b(?:inc|corp|corporation|company|co|ltd|limited|holdings?)\.?$",
        "",
        raw,
        flags=re.I,
    ).strip()
    if simplified:
        variants.add(normalized_key(simplified))
    return {value for value in variants if value}


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    if slug:
        return slug[:54]
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


PERSON_NAME_NOISE_RE = re.compile(
    r"(?:\b(?:company|business|corporate|global|development|sales|marketing|"
    r"supply\s+chain|manufacturing|technologies?|systems?|senior|vice|presiden(?:t)?|governo(?:r)?|government|class|"
    r"officer|cfo|cto|ceo|team|leadership|management|press|news|post|co)\b|"
    r"关注|作为|参加|出席|共同|同創|同创|創業者|创业者|創始|创始|董事|主席|"
    r"主题演讲|演讲|负责|負責|表示|介绍|介紹|宣布|致辞|致辭|担任|擔任|"
    r"现任|現任|曾任|来自|來自|团队|團隊|公司|集团|集團|部门|部門|供应链|供應鏈|业务发展|業務發展)",
    re.IGNORECASE,
)


def is_likely_person_name(value: str) -> bool:
    name = normalize_person_name(value)
    key = person_name_key(name)
    if not key or key in GENERIC_PERSON_NAMES or re.search(r"https?://|@|\d", name, re.I):
        return False
    if PERSON_NAME_NOISE_RE.search(name):
        return False
    if re.search(r"公司|集团|实验室|研究院|大学|基金|资本|科技|团队|委员会", name):
        return False
    if re.fullmatch(r"[\u3400-\u9fff·•]{2,8}", name):
        return 2 <= len(name.replace("·", "").replace("•", "")) <= 5
    words = name.split()
    return 2 <= len(words) <= 5 and all(re.fullmatch(r"[A-Za-z][A-Za-z'.-]*", word) for word in words)


def role_score(role: str) -> int:
    cleaned = clean_text(role, 100)
    for pattern, score in CORE_ROLE_RULES:
        if pattern.search(cleaned):
            return score
    return 0


def profile_index(payload: Any) -> dict[str, dict[str, Any]]:
    companies = payload.get("companies") if isinstance(payload, dict) else None
    rows = companies.values() if isinstance(companies, dict) else companies if isinstance(companies, list) else []
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        aliases: list[Any] = [row.get("name"), row.get("englishName"), row.get("slug")]
        aliases.extend(row.get("aliases") or [])
        for alias in aliases:
            for key in company_keys(alias):
                index.setdefault(key, row)
    return index


def social_from_url(url: str) -> SocialAccount | None:
    for platform, pattern in SOCIAL_HOST_PATTERNS:
        match = pattern.search(url)
        if match:
            value = match.group(1).strip()
            if platform == "X" and not re.fullmatch(r"[A-Za-z0-9_]{1,15}", value):
                return None
            return SocialAccount(platform=platform, value=value, url=match.group(0).rstrip("/"))
    return None


def local_people_index(payload: Any) -> dict[str, list[SocialAccount]]:
    people = payload.get("people") if isinstance(payload, dict) else None
    if not isinstance(people, list):
        return {}
    result: dict[str, list[SocialAccount]] = {}
    for person in people:
        if not isinstance(person, dict):
            continue
        aliases: list[Any] = [person.get("name"), person.get("englishName")]
        aliases.extend(person.get("aliases") or [])
        accounts: dict[str, SocialAccount] = {}
        for handle in person.get("handles") or []:
            if isinstance(handle, str):
                value = handle.strip().lstrip("@")
                if re.fullmatch(r"[A-Za-z0-9_]{1,15}", value):
                    account = SocialAccount("X", value, f"https://x.com/{value}")
                    accounts[account.url.casefold()] = account
            elif isinstance(handle, dict):
                url = clean_text(handle.get("url"), 500)
                account = social_from_url(url) if url else None
                if account:
                    accounts[account.url.casefold()] = account
        for field_name in ("socialAccounts", "materials"):
            for item in person.get(field_name) or []:
                if isinstance(item, dict):
                    url = clean_text(item.get("url"), 500)
                else:
                    url = clean_text(item, 500)
                account = social_from_url(url) if url else None
                if account:
                    accounts[account.url.casefold()] = account
        for alias in aliases:
            key = person_name_key(alias)
            if key:
                result.setdefault(key, []).extend(accounts.values())
    return result


def claim_strings(claims: dict[str, Any], prop: str) -> list[str]:
    values: list[str] = []
    for row in claims.get(prop, []) if isinstance(claims, dict) else []:
        value = row.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


def wikidata_social_accounts(
    client: PublicWikidataClient,
    person_name: str,
    company_name: str,
) -> list[SocialAccount]:
    query = f"{person_name} {company_name}".strip()
    search = client.json(
        "https://www.wikidata.org/w/api.php?action=wbsearchentities"
        f"&search={quote_plus(query)}&language=zh&uselang=zh&format=json&limit=5"
    )
    rows = search.get("search") if isinstance(search, dict) else None
    if not rows:
        search = client.json(
            "https://www.wikidata.org/w/api.php?action=wbsearchentities"
            f"&search={quote_plus(query)}&language=en&uselang=en&format=json&limit=5"
        )
        rows = search.get("search") if isinstance(search, dict) else None
    if not rows:
        return []

    wanted = person_name_key(person_name)
    company_tokens = [key for key in company_keys(company_name) if len(key) >= 3]
    selected: dict[str, Any] | None = None
    for row in rows:
        label_keys = {person_name_key(row.get("label"))}
        label_keys.update(person_name_key(alias) for alias in row.get("aliases") or [])
        if wanted not in label_keys:
            continue
        description = normalized_key(row.get("description"))
        if company_tokens and description and not any(token in description for token in company_tokens):
            continue
        selected = row
        break
    if not selected:
        return []

    entity_id = clean_text(selected.get("id"), 30)
    if not entity_id:
        return []
    detail = client.json(
        "https://www.wikidata.org/w/api.php?action=wbgetentities"
        f"&ids={entity_id}&props=claims&format=json"
    )
    claims = (
        detail.get("entities", {}).get(entity_id, {}).get("claims", {})
        if isinstance(detail, dict)
        else {}
    )
    accounts: dict[str, SocialAccount] = {}
    for prop, (platform, make_url) in SOCIAL_PROPERTIES.items():
        for value in claim_strings(claims, prop):
            if platform == "X" and not re.fullmatch(r"[A-Za-z0-9_]{1,15}", value.lstrip("@")):
                continue
            if platform == "Bilibili" and not value.isdigit():
                continue
            cleaned = value.lstrip("@") if platform == "X" else value
            url = make_url(cleaned)
            accounts[url.casefold()] = SocialAccount(platform, cleaned, url)
    return list(accounts.values())


def empty_ledger() -> dict[str, Any]:
    return {"schemaVersion": 1, "updatedAt": "", "tracks": {}, "added": [], "removed": []}


def ledger_key(track: Any, kind: Any, value: Any) -> tuple[str, str, str]:
    return (str(track or ""), str(kind or ""), normalized_key(value))


def config_values(track: dict[str, Any], kind: str, config: dict[str, Any]) -> list[str]:
    if kind == "sources":
        return [
            clean_text(source.get("url"), 500)
            for source in config.get("sources", [])
            if source.get("sector") == track.get("name")
        ]
    return [clean_text(value, 500) for value in track.get(kind, [])]


def sync_tombstones(ledger: dict[str, Any], config: dict[str, Any]) -> bool:
    tracks = {str(track.get("slug")): track for track in config.get("tracks", [])}
    removed = ledger.setdefault("removed", [])
    removed_keys = {ledger_key(row.get("track"), row.get("kind"), row.get("value")) for row in removed}
    retained: list[dict[str, Any]] = []
    changed = False
    for row in ledger.get("added", []):
        track = tracks.get(str(row.get("track")))
        values = {
            normalized_key(value)
            for value in config_values(track, str(row.get("kind")), config)
        } if track else set()
        if normalized_key(row.get("value")) in values:
            retained.append(row)
            continue
        key = ledger_key(row.get("track"), row.get("kind"), row.get("value"))
        if key not in removed_keys:
            removed.append({
                "track": row.get("track"),
                "kind": row.get("kind"),
                "value": row.get("value"),
                "removedAt": now_iso(),
            })
            removed_keys.add(key)
        changed = True
    ledger["added"] = retained
    return changed


def blocked_values(ledger: dict[str, Any], track: dict[str, Any], kind: str) -> set[str]:
    slug = str(track.get("slug") or "")
    values = {
        normalized_key(row.get("value"))
        for row in ledger.get("removed", [])
        if row.get("track") == slug and row.get("kind") == kind
    }
    if kind == "people":
        values.update(person_name_key(row.get("value")) for row in ledger.get("removed", []) if row.get("track") == slug and row.get("kind") == kind)
    ignored_map = {"people": "people", "sources": "sources"}
    ignored = track.get("ignoredRecommendations") or {}
    for value in ignored.get(ignored_map[kind], []) or []:
        values.add(person_name_key(value) if kind == "people" else normalized_key(value))
    return {value for value in values if value}


def source_id(person: str, platform: str) -> str:
    return f"source-auto-person-{slugify(person)}-{slugify(platform)}"


def choose_core_team(profile: dict[str, Any], company: str) -> list[TeamCandidate]:
    candidates: list[TeamCandidate] = []
    for order, row in enumerate(profile.get("team") or []):
        if not isinstance(row, dict):
            continue
        name = normalize_person_name(row.get("name"))
        role = clean_text(row.get("role"), 100)
        score = role_score(role)
        if not score or not is_likely_person_name(name):
            continue
        candidates.append(TeamCandidate(
            name=name,
            role=role,
            company=company,
            source_url=clean_text(row.get("sourceUrl"), 500),
            score=score - order,
        ))
    candidates.sort(key=lambda item: (-item.score, item.name))
    unique: list[TeamCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = person_name_key(candidate.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
        if len(unique) >= MAX_PEOPLE_PER_COMPANY:
            break
    return unique


def discover_candidates(
    track: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    local_people: dict[str, list[SocialAccount]],
    client: PublicWikidataClient,
) -> list[TeamCandidate]:
    result: list[TeamCandidate] = []
    seen: set[str] = set()
    for sample_company in track.get("sampleCompanies") or []:
        profile = None
        for key in company_keys(sample_company):
            profile = profiles.get(key)
            if profile:
                break
        if not profile:
            continue
        company = clean_text(profile.get("name") or sample_company, 100)
        for candidate in choose_core_team(profile, company):
            key = person_name_key(candidate.name)
            if key in seen:
                continue
            accounts: dict[str, SocialAccount] = {
                account.url.casefold(): account for account in local_people.get(key, [])
            }
            for account in wikidata_social_accounts(client, candidate.name, company):
                accounts[account.url.casefold()] = account
            candidate.socials = list(accounts.values())
            result.append(candidate)
            seen.add(key)
            if len(result) >= MAX_PEOPLE_PER_TRACK:
                return result
    return result


def x_handle(accounts: list[SocialAccount]) -> str:
    for account in accounts:
        if account.platform == "X" and re.fullmatch(r"[A-Za-z0-9_]{1,15}", account.value):
            return account.value
    return ""


def add_ledger_entry(
    ledger: dict[str, Any],
    track_slug: str,
    kind: str,
    value: str,
    evidence: list[str],
    stamp: str,
) -> None:
    key = ledger_key(track_slug, kind, value)
    for row in ledger.setdefault("added", []):
        if ledger_key(row.get("track"), row.get("kind"), row.get("value")) == key:
            merged = set(row.get("evidence") or []) | set(evidence)
            row["evidence"] = sorted(merged)
            return
    ledger["added"].append({
        "track": track_slug,
        "kind": kind,
        "value": value,
        "addedAt": stamp,
        "evidence": sorted(set(evidence)),
    })


def apply_candidates(
    config: dict[str, Any],
    ledger: dict[str, Any],
    track: dict[str, Any],
    candidates: list[TeamCandidate],
) -> dict[str, Any]:
    stamp = now_iso()
    slug = str(track.get("slug") or "")
    blocked_people = blocked_values(ledger, track, "people")
    blocked_sources = blocked_values(ledger, track, "sources")
    people = track.setdefault("people", [])
    people_by_name = {person_name_key(label): index for index, label in enumerate(people)}
    existing_urls = {normalized_key(source.get("url")) for source in config.get("sources", [])}
    existing_ids = {str(source.get("id") or "") for source in config.get("sources", [])}
    added_people: list[str] = []
    added_sources: list[str] = []

    for candidate in candidates:
        name_key = person_name_key(candidate.name)
        handle = x_handle(candidate.socials)
        label = f"{candidate.name} @{handle}" if handle else candidate.name
        if name_key and name_key not in blocked_people and normalized_key(label) not in blocked_people:
            existing_index = people_by_name.get(name_key)
            if existing_index is None:
                people.append(label)
                people_by_name[name_key] = len(people) - 1
                added_people.append(label)
                add_ledger_entry(
                    ledger, slug, "people", label,
                    ["sample-company-core-team", "verified-company-profile"] + (["wikidata-social"] if handle else []),
                    stamp,
                )
            elif handle and "@" not in str(people[existing_index]):
                old_label = str(people[existing_index])
                people[existing_index] = label
                added_people.append(label)
                ledger["added"] = [
                    row for row in ledger.get("added", [])
                    if ledger_key(row.get("track"), row.get("kind"), row.get("value"))
                    != ledger_key(slug, "people", old_label)
                ]
                add_ledger_entry(
                    ledger, slug, "people", label,
                    ["sample-company-core-team", "verified-company-profile", "wikidata-social"],
                    stamp,
                )

        social_count = 0
        for account in candidate.socials:
            if account.platform == "X":
                continue
            if social_count >= MAX_SOCIAL_SOURCES_PER_PERSON:
                break
            url_key = normalized_key(account.url)
            if not url_key or url_key in existing_urls or url_key in blocked_sources:
                continue
            base_id = source_id(candidate.name, account.platform)
            unique_id = base_id
            suffix = 2
            while unique_id in existing_ids:
                unique_id = f"{base_id}-{suffix}"
                suffix += 1
            config.setdefault("sources", []).append({
                "id": unique_id,
                "name": f"{candidate.name} · {account.platform}",
                "url": account.url,
                "sourceType": "listing-search",
                "sourceCategory": "person",
                "region": "全球",
                "sector": str(track.get("name") or "未分类"),
                "company": "",
                "ticker": "",
                "keywords": [candidate.name, candidate.company],
                "enabled": True,
            })
            existing_urls.add(url_key)
            existing_ids.add(unique_id)
            added_sources.append(account.url)
            social_count += 1
            add_ledger_entry(
                ledger, slug, "sources", account.url,
                ["sample-company-core-team", "public-social-identifier", account.platform],
                stamp,
            )

    if added_people or added_sources:
        ledger.setdefault("tracks", {}).setdefault(slug, {})["lastTeamExpandedAt"] = stamp
    return {
        "track": slug,
        "added": {"people": added_people, "sources": added_sources},
    }


def enrich_config(
    config: dict[str, Any],
    venture_payload: Any,
    people_payload: Any,
    ledger: dict[str, Any],
    client: PublicWikidataClient,
    max_tracks: int,
) -> dict[str, Any]:
    profiles = profile_index(venture_payload)
    local_people = local_people_index(people_payload)
    summaries: list[dict[str, Any]] = []
    tracks = [track for track in config.get("tracks", []) if track.get("enabled")]
    tracks = [track for track in tracks if track.get("sampleCompanies")][:max_tracks]
    for track in tracks:
        candidates = discover_candidates(track, profiles, local_people, client)
        summaries.append(apply_candidates(config, ledger, track, candidates))
    changed = any(
        summary["added"]["people"] or summary["added"]["sources"]
        for summary in summaries
    )
    return {
        "changed": changed,
        "requestsUsed": client.used_requests,
        "requestsFailed": client.failed_requests,
        "tracks": summaries,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-tracks", type=int, default=30)
    parser.add_argument("--max-requests", type=int, default=120)
    args = parser.parse_args(argv)

    config = load_json(CONFIG_PATH, None)
    if not isinstance(config, dict) or not isinstance(config.get("tracks"), list):
        print(json.dumps({"error": "config/user_tracking.json unreadable"}, ensure_ascii=False))
        return 1
    venture_payload = load_json(VENTURE_PROFILES_PATH, {})
    people_payload = load_json(PEOPLE_PATH, {})
    ledger = load_json(LEDGER_PATH, empty_ledger())
    if not isinstance(ledger, dict):
        ledger = empty_ledger()
    for key, fallback in empty_ledger().items():
        ledger.setdefault(key, fallback)

    tombstoned = sync_tombstones(ledger, config)
    client = PublicWikidataClient(max_requests=max(0, args.max_requests))
    result = enrich_config(
        config,
        venture_payload,
        people_payload,
        ledger,
        client,
        max(0, args.max_tracks),
    )

    if not args.dry_run and (result["changed"] or tombstoned):
        ledger["updatedAt"] = now_iso()
        LEDGER_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if not args.dry_run and result["changed"]:
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    result["tombstoned"] = tombstoned
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
