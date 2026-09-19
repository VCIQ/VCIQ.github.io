#!/usr/bin/env python3
"""Complete audited institution follow confirmations without approving new leads.

Only pending, pinned manual edges overlapping the active discovery ledger are
eligible. The versioned institution directory supplies identity evidence; owner
blocks, explicit resolution decisions, unreviewed automation and other tracks
remain untouched. Default mode is a read-only preview.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from . import manual_tracking as manual
    from .institution_identity import identity, lookup
except ImportError:
    import manual_tracking as manual
    from institution_identity import identity, lookup

ROOT = Path(__file__).resolve().parents[1]
BLOCKED = {'held', 'rejected', 'disabled', 'removed', 'ignored'}


def _keys(entity: dict[str, Any]) -> set[str]:
    return {identity(v) for v in [entity.get('name'), *entity.get('aliases', [])]} - {''}


def _investment_track(track: dict[str, Any]) -> bool:
    return identity(track.get('name')) in {identity('风险投资'), 'venturecapital'} or {
        identity('私人股权投资'), identity('天使轮')
    }.issubset({identity(v) for v in track.get('keywords', [])})


def reconcile(tracking_payload: dict[str, Any], inbox_payload: dict[str, Any],
              intents_payload: dict[str, Any], ledger: dict[str, Any], admins: dict[str, Any],
              *, track_slug: str | None = None, now: str | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    tracking, inbox, intents = copy.deepcopy((tracking_payload, inbox_payload, intents_payload))
    for payload, fields in ((tracking, ('tracks',)), (inbox, ('records',)), (intents, ('entities', 'memberships')), (ledger, ('added', 'removed'))):
        if payload.get('schemaVersion') != 1 or any(not isinstance(payload.get(k), list) for k in fields):
            raise ValueError('Unsupported or malformed tracking state; no files written')
    allowed = manual.allowed_actors(admins)
    timestamp = now or datetime.now(UTC).isoformat(timespec='seconds')
    tracks = {r['slug']: r for r in tracking['tracks'] if _investment_track(r) and (track_slug is None or r['slug'] == track_slug)}
    if track_slug is not None and track_slug not in tracks:
        raise ValueError('Requested investment track not found')
    entities = {e['id']: e for e in intents['entities']}
    tombstones: dict[str, set[str]] = {slug: set() for slug in tracks}
    automatic: dict[str, set[str]] = {slug: set() for slug in tracks}
    for state, target in (('added', automatic), ('removed', tombstones)):
        for row in ledger[state]:
            if row.get('track') in tracks and row.get('kind') in {'company', 'sampleCompanies', 'companies'}:
                target[row['track']].add(identity(row.get('value')))
    for slug, track in tracks.items():
        tombstones[slug].update(identity(v) for v in track.get('ignoredRecommendations', {}).get('companies', []))
    for member in intents['memberships']:
        slug = str(member.get('trackId', '')).removeprefix('track:')
        e = entities.get(member.get('entityId'), {})
        if slug in tracks and (member.get('state') in BLOCKED or e.get('state') in BLOCKED):
            tombstones[slug].update(_keys(e))
    promoted, held = [], []
    for member in list(intents['memberships']):
        slug = str(member.get('trackId', '')).removeprefix('track:')
        e = entities.get(member.get('entityId'), {})
        if slug not in tracks or e.get('kind') != 'company' or member.get('state') != 'review' or member.get('pinned') is not True:
            continue
        keys = _keys(e)
        if not keys & automatic[slug] or keys & tombstones[slug]:
            continue
        origins = [o for o in member.get('origins', []) if isinstance(o, dict) and o.get('origin') == 'manual'
                   and str(o.get('actor', '')).casefold() in allowed and o.get('evidenceUrl') and o.get('reasons')]
        if not origins:
            continue
        matches = lookup(e['name'])
        if len(matches) != 1:
            held.append({'name': e['name'], 'track': slug, 'reason': 'No unique evidence-backed institution identity'})
            continue
        # A veto on any reviewed alias remains authoritative during migration.
        institution = matches[0]
        if {identity(v) for v in institution['aliases']} & tombstones[slug]:
            continue
        origin = origins[-1]
        source = {'title': e['name'], 'summary': origin.get('note', ''), 'url': origin['evidenceUrl']}
        resolution = manual.resolve_entity('company', e['name'], source, tracking_payload=tracking)
        if resolution.status != 'resolved' or resolution.entityType != 'company' or resolution.targetId != institution['targetId']:
            held.append({'name': e['name'], 'track': slug, 'reason': resolution.reason})
            continue
        request = {
            'kind': 'company', 'name': e['name'], 'trackSlugs': [slug], 'trackSlug': '',
            'keywords': list(e.get('keywords', [])), 'sourceUrl': manual.normalize_url(origin['evidenceUrl'], required=True),
            'sourceCategory': 'media', 'sourceType': '', 'region': '全球',
            'reasons': list(origin['reasons']), 'note': origin.get('note', ''), 'origin': 'manual-confirmed',
        }
        result = manual.apply_request(tracking, inbox, intents, request, origin['actor'], timestamp)
        if result['reviewQueued']:
            raise ValueError('Institution identity changed while preparing the transaction')
        promoted.append({'name': e['name'], 'track': slug, 'institutionId': result['entityId'], 'identityEvidence': institution['sourceUrls']})
    report = {'changed': (tracking, inbox, intents) != (tracking_payload, inbox_payload, intents_payload),
              'promotedCount': len(promoted), 'promoted': promoted, 'heldCount': len(held), 'held': held,
              'automaticApprovals': 0}
    return tracking, inbox, intents, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--track')
    parser.add_argument('--now')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--check', action='store_true')
    for key, filename in (('tracking', 'user_tracking'), ('inbox', 'tracking_capture_inbox'), ('intents', 'tracking_intents'), ('ledger', 'tracking_auto_discovery'), ('admins', 'tracking_admins')):
        parser.add_argument('--' + key, type=Path, default=ROOT / 'config' / (filename + '.json'))
    args = parser.parse_args(argv)
    try:
        current = [json.loads(getattr(args, k).read_text(encoding='utf-8')) for k in ('tracking', 'inbox', 'intents', 'ledger', 'admins')]
        tracking, inbox, intents, report = reconcile(*current, track_slug=args.track, now=args.now)
        if args.check and report['changed']:
            print(json.dumps({'checkPassed': False, **report}, ensure_ascii=False))
            return 1
        if args.apply:
            for key, before, after in zip(('tracking', 'inbox', 'intents'), current, (tracking, inbox, intents)):
                if before != after:
                    manual.write_json_atomic(getattr(args, key), after)
        print(json.dumps({'mode': 'apply' if args.apply else 'check' if args.check else 'preview', **report}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
