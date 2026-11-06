"""Host-only tests for the signed-feed QEMU runner's strict result parsing.

These tests use synthetic serial logs. They do not boot a guest, run DNF or
verify any signature; only a real QEMU run can do that.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qemu_feed_check", ROOT / "scripts/qemu-feed-check.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
GUEST = ROOT / "meta-int/recipes-test/int-feed-smoke/files/int-feed-smoke"
FPR = "0123456789ABCDEF0123456789ABCDEF01234567"
OK = {"returncode": 0, "timed_out": False, "interrupted_signal": None}


def log(case, checks=None, final=True, extra=()):
    lines = [f"INT_FEED_BEGIN:{case}"]
    lines += [f"INT_FEED_CHECK:{name}:PASS" for name in (checks or runner.expected_checks(case))]
    lines += list(extra)
    if final:
        lines.append(f"INT_FEED_CASE:{case}:PASS")
    lines.append("[   12.0] reboot: Power down")
    return "\n".join(lines) + "\n"


class AnalyzeTests(unittest.TestCase):
    def test_complete_valid_and_negative_logs_pass(self):
        for case in runner.CASES:
            with self.subTest(case=case):
                self.assertTrue(runner.analyze_log(log(case), OK, case)["passed"])

    def test_negative_case_cannot_pass_with_valid_checks(self):
        result = runner.analyze_log(log("unsigned-rpm", runner.VALID), OK, "unsigned-rpm")
        self.assertFalse(result["passed"])

    def test_missing_reordered_or_duplicate_checks_fail(self):
        checks = list(runner.NEGATIVE)
        for variant in (checks[:-1], checks[::-1], checks + [checks[0]]):
            with self.subTest(variant=variant):
                self.assertFalse(runner.analyze_log(log("altered-repomd", variant), OK, "altered-repomd")["passed"])

    def test_failure_markers_process_status_and_shutdown_are_required(self):
        case = "valid"
        self.assertFalse(runner.analyze_log(log(case, final=False), OK, case)["passed"])
        self.assertFalse(runner.analyze_log(log(case, extra=["INT_FEED_FAIL:x"]), OK, case)["passed"])
        self.assertFalse(runner.analyze_log(log(case).replace("reboot: Power down", ""), OK, case)["passed"])
        for process in ({**OK, "returncode": 1}, {**OK, "timed_out": True}, {**OK, "interrupted_signal": 15}):
            self.assertFalse(runner.analyze_log(log(case), process, case)["passed"])
        other = log("altered-repomd").replace("altered-repomd", "valid", 1)
        self.assertFalse(runner.analyze_log(other, OK, "altered-repomd")["passed"])

    def test_wrong_case_pass_line_is_rejected(self):
        text = log("valid").replace("INT_FEED_CASE:valid:PASS", "INT_FEED_CASE:unsigned-rpm:PASS")
        self.assertFalse(runner.analyze_log(text, OK, "valid")["passed"])


class CommandTests(unittest.TestCase):
    def test_qemu_has_no_network_and_readonly_fixture(self):
        artifacts = {"kernel": {"snapshot": "/k"}, "rootfs": {"snapshot": "/r.ext4"}}
        command = runner.build_qemu_command("qemu", artifacts, Path("/f,eed.ext4"), "valid", FPR)
        self.assertIn("none", command[command.index("-nic") + 1])
        self.assertNotIn("-netdev", command)
        self.assertIn("file=/f,,eed.ext4,format=raw,if=virtio,readonly=on", command)
        self.assertIn("file=/r.ext4,format=raw,if=virtio,snapshot=on", command)
        self.assertIn(f"int.feed_fpr={FPR}", command[command.index("-append") + 1])

    def test_feed_disk_requires_report_and_independent_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            feed = Path(temporary)
            (feed / "feed.ext4").write_bytes(b"disk")
            digest = runner.smoke.sha256(feed / "feed.ext4")
            (feed / "report.json").write_text(json.dumps({"image": {"sha256": digest}}))
            self.assertEqual(digest, runner.check_feed_disk(feed, digest)["sha256"])
            with self.assertRaisesRegex(ValueError, "independently"):
                runner.check_feed_disk(feed, "0" * 64)
            (feed / "feed.ext4").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "report.json"):
                runner.check_feed_disk(feed, digest)

    def test_arguments_are_validated(self):
        for extra in (["--fingerprint", FPR.lower(), "--feed-sha256", "0" * 64],
                      ["--fingerprint", FPR, "--feed-sha256", "0" * 63]):
            with self.subTest(extra=extra), self.assertRaises(SystemExit), \
                    mock.patch("sys.stderr"):
                runner.main(["/d", "/f", "/e", *extra])


class GuestConsistencyTests(unittest.TestCase):
    def test_guest_and_runner_agree_on_cases_and_checks(self):
        source = GUEST.read_text()
        for case in runner.CASES[1:]:
            self.assertIn(f'"{case}":', source)
        for name in set(runner.VALID + runner.NEGATIVE):
            if name.startswith("installed-"):
                self.assertIn('check(f"installed-{label}")', source)
            else:
                self.assertIn(f'"{name}"', source)
        self.assertNotIn("--nogpgcheck\"]", source)
        for option in ("gpgcheck=1", "repo_gpgcheck=1", "localpkg_gpgcheck=1", "skip_if_unavailable=0"):
            self.assertIn(option, source)


if __name__ == "__main__":
    unittest.main()
