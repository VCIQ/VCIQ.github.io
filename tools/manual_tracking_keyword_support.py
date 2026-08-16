#!/usr/bin/env python3
"""Enable a first-class ``keyword`` manual-tracking kind without legacy topic rows.

The existing writer is intentionally conservative and its public flat runtime
still stores search signals in ``track.keywords``. This adapter extends that
writer at process startup so a pure search keyword:

* is validated by the governed tracking-keyword parser;
* creates an intent entity with ``kind=keyword`` and memberships with
  ``role=keyword``;
* updates only the selected tracks' keyword arrays;
* does not create a legacy ``topic`` capture record or appear as a technology
  entity merely because it is a search seed;
* remains a distinct intent identity from a genuine technology with the same
  display name.

The patch is process-local and idempotent. Existing technology semantics are
unchanged.
"""

from __future__ import annotations

import argparse
from typing import Any, Mapping


_PATCH_FLAG = "_vciq_first_class_keyword_enabled"
_SEMANTIC_SIGNAL_KINDS = {"keyword", "technology"}


def _keyword_error(manual: Any, value: str, error: Exception) -> Exception:
    detail = str(error).strip()
    replacements = {
        "技术名称": "追踪关键词",
        "追踪技术": "追踪关键词",
        "技术关键字": "追踪关键词",
        "技术对象": "追踪关键词",
    }
    for source, target in replacements.items():
        detail = detail.replace(source, target)
    if not detail:
        detail = f"追踪关键词无效或过于宽泛：{value}"
    return manual.ManualTrackingError(detail)


def enable_keyword_tracking(manual: Any) -> None:
    """Patch one imported ``manual_tracking`` module for keyword requests."""

    if getattr(manual, _PATCH_FLAG, False):
        return

    manual.KINDS.add("keyword")
    manual.ROLE_BY_KIND["keyword"] = "keyword"
    manual.FIELD_BY_KIND["keyword"] = "keywords"

    original_normalized_input = manual._normalized_input
    original_same_entity_identity = manual._same_entity_identity

    def keyword_aware_normalized_input(
        args: argparse.Namespace,
        tracking: Mapping[str, Any],
    ) -> dict[str, Any]:
        kind = manual.clean(getattr(args, "kind", ""), 30).casefold()
        if kind != "keyword":
            return original_normalized_input(args, tracking)

        raw_name = manual.clean(getattr(args, "name", ""), 160)
        if not manual.is_single_value(raw_name):
            raise manual.ManualTrackingError(
                "追踪关键词必须是一个完整条目，不能包含列表或多个对象。"
            )
        try:
            canonical_name = manual._validate_technology(raw_name)
        except manual.ManualTrackingError as exc:
            raise _keyword_error(manual, raw_name, exc) from exc

        keyword_args = argparse.Namespace(**vars(args))
        keyword_args.kind = "keyword"
        keyword_args.name = canonical_name
        request = original_normalized_input(keyword_args, tracking)

        # The entity name itself is the primary search seed. Keep only genuine
        # aliases in entity.keywords so feedback compilation does not count the
        # same human signal twice.
        name_identity = manual.signal_identity(request["name"], "keywords")
        request["keywords"] = [
            keyword
            for keyword in request["keywords"]
            if manual.signal_identity(keyword, "keywords") != name_identity
        ]
        return request

    def keyword_aware_same_entity_identity(
        entity: Mapping[str, Any],
        request: Mapping[str, Any],
    ) -> bool:
        entity_kind = manual.clean(entity.get("kind"), 40).casefold()
        request_kind = manual.clean(request.get("kind"), 40).casefold()

        # The legacy technology matcher intentionally compares topic names by
        # signal identity. Once keyword becomes first-class, that broad match
        # would incorrectly reuse a keyword intent entity for a later genuine
        # technology (or vice versa). Require exact kind agreement whenever
        # either side is one of these semantic signal kinds.
        if entity_kind in _SEMANTIC_SIGNAL_KINDS or request_kind in _SEMANTIC_SIGNAL_KINDS:
            if entity_kind != request_kind:
                return False
        return original_same_entity_identity(entity, request)

    manual._normalized_input = keyword_aware_normalized_input
    manual._same_entity_identity = keyword_aware_same_entity_identity
    setattr(manual, _PATCH_FLAG, True)
