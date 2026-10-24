"""Explicit live boundary. A spawned child gives each WeChat job a hard wall limit."""
from __future__ import annotations

import multiprocessing
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, assert_safe, canonical_bytes, load_json
from .guard import output_path, state_path
from .scheduler_state import SchedulerStore


def atomic_json(state_dir: Path, relative: str, payload: dict, *, roots: tuple[Path, ...]) -> Path:
    assert_safe(payload)
    root = state_path(state_dir, repo_roots=roots)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = output_path(root, relative, repo_roots=roots)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp_relative = str(destination.relative_to(root).parent / (".tmp-" + str(uuid4())))
    temporary = output_path(root, temp_relative, repo_roots=roots)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_bytes(payload) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        output_path(root, relative, repo_roots=roots)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _child(job: dict, context: dict, state_dir: str, roots: tuple[str, ...], grant: dict, relative: str) -> None:
    from .adapters.wechat import run_job, error_result
    from .adapters.wechat_transport import PublicTransport, FetchError
    clock = lambda: datetime.now(UTC)
    started = clock()
    deadline = time.monotonic() + job["limits"]["maxWallSeconds"]
    repo_roots = tuple(Path(root) for root in roots)
    with SchedulerStore(state_dir, repo_roots=repo_roots) as store:
        def before_request():
            try:
                wait = store.request_slot(clock())
                if time.monotonic() + wait >= deadline:
                    raise FetchError("timeout", "JOB_DEADLINE")
                time.sleep(wait)
                store.consume_request(grant, job["attemptId"], clock())
            except ContractError as exc:
                raise FetchError("cancelled", exc.code.upper()) from None
        transport = PublicTransport(before_request=before_request, deadline=deadline)
        try:
            result = run_job(job, context, transport)
        except Exception:
            result = error_result(job, "schema_error", "WORKER_ERROR", started, clock())
        result["diagnostics"]["requests"] = store.request_count(job["attemptId"])
    atomic_json(Path(state_dir), relative, result, roots=repo_roots)


def execute_job(job: dict, context: dict, *, state_dir: Path, roots: tuple[Path, ...], grant: dict) -> dict:
    from .adapters.wechat import error_result
    started = datetime.now(UTC)
    relative = "pending/" + job["attemptId"] + ".json"
    target = output_path(state_dir, relative, repo_roots=roots)
    if target.exists():
        raise ContractError("attempt_output_exists")
    child = multiprocessing.get_context("spawn").Process(target=_child,
        args=(job, context, str(state_dir), tuple(str(root) for root in roots), grant, relative))
    child.start()
    try:
        child.join(job["limits"]["maxWallSeconds"])
        if child.is_alive():
            child.terminate()
            child.join(3)
            if child.is_alive():
                child.kill()
                child.join(3)
            return error_result(job, "timeout", "WORKER_DEADLINE", started, datetime.now(UTC))
        if child.exitcode != 0 or not target.is_file():
            return error_result(job, "schema_error", "WORKER_NO_RECEIPT", started, datetime.now(UTC))
        output_path(state_dir, relative, repo_roots=roots)
        return load_json(target)
    finally:
        if child.is_alive():
            child.terminate()
            child.join(3)
        child.close()
