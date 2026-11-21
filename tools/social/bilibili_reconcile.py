"""Read-only reconciliation of a Bilibili result and existing person video materials."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bilibili_identity import reconcile_materials
from .contracts import ContractError, load_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True, help="JSON observation list or worker result with observations")
    parser.add_argument("--materials", type=Path, required=True, help="JSON list returned by discover_person_video_materials")
    args = parser.parse_args(argv)
    try:
        for path in (args.observations, args.materials):
            if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
                raise ContractError("readonly_input_path")
        observations, materials = load_json(args.observations), load_json(args.materials)
        if isinstance(observations, dict):
            observations = observations.get("observations")
        result = reconcile_materials(observations, materials)
        print(json.dumps({"ok": True, "liveExecuted": False, **result}, ensure_ascii=False, sort_keys=True))
        return 0
    except ContractError as exc:
        code = exc.code
    except (ValueError, OSError, TypeError):
        code = "reconciliation_input_error"
    print(json.dumps({"ok": False, "error": code, "liveExecuted": False, "productionWrites": False}), file=sys.stderr)
    return 2


if __name__ == "__main__": raise SystemExit(main())
