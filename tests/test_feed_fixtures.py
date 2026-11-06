"""Host-only path guard checks; these do not verify RPM or DNF behavior."""
import runpy
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest


MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                            "meta-int/recipes-test/int-feed-lab/files/int-feed-fixtures.py"))
LabError = MODULE["LabError"]
input_bytes = MODULE["input_bytes"]
create_output = MODULE["create_output"]
MAX_RPM = MODULE["MAX_RPM"]
verify_single_package_index = MODULE["verify_single_package_index"]
expect_index_failure = MODULE["expect_index_failure"]
validate_probe_files = MODULE["validate_probe_files"]
invoke_rpm = MODULE["invoke_rpm"]


class FixturePathsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.inputs = self.root / "int-feed-probe.copy"
        self.inputs.mkdir()
        self.v1 = self.inputs / "int-feed-probe-1.0-r0.noarch.rpm"
        self.v1.write_bytes(b"fake rpm for path checking")

    def test_accepts_bounded_copy_with_exact_name(self):
        self.assertEqual(input_bytes(self.root, str(self.v1), "1.0"), b"fake rpm for path checking")

    def test_rejects_deploy_nested_and_wrong_name(self):
        for path, version in ((self.root / "deploy" / self.v1.name, "1.0"),
                              (self.inputs / "other.rpm", "1.0"), (self.v1, "2.0")):
            with self.subTest(path=path), self.assertRaises(LabError):
                input_bytes(self.root, str(path), version)

    def test_rejects_symlink_file_and_symlink_parent(self):
        self.v1.unlink()
        source = self.root / "other"
        source.write_bytes(b"data")
        self.v1.symlink_to(source)
        with self.assertRaises(LabError):
            input_bytes(self.root, str(self.v1), "1.0")
        alias = self.root / "int-feed-probe.alias"
        alias.symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaises(LabError):
            input_bytes(self.root, str(alias / self.v1.name), "1.0")

    def test_rejects_empty_and_oversize(self):
        self.v1.write_bytes(b"")
        with self.assertRaises(LabError):
            input_bytes(self.root, str(self.v1), "1.0")
        with self.v1.open("wb") as stream:
            stream.truncate(MAX_RPM + 1)
        with self.assertRaises(LabError):
            input_bytes(self.root, str(self.v1), "1.0")

    def test_output_is_new_and_beneath_fixed_base(self):
        out = create_output(self.root, "case-01")
        self.assertEqual(out, self.root / "feed-fixtures" / "case-01")
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(LabError):
            create_output(self.root, "case-01")
        for name in ("../x", "/tmp/x", ".", "bad name", ""):
            with self.subTest(name=name), self.assertRaises(LabError):
                create_output(self.root, name)

    def test_rejects_symlinked_output_base(self):
        (self.root / "feed-fixtures").symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaises(LabError):
            create_output(self.root, "case")

    def test_probe_file_list_rejects_extra_paths_and_nonregular_version(self):
        directory = '/usr/share/int-feed-probe'
        file = directory + '/version'
        validate_probe_files(f'/usr\t40755\n/usr/share\t40755\n{directory}\t40755\n{file}\t100644\n')
        validate_probe_files(f'{directory}\t40755\n{file}\t100644\n')
        validate_probe_files(f'{file}\t100644\n')
        for output in (f'{file}\t120777\n', f'{file}\t100644\n/etc/extra\t100644\n',
                       f'/usr\t100644\n{file}\t100644\n',
                       f'{directory}\t40755\n', f'{file}\tinvalid\n',
                       f'{file}\t100644\n{file}\t100644\n'):
            with self.subTest(output=output), self.assertRaises(LabError):
                validate_probe_files(output)

    def test_rpm_tools_receive_only_the_isolated_database(self):
        # The fake tool records the real subprocess arguments; it does not
        # claim to verify signatures or replace the native integration test.
        tool = self.root / 'fake-rpm'
        tool.write_text('#!/usr/bin/python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
        tool.chmod(0o700)
        database = self.root / 'isolated-rpmdb'
        for options in (('-qp', '--qf', '%{NAME}', 'probe.rpm'),
                        ('--checksig', '--verbose', 'probe.rpm'),
                        ('--addsign', 'probe.rpm'), ('--version',)):
            with self.subTest(options=options):
                result = invoke_rpm(tool, database, *options, env=os.environ.copy())
                self.assertEqual(json.loads(result.stdout),
                                 ['--define', f'_dbpath {database}', *options])
        with self.assertRaises(LabError):
            invoke_rpm(tool, Path('relative-rpmdb'), '--version', env=os.environ.copy())

    def test_primary_index_rejects_changed_package(self):
        repo = self.root / "repo"
        repodata = repo / "repodata"
        repodata.mkdir(parents=True)
        package = repo / "int-feed-probe-1.0-r0.noarch.rpm"
        package.write_bytes(b"synthetic rpm")
        checksum = hashlib.sha256(package.read_bytes()).hexdigest()
        primary = (f'<metadata xmlns="http://linux.duke.edu/metadata/common" packages="1">'
                   f'<package><name>int-feed-probe</name><arch>noarch</arch>'
                   f'<version ver="1.0" rel="r0"/><checksum type="sha256">{checksum}</checksum>'
                   f'<location href="{package.name}"/></package></metadata>').encode()
        compressed = repodata / "primary.xml.gz"
        compressed.write_bytes(gzip.compress(primary))
        primary_sum = hashlib.sha256(compressed.read_bytes()).hexdigest()
        (repodata / "repomd.xml").write_text(
            '<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary">'
            f'<location href="repodata/{compressed.name}"/>'
            f'<checksum type="sha256">{primary_sum}</checksum></data></repomd>')
        self.assertEqual(verify_single_package_index(repo, "1.0"), compressed)
        with self.assertRaisesRegex(LabError, 'Expected index validation failure'):
            expect_index_failure(repo, "1.0", 'Indexed RPM checksum mismatch')
        package.write_bytes(b"changed")
        expect_index_failure(repo, "1.0", 'Indexed RPM checksum mismatch')
        with self.assertRaisesRegex(LabError, 'Unexpected index validation failure'):
            expect_index_failure(repo, "1.0", 'Primary checksum mismatch')
        package.write_bytes(b"synthetic rpm")
        with compressed.open('ab') as stream:
            stream.write(b'\n')
        expect_index_failure(repo, "1.0", 'Primary checksum mismatch')


if __name__ == "__main__":
    unittest.main()
