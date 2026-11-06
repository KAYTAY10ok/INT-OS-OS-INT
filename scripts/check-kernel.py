#!/usr/bin/env python3
"""Audit the generated core kernel configuration and optional image manifest.

Source fragments are requests. This checks the merged result and requires the
matching runtime packages when a firewall facility ended up as a module.
"""
import argparse
import hashlib
import json
from pathlib import Path


BUILTIN = (
    '64BIT', 'X86_64', 'MMU', 'PCI', 'DEVTMPFS', 'DEVTMPFS_MOUNT',
    'TTY', 'SERIAL_8250', 'SERIAL_8250_CONSOLE', 'VIRTIO_PCI', 'VIRTIO_BLK',
    'EXT4_FS', 'INET', 'IPV6', 'NETFILTER', 'NF_TABLES', 'NF_TABLES_INET',
    'NET_NS', 'IKCONFIG', 'IKCONFIG_PROC', 'STACKPROTECTOR_STRONG',
    'RANDOMIZE_BASE', 'SECURITY_DMESG_RESTRICT',
)
MODULAR = {'NF_CONNTRACK':'nf-conntrack', 'NFT_CT':'nft-ct', 'VETH':'veth'}


def parse_config(text):
    result = {}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            name, value = line.split('=', 1)
            result[name.removeprefix('CONFIG_')] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            result[line[9:-11]] = 'n'
    return result


def audit(config, local_version, packages=None, require_veth=False):
    failures = []
    observed = {}
    for name in BUILTIN:
        observed[name] = config.get(name, 'missing')
        if observed[name] != 'y':
            failures.append(f'CONFIG_{name}: expected y, observed {observed[name]}')
    if config.get('LOCALVERSION') != json.dumps(local_version):
        failures.append('CONFIG_LOCALVERSION differs from the locked kernel ABI')
    observed['LOCALVERSION'] = config.get('LOCALVERSION', 'missing')
    for name, module in MODULAR.items():
        if name == 'VETH' and not require_veth:
            continue
        observed[name] = config.get(name, 'missing')
        if observed[name] not in ('y', 'm'):
            failures.append(f'CONFIG_{name}: expected y or m, observed {observed[name]}')
        elif observed[name] == 'm' and packages is not None:
            prefix = 'kernel-module-' + module
            if not any(package == prefix or package.startswith(prefix + '-') for package in packages):
                failures.append(f'missing runtime package for CONFIG_{name}=m: {prefix}')
    return {'passed':not failures, 'observed':observed, 'failure_reasons':failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--require-veth', action='store_true')
    parser.add_argument('--profile', choices=['core', 'desktop'], default='core')
    args = parser.parse_args()
    lock = json.loads((Path(__file__).resolve().parents[1]/'configs/sources.lock.json').read_text())
    content = args.config.read_bytes()
    packages = None
    if args.manifest:
        packages = {line.split()[0] for line in args.manifest.read_text().splitlines() if line.strip()}
    local_version = lock['kernel']['local_version'] if args.profile == 'core' else lock['profiles']['desktop']['kernel_local_version']
    result = audit(parse_config(content.decode()), local_version, packages, args.require_veth)
    result['config_sha256'] = hashlib.sha256(content).hexdigest()
    result['config'] = str(args.config.resolve())
    result['manifest'] = str(args.manifest.resolve()) if args.manifest else None
    result['scope'] = 'merged configuration and package presence; not runtime functionality'
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
