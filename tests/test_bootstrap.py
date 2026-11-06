"""Exercise source checkout recovery and preservation with real local Git repos.

Only the source lock is replaced for the fixture. No network, Docker, or
user/global Git configuration is used or changed by these tests.
"""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "int"
LOADER = importlib.machinery.SourceFileLoader("int_build", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BootstrapFunctionalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self.work = self.root / "work"
        self.checkout = self.work / "sources" / "sample"
        environment = mock.patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ALLOW_PROTOCOL": "file",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.git("init", "--quiet", "--initial-branch=main", self.origin)
        (self.origin / "payload.txt").write_text("upstream fixture\n")
        self.git("add", "payload.txt", cwd=self.origin)
        self.git("-c", "user.name=INT test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture",
                 cwd=self.origin)
        self.revision = self.git("rev-parse", "HEAD", cwd=self.origin).strip()

    @staticmethod
    def git(*arguments, cwd=None):
        return subprocess.run(
            ["git", *map(str, arguments)], cwd=cwd, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout

    def bootstrap(self, url=None, revision=None):
        lock = {"sources": {"sample": {
            "url": str(self.origin) if url is None else str(url),
            "revision": self.revision if revision is None else revision,
        }}}
        with mock.patch.object(build, "LOCK", lock):
            build.bootstrap(self.work)

    def assert_fetch_failure_is_recoverable(self, **invalid_source):
        with self.assertRaises(subprocess.CalledProcessError):
            self.bootstrap(**invalid_source)
        self.assertFalse(self.checkout.exists())
        self.assertEqual(list((self.work / "sources").iterdir()), [])

        self.bootstrap()
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.checkout).strip(),
                         self.revision)
        self.assertEqual((self.checkout / "payload.txt").read_text(), "upstream fixture\n")
        self.assertEqual(self.git("status", "--porcelain", cwd=self.checkout), "")
        self.assertEqual(list((self.work / "sources").iterdir()), [self.checkout])
        self.assertEqual(self.git("status", "--porcelain", cwd=self.origin), "")

    def test_missing_local_source_leaves_no_partial_checkout_and_retry_succeeds(self):
        self.assert_fetch_failure_is_recoverable(url=self.root / "missing-origin")

    def test_invalid_revision_leaves_no_partial_checkout_and_retry_succeeds(self):
        self.assert_fetch_failure_is_recoverable(revision="0" * 40)

    def test_repeated_bootstrap_preserves_checkout_and_ignored_user_data(self):
        self.bootstrap()
        exclude = self.checkout / ".git" / "info" / "exclude"
        exclude_contents = exclude.read_text() + "\noperator-cache.dat\n"
        exclude.write_text(exclude_contents)
        cache = self.checkout / "operator-cache.dat"
        cache.write_bytes(b"operator-owned ignored data\x00\n")

        self.bootstrap()

        self.assertEqual(exclude.read_text(), exclude_contents)
        self.assertEqual(cache.read_bytes(), b"operator-owned ignored data\x00\n")
        self.assertEqual((self.checkout / "payload.txt").read_text(), "upstream fixture\n")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.checkout).strip(),
                         self.revision)
        self.assertEqual(self.git("status", "--porcelain", cwd=self.checkout), "")

    def test_user_modifications_are_refused_without_erasing_them(self):
        self.bootstrap()
        payload = self.checkout / "payload.txt"
        payload.write_text("operator-edited payload\n")
        notes = self.checkout / "operator-notes.txt"
        notes.write_text("local untracked notes\n")

        with self.assertRaisesRegex(RuntimeError, "local changes"):
            self.bootstrap()

        self.assertEqual(payload.read_text(), "operator-edited payload\n")
        self.assertEqual(notes.read_text(), "local untracked notes\n")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.checkout).strip(),
                         self.revision)
        status = self.git("status", "--porcelain", cwd=self.checkout)
        self.assertIn(" M payload.txt", status)
        self.assertIn("?? operator-notes.txt", status)
        self.assertEqual(list((self.work / "sources").iterdir()), [self.checkout])
        self.assertEqual((self.origin / "payload.txt").read_text(), "upstream fixture\n")


if __name__ == "__main__":
    unittest.main()
