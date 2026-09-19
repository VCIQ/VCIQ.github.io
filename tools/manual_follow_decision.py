"""Separate an authenticated follow decision from machine identity enrichment.

Only the manual writer may stamp decisions. Readers validate actor and scope
against the existing intent graph; model results never become approval records.
No new preference store, network requests or operating-company approvals.
"""
from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from typing import Any, Mapping

FIELDS = {'company': 'sampleCompanies', 'person': 'people', 'technology': 'keywords'}
BLOCKED = {'rejected', 'held', 'disabled', 'removed', 'ignored'}


def identity(value: Any, field: str = '') -> str:
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    if field == 'people':
        text = re.sub(r'\s+@[^\s]+$', '', text)
    return re.sub(r'[^a-z0-9\u3400-\u9fff+#./]+' if field == 'keywords' else r'[^a-z0-9\u3400-\u9fff]+', '', text)


def explicit_request(request: Mapping[str, Any]) -> bool:
    # Legacy callers without an origin retain the old fail-closed contract.
    # The authenticated CLI explicitly supplies manual; batch validates origin.
    return request.get('origin') in {'manual', 'manual-confirmed'}


def identity_state(resolution: Mapping[str, Any], kind: str) -> str:
    expected = 'topic' if kind == 'technology' else kind
    if resolution.get('status') == 'rejected' or resolution.get('entityType') != expected:
        return 'conflict'
    if resolution.get('status') == 'resolved' and resolution.get('source') in {
        'company-registry', 'people-registry', 'institution-directory',
        'human-decision', 'tracking-taxonomy', 'authenticated-manual-intent', 'explicit-type',
    }:
        return 'complete'
    if resolution.get('source') in {'company-registry', 'people-registry', 'human-decision', 'institution-directory'}:
        return 'conflict'
    return 'needs_enrichment'


def tracking_name(request: Mapping[str, Any], resolution: Mapping[str, Any]) -> str:
    expected = 'topic' if request['kind'] == 'technology' else request['kind']
    if resolution.get('status') == 'resolved' and resolution.get('entityType') == expected:
        return str(resolution.get('canonicalName') or request['name'])
    return str(request['name'])


def stamp_decision(intents: dict[str, Any], previous: Mapping[str, Any], request: Mapping[str, Any],
                   entity_id: str, actor: str, now: str, resolution: Mapping[str, Any]) -> bool:
    """Persist approval on the existing scoped edge, preserving retry timestamps."""
    if not explicit_request(request):
        return False
    old = {m['id']: m for m in previous.get('memberships', []) if isinstance(m, dict)}
    changed = False
    for member in intents.get('memberships', []):
        if member.get('entityId') != entity_id or member.get('trackId') not in {'track:' + s for s in request['trackSlugs']}:
            continue
        before = copy.deepcopy(member)
        former = old.get(member['id'], {})
        prior = former.get('manualDecision', {})
        material = '\x1f'.join([actor.casefold(), member['trackId'], entity_id, request['kind'], request['name']])
        decision_id = 'follow-' + hashlib.sha256(material.encode()).hexdigest()[:24]
        # A fresh re-enable is a new revision, not a retry of the old approval.
        at = prior.get('at') if former.get('state') == 'active' and prior.get('id') == decision_id else now
        member['manualDecision'] = {
            'version': 1, 'id': decision_id, 'status': 'approved', 'actor': actor,
            'at': at or now, 'trackId': member['trackId'], 'entityId': entity_id,
            'requestedName': request['name'], 'kind': request['kind'],
        }
        member['identityState'] = identity_state(resolution, request['kind'])
        member['identityResolution'] = copy.deepcopy(
            former['identityResolution'] if former.get('identityState') == member['identityState']
            and isinstance(former.get('identityResolution'), dict) else dict(resolution)
        )
        member['executionState'] = 'applied'
        member['state'] = 'active'
        member['pinned'] = True
        changed = changed or member != before
    return changed


def scoped_follow_states(intents: Mapping[str, Any], admins: Mapping[str, Any]) -> dict[tuple[str, str, str], str]:
    """Return exact approved/vetoed runtime keys. Negative edges always dominate."""
    actors = {str(a).strip().casefold() for a in admins.get('actors', []) if isinstance(a, str)}
    entities = {e.get('id'): e for e in intents.get('entities', []) if isinstance(e, dict)}
    states: dict[tuple[str, str, str], str] = {}
    for member in intents.get('memberships', []):
        if not isinstance(member, dict):
            continue
        entity = entities.get(member.get('entityId'), {})
        field = FIELDS.get(entity.get('kind'))
        slug = str(member.get('trackId') or '').removeprefix('track:')
        if not field or not slug:
            continue
        decision = member.get('manualDecision')
        decision = decision if isinstance(decision, dict) else {}
        origins = member.get('origins', [])
        auditable = any(isinstance(o, dict) and o.get('origin') == 'manual'
                        and str(o.get('actor', '')).casefold() in actors for o in origins)
        approved = bool(
            auditable and member.get('state') == 'active' and member.get('pinned') is True
            and decision.get('version') == 1 and decision.get('status') == 'approved'
            and decision.get('id') and decision.get('at')
            and str(decision.get('actor', '')).casefold() in actors
            and decision.get('trackId') == member.get('trackId')
            and decision.get('entityId') == member.get('entityId')
            and decision.get('kind') == entity.get('kind')
            and identity(decision.get('requestedName'), field) in {
                identity(n, field) for n in [entity.get('name'), *entity.get('aliases', [])] if n
            }
        )
        blocked = auditable and (member.get('state') in BLOCKED or entity.get('state') in BLOCKED)
        if not (approved or blocked):
            continue
        for name in [entity.get('name'), *entity.get('aliases', [])]:
            k = identity(name, field)
            key = (slug, field, k)
            if k and (blocked or states.get(key) != 'blocked'):
                states[key] = 'blocked' if blocked else 'approved'
    return states


def project_follow_states(config: dict[str, Any], intents: Mapping[str, Any], admins: Mapping[str, Any]) -> None:
    """Overlay explicit owner decisions after machine reconciliation, not before."""
    states = scoped_follow_states(intents, admins)
    tracks = {r.get('slug'): r for r in config.get('tracks', []) if isinstance(r, dict)}
    entities = {r.get('id'): r for r in intents.get('entities', []) if isinstance(r, dict)}
    for member in intents.get('memberships', []):
        e = entities.get(member.get('entityId'), {})
        field = FIELDS.get(e.get('kind'))
        slug = str(member.get('trackId', '')).removeprefix('track:')
        track = tracks.get(slug)
        if not track or not field:
            continue
        values = track.setdefault(field, [])
        name = str(e.get('name') or '')
        k = identity(name, field)
        if states.get((slug, field, k)) == 'approved' and not any(identity(v, field) == k for v in values):
            values.append(name)
    for slug, track in tracks.items():
        for field in FIELDS.values():
            if field in track:
                track[field] = [v for v in track[field] if states.get((slug, field, identity(v, field))) != 'blocked']
