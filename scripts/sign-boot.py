#!/usr/bin/env python3
"""Sign a copy of the INT boot chain (GRUB and kernel) for UEFI Secure Boot.

Owner-side host tool. It is meant to run on the owner's machine, after the
BitBake build, with the offline INT signing key. The private key is only ever
passed by path to the host's ``sbsign``; this script never reads, copies or
prints it, and BitBake never sees it.

INPUT is either a directory (a copy of an EFI System Partition or of an
unpacked ISO) or an ``.iso`` file. OUTPUT must not exist: the script works on
a private copy and creates OUTPUT only once every signature verified. INPUT is
never modified.

With ``--shim`` and ``--mokmanager`` (normally a Microsoft-signed shim, see
docs/development/secure-boot.md) the layout becomes
``EFI/BOOT/BOOTX64.EFI`` = shim, ``EFI/BOOT/grubx64.efi`` = signed GRUB and
``EFI/BOOT/mmx64.efi`` = MokManager. The public certificate is always written
in DER form as ``INT-SecureBoot.cer`` at the root of each ESP so MokManager's
"Enroll key from disk" can find it.

This tool does not make the system Secure-Boot ready on its own; see the list
of open work in docs/development/secure-boot.md.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import ssl
import stat
import struct
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
CERT_NAME = 'INT-SecureBoot.cer'
KERNEL_NAME = re.compile(r'(bzImage|vmlinuz)([-.][A-Za-z0-9_.+-]*)?\Z')
MAX_PE_HEADER = 64 * 1024
MAX_SECTIONS = 96
# EFI System Partition type: MBR 0xef, or the GPT GUID as xorriso prints it.
EFI_PARTITION_TYPES = {'0xef', 'ef', '28732ac11ff8d211ba4b00a0c93ec93b'}


class SignError(Exception):
    pass


def which(name):
    return shutil.which(name)


def run(argv):
    """Run a host tool. Its standard input stays attached so that sbsign can
    ask for the key passphrase on the terminal; nothing is captured or logged
    by this script."""
    result = subprocess.run(argv, check=False)
    if result.returncode != 0:
        raise SignError(f'{Path(argv[0]).name} failed with status {result.returncode}')


def capture(argv):
    """Run a host tool that only reports on public data and return stdout."""
    result = subprocess.run(argv, check=False, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    if result.returncode != 0:
        raise SignError(f'{Path(argv[0]).name} failed with status {result.returncode}')
    return result.stdout


def require_tools(names):
    found = {}
    missing = []
    for name in names:
        path = which(name)
        if path:
            found[name] = path
        else:
            missing.append(name)
    if missing:
        raise SignError('missing host tool(s): ' + ', '.join(missing)
                        + ' (install sbsigntool, xorriso and mtools)')
    return found


def is_within(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def check_private_key(key, forbidden_roots):
    """Refuse keys that are not a private regular file of the caller, or that
    sit in a Git checkout, the repository, the input or the output."""
    key = Path(key)
    try:
        info = os.lstat(key)
    except OSError:
        raise SignError(f'key file not found: {key}') from None
    if stat.S_ISLNK(info.st_mode):
        raise SignError('key path is a symbolic link; pass the real file')
    if not stat.S_ISREG(info.st_mode):
        raise SignError('key path is not a regular file')
    if info.st_mode & 0o077:
        raise SignError(f'key file mode {stat.S_IMODE(info.st_mode):04o} is group/world '
                        'accessible; run: chmod 600 <key>')
    if info.st_uid != os.geteuid():
        raise SignError('key file is not owned by the current user')
    resolved = key.resolve()
    for root in forbidden_roots:
        if root is not None and is_within(resolved, Path(root).resolve()):
            raise SignError(f'key file must not be inside {root}')
    for parent in resolved.parents:
        if (parent / '.git').exists():
            raise SignError(f'key file is inside a Git checkout ({parent}); keep it offline')
    return resolved


def load_certificate(cert):
    """Return the DER bytes of the first PEM certificate in CERT."""
    try:
        text = Path(cert).read_text(encoding='ascii')
    except (OSError, UnicodeDecodeError):
        raise SignError(f'cannot read PEM certificate: {cert}') from None
    if 'PRIVATE KEY' in text:
        raise SignError('the certificate file contains a private key; pass only the public certificate')
    match = re.search(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', text, re.S)
    if not match:
        raise SignError('certificate is not PEM (-----BEGIN CERTIFICATE-----)')
    try:
        return ssl.PEM_cert_to_DER_cert(match.group(0))
    except ValueError:
        raise SignError('certificate PEM block is malformed') from None


def pe_sections(path):
    """Section names of a PE/COFF image, or None when PATH is not PE."""
    with open(path, 'rb') as handle:
        head = handle.read(MAX_PE_HEADER)
    if len(head) < 0x40 or head[:2] != b'MZ':
        return None
    pe = struct.unpack_from('<I', head, 0x3c)[0]
    if pe + 24 > len(head) or head[pe:pe + 4] != b'PE\0\0':
        return None
    count = struct.unpack_from('<H', head, pe + 6)[0]
    optional = struct.unpack_from('<H', head, pe + 20)[0]
    table = pe + 24 + optional
    if count > MAX_SECTIONS or table + 40 * count > len(head):
        return None
    return [head[table + 40 * i:table + 40 * i + 8].rstrip(b'\0').decode('ascii', 'replace')
            for i in range(count)]


def find_ci(root, *parts):
    """Case-insensitive path lookup (FAT and ISO copies differ in case)."""
    current = Path(root)
    for part in parts:
        if not current.is_dir():
            return None
        matches = [entry for entry in current.iterdir() if entry.name.lower() == part.lower()]
        if len(matches) != 1:
            return None
        current = matches[0]
    return current


def find_kernels(root):
    kernels = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if KERNEL_NAME.match(name):
                kernels.append(Path(dirpath) / name)
    return kernels


def regular(path, what):
    if path.is_symlink() or not path.is_file():
        raise SignError(f'{what} is not a regular file: {path}')


class Signer:
    def __init__(self, tools, key, cert, chain=None):
        self.sbsign = tools['sbsign']
        self.sbverify = tools['sbverify']
        self.key = str(key)
        self.cert = str(cert)
        self.chain = str(chain) if chain else None

    def sign(self, path):
        signed = path.with_name(path.name + '.int-signed')
        argv = [self.sbsign, '--key', self.key, '--cert', self.cert]
        if self.chain:
            argv += ['--addcert', self.chain]
        run(argv + ['--output', str(signed), str(path)])
        if not signed.is_file():
            raise SignError(f'sbsign produced no output for {path.name}')
        run([self.sbverify, '--cert', self.cert, str(signed)])
        os.replace(signed, path)


def sign_esp(root, signer, cert_der, shim=None, mokmanager=None, sign_shim=False):
    """Sign GRUB and kernels inside ROOT (a private copy). Returns the paths,
    relative to ROOT, that were changed or added."""
    root = Path(root)
    loader = find_ci(root, 'EFI', 'BOOT', 'bootx64.efi')
    if loader is None:
        raise SignError(f'no EFI/BOOT/BOOTX64.EFI in {root}')
    regular(loader, 'boot loader')
    sections = pe_sections(loader)
    if sections is None:
        raise SignError(f'{loader.relative_to(root)} is not a PE/COFF image')
    if shim and '.sbat' not in sections:
        raise SignError('GRUB has no .sbat section; shim refuses it. Build GRUB with '
                        'grub-mkimage --sbat (see docs/development/secure-boot.md)')
    kernels = find_kernels(root)
    if not kernels:
        raise SignError(f'no kernel (bzImage/vmlinuz) found in {root}')
    for kernel in kernels:
        regular(kernel, 'kernel')
        if pe_sections(kernel) is None:
            raise SignError(f'{kernel.relative_to(root)} is not PE: the kernel needs CONFIG_EFI_STUB')

    changed = []
    if shim:
        grub = loader.with_name('grubx64.efi')
        os.replace(loader, grub)
        signer.sign(grub)
        shutil.copyfile(shim, loader)
        manager = loader.with_name('mmx64.efi')
        shutil.copyfile(mokmanager, manager)
        if sign_shim:
            signer.sign(loader)
            signer.sign(manager)
        changed += [loader, grub, manager]
    else:
        signer.sign(loader)
        changed.append(loader)
    for kernel in kernels:
        signer.sign(kernel)
        changed.append(kernel)
    cert_path = root / CERT_NAME
    cert_path.write_bytes(cert_der)
    changed.append(cert_path)
    return [path.relative_to(root) for path in changed]


def make_writable(root):
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o700)
        for name in filenames:
            path = os.path.join(dirpath, name)
            if not os.path.islink(path):
                os.chmod(path, 0o600)


def tree_bytes(root):
    total = 0
    entries = 0
    for dirpath, dirnames, filenames in os.walk(root):
        entries += 1 + len(filenames)
        total += sum(os.path.getsize(os.path.join(dirpath, name)) for name in filenames)
    return total, entries


def rebuild_fat(tools, source_dir, original, output):
    total, entries = tree_bytes(source_dir)
    needed_kib = (total + entries * 4096) * 5 // 4 // 1024 + 1024
    kib = max(os.path.getsize(original) // 1024, needed_kib)
    kib = (kib + 1023) // 1024 * 1024
    with open(output, 'xb') as handle:
        handle.truncate(kib * 1024)
    run([tools['mformat'], '-i', str(output), '-T', str(kib * 2), '-h', '64', '-s', '32', '::'])
    for entry in sorted(Path(source_dir).iterdir()):
        run([tools['mcopy'], '-s', '-m', '-i', str(output), str(entry), '::/'])


def appended_partitions(tools, iso):
    """(number, type) of partitions appended after the ISO filesystem. xorriso's
    boot replay would copy them unchanged, so an appended ESP must be replaced."""
    report = capture([tools['xorriso'], '-indev', str(iso), '-report_system_area', 'cmd'])
    found = []
    for line in report.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == '-append_partition':
            found.append((fields[1], fields[2]))
    return found


def sign_iso(tools, signer, cert_der, iso, work, output, **shim_args):
    appended = appended_partitions(tools, iso)
    tree = work / 'iso'
    tree.mkdir()
    run([tools['xorriso'], '-osirrox', 'on', '-indev', str(iso), '-extract', '/', str(tree)])
    make_writable(tree)
    maps = [(tree / rel, '/' + rel.as_posix()) for rel in sign_esp(tree, signer, cert_der, **shim_args)]
    efi_img = find_ci(tree, 'efi.img')
    if efi_img is not None:
        regular(efi_img, 'efi.img')
        fat = work / 'efi'
        fat.mkdir()
        run([tools['mcopy'], '-s', '-m', '-n', '-i', str(efi_img), '::*', str(fat)])
        make_writable(fat)
        sign_esp(fat, signer, cert_der, **shim_args)
        new_img = work / 'efi.img'
        rebuild_fat(tools, fat, efi_img, new_img)
        maps.append((new_img, '/' + efi_img.relative_to(tree).as_posix()))
    argv = [tools['xorriso'], '-indev', str(iso), '-outdev', str(output),
            '-boot_image', 'any', 'replay']
    for local, target in maps:
        argv += ['-map', str(local), target]
    for number, kind in appended:
        if kind.lower() in EFI_PARTITION_TYPES:
            if efi_img is None:
                raise SignError('ISO has an appended EFI partition but no /efi.img to rebuild it from')
            argv += ['-append_partition', number, kind, str(new_img)]
    run(argv + ['-commit'])
    if not output.is_file():
        raise SignError('xorriso produced no ISO')


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Sign a copy of the INT ESP or ISO (GRUB + kernel) with the owner key.')
    parser.add_argument('--key', required=True, help='private key (PEM), mode 0600, outside any checkout')
    parser.add_argument('--cert', required=True, help='matching public certificate (PEM)')
    parser.add_argument('--chain', help='optional PEM intermediate certificate(s) passed to sbsign --addcert')
    parser.add_argument('--shim', help='shimx64.efi to install as EFI/BOOT/BOOTX64.EFI')
    parser.add_argument('--mokmanager', help='mmx64.efi matching --shim')
    parser.add_argument('--sign-shim', action='store_true',
                        help='also sign shim and MokManager with the INT key (only for a self-built shim '
                             'whose trust comes from enrolling the INT certificate in firmware db)')
    parser.add_argument('input', help='ESP/ISO directory copy, or an .iso file (never modified)')
    parser.add_argument('output', help='new directory or .iso to create (must not exist)')
    return parser.parse_args(argv)


def sign(args):
    source = Path(args.input).resolve()
    output = Path(os.path.abspath(args.output))
    if not source.exists():
        raise SignError(f'input not found: {source}')
    if os.path.lexists(output):
        raise SignError(f'output already exists: {output}')
    if not output.parent.is_dir():
        raise SignError(f'output directory does not exist: {output.parent}')
    if source.is_dir() and (is_within(output, source) or is_within(source, output)):
        raise SignError('output and input must not contain each other')
    if bool(args.shim) != bool(args.mokmanager):
        raise SignError('--shim and --mokmanager go together')
    if args.sign_shim and not args.shim:
        raise SignError('--sign-shim needs --shim')
    key = check_private_key(args.key, [REPO_ROOT, source, output])
    cert_der = load_certificate(args.cert)
    if args.chain:
        load_certificate(args.chain)
    shim_args = {}
    if args.shim:
        for path, what in ((args.shim, 'shim'), (args.mokmanager, 'MokManager')):
            if pe_sections(path) is None:
                raise SignError(f'{what} is not a PE/COFF image: {path}')
        shim_args = {'shim': Path(args.shim), 'mokmanager': Path(args.mokmanager),
                     'sign_shim': args.sign_shim}

    is_iso = source.is_file()
    names = ['sbsign', 'sbverify'] + (['xorriso', 'mcopy', 'mformat'] if is_iso else [])
    tools = require_tools(names)
    signer = Signer(tools, key, Path(args.cert).resolve(), args.chain and Path(args.chain).resolve())

    work = Path(tempfile.mkdtemp(prefix='.int-sign-', dir=output.parent))
    try:
        if is_iso:
            staged = work / 'signed.iso'
            sign_iso(tools, signer, cert_der, source, work, staged, **shim_args)
            changed = None
        else:
            staged = work / 'out'
            shutil.copytree(source, staged, symlinks=True)
            changed = sign_esp(staged, signer, cert_der, **shim_args)
        os.replace(staged, output)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f'signed output: {output}')
    if changed is not None:
        for rel in changed:
            print(f'  {sha256(output / rel)}  {rel.as_posix()}')
    else:
        print(f'  {sha256(output)}  {output.name}')
    print(f'certificate SHA-256 fingerprint: {hashlib.sha256(cert_der).hexdigest()}')
    print(f'certificate SHA-1 fingerprint (shown by MokManager): {hashlib.sha1(cert_der).hexdigest()}')


def main(argv=None):
    args = parse_args(argv)
    try:
        sign(args)
    except SignError as error:
        print(f'sign-boot: error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
