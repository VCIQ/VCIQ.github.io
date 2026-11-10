"""Opt-in cross-job writer reservation and versioned receipt archival."""
from __future__ import annotations

import base64
import hashlib
import os
import re
from contextlib import closing
from datetime import UTC, datetime, timedelta

from .company_profile_writer_crawl_receipt import MAX_SELECTED
from .company_profile_writer_pr_gate import ALLOWED_FILES, SMOKE_BASE_BRANCH
from .company_profile_writer_pr_handoff import GitHubCli, RESERVATION, SMOKE_RESERVATION
from .company_profile_writer_receipt_journal import (
    JournalError, _MAX_DOC, _decode, _encode, _inspect_records, _stamp,
    _validate_id, _validate_sha, _validate_slugs,
)

_SCOPES = {
    "main": ("production", RESERVATION),
    SMOKE_BASE_BRANCH: ("smoke", SMOKE_RESERVATION),
}
_RECORD_NAME = re.compile(r"(?:manifest|reservation|complete|handoff|start-[0-9]{2}|receipt-[0-9]{2})\.json")
_RETENTION = timedelta(days=365)


def _checksum(raw):
    return base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii")


def _version(value):
    if type(value) is not str or value in ("", "null") or len(value) > 1024:
        raise JournalError("ARCHIVE_VERSION_UNCONFIRMED")
    return value


class S3ReceiptStore:
    """Use a trusted, bounded AWS SDK client supplied by the operator."""

    def __init__(self, client, *, bucket: str, owner: str):
        if (type(bucket) is not str or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
            or type(owner) is not str or not re.fullmatch(r"[0-9]{12}", owner)):
            raise JournalError("ARCHIVE_CONFIG_INVALID")
        self.client = client
        self.bucket = bucket
        self.owner = owner

    def _target(self, scope, run_id, name):
        _validate_id(run_id)
        if scope not in ("production", "smoke") or not _RECORD_NAME.fullmatch(name):
            raise JournalError("ARCHIVE_KEY_INVALID")
        return {
            "Bucket": self.bucket,
            "Key": f"vciq/company-profile-writer/{scope}/run-{run_id}/{name}",
            "ExpectedBucketOwner": self.owner,
        }

    def put(self, scope, run_id, name, value):
        target = self._target(scope, run_id, name)
        raw = _encode(value)
        retain_until = datetime.now(UTC).replace(microsecond=0) + _RETENTION
        try:
            response = self.client.put_object(
                **target, Body=raw, ContentType="application/json", IfNoneMatch="*",
                ChecksumSHA256=_checksum(raw), ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=retain_until,
            )
            version = _version(response.get("VersionId"))
        except Exception:
            raise JournalError("ARCHIVE_WRITE_UNCONFIRMED") from None
        verified = self._get(target, version=version)
        if verified[0] != raw or verified[2] < retain_until:
            raise JournalError("ARCHIVE_WRITE_UNCONFIRMED")

    def read(self, scope, run_id, name):
        return self._get(self._target(scope, run_id, name))

    def _get(self, target, *, version=None):
        options = {} if version is None else {"VersionId": version}
        try:
            response = self.client.get_object(**target, **options, ChecksumMode="ENABLED")
        except Exception as exc:
            error = getattr(exc, "response", None)
            if (version is None and isinstance(error, dict)
                and error.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404
                and error.get("Error", {}).get("Code") == "NoSuchKey"):
                return None
            raise JournalError("ARCHIVE_READ_UNCONFIRMED") from None
        try:
            with closing(response["Body"]) as body:
                raw = body.read(_MAX_DOC + 1)
            stored_version = _version(response.get("VersionId"))
            retain_until = response.get("ObjectLockRetainUntilDate")
            if (version is not None and stored_version != version
                or response.get("DeleteMarker")
                or response.get("ObjectLockMode") != "COMPLIANCE"
                or not isinstance(retain_until, datetime) or retain_until.tzinfo is None
                or retain_until <= datetime.now(UTC)
                or type(raw) is not bytes or len(raw) > _MAX_DOC
                or response.get("ChecksumSHA256") != _checksum(raw)):
                raise JournalError("ARCHIVE_READ_UNCONFIRMED")
        except Exception:
            raise JournalError("ARCHIVE_READ_UNCONFIRMED") from None
        return raw, stored_version, retain_until


class CrossJobReceiptArchive:
    """Hold the existing fixed GitHub reservation across jobs until human triage."""

    def __init__(self, github, store: S3ReceiptStore, *, authorized: bool = False):
        if authorized is not True:
            raise JournalError("ARCHIVE_EXPLICIT_APPROVAL_REQUIRED")
        if isinstance(github, GitHubCli) and os.name == "posix" and os.geteuid() == 0:
            raise JournalError("ARCHIVE_UNPRIVILEGED_OPERATOR_REQUIRED")
        config = _SCOPES.get(getattr(github, "base_branch", None))
        if (config is None or getattr(github, "reservation_ref", None) != config[1]
            or not isinstance(store, S3ReceiptStore)):
            raise JournalError("ARCHIVE_CONFIG_INVALID")
        self.github = github
        self.store = store
        self.scope, self.reservation = config
        self.run_id = None

    def begin(self, manifest):
        if self.run_id is not None:
            raise JournalError("ARCHIVE_ALREADY_STARTED")
        self.run_id = manifest["runId"]
        self.base_sha = manifest["baseSha"]
        self._check_remote(reserved=False)
        # Reserve the run ID in immutable storage before attempting the GitHub
        # mutation. Replaying an archived ID cannot create a new GitHub ref.
        self._put("manifest.json", manifest)
        manifest_digest = hashlib.sha256(_encode(manifest)).hexdigest()
        try:
            self.anchor_sha = self.github.create_reservation_commit(self.base_sha, manifest_digest)
            _validate_sha(self.anchor_sha, commit=True)
            if self.anchor_sha == self.base_sha:
                raise JournalError("ARCHIVE_RESERVATION_UNCONFIRMED")
            self.github.create_ref(self.reservation, self.anchor_sha)
        except Exception:
            raise JournalError("ARCHIVE_RESERVATION_UNCONFIRMED") from None
        self._check_remote(reserved=True)
        self._put("reservation.json", {
            "ref": self.reservation,
            "anchorSha": self.anchor_sha,
            "manifestSha256": manifest_digest,
        })

    def _check_remote(self, *, reserved):
        expected = [self.reservation] if reserved else []
        try:
            if (self.github.base_sha() == self.base_sha
                and not self.github.open_proposals()
                and self.github.candidate_branches() == expected
                and (not reserved or self.github.reservation_sha() == self.anchor_sha)):
                return
        except Exception:
            raise JournalError("ARCHIVE_RESERVATION_UNCONFIRMED") from None
        raise JournalError("ARCHIVE_RESERVATION_BLOCKED")

    def _put(self, name, value):
        self.store.put(self.scope, self.run_id, name, value)

    def start_company(self, index, slug, started_at):
        self._put(f"start-{index:02d}.json", {
            "slug": slug,
            "dispatchIntentAt": started_at,
        })
        self._check_remote(reserved=True)

    def record_company(self, name, entry):
        self._put(name, entry)

    def complete(self, final):
        if final.get("runId") != self.run_id:
            raise JournalError("ARCHIVE_COMPLETION_RUN_MISMATCH")
        self._check_remote(reserved=True)
        self._put("complete.json", final)

    def claim_handoff(self, *, attempt, candidate_sha256):
        self._check_remote(reserved=True)
        self._put("handoff.json", {
            "anchorSha": self.anchor_sha,
            "attempt": attempt,
            "candidateFilesSha256": candidate_sha256,
        })


def inspect_archived_run(store: S3ReceiptStore, *, scope: str, run_id: str) -> dict:
    """Read-only triage after job loss. Stop the old worker before inspecting."""
    records = {}
    versions = {}

    def read_optional(name):
        result = store.read(scope, run_id, name)
        if result is not None:
            raw, versions[name], _ = result
            records[name] = _decode(raw)
            if _encode(records[name]) != raw:
                raise JournalError("ARCHIVE_RECORD_NOT_CANONICAL")

    read_optional("manifest.json")
    if "manifest.json" not in records:
        return {"state": "manifest_missing", "runId": run_id,
                "manualTriageRequired": True, "automaticResumeAuthorized": False}

    manifest = records["manifest.json"]
    selected = _validate_slugs(manifest.get("selectedSlugs"))
    read_optional("reservation.json")
    read_optional("complete.json")
    read_optional("handoff.json")
    for index in range(MAX_SELECTED):
        read_optional(f"start-{index:02d}.json")
        read_optional(f"receipt-{index:02d}.json")
    journal_names = set(records) - {
        f"start-{index:02d}.json" for index in range(len(selected))
    } - {"reservation.json", "handoff.json"}
    state = _inspect_records(run_id, journal_names, records.__getitem__)
    reservation = records.get("reservation.json")
    if reservation is not None:
        expected_ref = RESERVATION if scope == "production" else SMOKE_RESERVATION
        if (set(reservation) != {"ref", "anchorSha", "manifestSha256"}
            or reservation["ref"] != expected_ref
            or reservation["anchorSha"] == manifest["baseSha"]
            or reservation["manifestSha256"] != hashlib.sha256(_encode(manifest)).hexdigest()):
            raise JournalError("ARCHIVE_RESERVATION_RECORD_INVALID")
        _validate_sha(reservation["anchorSha"], commit=True)
    handoff = records.get("handoff.json")
    if handoff is not None:
        if (state["state"] != "recorded" or reservation is None
            or set(handoff) != {"anchorSha", "attempt", "candidateFilesSha256"}
            or handoff["anchorSha"] != reservation["anchorSha"]
            or type(handoff["attempt"]) is not int or not 1 <= handoff["attempt"] <= 20
            or not isinstance(handoff["candidateFilesSha256"], dict)
            or set(handoff["candidateFilesSha256"]) != ALLOWED_FILES):
            raise JournalError("ARCHIVE_HANDOFF_RECORD_INVALID")
        for digest in handoff["candidateFilesSha256"].values():
            _validate_sha(digest)
    companies = {}
    last_time = _stamp(manifest["runStartedAt"])
    blocked = False
    for index, slug in enumerate(selected):
        intent = records.get(f"start-{index:02d}.json")
        entry = records.get(f"receipt-{index:02d}.json")
        if intent is None:
            if entry is not None:
                raise JournalError("ARCHIVE_COMMAND_SEQUENCE_INVALID")
            companies[slug] = "no_dispatch_record"
            blocked = True
            continue
        if (reservation is None or blocked or set(intent) != {"slug", "dispatchIntentAt"}
            or intent["slug"] != slug
            or _stamp(intent["dispatchIntentAt"]) < last_time):
            raise JournalError("ARCHIVE_COMMAND_SEQUENCE_INVALID")
        last_time = _stamp(intent["dispatchIntentAt"])
        if entry is None:
            companies[slug] = "possibly_dispatched"
            blocked = True
            continue
        captured = _stamp(entry["payload"]["receipt"]["capturedAt"])
        if captured < last_time:
            raise JournalError("ARCHIVE_COMMAND_SEQUENCE_INVALID")
        companies[slug] = "verified_receipt"
        last_time = captured
    state.update({
        "baseSha": manifest["baseSha"],
        "selectionSha256": manifest["selectionSha256"],
        "runStartedAt": manifest["runStartedAt"],
        "reservation": reservation,
        "handoff": handoff,
        "companies": companies,
        "archiveVersions": versions,
        "manualTriageRequired": True,
    })
    if state["state"] == "recorded":
        state["runCompletedAt"] = records["complete.json"]["completedAt"]
    return state
