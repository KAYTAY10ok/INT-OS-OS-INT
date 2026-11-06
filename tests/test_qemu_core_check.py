"""Conversation/evidence regression tests; fake guests do not qualify the real VM."""

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


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/qemu-core-check.py"
SPEC = importlib.util.spec_from_file_location("int_qemu_core", SCRIPT)
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)

PASS_LOG = "\n".join([
    "INT_CORE_CHECK:owner:PASS", "INT_CORE_CHECK:network:PASS", "INT_CORE_CHECK:firewall:PASS", "INT_CORE_READY",
    "INT_CORE_LOGIN_UID:1000", "INT_CORE_ROOT_PASS", "[   42.123456] reboot: Power down", "",
])
EXIT_OK = {
    "returncode": 0, "timed_out": False, "interrupted_signal": None,
    "protocol_error": None, "credential_echoed": False, "owner_password_prompts": 2,
    "login_password_prompt": True, "sudo_password_prompt": True,
    "sudo_rejected_wrong_password": True, "login_uid": 1000,
}

# Reads the credential from the PTY, never from program arguments/environment.
FAKE_GUEST = r'''
import select,sys,termios
settings=termios.tcgetattr(0)
settings[3] &= ~termios.ECHO
termios.tcsetattr(0,termios.TCSANOW,settings)
def request(prompt):
    print(prompt,end="",flush=True)
    return sys.stdin.readline().rstrip("\n")
assert request("INT_OWNER_USERNAME: ") == "intowner"
password=request("New password: ")
assert request("Retype new password: ") == password
print("\nINT_CORE_CHECK:owner:PASS\nINT_CORE_CHECK:network:PASS\nINT_CORE_CHECK:firewall:PASS\nINT_CORE_READY",flush=True)
assert request("int-linux login: ") == "intowner"
assert request("Password: ") == password
request("\n$ ")
print("\nINT_CORE_LOGIN_UID:1000",flush=True)
command=sys.stdin.readline()
assert "sudo -k" in command
# A real shell echoes the command, including the prompt text in its argument.
# No password should arrive until the separate, actual sudo prompt appears.
print("$ "+command,end="",flush=True)
assert not select.select([sys.stdin],[],[],0.15)[0]
assert request("INT_SUDO_PASSWORD: ") == "Wrong_"+password
print("\nSorry, try again.",flush=True)
assert request("INT_SUDO_PASSWORD: ") == password
print("\nINT_CORE_ROOT_PASS\n[ 1.234567] reboot: Power down",flush=True)
'''


class AnalysisTests(unittest.TestCase):
    def test_complete_markers_authentication_and_clean_shutdown(self):
        self.assertTrue(core.analyze_log(PASS_LOG, EXIT_OK)["passed"])
        self.assertTrue(core.analyze_log(PASS_LOG.replace("\n", "\r\n"), EXIT_OK)["passed"])

    def test_each_exact_marker_is_required(self):
        for line in PASS_LOG.splitlines():
            with self.subTest(line=line):
                self.assertFalse(core.analyze_log(PASS_LOG.replace(line, "echo " + line), EXIT_OK)["passed"])

    def test_all_markers_do_not_override_failures_or_missing_authentication(self):
        for update in [dict(timed_out=True), dict(returncode=1), dict(interrupted_signal=signal.SIGTERM),
                       dict(credential_echoed=True), dict(protocol_error="test failure"),
                       dict(owner_password_prompts=1), dict(login_password_prompt=False),
                       dict(sudo_password_prompt=False), dict(sudo_rejected_wrong_password=False),
                       dict(login_uid=0)]:
            with self.subTest(update=update):
                self.assertFalse(core.analyze_log(PASS_LOG, dict(EXIT_OK, **update))["passed"])
        for line in ["INT_FIRSTBOOT_FAIL: test", "INT_CORE_CHECK:firewall:FAIL", "Kernel panic"]:
            self.assertFalse(core.analyze_log(PASS_LOG + line, EXIT_OK)["passed"])

    def test_duplicates_premature_shutdown_and_root_login_fail(self):
        self.assertFalse(core.analyze_log(PASS_LOG + "INT_CORE_ROOT_PASS\n", EXIT_OK)["passed"])
        self.assertFalse(core.analyze_log("reboot: Power down\n" + PASS_LOG, EXIT_OK)["passed"])
        self.assertFalse(core.analyze_log(PASS_LOG.replace("UID:1000", "UID:0"), dict(EXIT_OK, login_uid=0))["passed"])
        ready_first = "INT_CORE_READY\n" + PASS_LOG.replace("INT_CORE_READY\n", "")
        self.assertFalse(core.analyze_log(ready_first, EXIT_OK)["passed"])

    def test_redaction_handles_secrets_split_between_read_chunks(self):
        capture = core.Transcript()
        capture.write("before test-")
        capture.write("credential after")
        self.assertEqual(core.redact(capture.getvalue(), "test-credential"), "before [REDACTED] after")


class ProcessTests(unittest.TestCase):
    def test_pty_double_carriage_returns_do_not_hide_assertions(self):
        # QEMU emits guest CRLF through a PTY whose ONLCR can add another CR.
        program = "import sys; sys.stdout.reconfigure(newline='\\r\\n')\n" + FAKE_GUEST
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            outcome = core.execute_interactive([sys.executable, "-c", program], log, timeout=5,
                                               termination_grace=0.1)
            self.assertIn(b'\r\r\n', log.read_bytes())
            self.assertTrue(core.analyze_log(log.read_text(), outcome)["passed"], outcome)

    def test_real_pty_conversation_uses_no_credential_argv_or_send_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            outcome = core.execute_interactive([sys.executable, "-c", FAKE_GUEST], log, timeout=5,
                                               termination_grace=0.1)
            self.assertTrue(core.analyze_log(log.read_text(), outcome)["passed"], outcome)
            self.assertFalse(outcome["credential_echoed"])

    def test_accidental_guest_echo_fails_and_is_redacted_before_writing(self):
        echo_guest = FAKE_GUEST.replace('password=request("New password: ")',
                                       'password=request("New password: "); print(password,flush=True)')
        fixture = "test-only-credential"
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(core, "generate_password", return_value=fixture):
            log = Path(directory) / "serial.log"
            outcome = core.execute_interactive([sys.executable, "-c", echo_guest], log, timeout=5,
                                               termination_grace=0.1)
            self.assertTrue(outcome["credential_echoed"])
            self.assertNotIn(fixture, log.read_text())
            self.assertIn("[REDACTED]", log.read_text())
            self.assertNotIn(fixture, json.dumps(outcome))
            self.assertFalse(core.analyze_log(log.read_text(), outcome)["passed"])

    def test_total_timeout_stops_an_unresponsive_process(self):
        program = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('waiting',flush=True); time.sleep(30)"
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            started = time.monotonic()
            outcome = core.execute_interactive([sys.executable, "-c", program], log, timeout=0.2,
                                               termination_grace=0.1)
            self.assertLess(time.monotonic() - started, 5)
            self.assertTrue(outcome["timed_out"])
            self.assertEqual(outcome["returncode"], -signal.SIGKILL)

    def test_wrong_password_echo_is_also_detected_and_redacted(self):
        echo_wrong = FAKE_GUEST.replace(
            'assert request("INT_SUDO_PASSWORD: ") == "Wrong_"+password',
            'wrong=request("INT_SUDO_PASSWORD: "); assert wrong == "Wrong_"+password; print(wrong,flush=True)',
        )
        fixture = "test-only-credential"
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(core, "generate_password", return_value=fixture):
            log = Path(directory) / "serial.log"
            outcome = core.execute_interactive([sys.executable, "-c", echo_wrong], log,
                                               timeout=5, termination_grace=0.1)
            self.assertTrue(outcome["credential_echoed"])
            self.assertNotIn(fixture, log.read_text())
            self.assertIn("Wrong_[REDACTED]", log.read_text())
            self.assertFalse(core.analyze_log(log.read_text(), outcome)["passed"])

    def test_accepting_wrong_password_cannot_pass_even_with_root_markers(self):
        no_rejection = FAKE_GUEST.replace(
            'print("\\nSorry, try again.",flush=True)\nassert request("INT_SUDO_PASSWORD: ") == password\n',
            '',
        )
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            outcome = core.execute_interactive([sys.executable, "-c", no_rejection], log,
                                               timeout=5, termination_grace=0.1)
            self.assertIn("INT_CORE_ROOT_PASS", log.read_text())
            self.assertFalse(outcome["sudo_rejected_wrong_password"])
            self.assertFalse(core.analyze_log(log.read_text(), outcome)["passed"])

    def test_cleanup_stops_helper_after_parent_exits(self):
        helper = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"
        program = ("import subprocess,sys,time; "
                   f"p=subprocess.Popen([sys.executable,'-c',{helper!r}]); "
                   "print('CHILD_PID='+str(p.pid),flush=True); time.sleep(30)")
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            outcome = core.execute_interactive([sys.executable, "-c", program], log, timeout=0.3,
                                               termination_grace=0.1)
            self.assertTrue(outcome["timed_out"])
            pid = int(log.read_text().split("CHILD_PID=")[1].split()[0])
            try:
                deadline = time.monotonic() + 1
                running = True
                while time.monotonic() < deadline:
                    try:
                        running = Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
                    except FileNotFoundError:
                        running = False
                    if not running:
                        break
                    time.sleep(0.01)
                self.assertFalse(running)
            finally:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.deploy = self.directory / "deploy"
        self.deploy.mkdir()
        for kind, filename in core.INPUTS.items():
            (self.deploy / filename).write_bytes((kind + " fixture").encode())
        kernel = bytearray(4096)
        kernel[0x202:0x206] = b"HdrS"
        struct.pack_into("<H", kernel, 0x20e, 0x600)
        version = b"6.18.54-yocto-standard (test fixture)\0"
        kernel[0x800:0x800 + len(version)] = version
        (self.deploy / core.INPUTS["kernel"]).write_bytes(kernel)
        (self.deploy / core.INPUTS["manifest"]).write_text(
            "kernel-6.18.54-yocto-standard qemux86_64 6.18.54\n")

    def invoke(self, outcome, log=PASS_LOG):
        def execute(_command, path, _timeout):
            path.write_text(log)
            return outcome
        with mock.patch.object(core.shutil, "which", return_value=sys.executable), \
                mock.patch.object(core.smoke, "qemu_version", return_value="unit-test double"), \
                mock.patch.object(core, "execute_interactive", side_effect=execute):
            return core.run_core(self.deploy, self.directory / "evidence", 2)

    def test_only_pass_retains_known_good_unprovisioned_inputs(self):
        code, run = self.invoke(EXIT_OK)
        self.assertEqual(code, 0)
        self.assertTrue((run / "known-good.json").exists())
        result = json.loads((run / "result.json").read_text())
        for artifact in result["artifacts"].values():
            self.assertEqual(core.smoke.sha256(Path(artifact["snapshot"])), artifact["sha256"])
        command = result["command"]
        self.assertIn("snapshot=on", command[command.index("-drive") + 1])
        self.assertIn("restrict=on", command[command.index("-netdev") + 1])
        self.assertNotIn("hostfwd", " ".join(command))
        self.assertIn("tcg,thread=multi", command)
        code, failed = self.invoke(dict(EXIT_OK, credential_echoed=True))
        self.assertNotEqual(code, 0)
        self.assertFalse((failed / "known-good.json").exists())
        self.assertFalse((failed / "artifacts").exists())
        self.assertTrue((failed / "serial.log").exists())

    def test_missing_manifest_fails_before_spawning(self):
        (self.deploy / core.INPUTS["manifest"]).unlink()
        with mock.patch.object(core.shutil, "which", return_value=sys.executable), \
                mock.patch.object(core.smoke, "qemu_version", return_value="test double"), \
                mock.patch.object(core, "execute_interactive") as execute:
            code, run = core.run_core(self.deploy, self.directory / "evidence", 2)
        self.assertNotEqual(code, 0)
        execute.assert_not_called()
        self.assertFalse((run / "artifacts").exists())
        self.assertFalse((run / "known-good.json").exists())

    def test_mismatched_kernel_manifest_fails_before_interaction(self):
        (self.deploy / core.INPUTS["manifest"]).write_text("kernel-6.19-other qemux86_64 6.19\n")
        with mock.patch.object(core.shutil, "which", return_value=sys.executable), \
                mock.patch.object(core.smoke, "qemu_version", return_value="test double"), \
                mock.patch.object(core, "execute_interactive") as execute:
            code, run = core.run_core(self.deploy, self.directory / "evidence", 2)
        self.assertNotEqual(code, 0)
        execute.assert_not_called()
        self.assertFalse((run / "artifacts").exists())
        self.assertFalse((run / "known-good.json").exists())


if __name__ == "__main__":
    unittest.main()
