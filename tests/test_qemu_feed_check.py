"""Host-side protocol and isolation checks; no QEMU guest is run here."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/qemu-feed-check.py'
SPEC = importlib.util.spec_from_file_location('int_feed_check_test', SCRIPT)
feed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(feed)


class FeedProtocolTests(unittest.TestCase):
    def setUp(self):
        self.process = {'returncode': 0, 'timed_out': False, 'interrupted_signal': None, 'output_limit': False}
        self.lines = list(feed.MARKERS) + ['[ 123.4] reboot: Power down']

    def analyze(self, lines, process=None):
        return feed.analyze_log('\r\n'.join(lines) + '\r\n', process or self.process)

    def test_complete_ordered_protocol_passes(self):
        self.assertTrue(self.analyze(self.lines)['passed'])

    def test_unsigned_protocol_requires_every_ordered_assertion(self):
        negative = list(feed.CASE_MARKERS['unsigned-rpm']) + ['[ 123.4] reboot: Power down']
        def check(lines):
            return feed.analyze_log('\r\n'.join(lines) + '\r\n', self.process, 'unsigned-rpm')['passed']
        self.assertTrue(check(negative))
        for index in range(len(negative)):
            with self.subTest(missing=negative[index]):
                self.assertFalse(check(negative[:index] + negative[index + 1:]))
        self.assertFalse(check(negative + [negative[2]]))
        self.assertFalse(check([negative[1], negative[0], *negative[2:]]))
        self.assertFalse(check(negative + ['INT_FEED_CASE:success:PASS']))
        self.assertFalse(feed.analyze_log('\n'.join(negative), self.process, 'success')['passed'])
        with self.assertRaises(ValueError):
            feed.analyze_log('', self.process, 'unknown')

    def test_wrong_key_protocol_requires_positive_and_negative_checks(self):
        negative = list(feed.CASE_MARKERS['wrong-key-rpm']) + ['[ 123.4] reboot: Power down']
        def check(lines, process=None):
            return feed.analyze_log('\r\n'.join(lines) + '\r\n', process or self.process,
                                    'wrong-key-rpm')['passed']
        self.assertTrue(check(negative))
        for index in range(len(negative)):
            with self.subTest(missing=negative[index]):
                self.assertFalse(check(negative[:index] + negative[index + 1:]))
        self.assertFalse(check(negative + [negative[3]]))
        self.assertFalse(check([negative[1], negative[0], *negative[2:]]))
        self.assertFalse(check(negative + ['INT_FEED_CASE:unsigned-rpm:PASS']))
        self.assertFalse(check(negative, {**self.process, 'returncode': 1}))
        self.assertFalse(feed.analyze_log('\n'.join(negative), self.process, 'unsigned-rpm')['passed'])

    def test_missing_duplicate_reordered_unknown_failures_and_panics_reject(self):
        cases = [self.lines[1:], self.lines + [self.lines[0]],
                 [self.lines[1], self.lines[0], *self.lines[2:]],
                 self.lines + ['INT_FEED_CASE:wrong:PASS'],
                 self.lines + ['INT_FEED_FAIL:bad'],
                 self.lines + ['Kernel panic - not syncing'], self.lines[:-1]]
        for lines in cases:
            with self.subTest(lines=lines):
                self.assertFalse(self.analyze(lines)['passed'])
        for state in ({'returncode': 1}, {'timed_out': True}, {'output_limit': True}, {'interrupted_signal': 15}):
            with self.subTest(state=state):
                self.assertFalse(self.analyze(self.lines, {**self.process, **state})['passed'])

    def test_command_disables_network_and_pins_read_only_disk(self):
        artifacts = {'rootfs': {'snapshot': '/tmp/root,one'}, 'feed_disk': {'snapshot': '/tmp/feed,two'},
                     'kernel': {'snapshot': '/tmp/kernel'}}
        command = feed.build_qemu_command('qemu', artifacts, 'A' * 40)
        self.assertIn('file=/tmp/root,,one,format=raw,if=virtio,snapshot=on', command)
        self.assertIn('file=/tmp/feed,,two,format=raw,if=virtio,readonly=on', command)
        self.assertEqual(command[command.index('-nic') + 1], 'none')
        self.assertNotIn('-netdev', command)
        append = command[command.index('-append') + 1]
        self.assertIn('int_feed_fingerprint=' + 'A' * 40, append)
        self.assertIn('int_feed_case=success', append)
        negative = feed.build_qemu_command('qemu', artifacts, 'A' * 40, 'unsigned-rpm')
        self.assertIn('int_feed_case=unsigned-rpm', negative[negative.index('-append') + 1])
        wrong_key = feed.build_qemu_command('qemu', artifacts, 'A' * 40, 'wrong-key-rpm')
        self.assertIn('int_feed_case=wrong-key-rpm', wrong_key[wrong_key.index('-append') + 1])
        with self.assertRaises(ValueError):
            feed.build_qemu_command('qemu', artifacts, 'A' * 40, 'unsigned-rpm kernel_init=foo')
        with self.assertRaises(ValueError):
            feed.build_qemu_command('qemu', artifacts, 'A' * 39 + ' ')

    def test_disk_pin_mismatch_rejected_and_copy_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source, output = base / 'fixture', base / 'artifacts'
            source.write_bytes(b'fixture data')
            output.mkdir()
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                feed.snapshot_disk(source, output, '0' * 64)
            info = feed.snapshot_disk(source, output, digest)
            self.assertEqual(Path(info['snapshot']).read_bytes(), source.read_bytes())
            self.assertEqual(info['sha256'], digest)

    def test_manifest_requires_real_guest_service_and_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'manifest'
            manifest.write_text('\n'.join(f'{name} x86_64 1' for name in feed.REQUIRED_PACKAGES) + '\n')
            feed.validate_feed_manifest(manifest)
            manifest.write_text('rpm x86_64 1\ndnf x86_64 1\n')
            with self.assertRaisesRegex(ValueError, 'int-feed-smoke'):
                feed.validate_feed_manifest(manifest)
            for missing in ('gnupg', 'gnupg-gpg'):
                with self.subTest(missing=missing):
                    manifest.write_text('\n'.join(f'{name} x86_64 1'
                                                  for name in feed.REQUIRED_PACKAGES - {missing}) + '\n')
                    with self.assertRaisesRegex(ValueError, f'feed manifest lacks required packages: {missing}$'):
                        feed.validate_feed_manifest(manifest)

    def test_detects_input_or_snapshot_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, copy = Path(tmp) / 'src', Path(tmp) / 'copy'
            source.write_bytes(b'old')
            copy.write_bytes(b'old')
            artifact = {'source': str(source), 'resolved_source': str(source), 'snapshot': str(copy),
                        'sha256': hashlib.sha256(b'old').hexdigest()}
            self.assertFalse(feed.artifact_failures({'rootfs': artifact}))
            source.write_bytes(b'new')
            self.assertIn('rootfs input changed during QEMU', feed.artifact_failures({'rootfs': artifact}))
            copy.unlink()
            self.assertTrue(feed.artifact_failures({'rootfs': artifact}))

    def test_capture_enforces_timeout_and_output_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'serial.log'
            stalled = feed.execute_qemu([sys.executable, '-c', 'import time; time.sleep(2)'], output, 0.2)
            self.assertTrue(stalled['timed_out'])
            with mock.patch.object(feed, 'MAX_SERIAL', 80):
                flooded = feed.execute_qemu([sys.executable, '-c', 'print("x"*200)'], output, 3)
            self.assertTrue(flooded['output_limit'])
            self.assertLessEqual(output.stat().st_size, 80)


if __name__ == '__main__':
    unittest.main()
