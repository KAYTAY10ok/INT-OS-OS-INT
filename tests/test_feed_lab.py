"""The laboratory must distinguish an RPM signature from a digest."""
import importlib.util
from pathlib import Path
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] /
          'meta-int/recipes-test/int-feed-lab/files/int-feed-lab.py')
SPEC = importlib.util.spec_from_file_location('int_feed_lab', SCRIPT)
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)


class SignatureLineTests(unittest.TestCase):
    def test_only_accepts_successful_signature_line(self):
        self.assertTrue(lab.signature_ok('    Header V4 RSA/SHA256 Signature, key ID 12345678: OK\n'))
        for output in ('    Header SHA256 digest: OK\n',
                       '    Header V4 RSA/SHA256 Signature, key ID 12345678: NOKEY\n',
                       '    Header V4 RSA/SHA256 Signature, key ID 12345678: BAD\n',
                       ''):
            with self.subTest(output=output):
                self.assertFalse(lab.signature_ok(output))

    def test_machine_status_requires_exact_record_and_argument(self):
        output = ('gpg: BAD signature from key DEADBEEF\n'
                  '[GNUPG:] BADSIG ABCDEF0123456789 signer\n'
                  '[GNUPG:] NO_PUBKEY 1234567890ABCDEF\n'
                  '[GNUPG:] FAILURE verify 33587281\n')
        self.assertTrue(lab.has_status(output, 'BADSIG', 'ABCDEF0123456789'))
        self.assertTrue(lab.has_status(output, 'NO_PUBKEY', '1234567890ABCDEF'))
        self.assertTrue(lab.has_status(output, 'FAILURE', 'verify'))
        self.assertFalse(lab.has_status(output, 'BADSIG', 'DEADBEEF'))
        self.assertFalse(lab.has_status(output, 'NO_PUBKEY', '12345678'))
        self.assertFalse(lab.has_status(output, 'FAILURE', 'gpg-exit'))
        self.assertFalse(lab.has_status('text [GNUPG:] BADSIG ABCDEF0123456789',
                                        'BADSIG', 'ABCDEF0123456789'))


if __name__ == '__main__':
    unittest.main()
