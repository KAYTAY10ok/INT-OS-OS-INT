"""Reject missing kernel capabilities and modules in the actual image contract."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('int_kernel_check', Path(__file__).resolve().parents[1]/'scripts/check-kernel.py')
kernel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kernel)


class KernelCheckTests(unittest.TestCase):
    def config(self):
        text = '\n'.join('CONFIG_'+name+'=y' for name in kernel.BUILTIN)
        text += '\nCONFIG_LOCALVERSION="-int-core1"\nCONFIG_NF_CONNTRACK=m\nCONFIG_NFT_CT=m\nCONFIG_VETH=m\n'
        return kernel.parse_config(text)

    def test_merged_disabled_capability_overrides_source_intention(self):
        config = self.config()
        config.update(kernel.parse_config('# CONFIG_NF_TABLES is not set\n'))
        self.assertEqual(config['NF_TABLES'], 'n')
        self.assertFalse(kernel.audit(config, '-int-core1')['passed'])

    def test_modular_firewall_requires_matching_image_packages(self):
        packages = {'kernel-module-nf-conntrack-6.18.54-int-core1', 'kernel-module-nft-ct-6.18.54-int-core1'}
        self.assertTrue(kernel.audit(self.config(), '-int-core1', packages)['passed'])
        for package in packages:
            self.assertFalse(kernel.audit(self.config(), '-int-core1', packages-{package})['passed'])
        self.assertFalse(kernel.audit(self.config(), '-int-core1', packages, require_veth=True)['passed'])
        self.assertTrue(kernel.audit(self.config(), '-int-core1', packages|{'kernel-module-veth-6.18.54-int-core1'}, True)['passed'])

    def test_wrong_abi_and_missing_builtins_are_rejected(self):
        self.assertFalse(kernel.audit(self.config(), '-different')['passed'])
        config = self.config()
        del config['VIRTIO_BLK']
        self.assertFalse(kernel.audit(config, '-int-core1')['passed'])


if __name__ == '__main__':
    unittest.main()
