#!/usr/bin/env python3
"""Drive venture publication plus cross-field noise guard to one fixed point.

The shared publication stabilizer already reconciles evidence refinement,
normalization, structural finalization and entity semantics.  The terminal
cross-field guard is intentionally information-reducing, however, so it must be
part of the same canonical transformation: an upstream gate may rediscover a
candidate that the guard correctly removes.  This wrapper iterates the complete
publication -> guard sequence until another complete sequence is a no-op.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable

try:
    from .guard_venture_cross_field_noise import guard_snapshot
    from .stabilize_venture_publication_pipeline import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_publication_snapshot,
    )
except ImportError:
    from guard_venture_cross_field_noise import guard_snapshot
    from stabilize_venture_publication_pipeline import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_publication_snapshot,
    )


PublicationStabilizer = Callable[..., tuple[dict[str, Any], dict[str, Any]]]
CrossFieldGuard = Callable[[dict[str, Any], str], tuple[dict[str, Any], dict[str, Any]]]


def _state_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stabilize_guarded_publication_snapshot(
    snapshot: dict[str, Any],
    articles: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
    publication_stabilizer: PublicationStabilizer = stabilize_publication_snapshot,
    cross_field_guard: CrossFieldGuard = guard_snapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a snapshot stable under publication normalization and the guard."""
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    current = copy.deepcopy(snapshot)
    seen: dict[str, int] = {_state_key(current): 0}
    history: list[dict[str, Any]] = []

    for pass_index in range(1, max_passes + 1):
        published, publication_diagnostics = publication_stabilizer(
            current,
            articles,
            catalog_text,
            max_passes=max_passes,
        )
        guarded, guard_diagnostics = cross_field_guard(published, catalog_text)

        republished, check_publication_diagnostics = publication_stabilizer(
            guarded,
            articles,
            catalog_text,
            max_passes=max_passes,
        )
        reguarded, check_guard_diagnostics = cross_field_guard(
            republished, catalog_text
        )

        stable = reguarded == guarded
        changed = guarded != current
        history.append(
            {
                "pass": pass_index,
                "changed": changed,
                "stable": stable,
                "publication": publication_diagnostics,
                "guard": guard_diagnostics,
                "publicationCheck": check_publication_diagnostics,
                "guardCheck": check_guard_diagnostics,
            }
        )

        if stable:
            return guarded, {
                "passes": pass_index,
                "changedPasses": sum(bool(item["changed"]) for item in history),
                "converged": True,
                "history": history,
            }

        state_key = _state_key(guarded)
        if state_key in seen:
            raise RuntimeError(
                "guarded venture publication entered a cycle before reaching a fixed point: "
                + json.dumps(
                    {
                        "repeatedFromPass": seen[state_key],
                        "repeatedAtPass": pass_index,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        seen[state_key] = pass_index
        current = guarded

    raise RuntimeError(
        f"guarded venture publication did not converge within {max_passes} passes"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--articles", type=Path, default=ARTICLE_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    stabilized, diagnostics = stabilize_guarded_publication_snapshot(
        snapshot,
        articles,
        args.catalog.read_text(encoding="utf-8"),
        max_passes=args.max_passes,
    )
    rendered = json.dumps(stabilized, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot has not reached the guarded publication fixed point.")
            return 1
        print("Venture profile snapshot passed the guarded publication fixed-point check.")
        return 0

    if rendered == current:
        print("No guarded venture publication changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
