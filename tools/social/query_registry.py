"""Full input registry. Exclusions are explicit; list positions never identify queries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import PLATFORMS, ContractError, assert_safe, digest, normalize_query, query_id, validate
from .query_compile import WECHAT_PROVIDERS, compile_query

PRIORITY = {"priority": 0, "core": 1, "longTail": 2}


@dataclass(frozen=True)
class QueryRegistry:
    entries: tuple[dict[str, Any], ...]
    terms: tuple[dict[str, Any], ...]
    scope: tuple[tuple[str, str], ...]

    def by_id(self) -> dict[str, dict[str, Any]]:
        return {entry["queryId"]: entry for entry in self.entries}


def build_query_registry(tracking: dict, policy: dict, *, platforms: tuple[str, ...] = ("wechat",),
                         providers: tuple[str, ...] = ("sogou-weixin",), accounts: dict | None = None,
                         aliases: dict[str, str] | None = None) -> QueryRegistry:
    validate(policy, expected_kind="discovery_policy")
    if not platforms or set(platforms) - set(PLATFORMS) or set(providers) - set(WECHAT_PROVIDERS) or not providers:
        raise ContractError("registry_platform_or_provider")
    if not isinstance(tracking, dict) or not isinstance(tracking.get("tracks"), list):
        raise ContractError("invalid_tracking")
    explicit_aliases = aliases or {}
    if not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in explicit_aliases.items()):
        raise ContractError("invalid_aliases")
    explicit_aliases = {normalize_query(k): normalize_query(v) for k, v in explicit_aliases.items()}
    catalog: dict[str, dict] = {}
    queries: dict[str, dict] = {}
    scope = tuple(sorted({(p, provider) for p in platforms for provider in (providers if p == "wechat" else ("mediacrawler",))}))
    account_rows = (accounts or {}).get("accounts", [])
    if not isinstance(account_rows, list):
        raise ContractError("invalid_accounts")
    account_ids: set[str] = set()
    for row in account_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in account_ids:
            raise ContractError("invalid_accounts")
        account_ids.add(row["id"])

    def register(track_ref: str, kind: str, raw: str, account: dict | None = None) -> None:
        if not isinstance(raw, str):
            raise ContractError("term_must_be_string")
        normalized = normalize_query(raw)
        alias_seen: set[str] = set()
        while normalized in explicit_aliases:
            if normalized in alias_seen:
                raise ContractError("alias_cycle")
            alias_seen.add(normalized)
            normalized = explicit_aliases[normalized]
        term_ref = digest({"kind": kind, "text": normalized})
        reason = None
        try:
            assert_safe(raw)
            assert_safe(normalized)
        except ContractError:
            reason = "sensitive_term"
        if not normalized and reason is None:
            reason = "empty_term"
        if len(normalized) > 500 and reason is None:
            reason = "term_too_long"
        text = "[redacted]" if reason == "sensitive_term" else normalized
        item = catalog.setdefault(term_ref, {"termRef": term_ref, "kind": kind, "text": text,
                                             "originals": [], "trackRefs": []})
        original = "[redacted]" if reason == "sensitive_term" else raw
        if original not in item["originals"]:
            item["originals"].append(original)
        if track_ref not in item["trackRefs"]:
            item["trackRefs"].append(track_ref)
        for platform, provider in scope:
            if account is not None and platform != "wechat":
                continue
            expected = []
            target_id = None
            if account is not None:
                if not isinstance(account.get("name"), str) or not account["name"].strip():
                    raise ContractError("invalid_accounts")
                expected = sorted({normalize_query(v) for v in (account["name"], account.get("accountId", "")) if isinstance(v, str) and v.strip()})
                assert_safe(expected)
                target_id = account["id"]
            excluded = reason
            compiled = text
            if excluded is None:
                try:
                    compiled = compile_query(platform, provider, text, account=account["name"] if account else None)
                except ContractError as exc:
                    excluded = exc.code
            query = {"text": compiled, "scope": "account" if account else "track", "targetId": target_id,
                     "termRefs": [term_ref], "providerFilters": {}}
            identity = {"platform": platform, "provider": provider, "query": query}
            qid = query_id(identity)
            if excluded:
                qid = digest({"excludedQuery": qid, "termRef": term_ref, "reason": excluded})
            entry = queries.setdefault(qid, {"queryId": qid, **identity, "trackRefs": [], "terms": [],
                                              "priority": "longTail", "expectedAccounts": expected, "excludedReason": excluded})
            tier = "priority" if kind in {"company", "person"} else "core" if account else "longTail"
            if PRIORITY[tier] < PRIORITY[entry["priority"]]:
                entry["priority"] = tier
            if track_ref not in entry["trackRefs"]:
                entry["trackRefs"].append(track_ref)
            if term_ref not in entry["query"]["termRefs"]:
                entry["query"]["termRefs"].append(term_ref)
            term = {"termRef": term_ref, "kind": kind, "text": text}
            if term not in entry["terms"]:
                entry["terms"].append(term)

    for track in tracking["tracks"]:
        if not isinstance(track, dict):
            raise ContractError("invalid_track")
        if track.get("enabled", True) is False:
            continue
        name = track.get("name", "")
        if not isinstance(name, str) or not name.strip():
            raise ContractError("invalid_track")
        track_ref = normalize_query(str(track.get("slug") or name))
        assert_safe(track_ref)
        if len(track_ref) > 500:
            raise ContractError("track_ref_too_long")
        terms: list[tuple[str, str]] = []
        for field, kind in (("keywords", "keyword"), ("sampleCompanies", "company"), ("people", "person")):
            values = track.get(field, [])
            if not isinstance(values, list):
                raise ContractError("invalid_term_list")
            for value in values:
                terms.append((kind, value))
                register(track_ref, kind, value)
        for account in account_rows:
            if account.get("enabled", True) is False or name not in account.get("sectorKeywords", {}):
                continue
            extra = account["sectorKeywords"][name]
            if not isinstance(extra, list):
                raise ContractError("invalid_account_terms")
            for kind, text in [*terms, *(("keyword", word) for word in extra)]:
                register(track_ref, kind, text, account)
    for entry in queries.values():
        entry["trackRefs"].sort()
        entry["query"]["termRefs"].sort()
        entry["terms"].sort(key=lambda term: term["termRef"])
        if len(entry["trackRefs"]) > 100 or len(entry["terms"]) > 100:
            entry["excludedReason"] = "reference_limit_requires_manual"
    for item in catalog.values():
        item["originals"].sort()
        item["trackRefs"].sort()
    return QueryRegistry(tuple(queries[key] for key in sorted(queries)),
                         tuple(catalog[key] for key in sorted(catalog)), scope)
