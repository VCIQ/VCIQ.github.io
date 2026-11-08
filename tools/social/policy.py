"""Explicit local activation. Only WeChat collection is implemented in PR-02."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import PLATFORMS, validate, load_json

DEFAULT_POLICY = Path(__file__).resolve().parents[2] / "config/social_discovery.json"
IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"wechat"})


def load_policy(path: Path | str = DEFAULT_POLICY) -> dict[str, Any]:
    return validate(load_json(path), expected_kind="discovery_policy")


def activation(policy: dict[str, Any], runtime: dict[str, Any] | None = None, *, live: bool = False, implemented: frozenset[str] = IMPLEMENTED_PLATFORMS) -> dict[str, str]:
    """Return decisions only; this function cannot launch a worker.

The committed policy is disabled by default. An explicit local runtime can opt
in without rewriting that committed default, but cannot expand policy budgets.
An implemented collector and a separate --live gate are still required.
"""
    validate(policy, expected_kind="discovery_policy")
    if runtime is not None:
        validate(runtime, expected_kind="runtime_config")
    result = {}
    for platform in PLATFORMS:
        if runtime is None or not runtime["enabled"] or not runtime["platforms"][platform]["enabled"]:
            reason = "disabled"
        elif not live:
            reason = "live_opt_in_required"
        elif platform not in implemented:
            reason = "not_implemented"
        else:
            reason = "eligible"
        result[platform] = reason
    return result
