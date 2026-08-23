#!/usr/bin/env python3
"""Run the cross-field guard with the shared venture publication contracts installed."""

from __future__ import annotations

try:
    from .guard_venture_cross_field_noise import main as guard_main
    from .stabilize_venture_publication_pipeline import align_capital_event_patterns
except ImportError:
    from guard_venture_cross_field_noise import main as guard_main
    from stabilize_venture_publication_pipeline import align_capital_event_patterns


def main() -> int:
    # The guard is also executable on its own, but publication validation must use
    # the same canonical capital-event/summary semantics as the full stabilizer.
    align_capital_event_patterns()
    return guard_main()


if __name__ == "__main__":
    raise SystemExit(main())
