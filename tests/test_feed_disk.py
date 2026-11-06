"""Fixture disk construction checks integrity, not signatures or DNF."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/feed-disk.py'
SPEC = importlib.util.spec_from_file_location('feed_disk', SCRIPT)
disk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(disk)


class FeedDiskTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'fixtures'
        (self.source / 'repo').mkdir(parents=True)
        self.content = b'synthetic fixture, no cryptographic claim\n'
        (self.source / 'repo' / 'probe.rpm').write_bytes(self.content)
        self.manifest = {'files': {'repo/probe.rpm': {
            'bytes': len(self.content), 'sha256': hashlib.sha256(self.content).hexdigest()}}}
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest))

    def copy(self):
        stage = self.root / 'stage'
        stage.mkdir()
        fd = os.open(self.source, disk.DIR_FLAGS)
        try:
            return disk.copy_verified(fd, stage)
        finally:
            os.close(fd)

    def test_valid_tree_is_copied(self):
        _, _, total = self.copy()
        self.assertEqual(total, len(self.content))
        self.assertEqual((self.root / 'stage/repo/probe.rpm').read_bytes(), self.content)

    def test_changed_and_extra_files_rejected(self):
        (self.source / 'repo/probe.rpm').write_bytes(b'changed')
        with self.assertRaises(disk.DiskError):
            self.copy()
        shutil.rmtree(self.root / 'stage')
        (self.source / 'repo/probe.rpm').write_bytes(self.content)
        (self.source / 'unexpected').write_text('extra')
        with self.assertRaises(disk.DiskError):
            self.copy()

    def test_symlink_and_hardlink_rejected(self):
        path = self.source / 'repo/probe.rpm'
        path.unlink()
        outside = self.root / 'outside'
        outside.write_bytes(self.content)
        path.symlink_to(outside)
        with self.assertRaises(disk.DiskError):
            self.copy()
        shutil.rmtree(self.root / 'stage')
        path.unlink()
        os.link(outside, path)
        with self.assertRaises(disk.DiskError):
            self.copy()

    def test_duplicate_json_and_unsafe_paths_rejected(self):
        for raw in (b'{"files":{},"files":{}}',
                    json.dumps({'files': {'../escape': {'bytes': 0, 'sha256': '0' * 64}}}).encode()):
            with self.subTest(raw=raw), self.assertRaises(disk.DiskError):
                disk.parse_manifest(raw)

    @unittest.skipUnless(shutil.which('mke2fs') and shutil.which('debugfs'),
                         'mke2fs and debugfs required for the image inspection')
    def test_builds_ext4_containing_verified_fixture(self):
        destination = self.root / 'output'
        report = disk.build(self.source, destination)
        image = destination / 'feed.ext4'
        self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), report['image']['sha256'])
        self.assertEqual(image.stat().st_mode & 0o777, 0o400)
        extracted = self.root / 'extracted'
        result = subprocess.run(['debugfs', '-R', f'dump /repo/probe.rpm {extracted}', str(image)],
                                capture_output=True, text=True, check=True)
        self.assertTrue(extracted.is_file(), result.stderr)
        self.assertEqual(extracted.read_bytes(), self.content)
        self.assertEqual(json.loads((destination / 'report.json').read_text()), report)
        with self.assertRaises(FileExistsError):
            disk.build(self.source, destination)


if __name__ == '__main__':
    unittest.main()
