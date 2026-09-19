#!/usr/bin/env python3
"""Exact investment-institution identities from the versioned public directory.

Directory membership verifies identity, not a user's follow intention or an
operating-company profile. Unknown/ambiguous names never receive a guessed ID.
"""
from __future__ import annotations

import copy
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RANKINGS_PATH = ROOT / 'config/institution_rankings.json'
ALIASES_PATH = ROOT / 'config/institution_entity_aliases.json'
CATALOG_PATH = ROOT / 'lib/catalog-data.ts'
OVERRIDES_PATH = ROOT / 'config/institution_identity_overrides.json'


def identity(value: Any) -> str:
    return re.sub(r'[^a-z0-9\u3400-\u9fff]+', '', unicodedata.normalize('NFKC', str(value or '')).casefold())


def _public_url(value: Any) -> bool:
    try:
        url = urlsplit(str(value or ''))
        return bool(url.scheme in {'http', 'https'} and url.hostname and not url.username and not url.password)
    except ValueError:
        return False


def build_index(rankings: dict[str, Any], aliases: dict[str, Any], catalog: str = '', supplements: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Keep primary ranking evidence separate from classification references."""
    if not isinstance(rankings, dict) or not isinstance(aliases, dict):
        raise ValueError('Institution registries must be JSON objects')
    sources = {r.get('id'): r for r in rankings.get('sources', []) if isinstance(r, dict)}
    directory: dict[str, dict[str, Any]] = {}
    reviewed = aliases.get('entities', {})
    if not isinstance(reviewed, dict):
        raise ValueError('Institution aliases must be an object')
    for category in rankings.get('categories', []):
        source = sources.get(category.get('sourceId'), {})
        if source.get('role') != 'primary-ranking-source' or not _public_url(source.get('url')):
            continue
        for entry in category.get('entries', []):
            name = str(entry.get('name') or '').strip()
            if not identity(name):
                continue
            row = directory.setdefault(name, {'name': name, 'aliases': [], 'sourceUrls': [], 'profileSlug': ''})
            row['aliases'].extend(v for v in (name, entry.get('fullName')) if v)
            row['sourceUrls'].append(source['url'])
    for name, values in reviewed.items():
        if name in directory and isinstance(values, list):
            directory[name]['aliases'].extend(v for v in values if isinstance(v, str))
    if catalog:
        try:
            from .venture_profile_extraction import parse_catalog
        except ImportError:
            from venture_profile_extraction import parse_catalog
        _, institutions = parse_catalog(catalog)
        for spec in institutions:
            if not _public_url(spec.source_url):
                continue
            matching = [r for r in directory.values() if identity(spec.name) in {identity(v) for v in r['aliases']}]
            if len(matching) == 1:
                row = matching[0]
            else:
                row = directory.setdefault(spec.name, {'name': spec.name, 'aliases': [], 'sourceUrls': [], 'profileSlug': ''})
            row['aliases'].extend(v for v in (spec.name, spec.english_name) if v)
            row['sourceUrls'].append(spec.source_url)
            row['profileSlug'] = spec.slug
    for entry in (supplements or {}).get('institutions', []):
        if entry.get('status') != 'verified' or not _public_url(entry.get('sourceUrl')) or not entry.get('evidence'):
            continue
        name = str(entry.get('name') or '').strip()
        if not identity(name):
            continue
        row = directory.setdefault(name, {'name': name, 'aliases': [], 'sourceUrls': [], 'profileSlug': ''})
        row['aliases'].extend([name, *entry.get('aliases', [])])
        row['sourceUrls'].append(entry['sourceUrl'])
    index: dict[str, list[dict[str, Any]]] = {}
    for row in directory.values():
        # Namespace deliberately differs from company: / company-candidate:.
        row['targetId'] = 'institution:' + identity(row['name'])
        row['sourceUrls'] = list(dict.fromkeys(row['sourceUrls']))
        row['aliases'] = list(dict.fromkeys(row['aliases']))
        for key in {identity(v) for v in row['aliases']} - {''}:
            index.setdefault(key, []).append(row)
    return index


@lru_cache(maxsize=8)
def _load_index(fingerprints: tuple[tuple[str, int, int], ...]) -> dict[str, list[dict[str, Any]]]:
    paths = [Path(item[0]) for item in fingerprints]
    return build_index(json.loads(paths[0].read_text(encoding='utf-8')), json.loads(paths[1].read_text(encoding='utf-8')), paths[2].read_text(encoding='utf-8'), json.loads(paths[3].read_text(encoding='utf-8')))


def lookup(name: str) -> list[dict[str, Any]]:
    paths = (RANKINGS_PATH, ALIASES_PATH, CATALOG_PATH, OVERRIDES_PATH)
    fingerprints = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
    return copy.deepcopy(_load_index(fingerprints).get(identity(name), []))
