#!/usr/bin/env python3
"""Origin-aware batch writer entrypoint with first-class keyword support."""

from __future__ import annotations

import sys

try:
    import manual_tracking as manual
    import manual_tracking_batch as batch
    from manual_tracking_keyword_support import enable_keyword_tracking
except ImportError:  # pragma: no cover
    from tools import manual_tracking as manual
    from tools import manual_tracking_batch as batch
    from tools.manual_tracking_keyword_support import enable_keyword_tracking


def main(argv: list[str] | None = None) -> int:
    enable_keyword_tracking(manual)
    return batch.main(argv)


if __name__ == "__main__":
    sys.exit(main())
