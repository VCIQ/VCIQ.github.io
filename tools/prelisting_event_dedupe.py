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
        (r"([A-F])\s*(?:轮|ROUND)", None),
        (r"([A-F])\s*轮", None),
        (r"([A-F])\s*\+", None),
        (r"([A-F])\s*1", None),
        (r"(天使轮|种子轮)", None),
    ]
    for pattern, fixed in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            if fixed:
                return fixed
            token = match.group(1)
            return f"{token}轮" if len(token) == 1 and token in "ABCDEF" else token
    return None


def extract_amount(title: str) -> str | None:
    text = str(title or "").replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(亿元|亿人民币|亿美元|万元|万人民币|万美元)", text)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


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
                      amount: str | None, event_date: str | None, title: str) -> str:
    day = parse_date(event_date)
    # Date is retained at month precision in the fingerprint to allow articles
    # published on adjacent days to point to one announcement.
    month = day.strftime("%Y-%m") if day else "undated"
    material = "|".join((
        normalize_text(company), event_type, round_name or "unknown-round",
        amount or "unknown-amount", month, normalize_text(title)[:80]
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def cluster_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group only high-confidence same-company/same-round/same-month candidates."""
    groups: list[dict[str, Any]] = []
    for row in rows:
        company = str(row.get("company") or "")
        title = str(row.get("title") or "")
        role = str(row.get("subjectRole") or "unknown")
        event_type = str(row.get("eventType") or (
            "financing" if role == "funding_subject" else "unclassified"
        ))
        round_name = row.get("round") or extract_round(title)
        amount = row.get("amount") or extract_amount(title)
        event_date = str(row.get("eventDate") or row.get("publishedAt") or "")
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
                    and (
                        not amount or not group["amount"] or amount == group["amount"]
                    )
                    and SequenceMatcher(
                        None, norm_title, group["titleKey"]
                    ).ratio() >= 0.42
                ):
                    matched = group
                    break

        if matched is None:
            fingerprint = event_fingerprint(
                company, event_type, round_name, amount, event_date, title
            )
            matched = {
                "eventId": f"evt-{fingerprint}",
                "company": company,
                "companyKey": normalize_text(company),
                "eventType": event_type,
                "round": round_name,
                "amount": amount,
                "eventMonth": parsed.strftime("%Y-%m") if parsed else None,
                "titleKey": norm_title,
                "candidateCount": 0,
                "sources": [],
                "dedupeConfidence": "proposed" if role == "funding_subject" and round_name and parsed else "singleton-unverified",
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
        })
        matched["candidateCount"] += 1

    for group in groups:
        group.pop("companyKey", None)
        group.pop("titleKey", None)
        group.pop("eventMonth", None)
    return groups
