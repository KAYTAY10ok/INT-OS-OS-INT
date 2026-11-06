"""Reject incomplete desktop evidence; fake PTYs do not qualify a real compositor."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("int_desktop_test", ROOT / "scripts/qemu-desktop-check.py")
desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop)
FIXTURE_SPEC = importlib.util.spec_from_file_location("int_desktop_core_fixtures", Path(__file__).with_name("test_qemu_core_check.py"))
fixtures = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(fixtures)

DESKTOP_LINES = [f"INT_DESKTOP_CHECK:{name}:PASS" for name in desktop.COMPONENTS] + ["INT_DESKTOP_USER_PASS"]
PASS_LOG = fixtures.PASS_LOG.replace("INT_CORE_ROOT_PASS", "\n".join(DESKTOP_LINES) + "\nINT_CORE_ROOT_PASS")
EXIT_OK = dict(fixtures.EXIT_OK, desktop_user_checked=True)

# The reusable core fixture performs actual PTY enrollment/login/sudo exchanges.
# Add the owner command before that fixture reads the sudo command.
HANDSHAKE = '''assert sys.stdin.readline().strip() == "/usr/libexec/int-desktop-user-check"
print({markers!r},flush=True)
'''.format(markers="\n" + "\n".join(DESKTOP_LINES))
FAKE_GUEST = fixtures.FAKE_GUEST.replace('command=sys.stdin.readline()', HANDSHAKE + 'command=sys.stdin.readline()')


class DesktopAnalysisTests(unittest.TestCase):
    def test_complete_core_and_owner_desktop_evidence_is_required(self):
        result = desktop.analyze_log(PASS_LOG, EXIT_OK)
        self.assertTrue(result['passed'], result)
        self.assertTrue(all(result['checks'].values()))
        self.assertFalse(desktop.analyze_log(fixtures.PASS_LOG, EXIT_OK)['passed'])
        self.assertFalse(desktop.analyze_log(PASS_LOG, fixtures.EXIT_OK)['passed'])
        for update in ({'credential_echoed':True}, {'timed_out':True}, {'login_uid':0}, {'returncode':1}):
            with self.subTest(update=update):
                self.assertFalse(desktop.analyze_log(PASS_LOG, dict(EXIT_OK, **update))['passed'])

    def test_each_exact_desktop_assertion_is_required(self):
        for line in DESKTOP_LINES:
            with self.subTest(line=line):
                self.assertFalse(desktop.analyze_log(PASS_LOG.replace(line, 'echo '+line), EXIT_OK)['passed'])
                self.assertFalse(desktop.analyze_log(PASS_LOG+'\n'+line, EXIT_OK)['passed'])

    def test_order_and_failure_markers_override_a_final_pass(self):
        misplaced = PASS_LOG.replace('\n'.join(DESKTOP_LINES)+'\n', '')
        self.assertFalse(desktop.analyze_log('\n'.join(DESKTOP_LINES)+'\n'+misplaced, EXIT_OK)['passed'])
        self.assertFalse(desktop.analyze_log(misplaced+'\n'+'\n'.join(DESKTOP_LINES), EXIT_OK)['passed'])
        reversed_checks = PASS_LOG.replace('\n'.join(DESKTOP_LINES), '\n'.join(reversed(DESKTOP_LINES)))
        self.assertFalse(desktop.analyze_log(reversed_checks, EXIT_OK)['passed'])
        for error in ('INT_DESKTOP_USER_FAIL:fixture', 'INT_DESKTOP_CHECK:terminal:FAIL'):
            self.assertFalse(desktop.analyze_log(PASS_LOG+'\n'+error, EXIT_OK)['passed'])


class DesktopInteractionTests(unittest.TestCase):
    def run_guest(self, program, password=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        log = Path(temp.name)/'serial.log'
        with mock.patch.object(desktop.core, 'generate_password', return_value=password or 'test-only-desktop-credential'):
            result = desktop.core.execute_interactive([sys.executable, '-c', program], log, 6,
                                                      termination_grace=0.1, on_owner=desktop.owner_checks)
        return result, log

    def test_desktop_hook_runs_as_authenticated_owner_before_sudo(self):
        result, log = self.run_guest(FAKE_GUEST)
        self.assertTrue(desktop.analyze_log(log.read_text(), result)['passed'], result)
        self.assertTrue(result['desktop_user_checked'])

    def test_real_pty_double_carriage_return_path(self):
        result, log = self.run_guest("import sys; sys.stdout.reconfigure(newline='\\r\\n')\n"+FAKE_GUEST)
        self.assertIn(b'\r\r\n', log.read_bytes())
        self.assertTrue(desktop.analyze_log(log.read_text(), result)['passed'], result)

    def test_final_marker_does_not_hide_a_missing_component(self):
        program = FAKE_GUEST.replace('INT_DESKTOP_CHECK:terminal:PASS', 'terminal assertion missing')
        result, log = self.run_guest(program)
        self.assertTrue(result['desktop_user_checked'])
        self.assertIn('INT_CORE_ROOT_PASS', log.read_text())
        self.assertFalse(desktop.analyze_log(log.read_text(), result)['passed'])

    def test_desktop_failure_stops_before_sudo(self):
        program = FAKE_GUEST.replace('INT_DESKTOP_USER_PASS', 'INT_DESKTOP_USER_FAIL:fixture')
        result, log = self.run_guest(program)
        self.assertIsNotNone(result['protocol_error'])
        self.assertFalse(result.get('desktop_user_checked', False))
        self.assertFalse(result['sudo_password_prompt'])
        self.assertFalse(desktop.analyze_log(log.read_text(), result)['passed'])

    def test_credential_echo_during_owner_hook_is_redacted_and_rejected(self):
        marker_print = "print("+repr("\n"+'\n'.join(DESKTOP_LINES))+",flush=True)"
        program = FAKE_GUEST.replace(marker_print, 'print(password,flush=True)\n'+marker_print)
        password = 'test-only-desktop-credential'
        result, log = self.run_guest(program, password)
        self.assertTrue(result['credential_echoed'])
        self.assertNotIn(password, log.read_text())
        self.assertNotIn(password, json.dumps(result))
        self.assertFalse(desktop.analyze_log(log.read_text(), result)['passed'])


class DesktopEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.deploy = self.root/'deploy'
        self.deploy.mkdir()
        for kind, filename in desktop.INPUTS.items():
            (self.deploy/filename).write_bytes((kind+' fixture').encode())
        kernel = bytearray(4096)
        kernel[0x202:0x206] = b'HdrS'
        struct.pack_into('<H', kernel, 0x20e, 0x600)
        version = b'6.18.54-int-desktop1 (fixture)\0'
        kernel[0x800:0x800+len(version)] = version
        (self.deploy/desktop.INPUTS['kernel']).write_bytes(kernel)
        (self.deploy/desktop.INPUTS['manifest']).write_text('kernel-6.18.54-int-desktop1 qemux86_64 6.18.54\n')

    def invoke(self, log):
        def execute(_command, path, _timeout, *, on_owner):
            self.assertIs(on_owner, desktop.owner_checks)
            path.write_text(log)
            return EXIT_OK.copy()
        with mock.patch.object(desktop.core.shutil, 'which', return_value=sys.executable), \
                mock.patch.object(desktop.core.smoke, 'qemu_version', return_value='test double'), \
                mock.patch.object(desktop.core, 'execute_interactive', side_effect=execute):
            return desktop.run_desktop(self.deploy, self.root/'evidence', 2)

    def test_only_complete_desktop_evidence_creates_known_good(self):
        code, run = self.invoke(PASS_LOG)
        self.assertEqual(code, 0)
        result = json.loads((run/'result.json').read_text())
        self.assertTrue(result['checks']['desktop'])
        self.assertTrue((run/'known-good.json').exists())
        self.assertIn('desktop_runner_sha256', result['context'])
        self.assertIn('headless', result['context']['desktop_scope'])
        self.assertIn('DRM', result['context']['unqualified'])
        code, run = self.invoke(fixtures.PASS_LOG)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads((run/'result.json').read_text())['status'], 'failed')
        self.assertFalse((run/'known-good.json').exists())
        self.assertFalse((run/'artifacts').exists())

    def test_rejected_analyzer_without_a_reason_cannot_create_known_good(self):
        def execute(_command, path, _timeout):
            path.write_text(PASS_LOG)
            return EXIT_OK.copy()
        def reject(_serial, _process):
            return {'passed':False, 'checks':{name:True for name in desktop.core.CHECKS}, 'failure_reasons':[]}
        with mock.patch.object(desktop.core.shutil, 'which', return_value=sys.executable), \
                mock.patch.object(desktop.core.smoke, 'qemu_version', return_value='test double'), \
                mock.patch.object(desktop.core, 'execute_interactive', side_effect=execute):
            code, run = desktop.core.run_core(self.deploy, self.root/'evidence', 2, analyzer=reject)
        self.assertNotEqual(code, 0)
        self.assertFalse((run/'known-good.json').exists())
        result = json.loads((run/'result.json').read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertIn('guest analyzer rejected required checks', result['failure_reasons'])


class GuestCleanupTests(unittest.TestCase):
    def test_rejected_invocation_does_not_exit_an_inherited_desktop_socket(self):
        source = ROOT/'meta-int-desktop/recipes-test/int-desktop-smoke/files/int-desktop-user-check'
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            commands = temporary/'bin'
            commands.mkdir()
            # No actual desktop command or account operation can run here.
            (commands/'id').write_text('#!/bin/sh\necho 0\n')
            (commands/'swaymsg').write_text('#!/bin/sh\nprintf touched > "$DESKTOP_TEST_EVENT"\n')
            for command in commands.iterdir():
                command.chmod(0o755)
            copied = temporary/'guest-check'
            text = source.read_text()
            self.assertEqual(text.count('PATH=/usr/bin:/bin'), 1)
            copied.write_text(text.replace('PATH=/usr/bin:/bin', f'PATH={commands}:/usr/bin:/bin'))
            event = temporary/'unexpected-desktop-exit'
            result = subprocess.run(['sh', str(copied), '--run'], timeout=5,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    env={**os.environ, 'SWAYSOCK':'/existing/session.sock',
                                         'DESKTOP_TEST_EVENT':str(event)})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires an unprivileged owner', result.stdout)
            self.assertFalse(event.exists())


if __name__ == '__main__':
    unittest.main()
