"""Validate the complete batch before any database mutation."""
from .batch import read_batch


def ingest_batch(directory, store, *, expected_policy=None):
    from .contracts import ContractError, validate
    batch = read_batch(directory)
    if expected_policy is not None:
        validate(expected_policy, expected_kind="discovery_policy")
        for job in batch["jobs"]:
            budget = expected_policy["budget"]
            if job["policyVersion"] != expected_policy["policyVersion"] or any(
                job["limits"][field] > budget[budget_key] for field, budget_key in
                (("maxSearchPages", "pagesPerJob"), ("maxRecords", "recordsPerJob"), ("maxWallSeconds", "wallSecondsPerJob"))):
                raise ContractError("batch_policy_mismatch")
    return store.import_validated(batch)
