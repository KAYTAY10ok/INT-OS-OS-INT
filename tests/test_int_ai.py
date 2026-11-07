"""Host tests for the INT local AI super command (no model, no BitBake).

The program is loaded from the recipe's files directory. Theme, dashboard and
model interactions use fixtures; no host theme, package or account is changed.
"""
import ast
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock


FILES = Path(__file__).resolve().parents[1] / "meta-int/recipes-ai/int-ai/files"


def load(name, filename):
    loader = importlib.machinery.SourceFileLoader(name, str(FILES / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ai = load("int_ai", "int-ai")
model = load("int_ai_model", "int-ai-model")


def quiet(func, *args, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        result = func(*args, **kwargs)
    return result, out.getvalue(), err.getvalue()


class RegistryTest(unittest.TestCase):
    def test_registry_names_and_policies(self):
        self.assertEqual(set(ai.REGISTRY), {
            "theme.set", "theme.list", "theme.current", "system.status", "files.create", "files.list",
            "security.check", "packages.install", "dashboard.show", "none"})
        auto = {n for n, (_s, p, _d) in ai.REGISTRY.items() if p == ai.AUTO}
        self.assertEqual(auto, {"theme.set", "theme.list", "theme.current", "system.status", "files.list",
                                "dashboard.show", "none"})
        for name in ("files.create", "packages.install", "security.check"):
            self.assertEqual(ai.REGISTRY[name][1], ai.CONFIRM)

    def test_schema_is_strict(self):
        schema = ai.action_schema()
        self.assertEqual(len(schema["oneOf"]), len(ai.REGISTRY))
        for variant in schema["oneOf"]:
            self.assertFalse(variant["additionalProperties"])
            self.assertFalse(variant["properties"]["args"]["additionalProperties"])
            self.assertEqual(variant["required"], ["action", "args"])
        json.dumps(schema)

    def test_valid_actions(self):
        cases = [
            {"action": "theme.set", "args": {"name": "dark"}},
            {"action": "theme.list", "args": {}},
            {"action": "system.status", "args": {}},
            {"action": "files.create", "args": {"path": "~/a.txt", "content": ""}},
            {"action": "files.list", "args": {"path": "/etc"}},
            {"action": "packages.install", "args": {"name": "nmap"}},
            {"action": "dashboard.show", "args": {"style": "compact"}},
        ]
        for case in cases:
            self.assertEqual(ai.validate(case), case)
            self.assertEqual(ai.validate(json.dumps(case)), case)

    def test_refuses_unknown_and_malformed(self):
        bad = [
            "not json", "[]", "null", '"theme.set"', "{}",
            {"action": "shell.run", "args": {"cmd": "rm -rf /"}},
            {"action": "files.delete", "args": {"path": "~/x"}},
            {"action": "theme.set"},
            {"action": "theme.set", "args": {}},
            {"action": "theme.set", "args": {"name": "dark", "extra": 1}},
            {"action": "theme.set", "args": {"name": "Dark; rm -rf ~"}},
            {"action": "theme.set", "args": {"name": "$(reboot)"}},
            {"action": "theme.set", "args": {"name": "dark\n"}},
            {"action": "theme.set", "args": {"name": 5}},
            {"action": "theme.set", "args": ["dark"]},
            {"action": "theme.list", "args": {}, "confirm": True},
            {"action": ["theme.list"], "args": {}},
            {"action": "packages.install", "args": {"name": "-oX"}},
            {"action": "packages.install", "args": {"name": "a b"}},
            {"action": "files.create", "args": {"path": "~/a"}},
            {"action": "files.create", "args": {"path": "~/a\x00b", "content": ""}},
            {"action": "files.create", "args": {"path": "~/a", "content": "x" * (ai.MAX_CONTENT + 1)}},
            {"action": "files.list", "args": {"path": ""}},
        ]
        for case in bad:
            with self.subTest(case=case):
                with self.assertRaises(ai.Invalid):
                    ai.validate(case)

    def test_invalid_model_output_is_never_executed(self):
        replies = ['{"action":"shell.run","args":{"cmd":"id"}}', "Sure! I will do it.", '{"action":"theme.set"}']
        for reply in replies:
            with self.subTest(reply=reply), \
                    mock.patch.object(ai, "ask_model", return_value=reply), \
                    mock.patch.object(ai, "execute") as execute, \
                    mock.patch.object(ai, "confirm") as confirm:
                code, _out, err = quiet(ai.main, ["--engine", "model", "do", "something"])
                self.assertEqual(code, ai.REFUSED)
                self.assertIn("not executed", err)
                execute.assert_not_called()
                confirm.assert_not_called()

    def test_model_unavailable(self):
        with mock.patch.object(ai, "ask_model", side_effect=ai.ModelUnavailable("down")), \
                mock.patch.object(ai, "execute") as execute:
            code, _o, _e = quiet(ai.main, ["--engine", "model", "anything"])
        self.assertEqual(code, ai.UNAVAILABLE)
        execute.assert_not_called()

    def test_model_schema_constrains_theme_names_and_home_paths(self):
        variants = {v["properties"]["action"]["const"]: v["properties"]["args"]
                    for v in ai.action_schema()["oneOf"]}
        self.assertEqual(variants["theme.set"]["properties"]["name"]["enum"], list(ai.THEMES))
        for name in ("files.create", "files.list"):
            pattern = variants[name]["properties"]["path"]["pattern"]
            self.assertRegex("~/Documents/notes.txt", pattern)
            self.assertNotRegex("/home/user/Documents/notes.txt", pattern)
            self.assertNotRegex("Documents/notes.txt", pattern)
        # The registry used for validation keeps accepting rule-based outputs.
        self.assertNotIn("enum", ai.REGISTRY["theme.set"][0]["properties"]["name"])

    def test_theme_synonyms_map_to_canonical_names(self):
        self.assertEqual(ai.validate('{"action":"theme.set","args":{"name":"rose"}}')["args"]["name"], "pink")
        self.assertEqual(ai.validate('{"action":"theme.set","args":{"name":"sombre"}}')["args"]["name"], "dark")
        self.assertEqual(ai.validate('{"action":"theme.set","args":{"name":"anime"}}')["args"]["name"], "anime")

    def test_refused_path_is_named(self):
        with self.assertRaisesRegex(ai.PathRefused, "/etc/passwd"):
            ai.home_relative("/etc/passwd", "/home/tester")

    def test_slow_model_is_reported_as_timeout_not_absent(self):
        class SlowOpener:
            def __init__(self, exc):
                self.exc = exc

            def open(self, request, timeout):
                self.timeout = timeout
                raise self.exc

        for exc in (TimeoutError("timed out"), ai.urllib.error.URLError(TimeoutError("timed out"))):
            opener = SlowOpener(exc)
            with self.subTest(exc=exc), self.assertRaises(ai.ModelTimeout):
                ai.ask_model("x", "http://127.0.0.1:8765", timeout=7, opener=opener)
            self.assertEqual(opener.timeout, 7)
        with self.assertRaises(ai.ModelUnavailable):
            ai.ask_model("x", "http://127.0.0.1:8765",
                         opener=SlowOpener(ai.urllib.error.URLError(ConnectionRefusedError())))
        with mock.patch.object(ai, "ask_model", side_effect=ai.ModelTimeout("slow")) as ask, \
                mock.patch.object(ai, "execute") as execute:
            code, _o, err = quiet(ai.main, ["--engine", "model", "--timeout", "900", "anything"])
        self.assertEqual(code, ai.UNAVAILABLE)
        self.assertIn("900", err)
        self.assertEqual(ask.call_args.kwargs["timeout"], 900.0)
        execute.assert_not_called()

    def test_server_must_be_loopback(self):
        for url in ("http://127.0.0.1:8765", "http://localhost:1", "http://[::1]:8765"):
            ai.check_server_url(url)
        for url in ("http://10.0.0.1:8765", "https://127.0.0.1:8765", "http://example.com", "file:///etc/passwd",
                    "http://127.0.0.1.example.com:80"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ai.check_server_url(url)

    def test_model_request_is_constrained(self):
        captured = {}

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class Opener:
            def open(self, request, timeout):
                captured["url"] = request.full_url
                captured["body"] = json.loads(request.data)
                content = json.dumps({"action": "theme.list", "args": {}})
                return Response(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

        raw = ai.ask_model("liste les thèmes", "http://127.0.0.1:8765", opener=Opener())
        self.assertEqual(ai.validate(raw), {"action": "theme.list", "args": {}})
        self.assertEqual(captured["url"], "http://127.0.0.1:8765/v1/chat/completions")
        fmt = captured["body"]["response_format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertEqual(fmt["json_schema"]["schema"], ai.action_schema())
        self.assertEqual(captured["body"]["temperature"], 0)


class ConfirmationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_handle(self, action, answer=None, assume_yes=False, tty=True):
        asked = []

        def ask(prompt):
            asked.append(prompt)
            if answer is None:
                raise AssertionError("confirmation must not be asked")
            return answer

        stdin = mock.Mock()
        stdin.isatty.return_value = tty
        with mock.patch.object(ai, "execute", return_value=ai.OK) as execute:
            code, out, _err = quiet(ai.handle, ai.validate(action), assume_yes=assume_yes, home=self.home,
                                    ask=ask if tty else None, stdin=stdin)
        return code, asked, execute, out

    def test_read_and_theme_actions_run_without_confirmation(self):
        for action in ({"action": "theme.set", "args": {"name": "blue"}},
                       {"action": "theme.current", "args": {}},
                       {"action": "system.status", "args": {}},
                       {"action": "files.list", "args": {"path": "~"}},
                       {"action": "dashboard.show", "args": {"style": "default"}}):
            with self.subTest(action=action["action"]):
                code, asked, execute, _out = self.run_handle(action)
                self.assertEqual(code, ai.OK)
                self.assertEqual(asked, [])
                execute.assert_called_once()

    def confirm_actions(self):
        return ({"action": "files.create", "args": {"path": "~/n.txt", "content": "x"}},
                {"action": "packages.install", "args": {"name": "nmap"}},
                {"action": "security.check", "args": {}})

    def test_changes_need_explicit_yes(self):
        for action in self.confirm_actions():
            for answer in ("", "n", "non", "no", "yes please", "1"):
                with self.subTest(action=action["action"], answer=answer):
                    code, asked, execute, out = self.run_handle(action, answer=answer)
                    self.assertEqual(code, ai.NOT_CONFIRMED)
                    self.assertEqual(len(asked), 1)
                    execute.assert_not_called()
            for answer in ("o", "oui", "y", "YES", " Oui "):
                with self.subTest(action=action["action"], answer=answer):
                    code, asked, execute, out = self.run_handle(action, answer=answer)
                    self.assertEqual(code, ai.OK)
                    execute.assert_called_once()

    def test_prompt_shows_exact_action(self):
        action = {"action": "files.create", "args": {"path": "~/n.txt", "content": "bonjour"}}
        _code, _asked, _execute, out = self.run_handle(action, answer="n")
        shown = {"action": "files.create", "args": {"path": os.path.join(self.home, "n.txt"), "content": "bonjour"}}
        self.assertIn(json.dumps(shown, ensure_ascii=False, sort_keys=True), out)

    def test_yes_flag_cannot_bypass(self):
        for action in self.confirm_actions():
            with self.subTest(action=action["action"]):
                code, asked, execute, out = self.run_handle(action, answer="n", assume_yes=True)
                self.assertEqual(code, ai.NOT_CONFIRMED)
                self.assertEqual(len(asked), 1)
                self.assertIn("--yes", out)
                execute.assert_not_called()
                code, asked, execute, _out = self.run_handle(action, assume_yes=True, tty=False)
                self.assertEqual(code, ai.NOT_CONFIRMED)
                execute.assert_not_called()

    def test_yes_flag_through_main_without_terminal(self):
        with mock.patch.object(ai, "execute") as execute, \
                mock.patch.object(sys, "stdin", io.StringIO("o\n")):
            code, out, _e = quiet(ai.main, ["--yes", "--action",
                                            '{"action":"packages.install","args":{"name":"nmap"}}'])
        self.assertEqual(code, ai.NOT_CONFIRMED)
        execute.assert_not_called()

    def test_package_install_refuses_after_confirmation(self):
        code, _o, err = quiet(ai.execute, {"action": "packages.install", "args": {"name": "nmap"}})
        self.assertEqual(code, ai.UNAVAILABLE)
        self.assertTrue("feed" in err or "dépôt" in err)


class PathConfinementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = os.path.realpath(self.tmp.name)
        self.home = os.path.join(root, "home")
        self.outside = os.path.join(root, "outside")
        os.makedirs(os.path.join(self.home, "docs"))
        os.makedirs(self.outside)

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_new_file_in_home(self):
        for path, rel in (("~/a.txt", "a.txt"), ("b.txt", "b.txt"), ("docs/c.txt", "docs/c.txt"),
                          (os.path.join(self.home, "docs", "d.txt"), "docs/d.txt"), ("./docs//e.txt", "docs/e.txt")):
            with self.subTest(path=path):
                created = ai.create_in_home(path, "salut", self.home)
                self.assertEqual(created, os.path.join(self.home, rel))
                with open(created, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "salut")

    def test_refusals(self):
        refused = ["../outside/x", "~/../outside/x", "docs/../../outside/x", "~root/x", "~", "/", "",
                   os.path.join(self.outside, "x"), "/etc/passwd", self.home, self.home + "2/x",
                   "missing/dir/x"]
        for path in refused:
            with self.subTest(path=path), self.assertRaises(ai.PathRefused):
                ai.create_in_home(path, "x", self.home)
        self.assertEqual(os.listdir(self.outside), [])

    def test_symlink_escape_refused(self):
        os.symlink(self.outside, os.path.join(self.home, "link"))
        os.symlink(os.path.join(self.outside, "target"), os.path.join(self.home, "dangling"))
        for path in ("link/x", "~/link/x", "dangling", "link"):
            with self.subTest(path=path), self.assertRaises(ai.PathRefused):
                ai.create_in_home(path, "x", self.home)
        self.assertEqual(os.listdir(self.outside), [])

    def test_never_overwrites(self):
        existing = os.path.join(self.home, "keep.txt")
        with open(existing, "w") as handle:
            handle.write("old")
        with self.assertRaises(ai.PathRefused):
            ai.create_in_home("keep.txt", "new", self.home)
        with open(existing) as handle:
            self.assertEqual(handle.read(), "old")

    def test_symlinked_home_is_accepted(self):
        alias = os.path.join(os.path.dirname(self.home), "alias")
        os.symlink(self.home, alias)
        created = ai.create_in_home(os.path.join(alias, "f.txt"), "", alias)
        self.assertEqual(created, os.path.join(self.home, "f.txt"))

    def test_files_create_refused_as_root(self):
        with mock.patch.object(ai.os, "geteuid", return_value=0):
            code, _o, _e = quiet(ai.execute, {"action": "files.create", "args": {"path": "a", "content": ""}},
                                 home=self.home)
        self.assertEqual(code, ai.REFUSED)
        self.assertFalse(os.path.exists(os.path.join(self.home, "a")))

    def test_prepare_refuses_before_confirmation(self):
        action = ai.validate({"action": "files.create", "args": {"path": "../x", "content": ""}})
        with mock.patch.object(ai, "confirm") as confirm:
            code, _o, _e = quiet(ai.handle, action, home=self.home)
        self.assertEqual(code, ai.REFUSED)
        confirm.assert_not_called()


class FallbackParserTest(unittest.TestCase):
    CASES = {
        "mets le thème bleu": ("theme.set", {"name": "blue"}),
        "Passe en thème sombre.": ("theme.set", {"name": "dark"}),
        "thème rose": ("theme.set", {"name": "pink"}),
        "passe en mode sombre": ("theme.set", {"name": "dark"}),
        "s'il te plaît, mets le thème anime": ("theme.set", {"name": "anime"}),
        "set theme to dark": ("theme.set", {"name": "dark"}),
        "switch to the pink theme": ("theme.set", {"name": "pink"}),
        "use the anime theme please": ("theme.set", {"name": "anime"}),
        "quels thèmes": ("theme.list", {}),
        "liste des thèmes": ("theme.list", {}),
        "list themes": ("theme.list", {}),
        "thème actuel": ("theme.current", {}),
        "quel est le thème actuel ?": ("theme.current", {}),
        "what is the current theme?": ("theme.current", {}),
        "état du système": ("system.status", {}),
        "system status": ("system.status", {}),
        "températures": ("system.status", {}),
        "utilisation de la mémoire": ("system.status", {}),
        "vérifie la sécurité": ("security.check", {}),
        "analyse d'intégrité du système": ("security.check", {}),
        "security check": ("security.check", {}),
        "check system integrity": ("security.check", {}),
        "installe le paquet nmap": ("packages.install", {"name": "nmap"}),
        "install firefox": ("packages.install", {"name": "firefox"}),
        "affiche le tableau de bord": ("dashboard.show", {"style": "default"}),
        "show the dashboard in compact style": ("dashboard.show", {"style": "compact"}),
        "liste mes fichiers": ("files.list", {"path": "~"}),
        "list my files": ("files.list", {"path": "~"}),
        "liste le dossier ~/Documents": ("files.list", {"path": "~/Documents"}),
        "list files in /etc": ("files.list", {"path": "/etc"}),
        "ls ~/Images": ("files.list", {"path": "~/Images"}),
        "crée un fichier notes.txt avec bonjour tout le monde": (
            "files.create", {"path": "notes.txt", "content": "bonjour tout le monde"}),
        "crée le fichier ~/todo.md": ("files.create", {"path": "~/todo.md", "content": ""}),
        'create a file ~/a.txt containing "hello world"': (
            "files.create", {"path": "~/a.txt", "content": "hello world"}),
    }

    def test_phrasings(self):
        for text, (name, args) in self.CASES.items():
            with self.subTest(text=text):
                action = ai.parse_rules(text)
                self.assertEqual(action, {"action": name, "args": args})
                ai.validate(action)

    def test_unknown_requests(self):
        for text in ("fais moi un café", "rm -rf /", "bonjour", "what time is it", "thème", "supprime tout"):
            with self.subTest(text=text):
                self.assertIsNone(ai.parse_rules(text))

    def test_rules_engine_does_nothing_on_unknown(self):
        with mock.patch.object(ai, "execute", wraps=ai.execute) as execute, \
                mock.patch.object(ai, "ask_model") as ask_model:
            code, _o, err = quiet(ai.main, ["--engine", "rules", "supprime", "tout"])
        self.assertEqual(code, ai.REFUSED)
        ask_model.assert_not_called()
        execute.assert_called_once()
        self.assertTrue("nothing" in err or "rien" in err)

    def test_dry_run(self):
        with mock.patch.object(ai, "execute") as execute:
            code, out, _e = quiet(ai.main, ["--dry-run", "installe", "nmap"])
        self.assertEqual(code, ai.OK)
        execute.assert_not_called()
        self.assertIn('"packages.install"', out)


class ExternalCommandTest(unittest.TestCase):
    def test_missing_theme_command_reported(self):
        with mock.patch.object(ai.shutil, "which", return_value=None):
            code, _o, err = quiet(ai.execute, {"action": "theme.set", "args": {"name": "dark"}})
        self.assertEqual(code, ai.UNAVAILABLE)
        self.assertIn("int-theme", err)

    def test_missing_dashboard_reported(self):
        with mock.patch.object(ai.shutil, "which", return_value=None):
            code, _o, err = quiet(ai.execute, {"action": "dashboard.show", "args": {"style": "default"}})
        self.assertEqual(code, ai.UNAVAILABLE)
        self.assertIn("int-dashboard", err)

    def test_theme_argv(self):
        result = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(ai.shutil, "which", return_value="/usr/bin/int-theme"), \
                mock.patch.object(ai.subprocess, "run", return_value=result) as run:
            code, _o, _e = quiet(ai.execute, {"action": "theme.set", "args": {"name": "blue"}})
        self.assertEqual(code, ai.OK)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/usr/bin/int-theme", "set", "blue"])
        self.assertFalse(kwargs["shell"])

    def test_run_argv_rejects_strings(self):
        with self.assertRaises(TypeError):
            ai.run_argv("int-theme list")


class SystemAndSecurityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text="", mode=0o644):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        os.chmod(path, mode)
        return path

    def test_system_status_from_fixtures(self):
        self.write("proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
        self.write("proc/loadavg", "0.10 0.20 0.30 1/100 42\n")
        self.write("proc/meminfo", "MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 400 kB\n")
        self.write("sys/class/thermal/thermal_zone0/type", "x86_pkg_temp\n")
        self.write("sys/class/thermal/thermal_zone0/temp", "45000\n")
        self.write("sys/class/hwmon/hwmon0/name", "k10temp\n")
        self.write("sys/class/hwmon/hwmon0/temp1_input", "51500\n")
        self.write("sys/class/hwmon/hwmon0/temp1_label", "Tctl\n")
        status = ai.system_status(os.path.join(self.root, "proc"), os.path.join(self.root, "sys"),
                                  disks=(self.root,), interval=0)
        self.assertEqual(status["memory"], {"total": 1024000, "used": 614400})
        self.assertEqual(status["load"], ["0.10", "0.20", "0.30"])
        self.assertEqual(status["temperatures"], {"x86_pkg_temp": 45.0, "k10temp/Tctl": 51.5})
        self.assertIn(self.root, status["disk"])
        quiet(ai.print_status, status)

    def test_security_check_reports_only(self):
        uid = os.getuid()
        self.write("etc/passwd", "root:x:0:0::/root:/bin/sh\n", 0o644)
        self.write("etc/group", "", 0o644)
        self.write("etc/shadow", "", 0o604)
        self.write("etc/sudoers", "", 0o440)
        self.write("etc/sudoers.d/owner", "", 0o666)
        tool = self.write("usr/bin/tool", "", 0o4755)
        self.write("usr/bin/plain", "", 0o755)
        self.write("tmp/dropper", "", 0o755)
        self.write("tmp/notes", "", 0o644)
        baseline = self.write("baseline", "", 0o644)
        before = {p: os.stat(p).st_mode for p in (tool, baseline)}

        report = ai.security_check(self.root, baseline, tmp_dirs=("/tmp",), setuid_dirs=("/usr/bin",))
        messages = {(f["path"], f["level"]) for f in report["findings"]}
        self.assertEqual(report["setuid"], ["/usr/bin/tool"])
        self.assertIn(("/usr/bin/tool", "critical"), messages)
        self.assertIn(("/etc/shadow", "critical"), messages)
        self.assertIn(("/etc/sudoers.d/owner", "critical"), messages)
        self.assertIn(("/tmp/dropper", "warning"), messages)
        self.assertNotIn(("/tmp/notes", "warning"), messages)
        if uid != 0:
            self.assertIn(("/etc/passwd", "critical"), messages)  # fixture is not owned by root
        self.assertEqual({p: os.stat(p).st_mode for p in (tool, baseline)}, before)

        with open(baseline, "w") as handle:
            handle.write("/usr/bin/tool\n/usr/bin/gone\n")
        report = ai.security_check(self.root, baseline, tmp_dirs=(), setuid_dirs=("/usr/bin",))
        messages = {(f["path"], f["level"]) for f in report["findings"]}
        self.assertNotIn(("/usr/bin/tool", "critical"), messages)
        self.assertIn(("/usr/bin/gone", "info"), messages)

    def test_symlinked_sensitive_file_is_flagged(self):
        self.write("real", "")
        os.makedirs(os.path.join(self.root, "etc"))
        os.symlink(os.path.join(self.root, "real"), os.path.join(self.root, "etc/shadow"))
        findings = ai._check_mode(self.root, "/etc/shadow", 0o077)
        self.assertEqual(findings[0]["message"], "is a symbolic link")


class ModelToolTest(unittest.TestCase):
    def test_pinned_models(self):
        for size, entry in model.MODELS.items():
            with self.subTest(size=size):
                self.assertRegex(entry["revision"], r"^[0-9a-f]{40}$")
                self.assertTrue(entry["files"])
                for name, digest, length in entry["files"]:
                    self.assertRegex(name, r"^[a-z0-9._-]+\.gguf$")
                    self.assertRegex(digest, r"^[0-9a-f]{64}$")
                    self.assertGreater(length, 100 * 1024 * 1024)
        self.assertEqual(model.MODELS["1.5b"]["license"], "Apache-2.0")
        self.assertEqual(model.MODELS["7b"]["license"], "Apache-2.0")
        self.assertNotEqual(model.MODELS["3b"]["license"], "Apache-2.0")
        self.assertTrue(model.MODELS["3b"]["needs_acceptance"])

    def test_urls_are_pinned_https(self):
        url = model.file_url("1.5b", model.MODELS["1.5b"]["files"][0][0])
        self.assertTrue(url.startswith("https://huggingface.co/"))
        self.assertIn(model.MODELS["1.5b"]["revision"], url)

    def test_verify_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.gguf")
            data = b"GGUF" + b"\0" * 100
            with open(path, "wb") as handle:
                handle.write(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertTrue(model.verify_file(path, digest, 104))
            self.assertFalse(model.verify_file(path, digest, 105))
            self.assertFalse(model.verify_file(path, "0" * 64, 104))
            os.symlink(path, os.path.join(tmp, "link.gguf"))
            self.assertFalse(model.verify_file(os.path.join(tmp, "link.gguf"), digest, 104))

    def test_recommendation_by_ram(self):
        gib = 1024 ** 3
        self.assertEqual(model.recommend(2 * gib), "none")
        self.assertEqual(model.recommend(6 * gib), "1.5b")
        self.assertEqual(model.recommend(32 * gib), "7b")

    def test_research_licence_requires_acceptance(self):
        with mock.patch.object(model, "download") as download:
            code, _o, err = quiet(model.main, ["install", "3b"])
        self.assertNotEqual(code, 0)
        download.assert_not_called()
        self.assertIn("licen", err.lower())

    def test_serve_argv_loopback_only(self):
        argv = model.server_argv("/var/lib/int-ai/models/x.gguf", threads=4)
        self.assertEqual(argv[0], "/usr/bin/llama-server")
        self.assertEqual(argv[argv.index("--host") + 1], "127.0.0.1")
        self.assertNotIn("--tools", argv)
        self.assertIn("--no-webui", argv)


class NoShellTest(unittest.TestCase):
    SOURCES = ("int-ai", "int-ai-model")

    def test_no_shell_execution(self):
        forbidden_calls = {("os", "system"), ("os", "popen"), ("subprocess", "getoutput"),
                           ("subprocess", "getstatusoutput"), ("os", "execlp"), ("os", "execvp"),
                           ("os", "spawnlp"), ("os", "spawnvp")}
        for source in self.SOURCES:
            text = (FILES / source).read_text(encoding="utf-8")
            self.assertNotIn("shell=True", text.replace(" ", ""))
            self.assertNotIn("os.system", text)
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                        self.assertNotIn((func.value.id, func.attr), forbidden_calls, source)
                    if isinstance(func, ast.Name):
                        self.assertNotIn(func.id, ("eval", "exec"), source)
                    for keyword in node.keywords:
                        if keyword.arg == "shell":
                            self.assertIsInstance(keyword.value, ast.Constant, source)
                            self.assertIs(keyword.value.value, False, source)


class PackagingTest(unittest.TestCase):
    RECIPE_DIR = FILES.parent

    def test_service_is_loopback_unprivileged_and_disabled(self):
        unit = (FILES / "int-ai.service").read_text()
        self.assertIn("User=int-ai", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertNotIn("0.0.0.0", unit)
        recipe = next(self.RECIPE_DIR.glob("int-ai_*.bb")).read_text()
        self.assertIn('SYSTEMD_AUTO_ENABLE:${PN} = "disable"', recipe)
        self.assertIn("useradd", recipe)

    def test_llama_cpp_recipe_pinned_cpu_only(self):
        recipes = list((self.RECIPE_DIR.parent / "llama-cpp").glob("llama-cpp_*.bb"))
        self.assertEqual(len(recipes), 1)
        text = recipes[0].read_text()
        self.assertRegex(text, r'SRCREV = "[0-9a-f]{40}"')
        for flag in ("-DGGML_CUDA=OFF", "-DGGML_VULKAN=OFF", "-DGGML_NATIVE=OFF", "-DLLAMA_USE_PREBUILT_UI=OFF",
                     "-DLLAMA_BUILD_UI=OFF", "-DLLAMA_SUBPROCESS=OFF", "-DLLAMA_OPENSSL=OFF"):
            self.assertIn(flag, text)


if __name__ == "__main__":
    unittest.main()
