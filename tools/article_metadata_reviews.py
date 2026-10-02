"""Material-scoped corrections shared with the public reader, not a general classifier.

The evidence is the archived title/summary. Matching a record does not validate
its factual claims or upgrade its source, importance, or publication eligibility.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MANIFEST = Path(__file__).resolve().parents[1] / "config" / "article_metadata_reviews.json"
NON_IDENTITY_QUERY_KEYS = {"gclid", "fbclid", "mc_cid", "mc_eid", "igshid"}


@lru_cache(maxsize=1)
def metadata_reviews() -> list[dict[str, Any]]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("reviews"), list):
        raise ValueError("Invalid article metadata review manifest")
    for review in payload["reviews"]:
        if (
            not review.get("articleId")
            or not review.get("sourceId")
            or not review.get("expectedTitle")
            or not _url_key(review.get("sourceUrl", ""))
        ):
            raise ValueError("Review requires article, source, URL and title identity")
        if not review.get("fields") or set(review["fields"]) - {"sector", "type", "company"}:
            raise ValueError("Review can only correct sector/type/company")
        if "company" in review["fields"] and (
            not review.get("expectedSummaryContains")
            or not review.get("evidenceUrl")
            or not isinstance(review.get("removeCompanySlugs"), list)
        ):
            raise ValueError("Company review requires summary evidence and explicit removal scope")
    return payload["reviews"]


def _url_key(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
            return ""
        query = sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in NON_IDENTITY_QUERY_KEYS
        )
        path = parts.path.rstrip("/") or "/"
        return urlunsplit(
            (parts.scheme, parts.netloc.lower(), path, urlencode(query), "")
        )
    except ValueError:
        return ""


def _title_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def apply_article_metadata_review(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source")
    if not isinstance(source, dict):
        return article
    url_key = _url_key(str(source.get("url", "")))
    if not url_key:
        return article
    for review in metadata_reviews():
        if (
            article.get("id") != review["articleId"]
            or article.get("sourceId") != review["sourceId"]
            or _title_key(str(article.get("title", ""))) != _title_key(review["expectedTitle"])
            or url_key != _url_key(review["sourceUrl"])
            or (
                review.get("expectedSummaryContains")
                and review["expectedSummaryContains"] not in str(article.get("summary", ""))
            )
        ):
            continue
        fields = review["fields"]
        if any(
            article.get(key) not in {change["from"], change["to"]}
            for key, change in fields.items()
        ):
            return article
        updates = {
            key: change["to"]
            for key, change in fields.items()
            if article.get(key) != change["to"]
        }
        tracks = article.get("trackSlugs")
        if isinstance(tracks, list) and (
            review["removeTrackSlugs"] or review["addTrackSlugs"]
        ):
            next_tracks = list(
                dict.fromkeys(
                    [
                        slug
                        for slug in tracks
                        if slug not in review["removeTrackSlugs"]
                    ]
                    + review["addTrackSlugs"]
                )
            )
            if tracks != next_tracks:
                updates["trackSlugs"] = next_tracks
        result = {**article, **updates}
        if "company" in fields:
            removed = set(review.get("removeCompanySlugs", []))
            for key in ("companySlugs", "companyCandidateSlugs"):
                if isinstance(result.get(key), list):
                    remaining = [slug for slug in result[key] if slug not in removed]
                    if remaining:
                        result[key] = remaining
                    else:
                        result.pop(key, None)
            if result.get("companySlug") in removed:
                result.pop("companySlug", None)
            if isinstance(result.get("companyMatch"), dict) and result["companyMatch"].get("slug") in removed:
                result.pop("companyMatch", None)
            if isinstance(result.get("companyMatches"), list):
                remaining = [row for row in result["companyMatches"] if not isinstance(row, dict) or row.get("slug") not in removed]
                if remaining:
                    result["companyMatches"] = remaining
                else:
                    result.pop("companyMatches", None)
            if isinstance(result.get("mentionedCompanies"), list):
                removed_names = set(review.get("removeMentionedCompanies", []))
                result["mentionedCompanies"] = list(dict.fromkeys(
                    [name for name in result["mentionedCompanies"] if name not in removed_names]
                    + [fields["company"]["to"]]
                ))
        return result if result != article else article
    return article
