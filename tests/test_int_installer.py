"""Dry-run tests of the INT disk installer with a synthetic block-device tree.

The installer runs with INT_INSTALL_DRY_RUN=1 under dash (a small POSIX shell
close to busybox sh); it prints commands instead of running them, so no disk
is touched. Real partitioning is covered only by the QEMU install test.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "meta-int/recipes-core/initrdscripts/files/int-install-efi.sh"
SHELL = shutil.which("dash") or shutil.which("sh")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sys = self.root / "sys"
        for name, sectors, model in (("sda", 2701312, "USB Stick"), ("nvme0n1", 500118192, "Samsung SSD 980"),
                                     ("loop0", 1000, ""), ("sr0", 1000, "DVD")):
            block = self.sys / "block" / name
            (block / "device").mkdir(parents=True)
            (block / "size").write_text(f"{sectors}\n")
            (block / "device" / "model").write_text(model + "\n")
        (self.root / "mounts").write_text("/dev/sda /run/media/sda iso9660 ro 0 0\n")
        (self.root / "meminfo").write_text("MemTotal:       16384000 kB\n")

    def install(self, answers, mounts=True):
        env = {"PATH": "/usr/bin:/bin", "INT_INSTALL_DRY_RUN": "1", "INT_SYS": str(self.sys),
               "INT_MEMINFO": str(self.root / "meminfo"),
               "INT_MOUNTS": str(self.root / ("mounts" if mounts else "none"))}
        return subprocess.run([SHELL, str(SCRIPT), "sda/", "rootfs.img"], input="\n".join(answers) + "\n",
                              capture_output=True, text=True, env=env, timeout=30)

    def test_french_install_plan_on_nvme_excludes_live_stick(self):
        result = self.install(["1", "1", "2", "2", "1", "1"])
        out = result.stdout
        self.assertEqual(0, result.returncode, out + result.stderr)
        self.assertIn("Installation d'INT Linux", out)
        self.assertIn("1) /dev/nvme0n1  238 GiB  Samsung SSD 980", out)
        self.assertNotIn("/dev/sda ", out.split("Disques disponibles")[1].split("ATTENTION")[0])
        self.assertNotIn("loop0", out)
        self.assertNotIn("sr0", out)
        for command in ("RUN: parted -s /dev/nvme0n1 mklabel gpt",
                        "RUN: mkfs.vfat -F 32 -n INT-EFI /dev/nvme0n1p1",
                        "RUN: mkfs.ext4 -F -q -L INT-ROOT /dev/nvme0n1p2",
                        "RUN: mkswap -L INT-SWAP /dev/nvme0n1p3",
                        "RUN: mount -o ro,loop /run/media/sda/rootfs.img /src_root",
                        "RUN: efibootmgr -c -d /dev/nvme0n1 -p 1 -L INT Linux"):
            self.assertIn(command, out)
        self.assertIn("INT_EDITION=os-int", out)
        self.assertIn("INT_KEYMAP=fr_CH", out)
        self.assertIn("INT_XKB_LAYOUT=ch", out)
        self.assertIn("LANG=fr_FR.UTF-8", out)
        self.assertIn("menuentry 'INT Linux'", out)
        self.assertIn("root=PARTUUID=DRYRUN-ROOT", out)
        # 16 GB RAM caps swap at 4 GiB.
        self.assertIn("swap    4096 MiB", out)

    def test_wrong_confirmation_cancels_before_any_command(self):
        result = self.install(["2", "4", "1", "2", "1", "3"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("No disk was modified", result.stdout)
        self.assertNotIn("RUN:", result.stdout)

    def test_invalid_answers_are_asked_again(self):
        result = self.install(["9", "abc", "", "2", "4", "1", "2", "1", "1"])
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertGreaterEqual(result.stdout.count("Invalid choice"), 3)
        self.assertIn("INT_EDITION=int-os", result.stdout)
        self.assertIn("LANG=en_US.UTF-8", result.stdout)

    def test_zero_cancels_and_end_of_input_cancels(self):
        for answers in (["2", "0"], ["2", "4", "1", "2", "0"], ["2", "4", "1", "0"], ["2"]):
            with self.subTest(answers=answers):
                result = self.install(answers)
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn("RUN:", result.stdout)

    def test_no_target_disk_besides_live_stick(self):
        for name in ("nvme0n1",):
            shutil.rmtree(self.sys / "block" / name)
        result = self.install(["2", "4", "1", "2"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("No installation disk found", result.stdout)

    def test_tiny_disk_is_refused(self):
        (self.sys / "block" / "nvme0n1" / "size").write_text("4194304\n")  # 2 GiB
        result = self.install(["2", "4", "1", "2", "1", "1"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("disk too small", result.stdout)
        self.assertNotIn("RUN:", result.stdout)

    def test_encrypted_os_int_install_uses_luks_no_swap_and_random_mac(self):
        result = self.install(["2", "4", "2", "1", "1", "1"])
        out = result.stdout
        self.assertEqual(0, result.returncode, out + result.stderr)
        self.assertIn("RUN: parted -s /dev/nvme0n1 mkpart root ext4 512MiB 100%", out)
        self.assertIn("RUN: cryptsetup luksFormat --type luks2 --pbkdf argon2id /dev/nvme0n1p2", out)
        self.assertIn("RUN: mkfs.ext4 -F -q -L INT-ROOT /dev/mapper/introot", out)
        self.assertIn("RUN: mount /dev/mapper/introot /tgt_root", out)
        self.assertIn("RUN: cryptsetup close introot", out)
        self.assertNotIn("mkswap", out)
        self.assertNotIn("swap  defaults", out)
        self.assertIn("intluks=PARTUUID=DRYRUN-ROOT root=/dev/mapper/introot", out)
        self.assertIn("initrd /initrd-luks.cpio.gz", out)
        self.assertIn("RUN: cp /tmp/initrd-luks.cpio.gz /tgt_boot/initrd-luks.cpio.gz", out)
        self.assertIn("INT_ENCRYPTED=1", out)
        self.assertIn("MACAddressPolicy=random", out)
        # The passphrase is never passed on a command line.
        for line in out.splitlines():
            if "cryptsetup" in line:
                self.assertNotIn("--key-file", line)

    def test_int_os_keeps_hardware_mac_and_plain_layout(self):
        result = self.install(["2", "4", "1", "2", "1", "1"])
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertNotIn("MACAddressPolicy", result.stdout)
        self.assertNotIn("cryptsetup", result.stdout)
        self.assertIn("INT_ENCRYPTED=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
