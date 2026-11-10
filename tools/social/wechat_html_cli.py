"""Preview or import one operator-saved WeChat HTML file, entirely offline."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .adapters.wechat import NORMALIZER_VERSION, _normalize_original, identity
from .adapters.wechat_transport import FetchError
from .batch import ROOT, build_batch, private_root, read_batch, read_private, seal_batch
from .contracts import OPERATOR_HTML, ContractError, digest, normalize_query, query_id, validate
from .guard import GuardError, assert_unchanged, output_path, protected_snapshot
from .lead_builder import build_leads
from .planning_cli import revision
from .review import ReviewStore
from .review_cli import registry_input
from .scheduler import utc
from .shadow_state import run_lock
from .signal_store import SignalStore

MAX_HTML_BYTES = 8 * 1024 * 1024


def records(canonical, keyword, html, config_hash, commit, now):
    term = {"text": keyword, "kind": "keyword"}
    job = {
        "schemaVersion": 1, "kind": "crawl_job", "runId": str(uuid4()), "attemptId": str(uuid4()),
        "platform": "wechat", "engine": "wechat-public", "provider": OPERATOR_HTML,
        "operation": "import-html", "mode": "shadow",
        "query": {"text": keyword, "scope": "track", "targetId": None,
                  "termRefs": [f"{OPERATOR_HTML}:{digest(term)}"], "providerFilters": {}},
        "trackRefs": [OPERATOR_HTML], "window": {"from": None, "to": None, "filterMode": "none"},
        "limits": {"maxSearchPages": 1, "maxRecords": 1, "maxWallSeconds": 60},
        "vciqCommit": commit, "configHash": config_hash, "upstreamCommit": None,
        "policyVersion": "operator-html-v1",
    }
    job["queryId"] = query_id(job)
    job["jobId"] = digest({"queryId": job["queryId"], "operation": job["operation"]})
    validate(job, expected_kind="crawl_job")
    observation = _normalize_original(job, {"terms": [term]}, canonical, html, now,
                                      access_status="unverified")
    receipt = {
        "schemaVersion": 1, "kind": "query_receipt", "startedAt": utc(now), "completedAt": utc(now),
        **{key: job[key] for key in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")},
        "status": "ok", "completeness": "bounded", "stopReason": "item_limit",
        "counts": {"searchItems": 0, "rawRows": 1, "emittedRows": 1, "rejectedRows": 0,
                   "duplicateRows": 0, "budgetSkipped": 0, "detailFailures": 0},
        "pageReceipts": [], "normalizerVersion": NORMALIZER_VERSION, "patchsetHash": digest([]),
        "errorCode": None,
    }
    return [job], [receipt], [observation]


def import_html(root, roots, raw, url, keyword, *, apply):
    _, canonical = identity(url)
    keyword = normalize_query(keyword)
    if not keyword or len(keyword) > 512:
        raise ContractError("operator_html_keyword")
    source_hash = hashlib.sha256(raw).hexdigest()
    config_hash = digest({"sourceSha256": source_hash, "canonicalUrl": canonical, "keyword": keyword})
    companies = registry_input(root, roots)
    now = datetime.now(UTC)
    commit = revision(ROOT)
    if not apply:
        batch = build_batch(*records(canonical, keyword, raw.decode("utf-8-sig"), config_hash, commit, now),
                            created_at=utc(now))
    else:
        relative = f"operator-html/{config_hash}"
        scheduler_db = output_path(root, "state.sqlite3", repo_roots=roots)
        if scheduler_db.exists():
            raise GuardError("operator_html_separate_state_required")
        with run_lock(root, roots):
            if output_path(root, "state.sqlite3", repo_roots=roots).exists():
                raise GuardError("operator_html_separate_state_required")
            manifest = output_path(root, relative + "/manifest.json", repo_roots=roots)
            if manifest.parent.exists():
                batch = read_batch(root, relative, repo_roots=roots)
                jobs, observations = batch.records("jobs.jsonl"), batch.records("observations.jsonl")
                if (len(jobs) != 1 or len(observations) != 1 or jobs[0]["provider"] != OPERATOR_HTML
                        or jobs[0]["configHash"] != config_hash or jobs[0]["query"]["text"] != keyword
                        or observations[0]["canonicalUrl"] != canonical):
                    raise ContractError("operator_html_batch_mismatch")
            else:
                batch = seal_batch(
                    root, relative, *records(canonical, keyword, raw.decode("utf-8-sig"), config_hash, commit, now),
                    repo_roots=roots, created_at=utc(now),
                )
            with SignalStore(root, repo_roots=roots) as source, ReviewStore(root, repo_roots=roots) as review:
                imported = source.import_batch(batch)
                queue = review.materialize(source, companies)

    (observation,) = batch.records("observations.jsonl")
    result = {
        "ok": True, "source": OPERATOR_HTML, "sourceSha256": source_hash,
        "title": observation["title"], "publisher": observation["author"]["displayName"],
        "publishedAt": observation["publishedAt"], "accessStatus": observation["accessStatus"],
        "candidateCount": len(build_leads(observation, companies)), "batchIntegrityChecked": True,
        "applied": apply, "writesPerformed": apply, "liveExecuted": False, "publish": False,
    }
    if apply:
        result.update(duplicate=imported["duplicate"], insertedSignals=imported["insertedSignals"],
                      reviewCandidateCount=queue["candidateCount"], queueVersion=queue["queueVersion"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--html", required=True, help="UTF-8 HTML path relative to the private state")
    parser.add_argument("--url", required=True, help="Original WeChat article URL; never fetched")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--apply", action="store_true", help="Seal and import into the private queue")
    args = parser.parse_args(argv)
    before = None
    try:
        roots = (ROOT,)
        root = private_root(args.state_dir, roots)
        before = protected_snapshot(ROOT)
        raw = read_private(root, args.html, roots, maximum=MAX_HTML_BYTES)
        result = import_html(root, roots, raw, args.url, args.keyword, apply=args.apply)
        assert_unchanged(before, repo_root=ROOT)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContractError, FetchError, GuardError) as exc:
        code = exc.code
    except (OSError, UnicodeError, ValueError):
        code = "operator_html_input_or_io_error"
    if before is not None:
        try:
            assert_unchanged(before, repo_root=ROOT)
        except GuardError:
            code = "production_modified"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": False, "publish": False}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
