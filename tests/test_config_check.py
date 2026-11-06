"""CPU guard regression cases from the actual hardened OE configuration."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/check-config.py"
spec = importlib.util.spec_from_file_location("int_config_check", path)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ArchitectureFlagsTests(unittest.TestCase):
    def test_generic_baseline_keeps_hardening(self):
        observed = "-m64 -fstack-protector-strong -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security"
        self.assertTrue(config.generic_x86_64_flags(observed))
        self.assertTrue(config.generic_x86_64_flags("-m64 -march=x86-64 -mtune=generic"))

    def test_rejects_new_isa_requirements(self):
        for extra in ("-mavx", "-mavx2", "-mavx512f", "-mbmi2", "-msse4.2"):
            with self.subTest(extra=extra):
                self.assertFalse(config.generic_x86_64_flags("-m64 " + extra))

    def test_rejects_narrow_or_host_architecture(self):
        for extra in ("-march=native", "-march=x86-64-v3", "-mcpu=native", "-mtune=skylake"):
            with self.subTest(extra=extra):
                self.assertFalse(config.generic_x86_64_flags("-m64 " + extra))

    def test_requires_64_bit_abi(self):
        for flags in ("", "-O2 -fstack-protector-strong", "-m32", "-m64 -m32", "-mx32"):
            with self.subTest(flags=flags):
                self.assertFalse(config.generic_x86_64_flags(flags))


if __name__ == "__main__":
    unittest.main()
