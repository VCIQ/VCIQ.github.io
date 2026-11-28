"""Conservative event candidate clustering for pre-listing audit reports.

This module proposes duplicate groups; it never declares a financing event true.
Ambiguous rows remain singleton candidates. Source articles are retained per group.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from typing import Any


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def extract_round(title: str) -> str | None:
    text = str(title or "").upper().replace("＋", "+")
    patterns = [
        (r"PRE[- ]?IPO", "PRE-IPO"),
        (r"PRE[- ]?A", "PRE-A"),
        (r"PRE[- ]?B", "PRE-B"),
        (r"天使轮|天使融资", "天使轮"),
        (r"种子轮|种子融资", "种子轮"),
        (r"战略融资|战略投资", "战略融资"),
        (r"([A-F])\s*(?:轮|ROUND)\s*(?:\+|PLUS)?", None),
        (r"([A-F])\s*\+", None),
        (r"([A-F])\s*1\b", None),
    ]
    for pattern, fixed in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            if fixed:
                return fixed
            token = match.group(1)
            suffix = "+" if "+" in match.group(0) or "PLUS" in match.group(0) else ""
            return f"{token}轮{suffix}"
    return None


def extract_amount(title: str) -> str | None:
    text = str(title or "").replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(亿元|亿人民币|亿美元|万元|万人民币|万美元)", text)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def extract_investors(title: str) -> list[str]:
    """Extract explicitly labelled investor names; never infer from co-mentions."""
    text = str(title or "")
    patterns = [
        r"(?:由|获)([\u4e00-\u9fffA-Za-z0-9·（）()]{2,24}?)(?:领投|联合领投)",
        r"([\u4e00-\u9fffA-Za-z0-9·（）()]{2,24}?)(?:领投|联合领投)",
        r"(?:投资方|投资机构)[:：]?([\u4e00-\u9fffA-Za-z0-9·（）()]{2,24}?)(?:参与|等|和|及|，|,|。|$)",
        r"由([\u4e00-\u9fffA-Za-z0-9·（）()]{2,24}?)(?:投资|战略投资)",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip(" ，,。及和")
            if name and name not in found:
                found.append(name)
    return found



def extract_investor_mentions(text: str) -> list[dict[str, str]]:
    """Extract explicitly labelled investor names and roles, retaining evidence."""
    content = str(text or "")
    generic_names = {
        "九大券商", "券商", "证券公司", "机构", "投资机构", "产业投资方",
        "投资方", "多家机构", "相关机构", "投资者", "金融机构",
        "知名海外基金", "等产业投资方",
    }
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_names(raw: str, role: str, clause: str) -> None:
        raw = re.sub(
            r"^(?:以及|并由|由|其中|本轮融资由|本轮由|本轮融资|本轮|本次融资由|本次由|本次|融资由|投资方包括|投资机构包括|投资方为|投资机构为)\s*",
            "", raw.strip(),
        )
        # Only explicit list delimiters split institutions. Do not split on “和”:
        # it can be part of a legal institution name (e.g. 屹唐盛和基金).
        for raw_name in re.split(r"[、，,；;]", raw):
            name = raw_name.strip(" ：:()（） ")
            name = re.sub(r"(?:等产业投资方|等)$", "", name).strip()
            if len(name) < 2 or len(name) > 30 or name in generic_names:
                continue
            if any(token in name for token in ("可能通过", "还可能", "九大券商集体", "不能简单地")):
                continue
            key = (name, role)
            if key not in seen:
                found.append({
                    "name": name,
                    "role": role,
                    "extractionMethod": "explicit_role_clause",
                    "evidenceText": clause[:240],
                })
                seen.add(key)

    clauses = re.split(r"[，,。；;！!？?\n]+", content)
    for raw_clause in clauses:
        clause = re.sub(r"\s+", " ", raw_clause).strip()
        if not clause or len(clause) > 240:
            continue

        # Explicit investor lists, including “本轮投资方包括 A、B、C”.
        label = re.search(
            r"(?:(?:本轮|本次)?(?:融资)?投资方|(?:本轮|本次)?投资机构)\s*(?:包括|为|[:：])\s*(.{2,120})$",
            clause,
        )
        if label:
            add_names(label.group(1), "investor_label", clause)

        # Explicit role-bearing clauses. Prefixes are removed in add_names.
        role_patterns = (
            ("lead", r"^(.{2,120}?)(?:联合领投|领投)$"),
            ("follow", r"^(.{2,120}?)(?:跟投)$"),
            ("participant", r"^(.{2,120}?)(?:参投|参与投资)$"),
        )
        for role, pattern in role_patterns:
            match = re.search(pattern, clause)
            if match:
                add_names(match.group(1), role, clause)
    return found


def normalize_amount(value: Any) -> str | None:
    """Normalize equivalent Chinese currency unit spellings without FX conversion."""
    raw = str(value or "").replace(" ", "").replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(亿元|亿人民币|亿美元|万元|万人民币|万美元)", raw)
    if not match:
        return raw or None
    number, unit = match.groups()
    currency = "USD" if "美元" in unit else "CNY"
    scale = "100m" if unit.startswith("亿") else "10k"
    return f"{number}:{currency}:{scale}"



def parse_date(value: Any) -> date | None:
    raw = str(value or "")
    match = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})?", raw)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3) or 1))
    except ValueError:
        return None


def event_fingerprint(company: str, event_type: str, round_name: str | None,
                      amount: str | None, event_date: str | None, title: str,
                      source_url: str | None = None) -> str:
    day = parse_date(event_date)
    month = day.strftime("%Y-%m") if day else "undated"
    # Stable business key: title wording is deliberately excluded. For rows
    # lacking date/round/amount, use URL to keep uncertain candidates singleton.
    core = "|".join((
        normalize_text(company), event_type, round_name or "unknown-round",
        amount or "unknown-amount", month
    ))
    if not (round_name and day):
        core += "|" + str(source_url or normalize_text(title))
    return hashlib.sha256(core.encode("utf-8")).hexdigest()[:16]


def cluster_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group only high-confidence same-company/same-round/same-month candidates."""
    groups: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str, str]] = set()
    for row in rows:
        raw_company = str(row.get("company") or "")
        raw_title = str(row.get("title") or "")
        raw_url = str(row.get("publisherUrl") or row.get("googleNewsUrl") or row.get("url") or "")
        candidate_key = (
            normalize_text(raw_company),
            raw_url.strip().rstrip("/").casefold(),
            normalize_text(raw_title),
        )
        if candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        company = str(row.get("company") or "")
        title = str(row.get("title") or "")
        role = str(row.get("subjectRole") or "unknown")
        event_type = str(row.get("eventType") or {
            "funding_subject": "financing",
            "investor": "investment",
            "investee": "investment_received",
            "partner": "partnership",
            "mentioned": "mention",
        }.get(role, "unclassified"))
        round_name = row.get("round") or (extract_round(title) if event_type == "financing" else None)
        amount = normalize_amount(row.get("amount") or (extract_amount(title) if event_type in {"financing", "investment", "investment_received"} else None))
        investors = row.get("investors") or extract_investors(title)
        event_date = str(row.get("eventDate") or "")
        parsed = parse_date(event_date)
        norm_title = normalize_text(title)

        matched = None
        if role == "funding_subject" and round_name and parsed:
            for group in groups:
                if (
                    group["companyKey"] == normalize_text(company)
                    and group["eventType"] == event_type
                    and group["round"] == round_name
                    and group["eventMonth"] == parsed.strftime("%Y-%m")
                    and amount == group["amount"]
                    and (
                        not investors or not group["investors"]
                        or set(investors) == set(group["investors"])
                    )
                    and SequenceMatcher(
                        None, norm_title, group["titleKey"]
                    ).ratio() >= 0.42
                ):
                    matched = group
                    break

        if matched is None:
            fingerprint = event_fingerprint(
                company, event_type, round_name, amount, event_date, title,
                str(row.get("publisherUrl") or row.get("googleNewsUrl") or row.get("url") or "")
            )
            matched = {
                "eventId": f"evt-{fingerprint}",
                "company": company,
                "companyKey": normalize_text(company),
                "eventType": event_type,
                "eventDate": event_date or None,
                "publishedAt": None,
                "round": round_name,
                "amount": amount,
                "investors": sorted(set(investors)),
                "eventMonth": parsed.strftime("%Y-%m") if parsed else None,
                "titleKey": norm_title,
                "candidateCount": 0,
                "sources": [],
                "dedupeConfidence": "proposed" if role == "funding_subject" and round_name and parsed else "singleton-unverified",
                "classificationConfidence": (
                    "high" if role == "funding_subject" and round_name and parsed
                    else "medium" if role in {"investor", "investee", "partner"}
                    else "low"
                ),
                "eventStatus": "DISCOVERED",
            }
            groups.append(matched)

        source_url = row.get("publisherUrl") or row.get("googleNewsUrl") or row.get("url")
        matched["sources"].append({
            "title": title,
            "publishedAt": row.get("publishedAt"),
            "url": source_url,
            "publisherDomain": row.get("publisherDomain"),
            "urlResolved": bool(row.get("publisherUrlResolved")),
            "subjectRole": role,
            "investorsExtracted": sorted(set(investors)),
            "investorMentions": row.get("investorMentions", []),
            "investorExtractionMethod": "body_explicit_role_pattern" if row.get("investorMentions") else ("title_explicit_pattern" if investors else "not_found"),
            "investorEvidenceStatus": "DISCOVERED" if investors else "MISSING",
            "eventDate": row.get("eventDate"),
            "eventDateEvidence": row.get("eventDateEvidence"),
        })
        matched["candidateCount"] += 1
        source_published = row.get("publishedAt")
        if source_published:
            matched["publishedAt"] = source_published if not matched.get("publishedAt") else matched["publishedAt"]
        if investors:
            matched["investors"] = sorted(set(matched.get("investors", [])) | set(investors))

    # Resolve coarse-key collisions deterministically. Two distinct events can
    # share company/type/round/month when amount is missing or the company raises
    # multiple rounds in one month. Keep the coarse ID for a unique group; when
    # duplicated, derive a stable suffix from its sorted canonical source URLs.
    id_buckets: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        id_buckets.setdefault(group["eventId"], []).append(group)
    for base_id, bucket in id_buckets.items():
        if len(bucket) > 1:
            for group in bucket:
                urls = sorted({
                    str(source.get("url") or "")
                    for source in group["sources"]
                    if source.get("url")
                })
                discriminator = urls[0] if urls else "|".join(
                    sorted(normalize_text(source.get("title")) for source in group["sources"])
                )
                suffix = hashlib.sha256(discriminator.encode("utf-8")).hexdigest()[:8]
                group["eventId"] = f"{base_id}-{suffix}"

    for group in groups:
        group.pop("companyKey", None)
        group.pop("titleKey", None)
        group.pop("eventMonth", None)
    return groups
