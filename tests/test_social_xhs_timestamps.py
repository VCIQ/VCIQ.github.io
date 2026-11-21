"""Source chronology is evidence, not an inferred platform guarantee."""
import copy
import unittest
from tests.test_social_xhs import inputs, captured, STAMP, PATCHES
from tools.social.adapters.xhs import finalize, normalize_record
from tools.social.contracts import ContractError, validate

PUBLISHED = 1792670400000
UPDATED = 1792584000000


class SourceTimestampTests(unittest.TestCase):
    def result(self, *, published=PUBLISHED, updated=UPDATED, status='ok'):
        job, context, row = inputs()
        row.update(time=published, last_update_time=updated)
        capture = captured(job, row)
        if status != 'ok':
            capture.update(status=status, stopReason='auth', errorCode='AUTH')
        original = copy.deepcopy(capture)
        result = finalize(job, capture, context, patchset_hash=PATCHES)
        self.assertEqual(capture, original)
        return result

    def test_valid_conflict_admitted_only_as_unverified_discovery(self):
        result = self.result()
        self.assertEqual(result['receipt']['status'], 'ok')
        self.assertEqual(result['receipt']['counts']['emittedRows'], 1)
        doc = result['observations'][0]
        validate(doc, expected_kind='signal_observation')
        self.assertEqual(doc['evidence'], {'grade':'D','role':'discovery','verification':'unverified'})
        self.assertEqual(doc['observedAt'], STAMP)
        self.assertEqual(doc['publishedAt'], '2026-10-22T12:00:00+00:00')
        self.assertEqual(doc['updatedAt'], '2026-10-21T12:00:00+00:00')

    def test_conflict_has_exact_values_and_no_extra_profile_fields(self):
        result = self.result()
        self.assertEqual(result['diagnostics']['metadataConflicts'], [{
            'signalId':result['observations'][0]['signalId'],
            'code':'SOURCE_UPDATE_BEFORE_PUBLICATION',
            'publishedAt':'2026-10-22T12:00:00+00:00',
            'updatedAt':'2026-10-21T12:00:00+00:00',
            'resolution':'source_values_preserved_unverified'}])

    def test_new_normalizer_version_is_explicit(self):
        self.assertEqual(self.result()['receipt']['normalizerVersion'], 'xhs-shadow-v2')

    def test_equal_timestamps_are_not_conflicting(self):
        self.assertEqual(self.result(updated=PUBLISHED)['diagnostics']['metadataConflicts'], [])

    def test_later_update_is_not_conflicting(self):
        self.assertEqual(self.result(updated=PUBLISHED + 1000)['diagnostics']['metadataConflicts'], [])

    def test_unknown_timestamps_are_not_invented(self):
        for pub, upd in [(0,UPDATED),(PUBLISHED,0),(None,None)]:
            with self.subTest(pub=pub,upd=upd):
                result = self.result(published=pub,updated=upd)
                self.assertEqual(result['diagnostics']['metadataConflicts'], [])
                if not pub: self.assertIsNone(result['observations'][0]['publishedAt'])
                if not upd: self.assertIsNone(result['observations'][0]['updatedAt'])

    def test_future_publication_still_rejected(self):
        result = self.result(published=9999999999999)
        self.assertEqual(result['receipt']['status'],'schema_error')
        self.assertEqual(result['observations'],[])
        self.assertEqual(result['diagnostics']['metadataConflicts'],[])

    def test_future_update_still_rejected(self):
        result = self.result(updated=9999999999999)
        self.assertEqual(result['receipt']['status'],'schema_error')
        self.assertEqual(result['observations'],[])

    def test_seconds_and_boolean_update_still_rejected(self):
        self.assertEqual(self.result(updated=1792584000)['observations'],[])
        # The upstream projection already rejects booleans before finalize.
        # Also exercise the normalizer's independent field-type boundary.
        job, context, row = inputs()
        row.update(time=PUBLISHED, last_update_time=True)
        with self.assertRaisesRegex(ContractError, 'xhs_timestamp_type'):
            normalize_record(row,job,context,observed_at=STAMP,original_title=True)

    def test_auth_status_is_not_upgraded_by_valid_content(self):
        result = self.result(status='auth_required')
        self.assertEqual(result['receipt']['status'],'auth_required')
        self.assertEqual(result['receipt']['stopReason'],'auth')

    def test_content_hash_still_ignores_metric_and_update_changes(self):
        earlier = self.result()['observations'][0]
        later = self.result(updated=PUBLISHED + 1000)['observations'][0]
        self.assertEqual(earlier['signalId'],later['signalId'])
        self.assertEqual(earlier['contentHash'],later['contentHash'])

    def test_secret_text_and_bad_identity_are_not_rescued(self):
        for fields in [{'desc':'cookie=PRIVATE_SYNTHETIC'}, {'note_id':'invalid'}]:
            job, context, row = inputs()
            row.update(time=PUBLISHED,last_update_time=UPDATED,**fields)
            with self.assertRaises(ContractError):
                normalize_record(row,job,context,observed_at=STAMP,original_title=True)


if __name__ == '__main__':
    unittest.main()
