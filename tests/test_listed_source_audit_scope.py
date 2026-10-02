import contextlib
import io
import json
import unittest
from unittest.mock import patch
from tools import audit_listed_innovation_sources as audit


class SourceAuditScopeTests(unittest.TestCase):
    def test_unapproved_company_cannot_start_collection(self):
        with patch('sys.argv', ['audit', '--company', 'unapproved-company']), \
             patch.object(audit, 'crawl_all_companies') as crawl:
            with self.assertRaises(ValueError):
                audit.main()
            crawl.assert_not_called()

    def test_explicit_company_selection_stays_read_only_and_bounded(self):
        output = io.StringIO()
        with patch('sys.argv', ['audit', '--company', 'tencent']), \
             patch.object(audit, 'crawl_all_companies', return_value=([], [{
                 'companySlug': 'tencent', 'accepted': 0,
             }])) as crawl, contextlib.redirect_stdout(output):
            self.assertEqual(audit.main(), 0)
        self.assertEqual([spec.slug for spec in crawl.call_args.args[0]], ['tencent'])
        receipt = json.loads(output.getvalue())
        self.assertFalse(receipt['snapshotPublished'])
        self.assertEqual(receipt['approvedCompanyCount'], 40)
        self.assertEqual(receipt['attemptedCompanyCount'], 1)
        self.assertEqual(receipt['selectedCompanySlugs'], ['tencent'])
