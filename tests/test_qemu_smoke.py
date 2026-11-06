"""Tests for smoke-runner failure detection, cleanup, and evidence retention.

Fake guest output is used only inside temporary test directories. These tests
do not replace booting the real INT image under QEMU.
"""

import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qemu-smoke.py"
SPEC = importlib.util.spec_from_file_location("int_qemu_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)

PASS_LOG = "\n".join([f"INT_CHECK:{name}:PASS" for name in smoke.CHECKS] + ["INT_SMOKE_PASS", ""])
EXIT_OK = {"returncode": 0, "timed_out": False, "interrupted_signal": None}
RELEASE = "6.18.54-yocto-standard"


def kernel_fixture(release=RELEASE):
    """A boot-header fixture only; this is not a bootable Linux kernel."""
    image = bytearray(4096)
    image[0x202:0x206] = b"HdrS"
    struct.pack_into("<H", image, 0x20e, 0x600)
    version = (release + " (test fixture) #1 SMP\0").encode("ascii")
    image[0x800:0x800 + len(version)] = version
    return image


class KernelPairingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.kernel = self.root / "bzImage"
        self.kernel.write_bytes(kernel_fixture())
        self.manifest = self.root / "manifest"
        self.valid_manifest = (f"kernel-{RELEASE} qemux86_64 6.18.54\n"
                               f"kernel-module-nf-tables-{RELEASE} qemux86_64 6.18.54\n")
        self.manifest.write_text(self.valid_manifest)

    def test_valid_boot_header_and_exact_kernel_module_suffix(self):
        self.assertEqual(smoke.read_kernel_release(self.kernel), RELEASE)
        self.assertEqual(smoke.validate_kernel_manifest(self.kernel, self.manifest), RELEASE)

    def test_invalid_header_pointer_and_version_fail_closed(self):
        cases = [b"short", bytearray(4096)]
        for pointer in (0, 1, 0x1000):
            image = kernel_fixture()
            struct.pack_into("<H", image, 0x20e, pointer)
            cases.append(image)
        unterminated = kernel_fixture()
        unterminated[0x800:0x900] = b"6" * 256
        cases.append(unterminated)
        non_ascii = kernel_fixture()
        non_ascii[0x800] = 255
        cases.append(non_ascii)
        unsafe = kernel_fixture("6.18/unsafe")
        cases.append(unsafe)
        whitespace = kernel_fixture()
        whitespace[0x800:0x802] = b" \0"
        cases.append(whitespace)
        for image in cases:
            with self.subTest(first_bytes=bytes(image[:8])):
                self.kernel.write_bytes(image)
                with self.assertRaises(ValueError):
                    smoke.read_kernel_release(self.kernel)

    def test_ambiguous_malformed_and_incompatible_manifests_are_rejected(self):
        cases = ["", "kernel-" + RELEASE + " missing-version\n",
                 self.valid_manifest + f"kernel-{RELEASE} qemux86_64 duplicate\n",
                 self.valid_manifest + "kernel-6.19-other qemux86_64 6.19\n",
                 self.valid_manifest.replace("kernel-module-nf-tables-" + RELEASE,
                                             "kernel-module-nf-tables-6.19-other"),
                 self.valid_manifest.replace("kernel-" + RELEASE, "kernel-6.19-other"),
                 self.valid_manifest + "broken\x00name all 1\n",
                 self.valid_manifest.replace("\n", "\v")]
        for manifest in cases:
            with self.subTest(manifest=manifest):
                self.manifest.write_text(manifest)
                with self.assertRaises(ValueError):
                    smoke.validate_kernel_manifest(self.kernel, self.manifest)

    def test_sparse_oversized_kernel_and_manifest_are_rejected_before_copying(self):
        deploy = self.root / "deploy"
        deploy.mkdir()
        for kind, filename in smoke.INPUTS.items():
            (deploy / filename).write_bytes(b"rootfs fixture")
        kernel = deploy / smoke.INPUTS["kernel"]
        manifest = deploy / smoke.INPUTS["manifest"]
        for oversize in ("kernel", "manifest"):
            kernel.write_bytes(kernel_fixture())
            manifest.write_text(self.valid_manifest)
            target = kernel if oversize == "kernel" else manifest
            limit = smoke.MAX_KERNEL_BYTES if oversize == "kernel" else smoke.MAX_MANIFEST_BYTES
            with target.open("r+b") as stream:
                stream.truncate(limit + 1)
            with mock.patch.object(smoke.shutil, "copyfile") as copy:
                with self.assertRaises(ValueError):
                    smoke.snapshot_inputs(deploy, self.root)
                copy.assert_not_called()


class LogAnalysisTests(unittest.TestCase):
    def test_complete_assertions_and_normal_exit_pass(self):
        self.assertTrue(smoke.analyze_log(PASS_LOG, EXIT_OK)["passed"])
        self.assertTrue(smoke.analyze_log(PASS_LOG.replace("\n", "\r\n"), EXIT_OK)["passed"])

    def test_final_marker_alone_is_not_a_pass(self):
        result = smoke.analyze_log("INT_SMOKE_PASS\n", EXIT_OK)
        self.assertFalse(result["passed"])
        self.assertFalse(any(result["checks"].values()))

    def test_each_guest_assertion_is_required(self):
        for name in smoke.CHECKS:
            with self.subTest(check=name):
                log = PASS_LOG.replace(f"INT_CHECK:{name}:PASS\n", "")
                self.assertFalse(smoke.analyze_log(log, EXIT_OK)["passed"])

    def test_substring_and_prefixed_markers_are_rejected(self):
        self.assertFalse(smoke.analyze_log(PASS_LOG.replace("INT_SMOKE_PASS", "echo INT_SMOKE_PASS"), EXIT_OK)["passed"])
        self.assertFalse(smoke.analyze_log(PASS_LOG.replace("INT_CHECK:arch:PASS", "[ 1.0] INT_CHECK:arch:PASS"), EXIT_OK)["passed"])

    def test_errors_override_complete_pass_even_with_exit_zero(self):
        for failure in ["INT_SMOKE_FAIL:root", "Kernel panic - not syncing: failure", "INT_CHECK:init:FAIL"]:
            with self.subTest(failure=failure):
                self.assertFalse(smoke.analyze_log(PASS_LOG + failure + "\n", EXIT_OK)["passed"])

    def test_timeout_nonzero_and_interruption_override_markers(self):
        for process in [dict(EXIT_OK, timed_out=True), dict(EXIT_OK, returncode=1),
                        dict(EXIT_OK, interrupted_signal=signal.SIGTERM), dict(EXIT_OK, returncode=None)]:
            with self.subTest(process=process):
                self.assertFalse(smoke.analyze_log(PASS_LOG, process)["passed"])

    def test_premature_or_duplicate_final_markers_are_rejected(self):
        without_final = PASS_LOG.replace("INT_SMOKE_PASS\n", "")
        self.assertFalse(smoke.analyze_log("INT_SMOKE_PASS\n" + without_final, EXIT_OK)["passed"])
        self.assertFalse(smoke.analyze_log(PASS_LOG + "INT_SMOKE_PASS\n", EXIT_OK)["passed"])


class ProcessTests(unittest.TestCase):
    def test_timeout_cannot_pass_after_printing_all_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            command = [sys.executable, "-c", f"import time; print({PASS_LOG!r}, flush=True); time.sleep(30)"]
            started = time.monotonic()
            outcome = smoke.execute_qemu(command, log, timeout=0.15, termination_grace=0.1)
            self.assertLess(time.monotonic() - started, 5)
            self.assertTrue(outcome["timed_out"])
            self.assertFalse(smoke.analyze_log(log.read_text(), outcome)["passed"])

    def test_timeout_stops_a_process_ignoring_sigterm(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            command = [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready',flush=True); time.sleep(30)"]
            outcome = smoke.execute_qemu(command, log, timeout=0.5, termination_grace=0.1)
            self.assertTrue(outcome["timed_out"])
            self.assertEqual(outcome["returncode"], -signal.SIGKILL)

    def test_timeout_also_stops_a_helper_after_parent_exits(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            helper = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
            program = (
                "import subprocess,sys,time; "
                f"child=subprocess.Popen([sys.executable,'-c',{helper!r}]); "
                "print('CHILD_PID='+str(child.pid),flush=True); time.sleep(30)"
            )
            outcome = smoke.execute_qemu([sys.executable, "-c", program], log,
                                         timeout=0.5, termination_grace=0.1)
            self.assertTrue(outcome["timed_out"])
            child_pid = int(log.read_text().strip().split("CHILD_PID=")[1])
            try:
                deadline = time.monotonic() + 1
                running = True
                while time.monotonic() < deadline:
                    try:
                        # A reparented zombie has stopped and awaits the host's init.
                        running = Path(f"/proc/{child_pid}/stat").read_text().split()[2] != "Z"
                    except FileNotFoundError:
                        running = False
                    if not running:
                        break
                    time.sleep(0.01)
                self.assertFalse(running, "helper survived process-group cleanup")
            finally:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.deploy = self.directory / "deploy"
        self.deploy.mkdir()
        self.evidence = self.directory / "evidence"
        for kind, filename in smoke.INPUTS.items():
            (self.deploy / filename).write_bytes((kind + " test fixture\n").encode())
        (self.deploy / smoke.INPUTS["kernel"]).write_bytes(kernel_fixture())
        (self.deploy / smoke.INPUTS["manifest"]).write_text(f"kernel-{RELEASE} qemux86_64 6.18.54\n")

    def fake_command(self, _executable, _artifacts):
        return [sys.executable, "-c", f"print({PASS_LOG!r})"]

    def test_pass_retains_exact_artifacts_and_never_overwrites_a_run(self):
        with mock.patch.object(smoke.shutil, "which", return_value=sys.executable), \
                mock.patch.object(smoke, "qemu_version", return_value="test double, not QEMU"), \
                mock.patch.object(smoke, "build_qemu_command", side_effect=self.fake_command):
            code, first = smoke.run_smoke(self.deploy, self.evidence, timeout=2)
            self.assertEqual(code, 0)
            (self.deploy / smoke.INPUTS["rootfs"]).write_bytes(b"a later image must not replace known-good")
            code, second = smoke.run_smoke(self.deploy, self.evidence, timeout=2)
        self.assertEqual(code, 0)
        self.assertNotEqual(first, second)
        self.assertNotEqual(
            smoke.sha256(first / "artifacts" / smoke.INPUTS["rootfs"]),
            smoke.sha256(second / "artifacts" / smoke.INPUTS["rootfs"]),
        )
        for run in [first, second]:
            result = json.loads((run / "result.json").read_text())
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["artifact_copies_retained"])
            self.assertTrue((run / "known-good.json").is_file())
            for artifact in result["artifacts"].values():
                self.assertEqual(smoke.sha256(Path(artifact["snapshot"])), artifact["sha256"])

    def test_failed_guest_retains_logs_but_no_known_good(self):
        with mock.patch.object(smoke.shutil, "which", return_value=sys.executable), \
                mock.patch.object(smoke, "qemu_version", return_value="test double, not QEMU"), \
                mock.patch.object(smoke, "build_qemu_command", return_value=[sys.executable, "-c", "print('INT_SMOKE_PASS')"]):
            code, run = smoke.run_smoke(self.deploy, self.evidence, timeout=2)
        self.assertNotEqual(code, 0)
        self.assertFalse((run / "known-good.json").exists())
        self.assertFalse((run / "artifacts").exists())
        self.assertIn("INT_SMOKE_PASS", (run / "serial.log").read_text())
        self.assertEqual(json.loads((run / "result.json").read_text())["status"], "failed")

    def test_missing_manifest_fails_before_qemu(self):
        (self.deploy / smoke.INPUTS["manifest"]).unlink()
        with mock.patch.object(smoke.shutil, "which", return_value=sys.executable), \
                mock.patch.object(smoke, "qemu_version", return_value="test double"), \
                mock.patch.object(smoke, "execute_qemu") as execute:
            code, run = smoke.run_smoke(self.deploy, self.evidence, timeout=2)
        self.assertNotEqual(code, 0)
        execute.assert_not_called()
        self.assertFalse((run / "known-good.json").exists())

    def test_real_command_uses_tcg_snapshot_and_no_exposed_ports(self):
        artifacts = {kind: {"snapshot": str(self.deploy / filename)} for kind, filename in smoke.INPUTS.items()}
        command = smoke.build_qemu_command("qemu-system-x86_64", artifacts)
        self.assertEqual(command[command.index("-accel") + 1], "tcg,thread=multi")
        self.assertEqual(command[command.index("-cpu") + 1], "qemu64")
        self.assertIn("snapshot=on", command[command.index("-drive") + 1])
        self.assertIn("restrict=on", command[command.index("-netdev") + 1])
        self.assertNotIn("hostfwd", " ".join(command))
        self.assertNotIn("kvm", " ".join(command))
        self.assertEqual(command[command.index("-monitor") + 1], "none")

    def test_kernel_abi_mismatch_fails_before_qemu_and_creates_no_known_good(self):
        (self.deploy / smoke.INPUTS["kernel"]).write_bytes(kernel_fixture("6.19-other"))
        with mock.patch.object(smoke.shutil, "which", return_value=sys.executable), \
                mock.patch.object(smoke, "qemu_version", return_value="test double"), \
                mock.patch.object(smoke, "execute_qemu") as execute:
            code, run = smoke.run_smoke(self.deploy, self.evidence, timeout=2)
        self.assertNotEqual(code, 0)
        execute.assert_not_called()
        self.assertFalse((run / "known-good.json").exists())
        self.assertFalse((run / "artifacts").exists())


if __name__ == "__main__":
    unittest.main()
