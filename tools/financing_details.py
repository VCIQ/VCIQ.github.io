"""Extract conservative structured fields from completed financing disclosures.

The parser intentionally reads only an article's published title and summary.
It never infers undisclosed numbers, investors or valuations. Literal money
phrases are preserved alongside a normalized currency only when the currency is
explicit in the source text.
"""

from __future__ import annotations

import re
from typing import Any

try:
    from .article_publication_gate import financing_event_supported
except ImportError:
    from article_publication_gate import financing_event_supported  # type: ignore

SUPPORTED_CURRENCIES = {"CNY", "USD", "EUR", "GBP", "HKD", "JPY", "CAD", "AUD", "SGD"}

_CN_MONEY = (
    r"(?:人民币\s*)?"
    r"(?:约|近|超|逾|超过|至少|不少于)?\s*"
    r"(?:\d+(?:\.\d+)?|数(?:十|百|千)?)\s*"
    r"(?:万|百万|千万|亿|十亿|百亿)?\s*"
    r"(?:元|人民币|美元|美金|港元|欧元|英镑|日元)"
)
_SYMBOL_MONEY = (
    r"(?:US\$|USD\s*|HK\$|C\$|A\$|S\$|\$|€|£|RMB\s*|CNY\s*)"
    r"\d[\d,.]*(?:\s?(?:billion|million|thousand|bn|mm|m|b|k))?(?![A-Za-z])"
)
_WORD_MONEY = (
    r"\d+(?:\.\d+)?\s*(?:thousand|million|billion)\s*"
    r"(?:US\s+dollars?|dollars?|yuan|renminbi|euros?|pounds?|yen)"
)
_MONEY = rf"(?:{_CN_MONEY}|{_SYMBOL_MONEY}|{_WORD_MONEY})"

_VALUATION_PATTERNS = (
    re.compile(
        rf"(?:投后估值|融资后估值|估值)(?:达到|达|约为|约|超过|超|为)?\s*(?P<money>{_MONEY})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:post[- ]money\s+valuation|valuation)(?:\s+(?:of|at))?\s*(?P<money>{_MONEY})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"valued\s+at\s+(?P<money>{_MONEY})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?P<money>{_MONEY})\s+(?:post[- ]money\s+)?valuation\b",
        re.IGNORECASE,
    ),
)
_MONEY_RE = re.compile(_MONEY, re.IGNORECASE)

_CN_ROUND_RE = re.compile(
    r"(?P<round>pre[-\s]?[a-f](?:\+)?|[a-f](?:\+)?|天使|种子|战略)\s*轮",
    re.IGNORECASE,
)
_EN_ROUND_PATTERNS = (
    re.compile(r"\b(?P<round>pre[- ]series\s+[a-f](?:\+)?)\b", re.IGNORECASE),
    re.compile(r"\b(?P<round>series\s+[a-f](?:\+)?)\b", re.IGNORECASE),
    re.compile(r"\b(?P<round>pre[- ]seed)\b", re.IGNORECASE),
    re.compile(r"\b(?P<round>seed)(?:\s+(?:round|financing|funding))\b", re.IGNORECASE),
    re.compile(r"\b(?P<round>angel)(?:\s+(?:round|financing|funding))\b", re.IGNORECASE),
    re.compile(r"\b(?P<round>strategic)(?:\s+(?:round|financing|funding))\b", re.IGNORECASE),
    re.compile(r"\b(?P<round>pre[- ]?[a-f](?:\+)?)(?:\s+round)\b", re.IGNORECASE),
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _currency(raw: str) -> str | None:
    text = _clean(raw)
    upper = text.upper()
    # Match specific dollar/元 denominations before generic symbols/suffixes.
    if "港元" in text or "HK$" in upper:
        return "HKD"
    if "美元" in text or "美金" in text or "US$" in upper or "USD" in upper or "DOLLAR" in upper:
        return "USD"
    if "欧元" in text or "€" in text or "EURO" in upper:
        return "EUR"
    if "英镑" in text or "£" in text or "POUND" in upper:
        return "GBP"
    if "日元" in text or "YEN" in upper:
        return "JPY"
    if "C$" in upper:
        return "CAD"
    if "A$" in upper:
        return "AUD"
    if "S$" in upper:
        return "SGD"
    if "人民币" in text or "RMB" in upper or "CNY" in upper or "YUAN" in upper or "RENMINBI" in upper:
        return "CNY"
    if text.endswith("元"):
        return "CNY"
    if re.search(r"(?<![A-Z])\$", upper):
        return "USD"
    return None


def _canonical_round(raw: str) -> str:
    value = _clean(raw)
    folded = value.casefold().replace(" ", "-")
    if value in {"天使", "种子", "战略"}:
        return f"{value}轮"
    if folded.startswith("pre-series-"):
        suffix = folded.removeprefix("pre-series-").upper()
        return f"Pre-Series {suffix}"
    if folded.startswith("series-"):
        suffix = folded.removeprefix("series-").upper()
        return f"Series {suffix}"
    if folded in {"pre-seed", "preseed"}:
        return "Pre-Seed"
    if folded == "seed":
        return "Seed"
    if folded == "angel":
        return "Angel"
    if folded == "strategic":
        return "Strategic"
    compact = folded.replace("-", "")
    if compact.startswith("pre") and len(compact) >= 4:
        return f"Pre-{compact[3:].upper()}轮"
    return f"{compact.upper()}轮"


def _extract_round(title: str, summary: str) -> str | None:
    for text in (title, summary):
        if not text:
            continue
        match = _CN_ROUND_RE.search(text)
        if match:
            return _canonical_round(match.group("round"))
        for pattern in _EN_ROUND_PATTERNS:
            match = pattern.search(text)
            if match:
                return _canonical_round(match.group("round"))
    return None


def _valuation_match(text: str) -> tuple[dict[str, str] | None, list[tuple[int, int]]]:
    spans: list[tuple[int, int]] = []
    for pattern in _VALUATION_PATTERNS:
        for match in pattern.finditer(text):
            spans.append(match.span())
            raw = _clean(match.group("money"))
            value: dict[str, str] = {"original": raw}
            if currency := _currency(raw):
                value["currency"] = currency
            return value, spans
    return None, spans


def _overlaps(span: tuple[int, int], excluded: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in excluded)


def _amount_match(text: str, excluded: list[tuple[int, int]]) -> dict[str, str] | None:
    for match in _MONEY_RE.finditer(text):
        if _overlaps(match.span(), excluded):
            continue
        raw = _clean(match.group(0))
        value: dict[str, str] = {"original": raw}
        if currency := _currency(raw):
            value["currency"] = currency
        return value
    return None


def extract_financing_details(title: Any, summary: Any = "") -> dict[str, Any] | None:
    """Return an evidence-constrained envelope for a completed financing event."""

    title_text = _clean(title)
    summary_text = _clean(summary)
    if not financing_event_supported(title_text, summary_text):
        return None

    details: dict[str, Any] = {"status": "completed"}
    if round_name := _extract_round(title_text, summary_text):
        details["round"] = round_name

    title_valuation, title_spans = _valuation_match(title_text)
    summary_valuation, summary_spans = _valuation_match(summary_text)
    valuation = title_valuation or summary_valuation
    if valuation:
        details["valuation"] = valuation

    amount = _amount_match(title_text, title_spans)
    if amount is None:
        amount = _amount_match(summary_text, summary_spans)
    if amount:
        details["amount"] = amount
    return details


def enrich_financing_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach envelopes only to semantically supported completed financings."""

    enriched: list[dict[str, Any]] = []
    for raw in articles:
        article = dict(raw)
        if article.get("type") == "融资":
            details = extract_financing_details(article.get("title"), article.get("summary"))
            if details:
                article["financing"] = details
            else:
                article.pop("financing", None)
        else:
            article.pop("financing", None)
        enriched.append(article)
    return enriched


def validate_financing_details(article: dict[str, Any]) -> list[str]:
    """Validate the optional public financing envelope without requiring one."""

    if "financing" not in article:
        return []
    details = article.get("financing")
    if not isinstance(details, dict):
        return ["invalid:financing"]

    errors: list[str] = []
    if article.get("type") != "融资":
        errors.append("invalid:financing-type")
    if not financing_event_supported(article.get("title"), article.get("summary")):
        errors.append("invalid:financing-semantics")
    if details.get("status") != "completed":
        errors.append("invalid:financing-status")

    round_name = details.get("round")
    if round_name is not None and not _clean(round_name):
        errors.append("invalid:financing-round")

    for field in ("amount", "valuation"):
        if field not in details:
            continue
        money = details.get(field)
        if not isinstance(money, dict) or not _clean(money.get("original")):
            errors.append(f"invalid:financing-{field}")
            continue
        currency = money.get("currency")
        if currency is not None and currency not in SUPPORTED_CURRENCIES:
            errors.append(f"invalid:financing-{field}-currency")

    for field in ("investors", "leadInvestors"):
        if field not in details:
            continue
        values = details.get(field)
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not _clean(value) for value in values)
            or len(set(values)) != len(values)
        ):
            errors.append(f"invalid:financing-{field}")

    investors = details.get("investors")
    leads = details.get("leadInvestors")
    if isinstance(investors, list) and isinstance(leads, list) and not set(leads).issubset(set(investors)):
        errors.append("invalid:financing-lead-subset")
    return errors
