from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import manual_tracking as manual
from tools import manual_tracking_batch as batch
from tools import manual_follow_decision as policy
from tools.entity_resolution import Resolution
from tools.reconcile_entity_resolution import stabilize_payloads
from tools.resolved_company_captures import resolved_company_captures

NOW = '2026-09-19T03:00:00+00:00'
ADMINS = {'actors': ['VCIQ']}


def fixture():
    config = {'schemaVersion': 1, 'tracks': [
        {'slug': s, 'name': s, 'keywords': [], 'people': [], 'sampleCompanies': []}
        for s in ('vc', 'other')], 'sources': []}
    return config, {'schemaVersion': 1, 'records': []}, {'schemaVersion': 1, 'entities': [], 'memberships': []}


def request(origin='manual-confirmed', tracks=None):
    return {'kind': 'company', 'name': '未入目录的新机构', 'trackSlugs': tracks or ['vc'],
            'trackSlug': '', 'keywords': [], 'sourceUrl': 'https://example.com/evidence',
            'sourceCategory': 'media', 'sourceType': '', 'region': '全球',
            'reasons': ['个人研究兴趣'], 'note': '批量确认自动扩展为持续关注', 'origin': origin}


def unknown():
    return Resolution('review', 'company', 'company', '未入目录的新机构', '', 'low', 'unresolved', 'No registry entry', '未入目录的新机构', False)


def apply(values, row=None, resolution=None, now=NOW):
    with patch.object(manual, 'resolve_entity', return_value=resolution or unknown()):
        return manual.apply_request(*values, row or request(), 'VCIQ', now)


def reconcile(values, admins=ADMINS):
    return stabilize_payloads(values[0], values[1], decisions_payload={'decisions': {}},
        company_registry_payload={'companies': []}, people_payload={'people': []},
        intents_payload=values[2], admins_payload=admins)


class ManualDecisionFirstTests(unittest.TestCase):
    def test_explicit_unknown_follow_is_active_with_real_machine_result_intact(self):
        values = fixture(); result = apply(values)
        self.assertFalse(result['reviewQueued'])
        self.assertEqual(result['manualDecisionStatus'], 'approved')
        self.assertEqual(result['resolution']['status'], 'review')
        self.assertEqual(result['identityState'], 'needs_enrichment')
        self.assertEqual(values[2]['memberships'][0]['state'], 'active')
        self.assertEqual(values[2]['memberships'][0]['manualDecision']['actor'], 'VCIQ')
        self.assertIn(request()['name'], values[0]['tracks'][0]['sampleCompanies'])
        self.assertNotIn(request()['name'], values[0]['tracks'][1]['sampleCompanies'])
        outcome = batch.applied_outcome({'index': 1, 'request': request(), 'applied': result})
        self.assertEqual(outcome['outcome'], 'applied')
        self.assertFalse(outcome['reviewQueued'])
        self.assertEqual(outcome['targetId'], result['entityId'])

    def test_automatic_and_unmarked_input_never_acquire_manual_approval(self):
        for origin in ('automatic', ''):
            with self.subTest(origin=origin):
                values = fixture(); result = apply(values, request(origin))
                self.assertTrue(result['reviewQueued'])
                self.assertNotIn('manualDecision', values[2]['memberships'][0])
                self.assertEqual(values[0]['tracks'][0]['sampleCompanies'], [])

    def test_reconciliation_cannot_undo_the_approval_or_create_second_review(self):
        values = fixture(); apply(values)
        first = reconcile(values)
        self.assertIn(request()['name'], first[0]['tracks'][0]['sampleCompanies'])
        self.assertEqual(first[1]['records'][0]['status'], 'applied')
        self.assertEqual(first[1]['records'][0]['manualDecisionStatus'], 'approved')
        self.assertEqual(first[1]['records'][0]['resolution']['status'], 'review')
        second = reconcile((first[0], first[1], values[2]))
        self.assertEqual(first[:2], second[:2])
        self.assertEqual(second[2]['rounds'], 0)

    def test_repeat_click_is_idempotent_and_does_not_forge_a_new_time(self):
        values = fixture(); apply(values); before = copy.deepcopy(values)
        result = apply(values, now='2026-09-20T03:00:00+00:00')
        self.assertFalse(result['changed'])
        self.assertEqual(values, before)

    def test_follow_remains_even_when_legacy_capture_is_absent(self):
        values = fixture(); apply(values)
        values[0]['tracks'][0]['sampleCompanies'] = []
        values[1]['records'] = []
        next_config, _, _ = reconcile(values)
        self.assertIn(request()['name'], next_config['tracks'][0]['sampleCompanies'])

    def test_removal_is_scoped_and_never_resurrected_by_machine_or_old_approval(self):
        values = fixture(); apply(values, request(tracks=['vc', 'other']))
        values[2]['memberships'][0]['state'] = 'rejected'
        next_config, inbox, _ = reconcile(values)
        self.assertEqual(next_config['tracks'][0]['sampleCompanies'], [])
        self.assertIn(request()['name'], next_config['tracks'][1]['sampleCompanies'])
        self.assertEqual(inbox['records'][0]['appliedTo'], ['other:sampleCompanies'])
        values[2]['memberships'][1]['state'] = 'removed'
        final, inbox, _ = reconcile((next_config, inbox, values[2]))
        self.assertEqual(final['tracks'][1]['sampleCompanies'], [])
        self.assertEqual(inbox['records'][0]['status'], 'dismissed')

    def test_explicit_reenable_replaces_revocation_and_records_new_time(self):
        values = fixture(); apply(values)
        values[2]['memberships'][0]['state'] = 'rejected'
        new_time = '2026-09-20T03:00:00+00:00'
        apply(values, now=new_time)
        self.assertEqual(values[2]['memberships'][0]['manualDecision']['at'], new_time)
        self.assertIn(request()['name'], reconcile(values)[0]['tracks'][0]['sampleCompanies'])

    def test_type_conflict_preserves_decision_without_merging_into_the_person(self):
        values = fixture()
        resolution = Resolution('resolved', 'company', 'person', 'Different Person', 'person:different',
            'high', 'people-registry', 'type conflict', '未入目录的新机构', True)
        result = apply(values, resolution=resolution)
        self.assertEqual(result['identityState'], 'conflict')
        self.assertEqual(result['manualDecisionStatus'], 'approved')
        self.assertNotEqual(result['entityId'], 'person:different')
        self.assertEqual(values[2]['entities'][0]['name'], request()['name'])
        self.assertEqual(values[0]['tracks'][0]['people'], [])
        self.assertIn(request()['name'], values[0]['tracks'][0]['sampleCompanies'])
        outcome = batch.applied_outcome({'index': 1, 'request': request(), 'applied': result})
        self.assertEqual(outcome['targetId'], result['entityId'])

    def test_scope_or_actor_tampering_cannot_manufacture_authority(self):
        for field, value in (('actor', 'github-actions[bot]'), ('trackId', 'track:other'),
                             ('entityId', 'company:unrelated'), ('requestedName', 'Unrelated'), ('status', 'rejected')):
            with self.subTest(field=field):
                values = fixture(); apply(values)
                values[2]['memberships'][0]['manualDecision'][field] = value
                self.assertNotIn('approved', policy.scoped_follow_states(values[2], ADMINS).values())

    def test_blocked_alias_wins_over_parallel_positive_edge(self):
        values = fixture(); apply(values)
        blocked = copy.deepcopy(values[2]['memberships'][0]); blocked['id'] = 'duplicate'; blocked['state'] = 'rejected'
        values[2]['memberships'].append(blocked)
        self.assertEqual(reconcile(values)[0]['tracks'][0]['sampleCompanies'], [])

    def test_follow_consent_is_not_formal_company_publication_approval(self):
        values = fixture(); apply(values)
        captures, _ = resolved_company_captures(values[1], entity_decisions_payload={'decisions': {}},
            company_registry_payload={'companies': []}, people_payload={'people': []}, tracking_payload=values[0])
        self.assertEqual(captures['records'], [])

    def test_failed_identity_evidence_does_not_remove_user_decision(self):
        values = fixture(); apply(values)
        before = copy.deepcopy(values[2])
        reconcile(values)
        self.assertEqual(values[2], before)
        self.assertEqual(values[2]['memberships'][0]['manualDecision']['status'], 'approved')


if __name__ == '__main__':
    unittest.main()
