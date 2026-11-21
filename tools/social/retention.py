"""Explicit historical-text retention; never automatic on an empty/failed crawl."""
from .signal_store import StoreError


def retain(store, before, *, apply=False, expected_plan_hash=None):
    if not apply:
        return {"ok": True, "applied": False, **store.retention_plan(before)}
    if expected_plan_hash is None:
        raise StoreError("retention_plan_hash_required")
    return store.apply_retention(before, expected_plan_hash)
