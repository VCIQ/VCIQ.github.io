"""Release human-reviewed investor announcements into the existing research ledger.

The daily official-source scout is navigation discovery, NOT evidence.  This
offline tool accepts a deliberate reviewer approval tied to a specific scout
candidate and a fully documented original article.  It neither fetches URLs nor
creates a second homepage news writer.  A successful main-branch commit triggers
the existing Pages publication bridge.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "config/innovation_global_investors.json"
EVIDENCE = ROOT / "config/innovation_investor_evidence.json"
IDENTITIES = ROOT / "config/innovation_investor_project_identities.json"
PARTICIPATIONS = {"lead", "co-lead", "participant", "sole-investor", "disclosed-investor"}
RECORD_FIELDS = {
    "id", "institutionId", "project", "kind", "date", "datePrecision", "title", "summary",
    "round", "participation", "roundAmount", "investorAmount", "speakers", "linkedPerson",
    "resultStatus", "realizedProceeds", "source", "nextCheck",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _string(value: object, label: str, limit: int = 3000) -> str:
    _require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
             f"missing or invalid {label}")
    return value.strip()


def _day(value: object, label: str) -> date:
    value = _string(value, label, 10)
    _require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)), f"invalid {label}")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"invalid calendar day for {label}") from error


def _url(value: object, label: str) -> tuple[str, str]:
    raw = _string(value, label, 2000)
    p = urlsplit(raw)
    host = (p.hostname or "").casefold()
    _require(p.scheme == "https" and bool(host) and not p.username and not p.password
             and p.port in (None, 443) and not p.query and not p.fragment,
             f"unsafe or non-canonical {label}")
    try:
        ipaddress.ip_address(host)
        raise ValueError(f"IP address not permitted for {label}")
    except ValueError as error:
        if str(error).startswith("IP address not permitted"):
            raise
    _require(host not in {"localhost"} and not host.endswith((".local", ".internal")),
             f"non-public {label}")
    return host.removeprefix("www."), (p.path.rstrip("/") or "/")


def _record(row: object, lead: dict, firm: dict, today: date) -> dict:
    _require(isinstance(row, dict), "reviewed record must be an object")
    _require(set(row) == RECORD_FIELDS, f"record must use canonical fields: {row.get('id', '?')}")
    item_id = _string(row["id"], "record.id", 120)
    _require(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item_id)), "unsafe evidence ID")
    _require(row["institutionId"] == lead["institutionId"] == firm["id"], "institution mismatch")
    _string(row["project"], "project", 160)
    _require(row["kind"] in {"investment", "viewpoint"}, "quick release only permits investments or authored viewpoints")
    _require(row["datePrecision"] == "day", "quick release requires original day precision")
    published = _day(row["date"], "article date")
    _require(0 <= (today - published).days < 14, "article is outside the homepage's 14-day window")
    _string(row["title"], "title", 320)
    _string(row["summary"], "reviewed summary", 1400)
    _string(row["nextCheck"], "next check", 600)
    source = row["source"]
    _require(isinstance(source, dict) and set(source) == {"url", "title", "publisher", "kind", "publishedAt", "locator"},
             "source must have the canonical provenance fields")
    _require(source["kind"] == "investor-official", "media and secondary sources cannot enter quick release")
    _string(source["title"], "source title", 350)
    _string(source["publisher"], "source publisher", 200)
    _string(source["locator"], "original article passage locator", 1000)
    _require(_day(source["publishedAt"], "source publication date") == published,
             "source date and reported date differ")
    candidate_host, candidate_path = _url(lead["originalUrl"], "scout candidate URL")
    source_host, source_path = _url(source["url"], "reviewed source URL")
    official_host, _ = _url(firm["officialUrl"], "institution official URL")
    _require((candidate_host, candidate_path) == (source_host, source_path)
             and source_host == official_host, "source does not match exact official scout candidate")
    _require(row["resultStatus"] is None and row["realizedProceeds"] is None,
             "unsupported returns or outcome assertions")
    _require(row["linkedPerson"] is None, "article authors cannot be promoted to deal owners")
    _require(isinstance(row["speakers"], list) and len(row["speakers"]) <= 12, "invalid speaker list")
    for speaker in row["speakers"]:
        _require(isinstance(speaker, dict) and set(speaker) ==
                 {"name", "roleAtPublication", "attribution", "projectResponsibility"}, "invalid speaker schema")
        _string(speaker["name"], "author", 200)
        _string(speaker["roleAtPublication"], "author role at publication", 320)
        _string(speaker["projectResponsibility"], "author responsibility caveat", 500)
        _require(speaker["attribution"] == "paraphrase", "direct quotations require a separate review path")
    if row["kind"] == "investment":
        _require(row["participation"] in PARTICIPATIONS, "investment participation unverified")
        _require(row["round"] is None or isinstance(row["round"], str), "invalid financing round")
        for key in ("roundAmount", "investorAmount"):
            amount = row[key]
            _require(amount is None or (isinstance(amount, dict) and set(amount) == {"value", "currency"}
                and type(amount["value"]) in (int, float) and amount["value"] > 0
                and isinstance(amount["currency"], str)
                and re.fullmatch(r"[A-Z]{3}", amount["currency"]) is not None), f"invalid {key}")
    else:
        _require(all(row[field] is None for field in ("round", "participation", "roundAmount", "investorAmount")),
                 "viewpoint cannot be disguised as a transaction")
        _require(bool(row["speakers"]), "authored viewpoint needs attributable speaker")
    return row


def prepare_release(batch: dict, queue: dict, roster: dict, evidence: dict,
                    identities: dict, today: date) -> tuple[dict, dict, dict]:
    _require(batch.get("schemaVersion") == 1 and isinstance(batch.get("reviews"), list)
             and 1 <= len(batch["reviews"]) <= 5, "expected 1-5 explicitly approved reviews")
    _require(queue.get("mode") == "offline-human-review-queue" and queue.get("autoPublication") is False,
             "only the unpromoted human review queue is accepted")
    leads = {row["candidateId"]: row for row in queue.get("reviewLeads", [])}
    firms = {row["id"]: row for row in roster.get("institutions", [])}
    _require(len(firms) == 30 and evidence.get("schemaVersion") == 1
             and identities.get("schemaVersion") == 1, "unexpected canonical registry schema")
    current = list(evidence["records"])
    projects = list(identities["projects"])
    record_ids = {row["id"] for row in current}
    seen_candidate_ids: set[str] = set()
    original_keys = {(row["institutionId"], row["project"], row["kind"], row["source"]["url"])
                     for row in current}
    deal_keys = {(row["institutionId"], row["project"], row["round"], row["date"])
                 for row in current if row["kind"] == "investment"}
    names = {name.casefold() for p in projects for name in p["observedNames"]}
    ids = {p["id"] for p in projects}
    added_sources: list[str] = []
    for review in batch["reviews"]:
        _require(isinstance(review, dict) and set(review) ==
                 {"candidateId", "decision", "originalArticleVerified", "records", "newProjectIdentity"},
                 "invalid review packet schema")
        candidate_id = _string(review["candidateId"], "candidateId", 160)
        _require(candidate_id not in seen_candidate_ids, "repeated scout candidate approval")
        seen_candidate_ids.add(candidate_id)
        _require(review["decision"] == "approved" and review["originalArticleVerified"] is True,
                 "human original-article approval is required")
        lead = leads.get(candidate_id)
        _require(lead is not None and lead.get("publicationAllowed") is False
                 and lead.get("type") != "source-navigation-only", "candidate is not a review lead")
        firm = firms.get(lead["institutionId"])
        _require(firm is not None, "unknown institution in review queue")
        rows = review["records"]
        _require(isinstance(rows, list) and 1 <= len(rows) <= 3, "review must contain 1-3 records")
        project_name = None
        source_url = None
        for raw in rows:
            row = _record(raw, lead, firm, today)
            _require(row["id"] not in record_ids, "evidence ID already recorded")
            record_ids.add(row["id"])
            _require(project_name in (None, row["project"]), "one scout candidate cannot mix project identities")
            project_name = row["project"]
            source_url = row["source"]["url"]
            unique_key = (row["institutionId"], row["project"], row["kind"], source_url)
            _require(unique_key not in original_keys, "official article/kind already present in evidence")
            original_keys.add(unique_key)
            if row["kind"] == "investment":
                deal = (row["institutionId"], row["project"], row["round"], row["date"])
                _require(deal not in deal_keys, "duplicate round/date investment disclosure")
                deal_keys.add(deal)
            current.append(row)
        identity = review["newProjectIdentity"]
        if identity is None:
            _require(project_name.casefold() in names,
                     "unmapped company requires a separately attested canonical identity")
        else:
            _require(isinstance(identity, dict) and set(identity) in (
                {"id", "name", "observedNames", "identityEvidenceUrls"},
                {"id", "name", "observedNames", "identityEvidenceUrls", "identityNote"}),
                "invalid project identity schema")
            _require(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",
                                        _string(identity["id"], "new project ID", 120))), "unsafe project ID")
            _require(identity["id"] not in ids, "duplicate project ID")
            _require(_string(identity["name"], "project name", 160) == project_name,
                     "new project identity differs from the reviewed record")
            _require(isinstance(identity["observedNames"], list)
                     and identity["observedNames"] == [project_name],
                     "only the verified project name is accepted as a new alias")
            _require(identity["identityEvidenceUrls"] == [source_url],
                     "new identity must cite this original source")
            _require(project_name.casefold() not in names, "existing project identity must be reused")
            if "identityNote" in identity:
                _string(identity["identityNote"], "identity caveat", 600)
            projects.append(identity)
            ids.add(identity["id"])
            names.add(project_name.casefold())
        added_sources.append(source_url)
    staged_evidence = {**evidence, "records": current}
    staged_identities = ({**identities, "projects": projects}
                         if len(projects) > len(identities["projects"]) else identities)
    report = {"status": "reviewed-not-yet-deployed", "newEvidenceRecords": len(current) - len(evidence["records"]),
              "reviewedOfficialArticles": len(added_sources), "candidateIds": sorted(seen_candidate_ids),
              "expectedHomepageSourceUrls": sorted(added_sources), "reviewedAt": today.isoformat(),
              "newCanonicalProjects": len(projects) - len(identities["projects"]),
              "handoff": "commit canonical evidence; existing Pages builds and deploys"}
    return staged_evidence, staged_identities, report


def append_canonical_json(path: Path, key: str, items: list[dict], *, reviewed_at: str) -> None:
    """Preserve the existing manually curated one-record-per-line ledger format.

    Reformatting every historical evidence record creates a noisy, unreviewable
    PR. Refuse to modify unfamiliar JSON layouts instead of silently rewriting
    the whole file.
    """
    if not items:
        return
    original = path.read_text(encoding="utf-8")
    parsed = json.loads(original)
    _require(isinstance(parsed.get(key), list), f"missing canonical array: {key}")
    _require(re.search(r"\n  \]\s*\}\s*$", original) is not None,
             f"unexpected canonical {key} layout")
    _require(f'"{key}": [' in original, f"unexpected canonical key: {key}")
    if key == "records":
        lines = [f"    {json.dumps(item, ensure_ascii=False, separators=(',', ':'))}" for item in items]
    else:
        lines = ["\n".join("    " + line for line in json.dumps(
            item, ensure_ascii=False, indent=2).splitlines()) for item in items]
    end = re.search(r"\n  \]\s*\}\s*$", original)
    assert end is not None
    prefix, suffix = original[:end.start()], original[end.start():]
    _require(bool(prefix.strip()), "empty canonical evidence object")
    edited = prefix + ("," if parsed[key] else "") + "\n" + ",\n".join(lines) + suffix
    edited, count = re.subn(r'("reviewedAt"\s*:\s*")[^"]+(")',
                            lambda m: m.group(1) + reviewed_at + m.group(2), edited, count=1)
    _require(count == 1, "missing top-level reviewedAt timestamp")
    updated = json.loads(edited)
    _require(len(updated[key]) == len(parsed[key]) + len(items), "canonical append mismatch")
    path.write_text(edited, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("validate", "apply"), required=True)
    p.add_argument("--review-queue", required=True, type=Path)
    p.add_argument("--batch-json", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--roster", type=Path, default=ROSTER)
    p.add_argument("--evidence", type=Path, default=EVIDENCE)
    p.add_argument("--identities", type=Path, default=IDENTITIES)
    p.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    args = p.parse_args()
    _string(args.actor, "approved operator", 120)
    today = _day(args.as_of, "review time")
    evidence, identities, report = prepare_release(
        json.loads(args.batch_json),
        json.loads(args.review_queue.read_text(encoding="utf-8")),
        json.loads(args.roster.read_text(encoding="utf-8")),
        json.loads(args.evidence.read_text(encoding="utf-8")),
        json.loads(args.identities.read_text(encoding="utf-8")), today,
    )
    report["actor"] = args.actor
    if args.mode == "apply":
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        original_evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        original_identities = json.loads(args.identities.read_text(encoding="utf-8"))
        append_canonical_json(args.evidence, "records",
                              evidence["records"][len(original_evidence["records"]):],
                              reviewed_at=reviewed_at)
        append_canonical_json(args.identities, "projects",
                              identities["projects"][len(original_identities["projects"]):],
                              reviewed_at=reviewed_at)
        report["status"] = "local-ledger-updated-awaiting-commit-and-pages"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
