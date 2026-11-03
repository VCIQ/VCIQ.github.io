"""Fail-closed MediaCrawler process boundary. No imports or login at module load."""
from __future__ import annotations

import os
import signal
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from workers.mediacrawler.upstream import UpstreamError, load_lock, verify_checkout
from .contracts import ContractError, load_json, validate
from .guard import GuardError, output_path, runtime_paths
from .policy import activation
from .wechat_runner import atomic_json
from .adapters.xhs import error_envelope, finalize

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def preflight(runtime, policy, *, live, runtime_file, python_executable=None, repo_root=ROOT):
    if activation(policy, runtime, live=live, implemented=frozenset({"xhs"}))["xhs"] != "eligible":
        raise ContractError("live_activation_required")
    state = runtime_paths(runtime, repo_root=repo_root, runtime_file=runtime_file)
    if os.name != "posix":
        raise ContractError("posix_worker_required")
    if not runtime["mediacrawlerDir"]:
        raise ContractError("upstream_directory_required")
    upstream = Path(runtime["mediacrawlerDir"])
    if upstream.resolve().is_relative_to(repo_root.resolve()) or repo_root.resolve().is_relative_to(upstream.resolve()):
        raise GuardError("upstream_overlaps_repository")
    lock = load_lock(repo_root / "workers/mediacrawler/upstream.lock.json")
    verify_checkout(upstream, lock)
    python = Path(python_executable) if python_executable else upstream / ".venv/bin/python"
    # An operator-selected interpreter is a path, never a shell command. A venv
    # Python may legitimately be a symlink to its base Python executable.
    if not python.is_absolute() or ".." in python.parts or not python.is_file() or not os.access(python, os.X_OK):
        raise ContractError("worker_python_required")
    if state.stat().st_mode & 0o077:
        raise GuardError("private_state_permissions_required")
    return state, upstream, python, lock


@contextmanager
def profile_lock(state, roots):
    import fcntl
    path = output_path(state, "locks/xhs.lock", repo_roots=roots)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path(state, "locks/xhs.lock", repo_roots=roots)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077 or os.fstat(fd).st_nlink != 1:
            raise GuardError("private_lock_permissions_required")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ContractError("profile_busy") from None
        yield
    finally:
        os.close(fd)


def child_environment(state):
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "SYSTEMROOT") if key in os.environ}
    env.update(HOME=str(state / "home"), TMPDIR=str(state / "tmp"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1",
               PLAYWRIGHT_BROWSERS_PATH=str(state / "browsers"))
    return env


def _kill_group(pid, sig):
    if os.name != "posix":
        raise ContractError("posix_worker_required")
    os.killpg(pid, sig)


def run_child(python, request_path, *, state, timeout, popen=subprocess.Popen, kill_group=_kill_group):
    command = [str(python), "-I", "-B", str(ROOT / "workers/mediacrawler/bootstrap.py"), str(request_path)]
    process = popen(command, cwd=state, env=child_environment(state), stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False, start_new_session=True)
    timed_out = False
    try:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        return_code = process.returncode
    finally:
        # Kill the entire new process group, including Chromium children. Even a
        # normally-exited Python child must not leave an unattended browser.
        try:
            kill_group(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            kill_group(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)
    return timed_out, return_code


def execute_job(job, context, *, runtime, policy, runtime_file, live=False,
                python_executable=None, popen=subprocess.Popen, kill_group=_kill_group):
    validate(job, expected_kind="crawl_job")
    if job["platform"] != "xhs":
        raise ContractError("xhs_worker_only")
    state, upstream, python, lock = preflight(runtime, policy, live=live,
        runtime_file=runtime_file, python_executable=python_executable)
    if job["upstreamCommit"] != lock["commit"]:
        raise ContractError("upstream_job_pin")
    roots = (ROOT, upstream)
    started = now()
    def failure(status, code):
        return finalize(job, error_envelope(job, status, code, started, now()), context,
                        patchset_hash=lock["patchsetHash"])
    profile = state / "profiles/xhs"
    output_path(state, "profiles/xhs/.profile-check", repo_roots=roots)
    if not profile.is_dir():
        return failure("auth_required", "PROFILE_NOT_INITIALIZED")
    with profile_lock(state, roots):
        attempt = "worker/" + job["attemptId"]
        target = output_path(state, attempt + "/captured.json", repo_roots=roots)
        request_path = output_path(state, attempt + "/request.json", repo_roots=roots)
        if request_path.exists() or target.exists():
            raise ContractError("attempt_output_exists")
        for name in ("home", "tmp"):
            output_path(state, name + "/.check", repo_roots=roots)
            (state / name).mkdir(mode=0o700, exist_ok=True)
        request = {"action": "run", "upstream": str(upstream), "profile": str(profile),
                   "output": str(target), "job": job, "lock": lock}
        atomic_json(state, attempt + "/request.json", request, roots=roots)
        try:
            timed_out, code = run_child(python, request_path, state=state,
                timeout=job["limits"]["maxWallSeconds"], popen=popen, kill_group=kill_group)
            if timed_out:
                return failure("timeout", "WORKER_DEADLINE")
            if code != 0 or not target.is_file():
                return failure("schema_error", "WORKER_NO_RECEIPT")
            output_path(state, attempt + "/captured.json", repo_roots=roots)
            result = finalize(job, load_json(target), context, patchset_hash=lock["patchsetHash"])
            atomic_json(state, "pending/" + job["attemptId"] + ".json", result, roots=roots)
            return result
        except (ContractError, GuardError, OSError, ValueError, subprocess.SubprocessError):
            return failure("schema_error", "WORKER_OUTPUT_REJECTED")


def bootstrap_session(*, runtime, policy, runtime_file, live=False, interactive=False, python_executable=None):
    if not interactive or not runtime.get("interactiveAuthAllowed"):
        raise ContractError("interactive_auth_opt_in_required")
    state, upstream, python, lock = preflight(runtime, policy, live=live,
        runtime_file=runtime_file, python_executable=python_executable)
    roots = (ROOT, upstream)
    with profile_lock(state, roots):
        for name in ("profiles/xhs", "home", "tmp"):
            output_path(state, name + "/.check", repo_roots=roots)
            (state / name).mkdir(mode=0o700, parents=True, exist_ok=True)
        attempt = "worker/session-" + str(uuid4())
        target = output_path(state, attempt + "/captured.json", repo_roots=roots)
        request = {"action": "session", "upstream": str(upstream), "profile": str(state / "profiles/xhs"),
                   "output": str(target), "job": None, "lock": lock}
        path = atomic_json(state, attempt + "/request.json", request, roots=roots)
        timed_out, code = run_child(python, path, state=state, timeout=240)
        if timed_out or code != 0 or not target.exists():
            return {"ok": False, "sessionPrepared": False, "liveQueryExecuted": False}
        output_path(state, attempt + "/captured.json", repo_roots=roots)
        result = load_json(target)
        if set(result) != {"sessionPrepared", "authenticationVerified", "liveQueryExecuted"} or any(type(v) is not bool for v in result.values()) or result["authenticationVerified"] or result["liveQueryExecuted"]:
            raise ContractError("session_result_invalid")
        return {"ok": result["sessionPrepared"], **result}
