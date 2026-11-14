"""Private child stop/disable guard; standard library, no upstream imports.

Called immediately before each instrumented API request. An already in-flight
request or Chromium internal resource load is not retroactively cancelled.
The parent supplies only state/runtime paths, never credentials, via its minimal
child environment. Direct dependency-injected unit calls without that environment
are unaffected. Invalid/missing runtime in a configured child fails closed.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path


def check(observer, *, platform, state_dir=None, runtime_file=None):
    state_value = state_dir or os.environ.get("VCIQ_SHADOW_STATE")
    if state_value is None:
        if runtime_file is not None or os.environ.get("VCIQ_SHADOW_RUNTIME") is not None:
            raise observer.CollectorError("cancelled", "SHADOW_CONTROL_UNAVAILABLE")
        return
    def fail(code): raise observer.CollectorError("cancelled", code)
    try:
        root = Path(state_value)
        if (not root.is_absolute() or ".." in root.parts or not root.is_dir()
                or any(p.is_symlink() for p in (root, *root.parents))):
            fail("SHADOW_CONTROL_PATH")
        # Recheck the outer privacy boundary before every API dispatch. A file
        # may still be 0600 even when a sync/other process loosens its directory.
        meta = root.lstat()
        if (os.name == "posix" and (meta.st_uid != os.geteuid()
                or meta.st_mode & (0o077 | stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX))):
            fail("SHADOW_CONTROL_PERMISSIONS")
        # lexists intentionally treats dangling links/directories as a stop.
        if os.path.lexists(root / "shadow.stop"): fail("SHADOW_STOP_REQUESTED")
        selected = runtime_file or os.environ.get("VCIQ_SHADOW_RUNTIME")
        if selected is None: fail("SHADOW_CONTROL_UNAVAILABLE")
        path = Path(selected)
        if (not path.is_absolute() or ".." in path.parts or not path.is_relative_to(root)
                or any(p.is_symlink() for p in (path, *path.parents))):
            fail("SHADOW_CONTROL_PATH")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            meta = os.fstat(stream.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_mode & 0o077:
                fail("SHADOW_CONTROL_PERMISSIONS")
            raw = stream.read(65537)
        if len(raw) > 65536: fail("SHADOW_CONTROL_SIZE")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result: fail("SHADOW_CONTROL_INVALID")
                result[key] = value
            return result
        value = json.loads(raw, object_pairs_hook=pairs)
        if (not isinstance(value, dict) or value.get("mode") != "shadow" or value.get("publish") is not False
                or value.get("stateDir") != str(root)):
            fail("SHADOW_CONTROL_INVALID")
        platforms = value.get("platforms")
        if (value.get("enabled") is not True or not isinstance(platforms, dict)
                or not isinstance(platforms.get(platform), dict) or platforms[platform].get("enabled") is not True):
            fail("SHADOW_PLATFORM_DISABLED")
    except observer.CollectorError:
        raise
    except (OSError, ValueError, TypeError, RecursionError):
        fail("SHADOW_CONTROL_UNAVAILABLE")
