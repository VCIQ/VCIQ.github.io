"""Offline import boundary: verify first, transaction second, sanitized quarantine."""
import hashlib
import re
from uuid import uuid4

from .batch import ROOT, private_root, read_batch, write_private
from .contracts import ContractError, canonical_bytes
from .guard import GuardError
from .signal_store import SignalStore, stamp


def import_from_path(state_dir, relative, *, repo_roots=(ROOT,)):
    """Never copy corrupt/raw input into logs. Keep input untouched for inspection.

    Quarantine is a logical rejection ledger, not a move of the source directory.
    No database is opened until the complete batch has passed verification.
    """
    root = private_root(state_dir, repo_roots)
    try:
        if any(".staging-" in part for part in relative.split("/")):
            raise ContractError("batch_unsealed_staging")
        checked = read_batch(root, relative, repo_roots=repo_roots)
        with SignalStore(root, repo_roots=repo_roots) as store:
            return {**store.import_batch(checked), "contentCommitted": True, "quarantineRecorded": False}
    except (ContractError, GuardError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "import_io_error")
        if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", code):
            code = "import_rejected"
        record = {"kind": "shadow_import_rejection", "reason": code, "recordedAt": stamp(),
                  "sourceRef": hashlib.sha256(str(relative).encode()).hexdigest(), "contentCommitted": False}
        quarantined = False
        try:
            write_private(root, "quarantine/" + str(uuid4()) + ".json", canonical_bytes(record) + b"\n", repo_roots)
            quarantined = True
        except (ContractError, GuardError, OSError):
            pass
        return {"ok": False, "error": code, "contentCommitted": False,
                "batchIntegrityChecked": False, "quarantineRecorded": quarantined}
