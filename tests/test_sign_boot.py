"""Owner-side boot signing: key hygiene, copy-only behaviour, chain layout.

sbsign, sbverify, xorriso and mtools are replaced by fakes; no real key or
signature is involved. Permission checks use real temporary files.
"""
import base64
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/sign-boot.py'
SPEC = importlib.util.spec_from_file_location('sign_boot', SCRIPT)
sign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sign)

MARK = b'\nFAKE-INT-SIGNATURE\n'
KEY_MARKER = 'THROWAWAY-KEY-MATERIAL-7f3a'
CERT_BODY = b'fake DER certificate for tests, not a real certificate'
CERT_PEM = ('-----BEGIN CERTIFICATE-----\n'
            + base64.encodebytes(CERT_BODY).decode()
            + '-----END CERTIFICATE-----\n')


def pe(*sections, payload=b''):
    """A minimal PE/COFF header with the given section names."""
    head = bytearray(b'MZ' + b'\0' * 0x3e)
    struct.pack_into('<I', head, 0x3c, 0x40)
    coff = b'PE\0\0' + struct.pack('<HHIIIHH', 0x8664, len(sections), 0, 0, 0, 0, 0x22)
    table = b''.join(name.encode().ljust(8, b'\0') + b'\0' * 32 for name in sections)
    return bytes(head) + coff + table + payload


class FakeTools:
    """Stands in for sbsign/sbverify/xorriso/mtools and records every call."""

    def __init__(self, iso_tree=None, fat_tree=None, verify_ok=True, system_area=''):
        self.calls = []
        self.system_area = system_area
        self.iso_tree = iso_tree or {}
        self.fat_tree = fat_tree or {}
        self.verify_ok = verify_ok

    @staticmethod
    def which(name):
        return '/usr/bin/' + name

    @staticmethod
    def populate(root, tree):
        for rel, data in tree.items():
            path = Path(root) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o444)

    def capture(self, argv):
        self.calls.append(list(argv))
        return self.system_area

    def run(self, argv):
        self.calls.append(list(argv))
        tool = Path(argv[0]).name
        if tool == 'sbsign':
            src, dst = Path(argv[-1]), Path(argv[argv.index('--output') + 1])
            dst.write_bytes(src.read_bytes() + MARK)
        elif tool == 'sbverify':
            if not self.verify_ok or not Path(argv[-1]).read_bytes().endswith(MARK):
                raise sign.SignError('sbverify failed with status 1')
        elif tool == 'xorriso' and '-extract' in argv:
            self.populate(argv[-1], self.iso_tree)
        elif tool == 'xorriso':
            Path(argv[argv.index('-outdev') + 1]).write_bytes(b'signed iso')
        elif tool == 'mcopy' and '::*' in argv:
            self.populate(argv[-1], self.fat_tree)
        elif tool == 'mformat':
            assert Path(argv[2]).stat().st_size % (1024 * 1024) == 0


def esp_tree(grub=None):
    return {'EFI/BOOT/bootx64.efi': grub or pe('.text', '.data'),
            'EFI/BOOT/grub.cfg': b'menuentry\n',
            'bzImage': pe('.setup', '.text', payload=b'kernel')}


class SignBootTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.keys = self.root / 'keys'
        self.keys.mkdir(mode=0o700)
        self.key = self.keys / 'int-sb.key'
        self.key.write_text(f'-----BEGIN PRIVATE KEY-----\n{KEY_MARKER}\n-----END PRIVATE KEY-----\n')
        self.key.chmod(0o600)
        self.cert = self.keys / 'int-sb.crt'
        self.cert.write_text(CERT_PEM)
        self.input = self.root / 'esp'
        FakeTools.populate(self.input, esp_tree())
        self.output = self.root / 'signed'

    def fakes(self, tools):
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(sign, 'which', tools.which))
        stack.enter_context(mock.patch.object(sign, 'run', tools.run))
        stack.enter_context(mock.patch.object(sign, 'capture', tools.capture))
        self.addCleanup(stack.close)
        return tools

    def main(self, *extra, inp=None, out=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ['--key', str(self.key), '--cert', str(self.cert), *extra,
                str(inp or self.input), str(out or self.output)]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = sign.main(args)
        return status, stdout.getvalue(), stderr.getvalue()

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(root).rglob('*') if p.is_file()}

    # Key hygiene -------------------------------------------------------

    def test_accepts_private_key_file(self):
        self.assertEqual(sign.check_private_key(self.key, []), self.key.resolve())

    def test_refuses_group_or_world_accessible_key(self):
        for mode in (0o640, 0o604, 0o660, 0o644, 0o610):
            with self.subTest(mode=oct(mode)):
                self.key.chmod(mode)
                with self.assertRaisesRegex(sign.SignError, 'group/world'):
                    sign.check_private_key(self.key, [])

    def test_refuses_symlink_and_non_file_key(self):
        link = self.keys / 'link.key'
        link.symlink_to(self.key)
        with self.assertRaisesRegex(sign.SignError, 'symbolic link'):
            sign.check_private_key(link, [])
        with self.assertRaisesRegex(sign.SignError, 'not a regular file'):
            sign.check_private_key(self.keys, [])
        with self.assertRaisesRegex(sign.SignError, 'not found'):
            sign.check_private_key(self.keys / 'missing.key', [])

    def test_refuses_key_inside_repository_or_git_checkout(self):
        with self.assertRaisesRegex(sign.SignError, 'must not be inside'):
            sign.check_private_key(self.key, [self.root])
        checkout = self.root / 'checkout'
        (checkout / '.git').mkdir(parents=True)
        inner = checkout / 'secret.key'
        inner.write_text('x')
        inner.chmod(0o600)
        with self.assertRaisesRegex(sign.SignError, 'Git checkout'):
            sign.check_private_key(inner, [])

    def test_main_refuses_key_inside_this_repository(self):
        self.fakes(FakeTools())
        with mock.patch.object(sign, 'REPO_ROOT', self.keys):
            status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('must not be inside', err)
        self.assertFalse(self.output.exists())

    def test_main_refuses_key_inside_input(self):
        self.fakes(FakeTools())
        moved = self.input / 'int-sb.key'
        shutil.copyfile(self.key, moved)
        moved.chmod(0o600)
        self.key = moved
        status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('must not be inside', err)

    def test_main_refuses_readable_key_before_any_tool_runs(self):
        tools = self.fakes(FakeTools())
        self.key.chmod(0o644)
        status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('chmod 600', err)
        self.assertEqual(tools.calls, [])
        self.assertFalse(self.output.exists())

    def test_certificate_must_be_public_pem(self):
        self.assertEqual(sign.load_certificate(self.cert), CERT_BODY)
        bad = self.keys / 'bad.crt'
        bad.write_text(CERT_PEM + self.key.read_text())
        with self.assertRaisesRegex(sign.SignError, 'private key'):
            sign.load_certificate(bad)
        bad.write_text('not pem')
        with self.assertRaisesRegex(sign.SignError, 'not PEM'):
            sign.load_certificate(bad)

    # Signing a directory copy -----------------------------------------

    def test_signs_copy_and_leaves_input_untouched(self):
        tools = self.fakes(FakeTools())
        before = self.snapshot(self.input)
        status, out, err = self.main()
        self.assertEqual(status, 0, err)
        self.assertEqual(self.snapshot(self.input), before)
        for rel in ('EFI/BOOT/bootx64.efi', 'bzImage'):
            self.assertTrue((self.output / rel).read_bytes().endswith(MARK), rel)
        self.assertEqual((self.output / 'EFI/BOOT/grub.cfg').read_bytes(), b'menuentry\n')
        self.assertEqual((self.output / sign.CERT_NAME).read_bytes(), CERT_BODY)
        signed = [c for c in tools.calls if c[0].endswith('sbsign')]
        verified = [c for c in tools.calls if c[0].endswith('sbverify')]
        self.assertEqual(len(signed), 2)
        self.assertEqual(len(verified), 2)
        self.assertTrue(all(c[c.index('--key') + 1] == str(self.key.resolve()) for c in signed))
        self.assertIn(hashlib.sha256(CERT_BODY).hexdigest(), out)
        self.assertEqual(list(self.root.glob('.int-sign-*')), [])

    def test_never_prints_key_material(self):
        self.fakes(FakeTools())
        status, out, err = self.main()
        self.assertEqual(status, 0, err)
        self.assertNotIn(KEY_MARKER, out + err)
        self.assertNotIn('PRIVATE KEY', out + err)

    def test_refuses_existing_output(self):
        self.fakes(FakeTools())
        self.output.mkdir()
        status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('already exists', err)

    def test_refuses_output_inside_input(self):
        self.fakes(FakeTools())
        status, _, err = self.main(out=self.input / 'signed')
        self.assertEqual(status, 2)
        self.assertIn('contain each other', err)

    def test_failed_verification_creates_no_output(self):
        self.fakes(FakeTools(verify_ok=False))
        status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('sbverify', err)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.int-sign-*')), [])

    def test_missing_host_tools(self):
        self.fakes(FakeTools())
        with mock.patch.object(sign, 'which', lambda name: None):
            status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('sbsign', err)

    def test_kernel_without_efi_stub_is_refused(self):
        self.fakes(FakeTools())
        (self.input / 'bzImage').chmod(0o644)
        (self.input / 'bzImage').write_bytes(b'\x7fELF not a PE kernel')
        status, _, err = self.main()
        self.assertEqual(status, 2)
        self.assertIn('CONFIG_EFI_STUB', err)

    # Shim layout -------------------------------------------------------

    def shim_files(self):
        shim = self.root / 'shimx64.efi'
        shim.write_bytes(pe('.text', '.sbat', '.vendor_cert', payload=b'shim'))
        manager = self.root / 'mmx64.efi'
        manager.write_bytes(pe('.text', '.sbat', payload=b'mm'))
        return shim, manager

    def test_shim_layout_keeps_shim_signature(self):
        self.fakes(FakeTools())
        shutil.rmtree(self.input)
        FakeTools.populate(self.input, esp_tree(grub=pe('.text', '.sbat')))
        shim, manager = self.shim_files()
        status, _, err = self.main('--shim', str(shim), '--mokmanager', str(manager))
        self.assertEqual(status, 0, err)
        boot = self.output / 'EFI/BOOT'
        self.assertEqual((boot / 'bootx64.efi').read_bytes(), shim.read_bytes())
        self.assertEqual((boot / 'mmx64.efi').read_bytes(), manager.read_bytes())
        self.assertTrue((boot / 'grubx64.efi').read_bytes().endswith(MARK))

    def test_sign_shim_signs_shim_and_mokmanager(self):
        self.fakes(FakeTools())
        shutil.rmtree(self.input)
        FakeTools.populate(self.input, esp_tree(grub=pe('.text', '.sbat')))
        shim, manager = self.shim_files()
        status, _, err = self.main('--shim', str(shim), '--mokmanager', str(manager), '--sign-shim')
        self.assertEqual(status, 0, err)
        for name in ('bootx64.efi', 'mmx64.efi', 'grubx64.efi'):
            self.assertTrue((self.output / 'EFI/BOOT' / name).read_bytes().endswith(MARK), name)

    def test_shim_refuses_grub_without_sbat(self):
        self.fakes(FakeTools())
        shim, manager = self.shim_files()
        status, _, err = self.main('--shim', str(shim), '--mokmanager', str(manager))
        self.assertEqual(status, 2)
        self.assertIn('.sbat', err)

    def test_shim_needs_mokmanager(self):
        self.fakes(FakeTools())
        shim, _ = self.shim_files()
        status, _, err = self.main('--shim', str(shim))
        self.assertEqual(status, 2)
        self.assertIn('go together', err)

    # ISO ---------------------------------------------------------------

    def test_iso_resigns_both_esps_and_replays_boot_setup(self):
        tree = dict(esp_tree(), **{'efi.img': b'fat image', 'rootfs.img': b'root'})
        tools = self.fakes(FakeTools(iso_tree=tree, fat_tree=esp_tree()))
        iso = self.root / 'int.iso'
        iso.write_bytes(b'original iso')
        status, out, err = self.main(inp=iso, out=self.root / 'int-signed.iso')
        self.assertEqual(status, 0, err)
        self.assertEqual(iso.read_bytes(), b'original iso')
        self.assertEqual((self.root / 'int-signed.iso').read_bytes(), b'signed iso')
        final = tools.calls[-1]
        self.assertEqual(final[final.index('-boot_image') + 1:final.index('-boot_image') + 3],
                         ['any', 'replay'])
        targets = [final[i + 2] for i, arg in enumerate(final) if arg == '-map']
        self.assertEqual(sorted(targets), ['/EFI/BOOT/bootx64.efi', '/' + sign.CERT_NAME,
                                           '/bzImage', '/efi.img'])
        self.assertEqual(sum(1 for c in tools.calls if c[0].endswith('sbsign')), 4)
        self.assertEqual(list(self.root.glob('.int-sign-*')), [])

    def test_iso_replaces_appended_efi_partition(self):
        tree = dict(esp_tree(), **{'efi.img': b'fat image'})
        area = ("-boot_image any efi_path='/efi.img'\n"
                "-append_partition 2 28732ac11ff8d211ba4b00a0c93ec93b "
                "--interval:imported_iso:8648d-16839d::'in.iso'\n"
                "-append_partition 3 0x83 --interval:imported_iso:1d-2d::'in.iso'\n")
        tools = self.fakes(FakeTools(iso_tree=tree, fat_tree=esp_tree(), system_area=area))
        iso = self.root / 'int.iso'
        iso.write_bytes(b'original iso')
        status, _, err = self.main(inp=iso, out=self.root / 'int-signed.iso')
        self.assertEqual(status, 0, err)
        final = tools.calls[-1]
        appended = [final[i + 1:i + 4] for i, arg in enumerate(final) if arg == '-append_partition']
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0][:2], ['2', '28732ac11ff8d211ba4b00a0c93ec93b'])
        self.assertEqual(Path(appended[0][2]).name, 'efi.img')

    def test_iso_appended_efi_partition_without_efi_img_is_refused(self):
        area = "-append_partition 2 0xef --interval:imported_iso:1d-2d::'in.iso'\n"
        self.fakes(FakeTools(iso_tree=esp_tree(), system_area=area))
        iso = self.root / 'int.iso'
        iso.write_bytes(b'iso')
        status, _, err = self.main(inp=iso, out=self.root / 'out.iso')
        self.assertEqual(status, 2)
        self.assertIn('appended EFI partition', err)
        self.assertFalse((self.root / 'out.iso').exists())

    def test_iso_needs_iso_tools(self):
        self.fakes(FakeTools())
        iso = self.root / 'int.iso'
        iso.write_bytes(b'iso')
        with mock.patch.object(sign, 'which', lambda n: None if n == 'xorriso' else '/usr/bin/' + n):
            status, _, err = self.main(inp=iso, out=self.root / 'out.iso')
        self.assertEqual(status, 2)
        self.assertIn('xorriso', err)

    def test_pe_parser(self):
        path = self.root / 'x.efi'
        path.write_bytes(pe('.text', '.sbat'))
        self.assertEqual(sign.pe_sections(path), ['.text', '.sbat'])
        path.write_bytes(b'MZ' + b'\0' * 10)
        self.assertIsNone(sign.pe_sections(path))


if __name__ == '__main__':
    unittest.main()
