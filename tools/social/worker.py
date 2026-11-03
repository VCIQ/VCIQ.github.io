"""Isolated, opt-in MediaCrawler process controller; no upstream imports here."""
from __future__ import annotations

import importlib
import os
import re
import signal
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .contracts import ContractError, assert_safe, digest, load_json, validate
from .guard import GuardError, output_path, runtime_paths
from .wechat_runner import atomic_json
from workers.mediacrawler.capabilities import available

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "workers/mediacrawler"
ADAPTERS = available(ROOT)
REASONS = {"auth_required": "auth", "verification_required": "verification", "rate_limited": "rate_limit",
           "network_error": "network", "timeout": "timeout", "schema_error": "schema", "unsupported": "unsupported", "cancelled": "cancelled"}


def stamp():
    return datetime.now(UTC).isoformat(timespec="seconds")


def child_environment(state_dir, *, source=None):
    source = os.environ if source is None else source
    env = {key: source[key] for key in ("PATH", "SystemRoot", "WINDIR", "LANG", "LC_ALL", "PLAYWRIGHT_BROWSERS_PATH") if key in source}
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(state_dir) / "browser-binaries"))
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", PYTHONUTF8="1", TZ="UTC",
               HOME=str(Path(state_dir) / "worker-home"), USERPROFILE=str(Path(state_dir) / "worker-home"),
               GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0")
    return env


def verify_upstream(directory, *, lock_path=None, command_runner=None):
    """Read-only local Git verification; never clone, pull, install, or log in."""
    directory = Path(directory)
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        raise GuardError("upstream_directory_missing")
    if directory == ROOT or directory.is_relative_to(ROOT) or ROOT.is_relative_to(directory):
        raise GuardError("upstream_overlaps_vciq")
    lock = load_json(lock_path or BRIDGE / "upstream.lock.json")
    if lock.get("repository") != "NanmiCoder/MediaCrawler" or not re.fullmatch(r"[0-9a-f]{40}", lock.get("commit", "")):
        raise ContractError("invalid_upstream_lock")
    if lock.get("patches") != [] or lock.get("patchsetHash") != digest([]):
        raise ContractError("unsupported_upstream_patchset")
    run = command_runner or subprocess.run
    env = child_environment(directory)
    options = dict(capture_output=True, text=True, timeout=15, env=env, check=False)
    prefix = ["git", "-c", "core.fsmonitor=false", "-C", str(directory)]
    head = run(prefix + ["rev-parse", "HEAD"], **options)
    if head.returncode or head.stdout.strip() != lock["commit"]:
        raise ContractError("upstream_revision_mismatch")
    dirty = run(prefix + ["diff", "--no-ext-diff", "--quiet", "HEAD", "--"], **options)
    if dirty.returncode:
        raise ContractError("upstream_worktree_modified")
    untracked = run(prefix + ["ls-files", "--others", "--exclude-standard"], **options)
    if untracked.returncode or any(line.endswith((".py", ".pth", ".so", ".pyd")) for line in untracked.stdout.splitlines()):
        raise ContractError("untracked_upstream_code")
    python = directory / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise ContractError("upstream_environment_missing")
    return {"commit": lock["commit"], "patchsetHash": lock["patchsetHash"], "python": python}


@contextmanager
def profile_lock(state_dir, platform, *, roots):
    if platform not in ADAPTERS:
        raise ContractError("worker_platform_unsupported")
    path = output_path(state_dir, f"locks/{platform}.lock", repo_roots=roots)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        if os.fstat(fd).st_nlink != 1:
            raise GuardError("unsafe_profile_lock")
        if os.name == "posix":
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ContractError("profile_busy") from None
        elif os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ContractError("profile_busy") from None
        else:
            raise ContractError("profile_lock_platform_unsupported")
        locked = True
        yield
    finally:
        if locked and os.name == "posix":
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
        elif locked and os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)


def stop_process_tree(process):
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        # A browser grandchild may outlive its parent after SIGTERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)
    elif os.name == "nt":
        executable = Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"
        subprocess.run([str(executable), "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
        process.wait(timeout=3)
    else:
        process.kill()
        process.wait(timeout=3)


def failed_result(job, status, code, *, started=None):
    receipt = {"schemaVersion": 1, "kind": "query_receipt",
        **{key: job[key] for key in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")},
        "startedAt": started or stamp(), "completedAt": stamp(), "status": status,
        "completeness": "unknown", "stopReason": REASONS[status],
        "counts": dict.fromkeys(("searchItems", "rawRows", "emittedRows", "rejectedRows", "duplicateRows", "budgetSkipped", "detailFailures"), 0),
        "pageReceipts": [], "normalizerVersion": "mc-shadow-v1", "patchsetHash": digest([]), "errorCode": code}
    validate(receipt)
    return {"receipt": receipt, "observations": [], "hints": [], "diagnostics": {"retryAfterSeconds": 0}}


def normalize_execution(payload, job, *, terms=None):
    validate(job, expected_kind="crawl_job")
    expected = {"schemaVersion", "jobId", "attemptId", "startedAt", "completedAt", "pages", "rows", "detailFailures", "error", "stopReason", "httpRequests", "browserRequests", "retryAfterSeconds"}
    if not isinstance(payload, dict) or set(payload) != expected or payload["schemaVersion"] != 1:
        raise ContractError("worker_report_shape")
    if payload["jobId"] != job["jobId"] or payload["attemptId"] != job["attemptId"]:
        raise ContractError("worker_report_identity")
    if job["platform"] not in ADAPTERS or not isinstance(payload["rows"], list) or len(payload["rows"]) > 1000:
        raise ContractError("worker_report_bounds")
    pages = payload["pages"]
    if not isinstance(pages, list) or len(pages) > job["limits"]["maxSearchPages"]:
        raise ContractError("worker_page_bounds")
    for key in ("detailFailures", "httpRequests", "browserRequests", "retryAfterSeconds"):
        if type(payload[key]) is not int or payload[key] < 0:
            raise ContractError("worker_counter")
    error = payload["error"]
    if error is not None and (not isinstance(error, dict) or set(error) != {"status", "code"} or error["status"] not in REASONS or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,119}", error["code"])):
        raise ContractError("worker_error_shape")
    module = importlib.import_module("tools.social.adapters." + ADAPTERS[job["platform"]])
    rows, seen = [], set()
    rejected = duplicate = skipped = 0
    for envelope in payload["rows"]:
        if not isinstance(envelope, dict) or set(envelope) != {"record", "observedAt", "titleOrigin"}:
            raise ContractError("worker_row_shape")
        try:
            row = module.normalize_record(envelope["record"], job, observed_at=envelope["observedAt"], title_origin=envelope["titleOrigin"], terms=terms)
        except ContractError:
            rejected += 1
            error = error or {"status": "schema_error", "code": "NORMALIZATION_REJECTED"}
            continue
        if row["signalId"] in seen:
            duplicate += 1
            continue
        seen.add(row["signalId"])
        window = job["window"]
        if window["filterMode"] == "post_filter" and (not row["publishedAt"] or
            (window["from"] and row["publishedAt"][:10] < window["from"]) or
            (window["to"] and row["publishedAt"][:10] > window["to"])):
            rejected += 1
            continue
        if len(rows) >= job["limits"]["maxRecords"]:
            skipped += 1
            continue
        rows.append(row)
    if payload["detailFailures"] and error is None:
        error = {"status": "network_error", "code": "DETAIL_FAILURE"}
    search_items = sum(page.get("contentItems", 0) for page in pages if isinstance(page, dict))
    if not pages and error is None:
        error = {"status": "schema_error", "code": "MISSING_SEARCH_EVIDENCE"}
    if search_items == 0 and error is None and (payload["stopReason"] != "exhausted" or not pages or pages[-1].get("hasMore") is not False):
        error = {"status": "schema_error", "code": "EMPTY_UNPROVEN"}
    reason = REASONS[error["status"]] if error else payload["stopReason"]
    status = ("partial" if rows else error["status"]) if error else ("ok" if search_items else "empty")
    receipt = {"schemaVersion": 1, "kind": "query_receipt",
        **{key: job[key] for key in ("jobId", "queryId", "runId", "attemptId", "platform", "provider", "upstreamCommit")},
        "startedAt": payload["startedAt"], "completedAt": payload["completedAt"], "status": status,
        "completeness": "incomplete" if error else "exhausted" if reason == "exhausted" else "bounded",
        "stopReason": reason, "counts": {"searchItems": search_items, "rawRows": len(payload["rows"]),
            "emittedRows": len(rows), "rejectedRows": rejected, "duplicateRows": duplicate,
            "budgetSkipped": skipped, "detailFailures": payload["detailFailures"]},
        "pageReceipts": pages, "normalizerVersion": "mc-shadow-v1", "patchsetHash": digest([]),
        "errorCode": error["code"] if error else None}
    validate(receipt, expected_kind="query_receipt")
    result = {"receipt": receipt, "observations": rows, "hints": [],
              "diagnostics": {key: payload[key] for key in ("httpRequests", "browserRequests", "retryAfterSeconds")}}
    assert_safe(result)
    return result


def execute_job(job, runtime, *, live=False, interactive=False, runner=None, upstream_check=None, terms=None):
    """Return validated observations/receipt. Credentials never enter argv or logs."""
    validate(runtime, expected_kind="runtime_config")
    validate(job, expected_kind="crawl_job")
    platform = job["platform"]
    if not live or not runtime["enabled"] or not runtime["platforms"][platform]["enabled"]:
        raise ContractError("live_activation_required")
    if platform not in ADAPTERS or job["window"]["filterMode"] == "native" or "," in job["query"]["text"]:
        raise ContractError("worker_operation_unsupported")
    if interactive and not runtime["interactiveAuthAllowed"]:
        raise ContractError("interactive_auth_not_allowed")
    if not runtime["mediacrawlerDir"]:
        raise ContractError("upstream_directory_required")
    root = runtime_paths(runtime, repo_root=ROOT)
    upstream = Path(runtime["mediacrawlerDir"])
    roots = (ROOT, upstream)
    checked = (upstream_check or verify_upstream)(upstream)
    if checked["commit"] != job["upstreamCommit"]:
        raise ContractError("job_upstream_mismatch")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and root.stat().st_mode & 0o077:
        raise GuardError("private_state_permissions_required")
    relative = f'raw/{job["runId"]}/{job["attemptId"]}'
    report_path = output_path(root, relative + "/worker.json", repo_roots=roots)
    input_path = output_path(root, relative + "/input.json", repo_roots=roots)
    if report_path.exists() or input_path.exists():
        raise ContractError("attempt_output_exists")
    # Validate prospective children before mkdir: a symlinked platform directory
    # must never redirect Chromium into an unrelated daily browser profile.
    output_path(root, f"profiles/{platform}/.profile-check", repo_roots=roots)
    output_path(root, "worker-home/.home-check", repo_roots=roots)
    profile = root / "profiles" / platform
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    (root / "worker-home").mkdir(mode=0o700, exist_ok=True)
    atomic_json(root, relative + "/input.json", {"job": job, "profile": str(profile), "interactive": interactive,
                "upstream": str(upstream), "output": str(report_path)}, roots=roots)
    started = stamp()
    start = runner or subprocess.Popen
    process = None
    with profile_lock(root, platform, roots=roots):
        try:
            args = [str(checked["python"]), "-I", "-B", str(BRIDGE / "bootstrap.py"), str(input_path)]
            options = {"cwd": str(upstream), "env": child_environment(root), "stdin": subprocess.DEVNULL,
                       "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "shell": False}
            if os.name == "posix":
                options["start_new_session"] = True
            elif os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            process = start(args, **options)
            try:
                process.wait(timeout=job["limits"]["maxWallSeconds"])
            except subprocess.TimeoutExpired:
                stop_process_tree(process)
                return failed_result(job, "timeout", "WORKER_DEADLINE", started=started)
            if not report_path.is_file():
                return failed_result(job, "schema_error", "WORKER_NO_RECEIPT", started=started)
            output_path(root, relative + "/worker.json", repo_roots=roots)
            report = load_json(report_path)
            if interactive:
                if set(report) != {"sessionStatus", "platform"} or report["platform"] != platform or report["sessionStatus"] not in {"ready", "auth_required", "verification_required", "rate_limited", "timeout", "error"}:
                    raise ContractError("session_report_shape")
                assert_safe(report)
                return report
            result = normalize_execution(report, job, terms=terms)
            if process.returncode != 0 and result["receipt"]["status"] in {"ok", "empty"}:
                return failed_result(job, "schema_error", "WORKER_EXIT_CONFLICT", started=started)
            return result
        finally:
            if process is not None and process.poll() is None:
                stop_process_tree(process)
