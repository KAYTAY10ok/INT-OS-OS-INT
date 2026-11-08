"""Host tests for int-apps (application presets) with a fake rpm/dnf."""
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "meta-int/recipes-core/int-apps/files"
LIVE = ROOT / "meta-int/dynamic-layers/int-desktop/recipes-core/images/int-image-live.bb"


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


apps = load(FILES / "int-apps", "int_apps")
ai = load(ROOT / "meta-int/recipes-ai/int-ai/files/int-ai", "int_ai_for_apps")

FAKE_RPM = """#!/bin/sh
db="$INT_FAKE_DB"
echo "rpm $*" >> "$INT_FAKE_LOG"
if [ "$1" = -q ]; then grep -qx "$4" "$db"; exit $?; fi
if [ "$1" = -e ]; then
    shift 2
    [ -n "${INT_FAKE_RPM_FAIL:-}" ] && exit 1
    for p in "$@"; do grep -vx "$p" "$db" > "$db.new"; mv "$db.new" "$db"; done
    exit 0
fi
exit 2
"""
FAKE_DNF = """#!/bin/sh
echo "dnf $*" >> "$INT_FAKE_LOG"
shift 3
for p in "$@"; do echo "$p" >> "$INT_FAKE_DB"; done
"""


def all_media_packages():
    names = set()
    for p in apps.presets():
        if p["source"] == "media":
            names.update(p["packages"])
    return names


class AppsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name, body in (("rpm", FAKE_RPM), ("dnf", FAKE_DNF)):
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        self.db = self.root / "db"
        self.log = self.root / "log"
        self.log.write_text("")
        (self.root / "rpmdb").mkdir()
        (self.root / "rpmdb" / "rpmdb.sqlite").write_text("x")
        (self.root / "repos").mkdir()
        self.conf = self.root / "install.conf"
        self.conf.write_text("INT_EDITION=int-os\nINT_LANGUAGE=en\n")
        env = {"PATH": "%s:/usr/bin:/bin" % bin_dir, "INT_FAKE_DB": str(self.db), "INT_FAKE_LOG": str(self.log),
               "XDG_CONFIG_HOME": str(self.root / "config"), "LANG": "C"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("INT_FAKE_RPM_FAIL", None)
        for attr, value in (("SHARE", str(FILES / "presets")), ("INSTALL_CONF", str(self.conf)),
                            ("RPM_DB", str(self.root / "rpmdb")), ("REPOS_DIR", str(self.root / "repos"))):
            p = mock.patch.object(apps, attr, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(apps.os, "geteuid", return_value=0)
        p.start()
        self.addCleanup(p.stop)
        # As shipped on the ISO: every media preset plus the OS-INT packagegroup.
        self.db.write_text("\n".join(sorted(all_media_packages() | {"packagegroup-int-osint", "cryptsetup"})) + "\n")

    def db_set(self):
        return set(self.db.read_text().split())

    def run_main(self, *argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            code = apps.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_presets_parse_and_media_packages_are_on_the_iso(self):
        presets = apps.presets()
        names = [p["name"] for p in presets]
        self.assertEqual(names[:6], ["cyber", "opsec", "terminal", "desktop-tools", "audio", "dev"])
        self.assertEqual(sorted(names), sorted(ai.APP_PRESETS))
        live = LIVE.read_text()
        listed = set(re.search(r'INT_APP_PRESET_PACKAGES = "(.*?)"', live, re.S).group(1).replace("\\", " ").split())
        osint = (ROOT / "meta-int/recipes-core/packagegroups/packagegroup-int-osint.bb").read_text()
        for p in presets:
            if p["source"] != "media":
                continue
            for pkg in p["packages"]:
                self.assertTrue(pkg in listed or re.search(r"\b%s\b" % re.escape(pkg), osint), pkg)
        self.assertIn("package-management", live)
        self.assertIn("int-apps", live)

    def test_list_shows_states(self):
        code, out, _ = self.run_main("list")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"cyber\s+installed\s+ISO")
        self.assertRegex(out, r"web\s+not installed\s+feed")

    def test_remove_keeps_shared_and_protected_packages(self):
        code, out, _ = self.run_main("remove", "cyber", "--yes")
        self.assertEqual(code, 0, out)
        db = self.db_set()
        self.assertNotIn("nmap", db)
        self.assertNotIn("packagegroup-int-osint", db)
        self.assertIn("tor", db)
        self.assertIn("cryptsetup", db)
        code, _, _ = self.run_main("remove", "opsec", "--yes")
        self.assertIn("cryptsetup", self.db_set())  # disk encryption is never removed
        self.assertNotIn("tor", self.db_set())

    def test_add_feed_preset_without_feed_installs_nothing(self):
        code, _, err = self.run_main("add", "web", "--yes")
        self.assertEqual(code, apps.UNAVAILABLE)
        self.assertIn("feed is not configured", err)
        self.assertNotIn("dnf", self.log.read_text())

    def test_add_with_configured_feed_uses_dnf_argv(self):
        (self.root / "repos" / "int.repo").write_text("[int]\nbaseurl=https://feed.example/int\ngpgcheck=1\n")
        code, _, _ = self.run_main("add", "multimedia", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("dnf install --assumeyes -- mpv ffmpeg", self.log.read_text())

    def test_changes_need_confirmation(self):
        code, out, _ = self.run_main("remove", "dev", stdin="n\n")
        self.assertEqual(code, apps.NOT_CONFIRMED)  # no terminal: refused
        self.assertIn("git", self.db_set())

    def test_unknown_or_bad_names_are_refused(self):
        self.assertEqual(self.run_main("add", "../../etc", "--yes")[0], apps.USAGE)
        self.assertEqual(self.run_main("remove", "nope", "--yes")[0], apps.USAGE)
        self.assertEqual(self.run_main("frobnicate")[0], apps.USAGE)

    def test_bad_package_name_in_preset_is_rejected(self):
        with self.assertRaises(apps.PresetError):
            apps.parse_preset("x", "title_fr=a\ntitle_en=a\nsummary_fr=a\nsummary_en=a\nsource=media\n"
                                   "packages=ok; rm -rf /\n")

    def test_choose_defaults_by_edition(self):
        with mock.patch.object(apps, "confirm", return_value=True):
            out = io.StringIO()
            with mock.patch.object(sys, "stdout", out):
                code = apps.choose(apps.presets(), True, answer="")
        self.assertEqual(code, 0)
        db = self.db_set()
        # INT-OS default keeps only the desktop tools.
        self.assertIn("grim", db)
        self.assertIn("int-audio", db)
        for gone in ("nmap", "tor", "htop", "git"):
            self.assertNotIn(gone, db)
        self.assertIn("cryptsetup", db)

    def test_choose_os_int_defaults_keep_cyber_and_opsec(self):
        self.conf.write_text("INT_EDITION=os-int\nINT_LANGUAGE=fr\n")
        out = io.StringIO()
        with mock.patch.object(sys, "stdout", out):
            code = apps.choose(apps.presets(), True, answer="")
        self.assertEqual(code, 0)
        db = self.db_set()
        for kept in ("nmap", "tor", "htop", "grim", "packagegroup-int-osint"):
            self.assertIn(kept, db)
        self.assertNotIn("gdb", db)
        self.assertIn("Choisis", out.getvalue())

    def test_choose_explicit_numbers_and_invalid(self):
        out = io.StringIO()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(apps.choose(apps.presets(), True, answer="99"), apps.USAGE)
            self.assertEqual(apps.choose(apps.presets(), True, answer="6"), 0)
        db = self.db_set()
        self.assertIn("gdb", db)
        self.assertNotIn("grim", db)

    def test_failed_rpm_transaction_reports_failure(self):
        os.environ["INT_FAKE_RPM_FAIL"] = "1"
        code, _, err = self.run_main("remove", "terminal", "--yes")
        self.assertEqual(code, apps.FAILED)
        self.assertIn("nothing was removed", err)

    def test_live_session_changes_nothing(self):
        (self.root / "rpmdb" / "rpmdb.sqlite").unlink()
        code, _, err = self.run_main("remove", "dev", "--yes")
        self.assertEqual(code, apps.UNAVAILABLE)
        self.assertIn("git", self.db_set())

    def test_firstrun_only_on_installed_system_with_terminal(self):
        self.conf.unlink()
        self.assertEqual(self.run_main("firstrun")[0], 0)
        self.assertEqual(self.log.read_text(), "")
        source = (FILES / "int-apps").read_text()
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)

    def test_session_hooks(self):
        start = (ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/start-int-desktop").read_text()
        self.assertIn("int-apps firstrun", start)
        self.assertIn("Moteur du bureau", start)  # engine asked once when Hyprland exists
        self.assertLess(start.index("int-apps firstrun"), start.index("Moteur du bureau"))
        tools = ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/int-desktop-tools"
        result = subprocess.run(["/bin/sh", str(tools), "screenshot"], env={"PATH": "/nonexistent", "HOME": "/tmp"},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)  # tool not chosen: does nothing
        self.assertEqual(subprocess.run(["/bin/sh", str(tools)], capture_output=True, timeout=10).returncode, 2)


if __name__ == "__main__":
    unittest.main()


class AutostartTest(unittest.TestCase):
    SESSION = ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/int-session"
    PROFILE = ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/int-autostart.sh"

    def test_autostart_toggle_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"HOME": tmp, "PATH": "/usr/bin:/bin"}
            off = subprocess.run(["/bin/sh", str(self.SESSION), "autostart", "off"], env=env, capture_output=True, text=True)
            self.assertEqual(off.returncode, 0, off.stderr)
            self.assertTrue((Path(tmp) / ".config/int/no-autostart").exists())
            subprocess.run(["/bin/sh", str(self.SESSION), "autostart", "on"], env=env, check=True, capture_output=True)
            self.assertFalse((Path(tmp) / ".config/int/no-autostart").exists())
            self.assertEqual(subprocess.run(["/bin/sh", str(self.SESSION), "autostart", "maybe"], env=env,
                                            capture_output=True).returncode, 2)
        text = self.PROFILE.read_text()
        for guard in ("/dev/tty1", "/etc/int/install.conf", "WAYLAND_DISPLAY", "no-autostart", "INT_AUTOSTARTED"):
            self.assertIn(guard, text)
        self.assertNotIn("exec start-int-desktop", text)  # a failure must leave a usable console
        # Sourced by a non-interactive shell: does nothing.
        result = subprocess.run(["/bin/sh", "-c", ". %s; echo alive" % self.PROFILE], capture_output=True, text=True,
                                env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})
        self.assertEqual(result.stdout.strip(), "alive")


class VolumeTest(unittest.TestCase):
    def test_status_bar_shows_volume_from_wpctl(self):
        script = ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/int-status"
        status = load(script, "int_status_volume")
        fake = mock.Mock(stdout="Volume: 0.40 [MUTED]\n")
        with mock.patch.object(status.shutil, "which", return_value="/usr/bin/wpctl"), \
                mock.patch.object(status.subprocess, "run", return_value=fake) as run:
            self.assertEqual(status.volume(), (40, True))
        self.assertEqual(run.call_args.args[0], ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        with mock.patch.object(status.shutil, "which", return_value=None):
            self.assertIsNone(status.volume())

    def test_volume_keys_are_bound_in_both_sessions(self):
        files = ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files"
        for name in ("sway-config", "hyprland.conf"):
            text = (files / name).read_text()
            for key in ("XF86AudioRaiseVolume", "XF86AudioLowerVolume", "XF86AudioMute"):
                self.assertIn(key, text)
        tools = files / "int-desktop-tools"
        result = subprocess.run(["/bin/sh", str(tools), "volume", "up"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)  # no wpctl on the host: does nothing
