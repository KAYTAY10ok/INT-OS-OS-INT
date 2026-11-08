"""A failed tool or wrong failure stage must never qualify a negative case."""
from pathlib import Path
import runpy
import unittest

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    "meta-int/recipes-test/int-feed-lab/files/int-feed-audit-matrix.py"))


class MatrixQualificationTests(unittest.TestCase):
    def test_positive_requires_complete_audit_and_empty_db_control(self):
        check = MODULE['qualifies']
        report = dict(result='pass', complete=True, checks_passed=['rpm_signatures_rejected_empty_db'])
        self.assertTrue(check('valid-v1', 0, report))
        for changed in (dict(complete=False), dict(result='fail'), dict(checks_passed=[])):
            self.assertFalse(check('valid-v1', 0, {**report, **changed}))
        self.assertFalse(check('valid-v1', 1, report))

    def test_negative_requires_exact_stage_and_specific_reason(self):
        check = MODULE['qualifies']
        report = dict(result='fail', complete=False,
                      checks_passed=['rpm_key_imported_isolated_db'],
                      error='RPM verification failed: Header signature: NOKEY')
        self.assertTrue(check('wrong-key-rpm', 1, report))
        for changed in (dict(error='could not run rpmkeys'), dict(complete=True),
                        dict(checks_passed=['feed_tree_regular_files_only']), dict(result='pass')):
            self.assertFalse(check('wrong-key-rpm', 1, {**report, **changed}))
        self.assertFalse(check('wrong-key-rpm', 127, report))
        self.assertFalse(check('unsigned-rpm', 1, report))
