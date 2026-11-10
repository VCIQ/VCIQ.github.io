"""Prepare a public WeChat snapshot from one explicitly source-checked review."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from .adapters.wechat import identity
from .adapters.wechat_transport import FetchError
from .batch import ROOT
from .contracts import ContractError, assert_safe, load_json, validate
from .guard import GuardError
from .lead_builder import validate_item
from .review import ReviewStore, pin_reference, read_transaction
from .signal_store import SignalStore

SNAPSHOT = ROOT / "config/innovation_wechat_media.json"
PUBLIC_FIELDS = {"url", "title", "publisher", "publishedAt"}
MAX_ARTICLES = 100


def public_row(row):
    if not isinstance(row, dict) or row.keys() != PUBLIC_FIELDS:
        raise ContractError("wechat_release_fields")
    for key, limit in (("title", 220), ("publisher", 200)):
        value = row[key]
        if (not isinstance(value, str) or not 1 <= len(value) <= limit
                or value != value.strip() or re.search(r"[<>\x00-\x1f\x7f]", value)):
            raise ContractError("wechat_release_text")
    url = row["url"]
    if not isinstance(url, str) or len(url) > 2048 or not url.startswith("https://mp.weixin.qq.com/"):
        raise ContractError("wechat_release_url")
    if identity(url)[1] != url:
        raise ContractError("wechat_release_url")
    published = row["publishedAt"]
    if not isinstance(published, str) or date.fromisoformat(published).isoformat() != published:
        raise ContractError("wechat_release_date")
    assert_safe(row)
    return row


def prepare_snapshot(existing, row):
    if not isinstance(existing, list) or len(existing) > MAX_ARTICLES:
        raise ContractError("wechat_release_snapshot")
    articles = {item["url"]: item for item in map(public_row, existing)}
    if len(articles) != len(existing):
        raise ContractError("wechat_release_duplicate_url")
    row = public_row(row)
    articles[row["url"]] = row
    if len(articles) > MAX_ARTICLES:
        raise ContractError("wechat_release_snapshot")
    return sorted(articles.values(), key=lambda article: (article["publishedAt"], article["url"]), reverse=True)


def reviewed_article(source, review, candidate_key, fingerprint, confirmed_url):
    if source.root != review.root:
        raise ContractError("review_state_mismatch")
    with read_transaction(source.db), read_transaction(review.db):
        row = review.db.execute("""SELECT c.item_json, c.snapshot_json FROM candidates c
            JOIN decisions d ON c.candidate_key=d.candidate_key AND c.fingerprint=d.fingerprint
            WHERE c.active=1 AND c.candidate_key=? AND c.fingerprint=? AND d.decision='accepted'""",
            (candidate_key, fingerprint)).fetchone()
        if not row:
            raise ContractError("wechat_release_accepted_revision_required")
        item = validate_item(json.loads(row["item_json"]))
        if item["candidateKey"] != candidate_key or item["candidateFingerprint"] != fingerprint:
            raise ContractError("review_fingerprint")
        doc = validate(json.loads(row["snapshot_json"])["observation"], expected_kind="signal_observation")
        if (doc["platform"], doc["contentType"], doc["titleOrigin"], doc["publishedPrecision"]) != (
                "wechat", "article", "upstream", "day"):
            raise ContractError("wechat_release_original_required")
        if confirmed_url != doc["canonicalUrl"]:
            raise ContractError("wechat_release_source_confirmation_mismatch")
        evidence = item["evidence"][0]
        reference = (doc["signalId"], doc["contentHash"])
        pinned = source.db.execute("SELECT signal_id,content_hash FROM evidence_pins WHERE reference_id=?",
                                   (pin_reference(item, evidence),)).fetchone()
        if (not pinned or tuple(pinned) != reference or (evidence["signalId"], evidence["contentHash"]) != reference
                or evidence["canonicalUrl"] != doc["canonicalUrl"] or evidence["publishedAt"] != doc["publishedAt"]):
            raise ContractError("review_evidence_not_pinned")
        current = source.get_signal(doc["signalId"])
        if not current or any(current["latest"][key] != doc[key] for key in ("contentHash", "canonicalUrl", "author")):
            raise ContractError("review_evidence_changed")
        return public_row({"url": doc["canonicalUrl"], "title": doc["title"],
                           "publisher": doc["author"]["displayName"], "publishedAt": doc["publishedAt"]})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--candidate-key", required=True)
    parser.add_argument("--candidate-fingerprint", required=True)
    parser.add_argument("--confirmed-source-url", required=True,
                        help="Canonical URL opened and verified by the release operator")
    args = parser.parse_args(argv)
    try:
        with SignalStore(args.state_dir, readonly=True) as source, ReviewStore(args.state_dir, readonly=True) as review:
            article = reviewed_article(source, review, args.candidate_key, args.candidate_fingerprint,
                                       args.confirmed_source_url)
        print(json.dumps(prepare_snapshot(load_json(SNAPSHOT), article), ensure_ascii=False, indent=2))
        return 0
    except (ContractError, FetchError, GuardError) as exc:
        code = exc.code
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        code = "wechat_release_input_or_io_error"
    print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
