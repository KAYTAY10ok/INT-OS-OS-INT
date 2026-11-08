"""Repository trust configuration rejects injected options and wrong keys."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'meta-int/recipes-core/int-package-feed/files/feed_config.py'
SPEC = importlib.util.spec_from_file_location('feed_config', SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
PIN = 'A' * 40
NOW = 1800000000
LISTING = 'pub:-:3072:1:1234:1700000000:1900000000:::::scSC:\nfpr:::::::::' + PIN + ':\n'

class FeedConfigTests(unittest.TestCase):
    def test_required_trust_checks_and_literal_local_key(self):
        config = helper.repository('https://packages.example.invalid/int/x86_64', PIN)
        for setting in ('gpgcheck=1', 'repo_gpgcheck=1',
                        'sslverify=1', 'skip_if_unavailable=0'):
            self.assertIn('\n' + setting + '\n', config)
        self.assertIn('gpgkey=file://' + helper.KEY_PATH, config)

    def test_unsafe_or_ambiguous_addresses_fail(self):
        for url in ('http://host/repo', 'file:///repo', 'https://user:pass@host/repo',
                    'https://host/repo\ngpgcheck=0', 'https://host/$releasever',
                    'https://host/repo?token=secret', 'https://host/repo#fragment',
                    'https://host/repo;enabled=0', 'https://host:99999/repo',
                    'https://host/`cmd`', 'https://host/$(cmd)'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                helper.repository(url, PIN)
        for pin in ('A'*16, 'a'*40, '', PIN+'\n'):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                helper.repository('https://host/repo', pin)

    def test_key_identity_and_validity(self):
        helper.validate_key_listing(LISTING, PIN, NOW)
        for listing in ('', LISTING + LISTING, LISTING.replace(PIN, 'B'*40),
                        LISTING.replace('pub:-:', 'pub:r:'), LISTING.replace('scSC', 'cC'), LISTING.replace('scSC', 'scSCD'),
                        LISTING.replace('1900000000', '1750000000'),
                        LISTING.replace('1700000000', '1850000000'),
                        LISTING + 'sec:-:3072:1:1234:1700000000:1900000000:::::scSC:\n'):
            with self.subTest(listing=listing), self.assertRaises(ValueError):
                helper.validate_key_listing(listing, PIN, NOW)

if __name__ == '__main__':
    unittest.main()
