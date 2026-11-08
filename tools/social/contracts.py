"""Fail-closed v1 contracts; standard library only, no network reference resolver.

The small schema interpreter intentionally supports only the vocabulary in the
bundled schema. It is not a general JSON Schema implementation. A vocabulary
change fails closed; optional jsonschema parity tests cover the frozen shapes.
Schema validation and single-record semantic checks are distinct from PR-07's
future batch-integrity/import checks. Error messages never echo input values.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit
from uuid import UUID

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/social/contracts-v1.schema.json"
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
KINDS = {
    "crawl_job": "CrawlJob", "query_receipt": "QueryReceipt",
    "signal_observation": "SignalObservation", "run_manifest": "RunManifest",
    "review_item": "ReviewItem", "decision_request": "DecisionRequest",
    "discovery_policy": "DiscoveryPolicy", "runtime_config": "RuntimeConfig",
    "job_plan": "JobPlan",
}
PLATFORMS = ("wechat", "xhs", "wb", "bili", "zhihu")
SCHEMA_KEYS = frozenset({
    "$schema", "$defs", "$ref", "title", "description", "type", "properties",
    "required", "additionalProperties", "const", "enum", "not", "allOf",
    "anyOf", "oneOf", "if", "then", "else", "items", "minItems", "maxItems",
    "uniqueItems", "minLength", "maxLength", "minimum", "maximum", "pattern", "format",
})
SECRET_KEYS = frozenset({
    "cookie", "cookies", "setcookie", "authorization", "proxyauthorization",
    "password", "passwd", "secret", "clientsecret", "privatekey", "token",
    "accesstoken", "refreshtoken", "idtoken", "xsectoken", "sessionid",
    "storagestate", "browserstate", "csrftoken", "xsrftoken",
})
SECRET_ASSIGNMENT = re.compile(
    r'''(?ix)(?:["']?\b(?:cookies?|set[-_]?cookie|(?:proxy[-_]?)?authorization|password|passwd|client[-_]?secret|access[-_]?token|refresh[-_]?token|xsec[-_]?token|csrf[-_]?token|xsrf[-_]?token|session[-_]?id|private[-_]?key|token)["']?\s*[:=]\s*[^\s,;}]+|\bbearer\s+[\w.+/=-]+|\bgh[pousr]_[a-z0-9]{20,}|\bgithub_pat_[a-z0-9_]+|-----BEGIN[^\n]*PRIVATE KEY-----)'''
)
DATE_TIME = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})\Z")
CONTENT_FIELDS = ("nativeId", "contentType", "title", "titleOrigin", "excerpt", "textScope", "publishedAt", "publishedPrecision")


class ContractError(ValueError):
    """A stable error code and schema-owned location, with no raw payload."""
    def __init__(self, code: str, path: str = "$") -> None:
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}")


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ContractError("invalid_json_value") from None


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path | str) -> Any:
    """Bounded UTF-8 input; duplicate keys and NaN/Infinity are never accepted."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate_key")
            result[key] = value
        return result

    def constant(_: str) -> Any:
        raise ContractError("non_finite_number")

    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ContractError("document_too_large")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ContractError("invalid_document") from None


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", unquote(value)).casefold())


def assert_safe(value: Any, path: str = "$", depth: int = 0) -> None:
    """Reject sensitive keys, URLs and credential assignments, including logs."""
    if depth > 32:
        raise ContractError("nesting_limit", path)
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError("non_string_key", path)
            if _key(key) in SECRET_KEYS:
                raise ContractError("sensitive_field", path)
            # Keys are untrusted too; never include their text in an exception.
            assert_safe(key, path, depth + 1)
            assert_safe(item, path, depth + 1)
    elif isinstance(value, list):
        for item in value:
            assert_safe(item, path, depth + 1)
    elif isinstance(value, str):
        decoded = unicodedata.normalize("NFKC", value)
        for _ in range(3):
            decoded = html.unescape(unquote(decoded))
        if SECRET_ASSIGNMENT.search(decoded):
            raise ContractError("sensitive_text", path)
        for match in re.finditer(r'https?://[^\s<>"\']+', decoded, re.I):
            try:
                parts = urlsplit(match.group())
                if parts.username is not None or parts.password is not None:
                    raise ContractError("sensitive_url", path)
                keys = [k for k, _ in parse_qsl(parts.query)] + [k for k, _ in parse_qsl(parts.fragment)]
                if any(_key(k) in SECRET_KEYS | {"sn", "signature", "sign", "auth", "key"} for k in keys):
                    raise ContractError("sensitive_url", path)
            except ValueError as exc:
                if isinstance(exc, ContractError):
                    raise
                raise ContractError("invalid_url", path) from None
    elif isinstance(value, float) and not math.isfinite(value):
        raise ContractError("non_finite_number", path)


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _is_type(value: Any, kind: str) -> bool:
    return {
        "null": value is None, "object": isinstance(value, dict),
        "array": isinstance(value, list), "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and math.isfinite(value) and value.is_integer()),
    }.get(kind, False)


def _timestamp(value: str) -> datetime:
    if not DATE_TIME.fullmatch(value):
        raise ValueError("RFC3339 timestamp required")
    parsed = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("offset required")
    return parsed


def _format(value: str, name: str) -> bool:
    try:
        if name == "date":
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and date.fromisoformat(value) is not None
        if name == "date-time":
            return _timestamp(value) is not None
        if name == "uuid":
            return str(UUID(value)) == value.lower()
        if name == "uri":
            return bool(urlsplit(value).scheme) and not re.search(r"[\s\x00-\x1f]", value)
    except (ValueError, TypeError, OverflowError):
        return False
    raise ContractError("unsupported_schema_format")


def _audit_schema(node: Any, root: dict[str, Any]) -> None:
    if not isinstance(node, dict) or set(node) - SCHEMA_KEYS:
        raise ContractError("unsupported_schema_keyword")
    if "$ref" in node and (not re.fullmatch(r"#/\$defs/[A-Za-z]+", node["$ref"]) or node["$ref"].split("/")[-1] not in root["$defs"]):
        raise ContractError("unsupported_schema_reference")
    if "format" in node and node["format"] not in {"date", "date-time", "uri", "uuid"}:
        raise ContractError("unsupported_schema_format")
    for name in ("properties", "$defs"):
        for child in node.get(name, {}).values():
            _audit_schema(child, root)
    for name in ("allOf", "anyOf", "oneOf"):
        for child in node.get(name, []):
            _audit_schema(child, root)
    for name in ("not", "if", "then", "else", "items"):
        if name in node:
            _audit_schema(node[name], root)
    if "additionalProperties" in node and node["additionalProperties"] is not False:
        raise ContractError("unsupported_schema_keyword")


def _shape(value: Any, node: dict[str, Any], root: dict[str, Any], path: str) -> None:
    def matches(branch: dict[str, Any]) -> bool:
        try:
            _shape(value, branch, root, path)
            return True
        except ContractError:
            return False

    if "$ref" in node:
        _shape(value, root["$defs"][node["$ref"].split("/")[-1]], root, path)
    if "type" in node and not _is_type(value, node["type"]):
        raise ContractError("type", path)
    if "const" in node and not _same(value, node["const"]):
        raise ContractError("const", path)
    if "enum" in node and not any(_same(value, x) for x in node["enum"]):
        raise ContractError("enum", path)
    for branch in node.get("allOf", []):
        _shape(value, branch, root, path)
    if "anyOf" in node and not any(matches(x) for x in node["anyOf"]):
        raise ContractError("any_of", path)
    if "oneOf" in node and sum(matches(x) for x in node["oneOf"]) != 1:
        raise ContractError("one_of", path)
    if "not" in node and matches(node["not"]):
        raise ContractError("not", path)
    if "if" in node:
        _shape(value, node.get("then" if matches(node["if"]) else "else", {}), root, path)
    if isinstance(value, dict):
        for key in node.get("required", []):
            if key not in value:
                raise ContractError("required", f"{path}.{key}")
        props = node.get("properties", {})
        if node.get("additionalProperties") is False and set(value) - set(props):
            raise ContractError("additional_properties", path)
        for key in props.keys() & value.keys():
            _shape(value[key], props[key], root, f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0) or len(value) > node.get("maxItems", math.inf):
            raise ContractError("items_length", path)
        if node.get("uniqueItems") and len({canonical_bytes(x) for x in value}) != len(value):
            raise ContractError("unique_items", path)
        if "items" in node:
            for i, item in enumerate(value):
                _shape(item, node["items"], root, f"{path}[{i}]")
    if isinstance(value, str):
        if len(value) < node.get("minLength", 0) or len(value) > node.get("maxLength", math.inf):
            raise ContractError("string_length", path)
        if "pattern" in node and not re.search(node["pattern"], value):
            raise ContractError("pattern", path)
        if "format" in node and not _format(value, node["format"]):
            raise ContractError("format", path)
    if _is_type(value, "number") and (value < node.get("minimum", -math.inf) or value > node.get("maximum", math.inf)):
        raise ContractError("number_range", path)


def load_schema() -> dict[str, Any]:
    schema = load_json(SCHEMA_PATH)
    _audit_schema(schema, schema)
    return schema


def normalize_query(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def query_id(job: dict[str, Any]) -> str:
    q = job["query"]
    return digest({"platform": job["platform"], "provider": job["provider"], "scope": q["scope"], "targetId": q["targetId"], "text": normalize_query(q["text"]), "providerFilters": q["providerFilters"]})


def content_hash(observation: dict[str, Any]) -> str:
    return digest({key: observation[key] for key in CONTENT_FIELDS})


def _public_url(value: str | None, platform: str, path: str) -> None:
    if value is None:
        return
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.port is not None or parts.username is not None or parts.fragment or "\\" in value or "%" in parts.path:
            raise ValueError
        hosts = {
            "wechat": {"mp.weixin.qq.com"}, "xhs": {"www.xiaohongshu.com", "xiaohongshu.com"},
            "wb": {"m.weibo.cn", "weibo.com", "www.weibo.com"},
            "bili": {"www.bilibili.com", "bilibili.com"},
            "zhihu": {"www.zhihu.com", "zhihu.com", "zhuanlan.zhihu.com"},
        }
        patterns = {
            "wechat": r"/s(?:/[A-Za-z0-9_-]+)?", "xhs": r"/(?:explore|discovery/item)/[A-Za-z0-9_-]+",
            "wb": r"/(?:detail/\d+|\d+/[A-Za-z0-9]+)", "bili": r"/video/(?:av\d+|BV[A-Za-z0-9]+)/?",
            "zhihu": r"/(?:question/\d+/answer/\d+|p/\d+|zvideo/\d+)",
        }
        if parts.hostname not in hosts.get(platform, set()) or not re.fullmatch(patterns.get(platform, r"(?!)"), parts.path):
            raise ValueError
        allowed = {"__biz", "mid", "idx"} if platform == "wechat" else set()
        if any(key not in allowed for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
            raise ValueError
    except ValueError:
        raise ContractError("canonical_url", path) from None


def _semantics(doc: dict[str, Any]) -> None:
    kind = doc["kind"]
    if kind == "crawl_job":
        q, window = doc["query"], doc["window"]
        if not normalize_query(q["text"]):
            raise ContractError("blank_query", "$.query.text")
        if (q["scope"] == "track" and q["targetId"] is not None) or (q["scope"] == "account" and not q["targetId"]):
            raise ContractError("query_scope", "$.query.targetId")
        if window["from"] and window["to"] and window["from"] > window["to"]:
            raise ContractError("window_order", "$.window")
        if window["filterMode"] == "none" and (window["from"] or window["to"]):
            raise ContractError("window_filter", "$.window")
        if doc["queryId"] != query_id(doc) or doc["jobId"] != digest({"queryId": doc["queryId"], "operation": "search"}):
            raise ContractError("identity_hash", "$.jobId")
    elif kind == "signal_observation":
        if not doc["nativeId"].strip() or doc["nativeId"].strip().casefold() in {"none", "null", "undefined"}:
            raise ContractError("native_id", "$.nativeId")
        if doc["signalId"] != f'{doc["platform"]}:{doc["contentType"]}:{doc["nativeId"]}':
            raise ContractError("signal_identity", "$.signalId")
        published, precision = doc["publishedAt"], doc["publishedPrecision"]
        if (precision == "unknown" and published is not None) or (precision != "unknown" and published is None):
            raise ContractError("publication_precision", "$.publishedAt")
        if published is not None and not _format(published, "date" if precision == "day" else "date-time"):
            raise ContractError("publication_precision", "$.publishedAt")
        if _timestamp(doc["observedAt"]).utcoffset().total_seconds() != 0:
            raise ContractError("observation_not_utc", "$.observedAt")
        if published is not None:
            observed = _timestamp(doc["observedAt"])
            # A day-precision source can be in another timezone; do not invent a clock time.
            if precision == "second" and _timestamp(published) > observed:
                raise ContractError("future_publication", "$.publishedAt")
            if precision == "day" and date.fromisoformat(published) > (observed + timedelta(hours=14)).date():
                raise ContractError("future_publication", "$.publishedAt")
        if doc["updatedAt"] and _timestamp(doc["updatedAt"]) > _timestamp(doc["observedAt"]):
            raise ContractError("future_update", "$.updatedAt")
        if (doc["titleOrigin"] == "missing") != (not doc["title"]):
            raise ContractError("title_origin", "$.titleOrigin")
        _public_url(doc["canonicalUrl"], doc["platform"], "$.canonicalUrl")
        if doc["contentHash"] != content_hash(doc):
            raise ContractError("content_hash", "$.contentHash")
    elif kind == "query_receipt":
        counts, status, pages = doc["counts"], doc["status"], doc["pageReceipts"]
        if _timestamp(doc["completedAt"]) < _timestamp(doc["startedAt"]):
            raise ContractError("receipt_time_order", "$.completedAt")
        if counts["rawRows"] != sum(counts[x] for x in ("emittedRows", "rejectedRows", "duplicateRows", "budgetSkipped")):
            raise ContractError("receipt_counts", "$.counts")
        if counts["searchItems"] != sum(page["contentItems"] for page in pages):
            raise ContractError("search_counts", "$.counts.searchItems")
        if len({p["pageIndex"] for p in pages}) != len(pages):
            raise ContractError("duplicate_page", "$.pageReceipts")
        healthy_pages = bool(pages) and all(p["schemaValid"] and p["processed"] for p in pages)
        if status in {"ok", "empty"}:
            if not healthy_pages or counts["detailFailures"] or doc["errorCode"] is not None:
                raise ContractError("success_evidence", "$.status")
            if doc["stopReason"] not in {"exhausted", "item_limit", "page_limit"} or doc["completeness"] != ("exhausted" if doc["stopReason"] == "exhausted" else "bounded"):
                raise ContractError("receipt_status", "$.completeness")
            if doc["completeness"] == "exhausted" and pages[-1]["hasMore"] is not False:
                raise ContractError("exhaustion_unproven", "$.pageReceipts")
            if status == "empty" and (any(counts.values()) or doc["completeness"] != "exhausted"):
                raise ContractError("empty_unproven", "$.status")
            if status == "ok" and not counts["searchItems"]:
                raise ContractError("use_empty_status", "$.status")
        else:
            reasons = {"auth_required": "auth", "verification_required": "verification", "rate_limited": "rate_limit", "network_error": "network", "timeout": "timeout", "schema_error": "schema", "unsupported": "unsupported", "cancelled": "cancelled"}
            if status == "partial":
                if not counts["emittedRows"] or doc["completeness"] != "incomplete" or doc["stopReason"] not in set(reasons.values()):
                    raise ContractError("partial_unproven", "$.status")
            elif doc["stopReason"] != reasons[status] or doc["completeness"] not in {"incomplete", "unknown"}:
                raise ContractError("receipt_status", "$.status")
        if doc["platform"] == "wechat":
            if doc["provider"] == "mediacrawler" or doc["upstreamCommit"] is not None:
                raise ContractError("receipt_provider", "$.provider")
        elif doc["provider"] != "mediacrawler" or doc["upstreamCommit"] is None:
            raise ContractError("receipt_provider", "$.provider")
        if doc["errorCode"] is not None and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,119}", doc["errorCode"]):
            raise ContractError("error_code", "$.errorCode")
    elif kind == "run_manifest":
        files = {item["path"]: item for item in doc["files"]}
        if len(files) != 3:
            raise ContractError("manifest_paths", "$.files")
        for name, counter in (("jobs.jsonl", "jobs"), ("observations.jsonl", "observations"), ("query_receipts.jsonl", "receipts")):
            if files[name]["rows"] != doc["counts"][counter]:
                raise ContractError("manifest_counts", "$.counts")
        if doc["counts"]["jobs"] != doc["counts"]["receipts"]:
            raise ContractError("manifest_receipts", "$.counts")
    elif kind == "job_plan":
        stats = doc["stats"]
        if stats["registeredQueries"] != stats["eligibleQueries"] + stats["excludedQueries"] or stats["eligibleQueries"] != stats["selectedJobs"] + stats["deferredQueries"] or stats["selectedJobs"] != len(doc["jobs"]):
            raise ContractError("plan_counts", "$.stats")
        if len({j["attemptId"] for j in doc["jobs"]}) != len(doc["jobs"]):
            raise ContractError("duplicate_attempt", "$.jobs")
        for job in doc["jobs"]:
            _semantics(job)
        if doc["planId"] != digest({k: v for k, v in doc.items() if k not in {"planId", "generatedAt"}}):
            raise ContractError("plan_hash", "$.planId")
    elif kind == "review_item":
        expected = {"pending": "not-reviewed", "accepted": "awaiting-primary-evidence", "rejected": "rejected"}
        if doc["promotionStatus"] != expected[doc["status"]]:
            raise ContractError("promotion_status", "$.promotionStatus")
        for row in doc["evidence"]:
            _public_url(row["canonicalUrl"], row["signalId"].split(":", 1)[0], "$.evidence.canonicalUrl")
    elif kind == "runtime_config":
        if any(len(doc[k] or "") > 4096 for k in ("stateDir", "mediacrawlerDir", "profileRoot")):
            raise ContractError("path_length")


def validate(document: Any, *, expected_kind: str | None = None) -> dict[str, Any]:
    """Validate without mutating input or resolving remote references."""
    assert_safe(document)
    if len(canonical_bytes(document)) > MAX_DOCUMENT_BYTES:
        raise ContractError("document_too_large")
    if not isinstance(document, dict) or not isinstance(document.get("kind"), str) or document["kind"] not in KINDS:
        raise ContractError("unknown_kind", "$.kind")
    if expected_kind is not None and document["kind"] != expected_kind:
        raise ContractError("unexpected_kind", "$.kind")
    schema = load_schema()
    _shape(document, schema["$defs"][KINDS[document["kind"]]], schema, "$")
    _semantics(document)
    return document
