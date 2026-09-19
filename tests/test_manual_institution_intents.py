from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import institution_identity as institutions
from tools import manual_tracking as manual
from tools import reconcile_manual_institution_intents as repair
from tools.apply_manual_company_trust import apply_manual_company_trust
from tools.entity_resolution import resolve_entity
from tools.resolved_company_captures import resolved_company_captures

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-19T03:00:00+00:00'


def state(name='创新工场'):
    eid = manual.stable_id('company', name)
    tracking = {'schemaVersion': 1, 'tracks': [
        {'slug': 'vc', 'name': '风险投资', 'enabled': True, 'keywords': [], 'people': [], 'sampleCompanies': [name, '源码资本']},
        {'slug': 'other', 'name': '其他赛道', 'keywords': [], 'people': [], 'sampleCompanies': []},
    ], 'sources': []}
    origin = {'id': 'old-origin', 'origin': 'manual', 'actor': 'VCIQ', 'at': '2026-09-18T10:24:10+00:00',
              'evidenceUrl': 'https://vciq.github.io/companies/', 'reasons': ['个人研究兴趣'], 'note': '批量确认自动扩展为持续关注'}
    intents = {'schemaVersion': 1, 'entities': [{'id': eid, 'kind': 'company', 'name': name, 'aliases': [], 'keywords': [],
                                              'state': 'review', 'resolutionSource': 'unresolved', 'resolutionStatus': 'review'}],
               'memberships': [{'id': manual.stable_id('membership', 'track:vc', eid, 'actor'), 'entityId': eid, 'trackId': 'track:vc',
                                'role': 'actor', 'state': 'review', 'pinned': True, 'origins': [origin]}]}
    ledger = {'schemaVersion': 1, 'added': [{'track': 'vc', 'kind': 'sampleCompanies', 'value': v} for v in [name, '源码资本']], 'removed': []}
    return tracking, {'schemaVersion': 1, 'records': []}, intents, ledger, {'actors': ['VCIQ']}


class InstitutionIdentityTests(unittest.TestCase):
    def resolve(self, name, **kwargs):
        args = dict(decisions_payload={'decisions': {}}, company_registry_payload={'companies': []}, people_payload={'people': []}, tracking_payload={'tracks': []})
        args.update(kwargs)
        return resolve_entity('company', name, **args)

    def test_known_names_and_reviewed_aliases_resolve_without_suffix_guessing(self):
        for name in ('创新工场', '美团龙珠', '国投创新', '鼎晖投资', '联想之星', 'Sinovation Ventures', 'CMC资本'):
            with self.subTest(name=name):
                r = self.resolve(name)
                self.assertEqual(r.source, 'institution-directory')
                self.assertEqual(r.status, 'resolved')
                self.assertTrue(r.targetId.startswith('institution:'))
        self.assertEqual(self.resolve('Sinovation Ventures').targetId, self.resolve('创新工场').targetId)

    def test_unknown_institution_name_is_not_whitelisted(self):
        self.assertEqual(self.resolve('尚无核验的机构名字').status, 'review')

    def test_classification_only_source_cannot_verify_an_institution(self):
        payload = {'sources': [{'id': 's', 'role': 'classification-reference', 'url': 'https://example.com/'}],
                   'categories': [{'sourceId': 's', 'entries': [{'name': 'UnverifiedExample'}]}]}
        self.assertEqual(institutions.build_index(payload, {'entities': {}}), {})

    def test_duplicate_reviewed_aliases_remain_ambiguous(self):
        payload = {'sources': [{'id': 's', 'role': 'primary-ranking-source', 'url': 'https://example.com/rank'}],
                   'categories': [{'sourceId': 's', 'entries': [{'name': 'Alpha'}, {'name': 'Beta'}]}]}
        index = institutions.build_index(payload, {'entities': {'Alpha': ['Collision'], 'Beta': ['Collision']}})
        with patch.object(institutions, 'lookup', return_value=index['collision']):
            r = self.resolve('Collision')
        self.assertEqual(r.status, 'review')
        self.assertEqual(r.targetId, '')

    def test_human_rejection_or_reclassification_dominates_directory(self):
        for status, kind in (('rejected', 'company'), ('review', 'company'), ('resolved', 'person')):
            with self.subTest(status=status, kind=kind):
                decisions = {'decisions': {'创新工场': {'status': status, 'entityType': kind, 'canonicalName': '创新工场', 'confidence': 'verified', 'note': 'reviewed'}}}
                r = self.resolve('创新工场', decisions_payload=decisions)
                self.assertEqual((r.status, r.entityType, r.source), (status, kind, 'human-decision'))

    def test_company_alias_ambiguity_is_not_bypassed(self):
        r = self.resolve('创新工场', company_registry_payload={'companies': [{'name': '创新工场', 'slug': 'one'}, {'name': '创新工场', 'slug': 'two'}]})
        self.assertEqual(r.status, 'review')
        self.assertEqual(r.source, 'company-registry')

    def test_future_explicit_confirmation_uses_the_real_manual_writer(self):
        tracking, inbox, intents, *_ = state()
        request = {'kind': 'company', 'name': '创新工场', 'trackSlugs': ['vc'], 'trackSlug': '', 'keywords': [],
                   'sourceUrl': 'https://vciq.github.io/companies/', 'sourceCategory': 'media', 'sourceType': '',
                   'region': '全球', 'reasons': ['个人研究兴趣'], 'note': '显式确认', 'origin': 'manual-confirmed'}
        result = manual.apply_request(tracking, inbox, intents, request, 'VCIQ', NOW)
        self.assertFalse(result['reviewQueued'])
        self.assertEqual(intents['memberships'][0]['state'], 'active')
        self.assertEqual(result['entityId'], 'institution:创新工场')

    def test_automatic_input_does_not_inherit_human_confirmation(self):
        tracking, inbox, intents, *_ = state()
        intents['entities'] = []; intents['memberships'] = []
        request = {'kind': 'company', 'name': '源码资本', 'trackSlugs': ['vc'], 'trackSlug': '', 'keywords': [],
                   'sourceUrl': 'https://vciq.github.io/companies/', 'sourceCategory': 'media', 'sourceType': '',
                   'region': '全球', 'reasons': ['个人研究兴趣'], 'note': 'machine candidate', 'origin': 'automatic'}
        result = manual.apply_request(tracking, inbox, intents, request, 'VCIQ', NOW)
        self.assertTrue(result['reviewQueued'])
        self.assertNotEqual(intents['memberships'][0]['state'], 'active')

    def test_raw_builder_cannot_reintroduce_an_institution_with_an_old_acceptance(self):
        from tools.build_company_candidates import build_candidate_snapshot
        from tools.resolve_company_entities import build_registry
        articles = {'generatedAt': NOW, 'articles': [{'id': 'a', 'company': '创新工场', 'type': '融资', 'source': {'url': 'https://example.com/a'}}]}
        captures = {'records': [{'id': 'c', 'status': 'applied', 'entityType': 'company', 'canonicalName': '创新工场', 'source': {'url': 'https://example.com/c'}}]}
        decisions = {'decisions': {'创新工场': {'status': 'accepted', 'note': 'previous follow'}}}
        result = build_candidate_snapshot(articles, build_registry({'companies': []}), decisions, captures)
        self.assertEqual(result['candidates'], [])

    def test_institution_capture_does_not_enter_company_onboarding_or_autotrust(self):
        captures = {'records': [{'id': 'c1', 'status': 'applied', 'entityType': 'company', 'canonicalName': '创新工场', 'rawSelection': '创新工场',
                                 'capturedBy': 'VCIQ', 'source': {'url': 'https://vciq.github.io/companies/'}}]}
        args = dict(entity_decisions_payload={'decisions': {}}, company_registry_payload={'companies': []}, people_payload={'people': []}, tracking_payload={'tracks': []})
        output, stats = resolved_company_captures(captures, **args)
        self.assertEqual(output['records'], [])
        self.assertEqual(stats.get('institutionCount'), 1)
        decisions, report = apply_manual_company_trust({'candidates': [{'name': '创新工场', 'decisionKey': '创新工场', 'captureIds': ['c1']}]}, {'decisions': {}}, args.pop('tracking_payload'), captures, **args)
        self.assertEqual(decisions['decisions'], {})
        self.assertEqual(report['trustedCount'], 0)


class ManualInstitutionMigrationTests(unittest.TestCase):
    def test_only_audited_pin_changes_and_replay_is_idempotent(self):
        values = state(); original = copy.deepcopy(values)
        first = repair.reconcile(*values, track_slug='vc', now=NOW)
        self.assertEqual(first[3]['promotedCount'], 1)
        self.assertEqual(first[3]['automaticApprovals'], 0)
        self.assertEqual(first[0]['tracks'][1], values[0]['tracks'][1])
        self.assertNotIn('源码资本', [e['name'] for e in first[2]['entities']])
        self.assertIn(original[2]['memberships'][0]['origins'][0], first[2]['memberships'][0]['origins'])
        self.assertEqual(values, original)
        second = repair.reconcile(*first[:3], values[3], values[4], track_slug='vc', now='2026-09-20T03:00:00+00:00')
        self.assertEqual(first[:3], second[:3])
        self.assertFalse(second[3]['changed'])

    def test_owner_removal_ignore_and_blocked_alias_are_never_resurrected(self):
        for veto in ('ledger', 'ignored', 'edge', 'entity', 'alias'):
            with self.subTest(veto=veto):
                values = state()
                if veto == 'ledger': values[3]['removed'].append({'track': 'vc', 'kind': 'sampleCompanies', 'value': '创新工场'})
                elif veto == 'ignored': values[0]['tracks'][0]['ignoredRecommendations'] = {'companies': ['创新工场']}
                elif veto == 'edge': values[2]['memberships'][0]['state'] = 'removed'
                elif veto == 'entity': values[2]['entities'][0]['state'] = 'rejected'
                else: values[3]['removed'].append({'track': 'vc', 'kind': 'sampleCompanies', 'value': 'Sinovation Ventures'})
                result = repair.reconcile(*values, now=NOW)
                self.assertEqual(result[:3], values[:3])
                self.assertEqual(result[3]['promotedCount'], 0)

    def test_actor_pin_origin_and_active_ledger_are_all_required(self):
        for missing in ('actor', 'pin', 'origin', 'ledger'):
            with self.subTest(missing=missing):
                values = state(); member = values[2]['memberships'][0]
                if missing == 'actor': member['origins'][0]['actor'] = 'github-actions[bot]'
                elif missing == 'pin': member['pinned'] = False
                elif missing == 'origin': member['origins'][0]['origin'] = 'automatic'
                else: values[3]['added'] = []
                result = repair.reconcile(*values, now=NOW)
                self.assertEqual(result[:3], values[:3])

    def test_default_cli_preview_is_byte_for_byte_read_only(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / (k + '.json') for k in ('tracking', 'inbox', 'intents', 'ledger', 'admins')]
            argv = ['--track', 'vc', '--now', NOW]
            for key, path, value in zip(('tracking', 'inbox', 'intents', 'ledger', 'admins'), paths, state()):
                path.write_text(json.dumps(value), encoding='utf-8'); argv += ['--' + key, str(path)]
            before = [p.read_bytes() for p in paths]
            with contextlib.redirect_stdout(io.StringIO()): code = repair.main(argv)
            self.assertEqual(code, 0)
            self.assertEqual([p.read_bytes() for p in paths], before)

    def test_unknown_names_and_corrupt_state_fail_closed(self):
        values = state('尚无核验的机构名字')
        result = repair.reconcile(*values, now=NOW)
        self.assertEqual(result[:3], values[:3])
        self.assertEqual(result[3]['heldCount'], 1)
        values[2]['memberships'] = 'corrupt'
        with self.assertRaises(ValueError): repair.reconcile(*values, now=NOW)


if __name__ == '__main__':
    unittest.main()
