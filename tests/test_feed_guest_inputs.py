"""Fail-closed parsing for the disposable feed guest's independent pin."""
from pathlib import Path
import subprocess
import tempfile
import unittest


FILES = (Path(__file__).resolve().parents[1] /
         'meta-int/recipes-test/int-feed-smoke/files')
FINGERPRINT = 'A' * 40
PUBLIC = 'pub:-:2048:1:1234:1700000000:1700086400::::::scSC:\n'
FPR = f'fpr:::::::::{FINGERPRINT}:\n'


class GuestInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'input'

    def run_helper(self, name, contents, *args):
        self.path.write_text(contents)
        return subprocess.run(['sh', str(FILES / name), str(self.path), *args],
                              capture_output=True, text=True, check=False)

    def test_unique_fingerprint_and_success_case(self):
        result = self.run_helper('int-feed-args',
                                 f'console=ttyS0 int_feed_case=success int_feed_fingerprint={FINGERPRINT}')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, FINGERPRINT + '\n')
        for cmdline in (f'int_feed_case=success int_feed_fingerprint={FINGERPRINT.lower()}',
                        f'int_feed_case=fail int_feed_fingerprint={FINGERPRINT}',
                        f'int_feed_case= int_feed_case=success int_feed_fingerprint={FINGERPRINT}',
                        f'int_feed_case=success int_feed_fingerprint= int_feed_fingerprint={FINGERPRINT}',
                        f'int_feed_case=success int_feed_fingerprint={FINGERPRINT} int_feed_fingerprint={FINGERPRINT}'):
            with self.subTest(cmdline=cmdline):
                self.assertNotEqual(self.run_helper('int-feed-args', cmdline).returncode, 0)

    def test_primary_key_must_match_and_remain_valid(self):
        def check(listing, expected=FINGERPRINT, now='1700000001'):
            return self.run_helper('int-feed-keycheck', listing, expected, now).returncode

        self.assertEqual(check(PUBLIC + FPR), 0)
        for listing in (PUBLIC + FPR + PUBLIC + FPR,
                        PUBLIC + FPR + 'sub:-:2048:1:1:1700000000:1700086400:\n',
                        PUBLIC.replace('pub:-:', 'pub:r:') + FPR,
                        PUBLIC.replace('1700086400', '1700000000') + FPR,
                        PUBLIC.replace('1700086400', '') + FPR,
                        PUBLIC + f'fpr:::::::::{"B" * 40}:\n',
                        PUBLIC + FPR + 'sec:-:2048:1:1:1700000000:1700086400:\n'):
            with self.subTest(listing=listing):
                self.assertNotEqual(check(listing), 0)
        self.assertNotEqual(check(PUBLIC + FPR, now='not-a-time'), 0)


if __name__ == '__main__':
    unittest.main()
