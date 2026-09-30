"""Bounded public mention attribution, separate from company/profile approval.

Reuse the existing company registries and public people aliases. Ambiguous aliases
are withheld; matching mentions never create companySlug/personSlug or a follow.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERIC = {"", "科技产业", "科技公司", "公司", "未知", "未识别"}


@lru_cache(maxsize=1)
def public_entities():
    result = {}
    for path, key, kind in [("config/company_registry.json", "companies", "company"),
                            ("config/official_company_sources.json", "companies", "company"),
                            ("public/data/people.json", "people", "person")]:
        data = json.loads((ROOT / path).read_text(encoding="utf-8"))
        for row in data.get(key, []):
            name, slug = row.get("name"), row.get("slug")
            if not isinstance(name, str) or not isinstance(slug, str):
                continue
            identity = f"{kind}:{slug}"
            old = result.get(identity, {})
            aliases = [name, *old.get("aliases", []), *row.get("aliases", [])]
            result[identity] = {"id": identity, "kind": kind, "name": name,
                                "aliases": list(dict.fromkeys(x for x in aliases if isinstance(x, str)))}
    supplement = json.loads((ROOT / "config/priority_entity_aliases.json").read_text())
    for row in supplement["entities"]:
        # Prefer an existing registry identity over a supplementary mention ID.
        existing = next((x for x in result.values() if x["kind"] == row["kind"] and
                         x["name"].casefold() == row["name"].casefold()), None)
        key = existing["id"] if existing else row["id"]
        result[key] = {**row, "id": key, "aliases": list(dict.fromkeys([
            *(existing or {}).get("aliases", []), *row["aliases"]]))}
    return tuple(result.values())


@lru_cache(maxsize=8000)
def _pattern(alias):
    pattern = re.escape(alias)
    if alias.isascii():
        pattern = r"(?<![A-Za-z0-9])" + pattern + r"(?![A-Za-z0-9])"
    return re.compile(pattern, re.IGNORECASE)


def match_alias(text, alias):
    if not isinstance(alias, str) or not 2 <= len(alias) <= 100 or alias in GENERIC:
        return False
    return _pattern(alias).search(text) is not None


def link_priority_entities(item, entities=None):
    entities = public_entities() if entities is None else entities
    aliases = {}
    for row in entities:
        for alias in [row["name"], *row.get("aliases", [])]:
            if isinstance(alias, str):
                aliases.setdefault(alias.casefold(), set()).add(row["id"])
    mentions, ambiguous = [], False
    for row in entities:
        for field in ("title", "summary"):
            matched = next((a for a in [row["name"], *row.get("aliases", [])]
                            if match_alias(item.get(field, ""), a)), None)
            if not matched:
                continue
            if len(aliases[matched.casefold()]) != 1:
                ambiguous = True
                continue
            mentions.append({"id": row["id"], "kind": row["kind"], "name": row["name"],
                             "alias": matched, "field": field})
            break
        if len(mentions) >= 12:
            break
    # Title evidence comes first; no claim about buyer/target/employment roles.
    mentions.sort(key=lambda m: (m["field"] != "title", m["kind"] != "company", m["id"]))
    companies = list(dict.fromkeys(m["name"] for m in mentions if m["kind"] == "company"))
    people = list(dict.fromkeys(m["name"] for m in mentions if m["kind"] == "person"))
    result = {**item, "mentionedCompanies": companies, "mentionedPeople": people,
              "entityResolutionStatus": "ambiguous" if ambiguous else "matched" if mentions else "unresolved",
              "entityMentions": mentions}
    if item.get("company", "") in GENERIC:
        title_mentions = [m for m in mentions if m["kind"] == "company" and m["field"] == "title"]
        title_mentions.sort(key=lambda m: item.get("title", "").casefold().find(m["alias"].casefold()))
        titled = [m["name"] for m in title_mentions]
        if len(titled) == 1:
            result["company"] = titled[0]
        elif item.get("sourceId") == "amd-newsroom" and "AMD" in titled:
            result["company"] = "AMD"
        elif titled:
            # Keep one company value for existing single-entity capture flows.
            # Other parties remain structured mentions, never a compound entity.
            result["company"] = titled[0]
        elif len(companies) == 1:
            result["company"] = companies[0]
    return result
