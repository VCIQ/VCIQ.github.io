"""Bind #668's queue transition validation to #665's Draft-PR adapter.

Review-only composition: no CLI, scheduler hook, account access, network I/O,
token handling or import-time work. The underlying handoff can mutate remote
refs only after a separate, explicit submit(..., authorized=True) call.

No coverage-only changes are accepted here. Those require independent
pre-crawl provenance and a future separately reviewed contract.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from .company_profile_refresh_queue import build_queue
from .company_profile_writer_coverage_attestation import (
    CoverageError, attest_coverage,
)
from .company_profile_writer_pinned_catalog import (
    PinnedCatalogError, pinned_catalog,
)
from .company_profile_writer_pr_gate import ALLOWED_FILES
from .company_profile_writer_pr_handoff import HandoffError, Snapshot, _sha
from .company_profile_writer_transition_gate import (
    MAX_RUN_DURATION, TransitionError, _stamp, check_transition,
)
from .venture_profile_extraction import (
    parse_catalog,
)

QUEUE = "public/data/company_profile_refresh_queue.json"
PROFILES = "public/data/venture_profiles.json"
ARTICLES = "public/data/articles.json"
CATALOG = "lib/catalog-data.ts"
REGISTRY_TS = "lib/company-registry.ts"
REGISTRY_JSON = "config/company_registry.json"
MAX_RECORD_BYTES = 8 * 1024 * 1024


class EvidenceError(HandoffError):
    """A fixed error code, without file content or identity in its message."""


def _parse(data: bytes | str) -> dict:
    if not isinstance(data, (bytes, str)):
        raise EvidenceError("EVIDENCE_FORMAT_INVALID")
    if len(data if isinstance(data, bytes) else data.encode("utf-8")) > MAX_RECORD_BYTES:
        raise EvidenceError("EVIDENCE_SIZE_INVALID")
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("EVIDENCE_DUPLICATE_KEY")
            result[key] = value
        return result
    def no_nonfinite(_):
        raise EvidenceError("EVIDENCE_NONFINITE_NUMBER")
    try:
        result = json.loads(data, object_pairs_hook=no_duplicates,
                            parse_constant=no_nonfinite)
    except EvidenceError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceError("EVIDENCE_JSON_INVALID") from None
    if not isinstance(result, dict):
        raise EvidenceError("EVIDENCE_OBJECT_REQUIRED")
    return result


@dataclass(frozen=True)
class EvidenceBoundWorkspace:
    """Read from one isolated detached checkout, never from an operator path.

    `pre_crawl_selection` must be captured from the exact queued selection
    before any crawl or mark-processed operation. Its provenance is still
    unverified by this module, and must be supplied by the future workflow.
    """

    workspace: object
    pre_crawl_selection: dict
    run_started_at: str
    run_completed_at: str
    coverage_snapshot: dict | None = None
    coverage_report: dict | None = None
    coverage_updated_at: str | None = None

    def __post_init__(self):
        if not isinstance(self.pre_crawl_selection, dict):
            raise EvidenceError("EVIDENCE_SELECTION_REQUIRED")
        # Freeze the mutable input without calling untrusted hooks.
        try:
            raw = json.dumps(self.pre_crawl_selection, ensure_ascii=False,
                             sort_keys=True, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, RecursionError):
            raise EvidenceError("EVIDENCE_SELECTION_INVALID") from None
        object.__setattr__(self, "pre_crawl_selection", _parse(raw))
        supplied = (self.coverage_snapshot is not None,
                    self.coverage_report is not None,
                    self.coverage_updated_at is not None)
        if any(supplied) and not all(supplied):
            raise EvidenceError("EVIDENCE_COVERAGE_INCOMPLETE")
        for name in ("coverage_snapshot", "coverage_report"):
            value = getattr(self, name)
            if value is not None:
                try:
                    frozen = json.dumps(value, ensure_ascii=False,
                                        sort_keys=True, allow_nan=False).encode("utf-8")
                except (TypeError, ValueError, RecursionError):
                    raise EvidenceError("EVIDENCE_COVERAGE_INVALID") from None
                object.__setattr__(self, name, _parse(frozen))

    def _tracked_bytes(self, name: str, base_sha: str) -> bytes:
        if name not in ALLOWED_FILES | {ARTICLES, CATALOG, REGISTRY_TS, REGISTRY_JSON}:
            raise EvidenceError("EVIDENCE_PATH_INVALID")
        _sha(base_sha)
        # Ensure the base is a tracked regular Git blob, not a symbolic link.
        entry = self.workspace._git("ls-tree", "-z", base_sha, "--", name)
        if (not entry.startswith(b"100644 blob ")
            or not entry.endswith(b"\t" + name.encode("utf-8") + b"\0")
            or entry.count(b"\0") != 1):
            raise EvidenceError("EVIDENCE_BASE_BLOB_INVALID")
        raw = self.workspace._git("show", base_sha + ":" + name)
        if not isinstance(raw, bytes) or len(raw) > MAX_RECORD_BYTES:
            raise EvidenceError("EVIDENCE_SIZE_INVALID")
        return raw

    def _base_json(self, name: str, base_sha: str) -> dict:
        return _parse(self._tracked_bytes(name, base_sha))

    def _verify_selection_source(self, baseline: dict, base_sha: str) -> dict:
        """Rebuild selection from pinned sources and verified coverage state."""
        # The *selection* is generated during this run, even if the underlying
        # article snapshot is several days old. Never replay an old selection.
        try:
            started_at = _stamp(self.run_started_at)
            completed_at = _stamp(self.run_completed_at)
            selected_at = _stamp(self.pre_crawl_selection.get("generatedAt"))
        except TransitionError:
            raise EvidenceError("EVIDENCE_RUN_WINDOW_INVALID") from None
        if completed_at < started_at or completed_at - started_at > MAX_RUN_DURATION:
            raise EvidenceError("EVIDENCE_RUN_WINDOW_INVALID")
        if not started_at <= selected_at <= completed_at:
            raise EvidenceError("EVIDENCE_SELECTION_OUTSIDE_RUN")
        article = self._base_json(ARTICLES, base_sha)
        try:
            catalog = self._tracked_bytes(CATALOG, base_sha).decode("utf-8")
        except UnicodeError:
            raise EvidenceError("EVIDENCE_CATALOG_INVALID") from None
        is_reexport = 'export { companies } from "./company-registry"' in catalog
        registry_ts, registry = None, None
        if is_reexport:
            try:
                registry_ts = self._tracked_bytes(REGISTRY_TS, base_sha).decode("utf-8")
            except UnicodeError:
                raise EvidenceError("EVIDENCE_CATALOG_INVALID") from None
            registry = self._base_json(REGISTRY_JSON, base_sha)
        try:
            companies, _ = pinned_catalog(catalog, registry_ts, registry)
        except (PinnedCatalogError, ValueError, TypeError, RecursionError):
            raise EvidenceError("EVIDENCE_CATALOG_INVALID") from None
        if not companies or len({item.slug for item in companies}) != len(companies):
            raise EvidenceError("EVIDENCE_CATALOG_INVALID")
        selection_profiles = baseline[PROFILES]
        if self.coverage_snapshot is not None:
            try:
                attest_coverage(
                    baseline[PROFILES], self.coverage_snapshot, catalog,
                    self.coverage_report, updated_at=self.coverage_updated_at,
                    run_started_at=self.run_started_at,
                    run_completed_at=self.run_completed_at,
                    registry_ts=registry_ts, registry=registry,
                )
            except CoverageError as exc:
                msg = str(exc)
                if (not msg.startswith("COVERAGE_")
                    or not msg.replace("_", "").isalnum() or len(msg) > 90):
                    msg = "EVIDENCE_COVERAGE_REJECTED"
                raise EvidenceError(msg) from None
            selection_profiles = self.coverage_snapshot
        lookback = self.pre_crawl_selection.get("lookbackDays")
        limit = self.pre_crawl_selection.get("selectionLimit")
        if (type(lookback) is not int or not 1 <= lookback <= 90
            or type(limit) is not int or not 0 <= limit <= 10):
            raise EvidenceError("EVIDENCE_SELECTION_PARAMETERS_INVALID")
        try:
            expected = build_queue(
                article, selection_profiles,
                {item.slug: item.name for item in companies},
                baseline[QUEUE],
                now=selected_at,
                lookback_days=lookback, select_limit=limit,
            )
        except (ValueError, TypeError, RecursionError, OverflowError, KeyError):
            raise EvidenceError("EVIDENCE_SELECTION_SOURCE_INVALID") from None
        if expected != self.pre_crawl_selection:
            raise EvidenceError("EVIDENCE_SELECTION_SOURCE_MISMATCH")
        return selection_profiles

    def snapshot(self) -> Snapshot | None:
        prepared = self.workspace.snapshot()
        base_sha = (prepared.base_sha if prepared is not None
                    else self.workspace._git("rev-parse", "HEAD").decode("ascii").strip())
        _sha(base_sha)
        if self.workspace._git("rev-parse", "HEAD").decode("ascii").strip() != base_sha:
            raise EvidenceError("EVIDENCE_BASE_MOVED")
        baseline = {path: self._base_json(path, base_sha) for path in (QUEUE, PROFILES)}
        selection_profiles = self._verify_selection_source(baseline, base_sha)
        if self.workspace._git("rev-parse", "HEAD").decode("ascii").strip() != base_sha:
            raise EvidenceError("EVIDENCE_BASE_MOVED")
        candidate = {}
        for path in (QUEUE, PROFILES):
            if prepared is not None and path in prepared.files:
                candidate[path] = _parse(prepared.files[path])
            else:
                candidate[path] = baseline[path]
        if prepared is not None and set(prepared.files) - ALLOWED_FILES:
            raise EvidenceError("EVIDENCE_UNEXPECTED_FILE")
        # The checker knows the real build_queue/mark_processed semantics,
        # including chronology and unmodified processed history.
        try:
            check_transition(
                baseline[QUEUE], copy.deepcopy(self.pre_crawl_selection),
                candidate[QUEUE], selection_profiles, candidate[PROFILES],
                run_started_at=self.run_started_at,
                run_completed_at=self.run_completed_at,
                coverage_slugs=[],
            )
        except TransitionError as exc:
            code = str(exc)
            if (not code.startswith("WRITER_TRANSITION_")
                or not code.replace("_", "").isalnum() or len(code) > 90):
                code = "EVIDENCE_TRANSITION_REJECTED"
            raise EvidenceError(code) from None
        return prepared
