#!/usr/bin/env python3
"""Authenticated single-object writer entrypoint with keyword support."""

from __future__ import annotations

import sys

try:
    import manual_tracking as manual
    from manual_tracking_keyword_support import enable_keyword_tracking
except ImportError:  # pragma: no cover
    from tools import manual_tracking as manual
    from tools.manual_tracking_keyword_support import enable_keyword_tracking


def main(argv: list[str] | None = None) -> int:
    enable_keyword_tracking(manual)
    return manual.main(argv)


if __name__ == "__main__":
    sys.exit(main())
