"""Read-only shadow health. Missing evidence is unknown, never green by default."""
from __future__ import annotations

from collections import Counter

from .contracts import PLATFORMS, ContractError
from .guard import output_path
from .review import ReviewStore, read_transaction
from .scheduler_state import read_state
from .shadow_state import stopped, load, run_prefix
from .signal_store import SignalStore


def health(root, roots):
    state = read_state(root, repo_roots=roots)
    platforms = {}
    for platform in PLATFORMS:
        pause = state["platforms"].get(platform, {})
        platforms[platform] = {"pauseReason": pause.get("pauseReason"),
            "pauseUntil": pause.get("pauseUntil"), "leaseUntil": pause.get("leaseUntil"),
            "liveAcceptance": "not_attested"}
    content, review = None, None
    if output_path(root, "signals.sqlite3", repo_roots=roots).exists():
        with SignalStore(root, repo_roots=roots, readonly=True) as source:
            content = source.counts()
    if output_path(root, "reviews.sqlite3", repo_roots=roots).exists():
        with ReviewStore(root, repo_roots=roots, readonly=True) as store:
            counts = Counter()
            offset = 0
            with read_transaction(store.db):
                while True:
                    page = store.view(offset=offset, limit=100)
                    counts.update(row["item"]["status"] for row in page["items"])
                    if page["nextOffset"] is None: break
                    offset = page["nextOffset"]
                review = {"activeByStatus": dict(counts), "queueVersion": store.queue_version()}
    parent = output_path(root, "orchestration/.check", repo_roots=roots).parent
    runs = []
    if parent.exists():
        entries = list(parent.iterdir())
        if len(entries) > 1000: raise ContractError("shadow_run_history_limit")
        for entry in sorted(entries, key=lambda p: p.name):
            prefix = run_prefix(entry.name)
            marker = output_path(root, prefix + "/report.json", repo_roots=roots)
            if marker.exists():
                report = load(root, prefix + "/report.json", roots)
                runs.append({"runId": entry.name, "status": report["status"], "pipelineComplete": report["pipelineComplete"],
                    "receiptJobs": report.get("receiptJobs"), "notCompletedJobs": report.get("notCompletedJobs"),
                    "checkpointReconciliationRequired": report.get("checkpointReconciliationRequired")})
            else:
                runs.append({"runId": entry.name, "status": "unfinished", "pipelineComplete": False})
    queries = list(state["queries"].values())
    return {"ok": True, "mode": "shadow", "publish": False, "writesPerformed": False,
        "liveExecuted": False, "stopRequested": stopped(root, roots), "platforms": platforms,
        "scheduler": {"knownQueries": len(queries), "coveredEver": sum(bool(q["lastCoveredAt"]) for q in queries),
            "withFailures": sum(q["consecutiveFailures"] > 0 for q in queries)},
        "content": content, "review": review, "runs": runs, "productionChanged": False,
        "note": "Offline checks and accepted leads do not attest platform availability or event truth."}
