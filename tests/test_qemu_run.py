"""Host-only tests for the interactive QEMU launcher.

They build synthetic kernel/rootfs/manifest files; no guest is booted.
"""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qemu_run", ROOT / "scripts/qemu-run.py")
run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run)
RELEASE = "6.18.54-int-core1"


def fake_kernel(path):
    data = bytearray(0x400)
    data[0x202:0x206] = b"HdrS"
    struct.pack_into("<H", data, 0x20e, 0x100)
    version = (RELEASE + " (builder@int) #1").encode() + b"\0"
    data[0x300:0x300 + len(version)] = version
    path.write_bytes(bytes(data))


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.deploy = self.work / "build/tmp/deploy/images/qemux86-64"
        self.deploy.mkdir(parents=True)
        fake_kernel(self.deploy / "bzImage")
        (self.deploy / "int-image-core-qemux86-64.rootfs.ext4").write_bytes(b"rootfs v1")
        (self.deploy / "int-image-core-qemux86-64.rootfs.manifest").write_text(
            f"kernel-{RELEASE} qemux86_64 1.0\nsystemd core2_64 258\n")

    def files(self, reset=False):
        sources = run.artifacts(self.deploy, "int-image-core")
        return run.prepare_state(sources, self.work / "run/int-image-core", reset)

    def test_state_copy_persists_and_never_touches_deploy(self):
        files = self.files()
        files["rootfs"].write_bytes(b"enrolled owner")
        self.assertEqual(b"rootfs v1", (self.deploy / "int-image-core-qemux86-64.rootfs.ext4").read_bytes())
        self.assertEqual(b"enrolled owner", self.files()["rootfs"].read_bytes())
        self.assertEqual(b"rootfs v1", self.files(reset=True)["rootfs"].read_bytes())

    def test_missing_image_or_mismatched_kernel_is_rejected(self):
        with self.assertRaisesRegex(FileNotFoundError, "build int-image-desktop"):
            run.artifacts(self.deploy, "int-image-desktop")
        (self.deploy / "int-image-core-qemux86-64.rootfs.manifest").write_text("kernel-6.1.0 x 1\n")
        with self.assertRaises(ValueError):
            run.artifacts(self.deploy, "int-image-core")

    def test_console_command_has_no_forwarded_ports(self):
        with mock.patch.object(run.os, "access", return_value=False):
            command = run.qemu_command("qemu", self.files(), "core", "gtk")
        joined = " ".join(command)
        self.assertNotIn("hostfwd", joined)
        self.assertIn("mon:stdio", command)
        self.assertIn("tcg,thread=multi", command)
        self.assertTrue(command[command.index("-append") + 1].endswith("console=ttyS0,115200n8"))

    def test_desktop_enrollment_console_is_the_graphical_one(self):
        with mock.patch.object(run.os, "access", return_value=True):
            command = run.qemu_command("qemu", self.files(), "desktop", "sdl")
        self.assertTrue(command[command.index("-append") + 1].endswith("console=tty0"))
        self.assertIn("kvm", command)
        self.assertEqual("sdl", command[command.index("-display") + 1])
        self.assertNotIn("hostfwd", " ".join(command))


if __name__ == "__main__":
    unittest.main()
