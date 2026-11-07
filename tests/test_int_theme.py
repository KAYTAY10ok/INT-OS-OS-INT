"""Host tests for int-theme, its presets and the wallpaper generator."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "meta-int-desktop/recipes-desktop/int-theme/files"


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


theme = load(FILES / "int-theme", "int_theme")
ai = load(ROOT / "meta-int/recipes-ai/int-ai/files/int-ai", "int_ai_for_theme")


class ThemeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.share = self.root / "share"
        (self.share / "themes").mkdir(parents=True)
        for file in (FILES / "themes").glob("*.theme"):
            shutil.copy(file, self.share / "themes")
        (self.share / "wallpapers").mkdir()
        (self.share / "ascii").mkdir()
        shutil.copy(FILES / "int.txt", self.share / "ascii")
        self.home = self.root / "home"
        self.home.mkdir()
        self.conf = self.root / "install.conf"
        self.conf.write_text("INT_LANGUAGE=fr\nINT_XKB_LAYOUT=ch\nINT_XKB_VARIANT=fr\n")
        env = {"INT_THEME_SHARE": str(self.share), "INT_INSTALL_CONF": str(self.conf),
               "XDG_CONFIG_HOME": str(self.home / ".config"), "HOME": str(self.home)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("SWAYSOCK", "HYPRLAND_INSTANCE_SIGNATURE"):
            os.environ.pop(key, None)
        theme.SHARE = str(self.share)
        theme.INSTALL_CONF = str(self.conf)

    def cfg(self, *parts):
        return self.home.joinpath(".config", *parts)

    def test_presets_match_the_names_int_ai_may_choose(self):
        self.assertEqual(sorted(theme.presets()), sorted(ai.THEMES))
        for name in theme.presets():
            theme.load(name)  # complete and valid

    def test_set_writes_all_targets_with_preset_colours_and_keyboard(self):
        self.assertEqual(theme.main(["set", "pink"]), 0)
        self.assertEqual(theme.current(), "pink")
        sway = self.cfg("int", "theme", "sway.conf").read_text()
        self.assertIn("#ff6fb5", sway)
        self.assertIn("output * bg", sway)
        self.assertIn("status_command /usr/libexec/int-status", sway)
        self.assertIn("xkb_layout ch", self.cfg("int", "theme", "keyboard.conf").read_text())
        self.assertIn("xkb_variant fr", self.cfg("int", "theme", "keyboard.conf").read_text())
        foot = self.cfg("foot", "foot.ini").read_text()
        self.assertTrue(foot.startswith(theme.MARKER))
        self.assertIn("alpha=0.88", foot)
        self.assertIn("login-shell=yes", foot)
        self.assertIn("Chercher une application", self.cfg("fuzzel", "fuzzel.ini").read_text())
        fetch = self.cfg("fastfetch", "config.jsonc").read_text()
        self.assertIn("int.txt", fetch)
        self.assertIn("rounding = 12", self.cfg("int", "theme", "hyprland.conf").read_text())

    def test_user_owned_configs_are_never_overwritten(self):
        mine = self.cfg("foot", "foot.ini")
        mine.parent.mkdir(parents=True)
        mine.write_text("[main]\nfont=Mine:size=14\n")
        self.assertEqual(theme.main(["set", "blue"]), 0)
        self.assertEqual(mine.read_text(), "[main]\nfont=Mine:size=14\n")
        link = self.cfg("fuzzel", "fuzzel.ini")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.unlink(missing_ok=True)
        target = self.root / "elsewhere"
        target.write_text("x")
        link.symlink_to(target)
        theme.main(["set", "dark"])
        self.assertEqual(target.read_text(), "x")

    def test_unknown_theme_and_bad_usage_fail_without_writing(self):
        self.assertEqual(theme.main(["set", "../../etc"]), 2)
        self.assertEqual(theme.main(["set"]), 2)
        self.assertFalse(self.cfg("int", "theme", "current").exists())

    def test_ensure_creates_default_once(self):
        self.assertEqual(theme.main(["ensure"]), 0)
        self.assertEqual(theme.current(), "dark")
        theme.main(["set", "anime"])
        theme.main(["ensure"])
        self.assertEqual(theme.current(), "anime")

    def test_custom_wallpaper_must_be_an_image_and_is_kept(self):
        bad = self.root / "evil.png"
        bad.write_text("#!/bin/sh\n")
        self.assertEqual(theme.main(["wallpaper", str(bad)]), 2)
        good = self.root / "mine.png"
        good.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        self.assertEqual(theme.main(["wallpaper", str(good)]), 0)
        theme.main(["set", "light"])
        self.assertIn(str(self.cfg("int", "theme", "wallpaper")), self.cfg("int", "theme", "sway.conf").read_text())
        theme.main(["wallpaper", "reset"])
        self.assertIn("light.png", self.cfg("int", "theme", "sway.conf").read_text())

    def test_unsafe_keyboard_values_are_ignored(self):
        self.conf.write_text("INT_XKB_LAYOUT=ch; exec rm\n")
        theme.main(["set", "dark"])
        self.assertNotIn("exec", self.cfg("int", "theme", "keyboard.conf").read_text())

    def test_reload_uses_argv_only(self):
        source = (FILES / "int-theme").read_text()
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)
        with mock.patch.dict(os.environ, {"SWAYSOCK": "/tmp/x"}), \
                mock.patch.object(theme.shutil, "which", return_value="/usr/bin/swaymsg"), \
                mock.patch.object(theme.subprocess, "run") as run:
            theme.reload_compositor()
        self.assertEqual(run.call_args.args[0], ["swaymsg", "reload"])


class DashboardTest(unittest.TestCase):
    def test_dashboard_draws_real_values_and_quits_on_pipe_close(self):
        proc = subprocess.Popen([sys.executable, str(FILES / "int-dashboard"), "run"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first = proc.stdout.read(400)
        proc.stdout.close()
        proc.wait(timeout=10)
        self.assertIn("RAM", first)
        self.assertNotIn("Traceback", proc.stderr.read())
        source = (FILES / "int-dashboard").read_text()
        self.assertNotIn("shell=True", source)


class WallpaperTest(unittest.TestCase):
    def test_generator_writes_one_png_per_preset(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run([sys.executable, str(FILES / "int-wallpaper-gen"), str(FILES / "themes"), out, "64", "36"],
                           check=True, timeout=120)
            names = sorted(p.name for p in Path(out).iterdir())
            self.assertEqual(names, sorted(p.stem + ".png" for p in (FILES / "themes").glob("*.theme")))
            for p in Path(out).iterdir():
                self.assertTrue(p.read_bytes().startswith(b"\x89PNG"))


class SessionTest(unittest.TestCase):
    def test_sway_config_includes_theme_and_keyboard(self):
        config = (ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/sway-config").read_text()
        self.assertIn("include ~/.config/int/theme/sway.conf", config)
        self.assertIn("include ~/.config/int/theme/keyboard.conf", config)
        self.assertEqual(config.count("bar {"), 0)  # the bar now comes from the theme
        start = (ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/start-int-desktop").read_text()
        self.assertIn("int-theme ensure", start)


if __name__ == "__main__":
    unittest.main()


class SessionEngineTest(unittest.TestCase):
    SCRIPT = ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/int-session"

    def run_session(self, *args, home, path="/usr/bin:/bin"):
        env = {"HOME": str(home), "PATH": path}
        return subprocess.run(["sh", str(self.SCRIPT), *args], env=env, capture_output=True, text=True, timeout=10)

    def test_choose_engine_and_refuse_missing_hyprland(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = self.run_session("sway", home=home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((home / ".config/int/session").read_text(), "sway\n")
            result = self.run_session("hyprland", home=home)
            self.assertEqual(result.returncode, 2)
            self.assertIn("not installed", result.stderr)
            fake = home / "bin"
            fake.mkdir()
            (fake / "Hyprland").write_text("#!/bin/sh\n")
            (fake / "Hyprland").chmod(0o755)
            result = self.run_session("hyprland", home=home, path=f"{fake}:/usr/bin:/bin")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((home / ".config/int/session").read_text(), "hyprland\n")
            self.assertEqual(self.run_session("bogus", home=home).returncode, 2)

    def test_start_script_prefers_hyprland_only_for_os_int(self):
        start = (ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/start-int-desktop").read_text()
        self.assertIn("INT_EDITION=", start)
        self.assertIn("os-int", start)
        self.assertIn("Hyprland --config", start)
        self.assertIn("sway --config", start)
        hypr = (ROOT / "meta-int-desktop/recipes-desktop/int-desktop-config/files/hyprland.conf").read_text()
        self.assertIn("source = ~/.config/int/theme/hyprland.conf", hypr)
        self.assertIn("bind = $mod, I, exec, int-dashboard show", hypr)
