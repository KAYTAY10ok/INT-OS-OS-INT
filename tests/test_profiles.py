"""Profile selection preserves the console configuration and isolates outputs."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/int'
LOADER = importlib.machinery.SourceFileLoader('int_profile_test', str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        source = self.work/'sources/openembedded-core/oe-init-build-env'
        source.parent.mkdir(parents=True)
        source.touch()

    def test_desktop_keeps_console_bytes_and_private_override_unchanged(self):
        helper.configure(self.work)
        conf = self.work/'build/conf'
        original = {path.name:path.read_bytes() for path in conf.iterdir()}
        private = conf/'int-local.conf'
        private.write_text('# operator private override\n')
        helper.configure(self.work, 'desktop')
        for name, contents in original.items():
            self.assertEqual((conf/name).read_bytes(), contents)
        self.assertEqual(private.read_text(), '# operator private override\n')
        desktop = self.work/'build-desktop/conf'
        self.assertIn('/src/meta-int-desktop', (desktop/'bblayers.conf').read_text())
        self.assertIn('require conf/distro/include/int-desktop.inc', (desktop/'local.conf').read_text())
        self.assertIn('DL_DIR = "/work/downloads"', (desktop/'local.conf').read_text())

    def test_edited_desktop_configuration_is_preserved_and_rejected(self):
        helper.configure(self.work, 'desktop')
        path = self.work/'build-desktop/conf/local.conf'
        edited = path.read_text()+'# local operator change\n'
        path.write_text(edited)
        with self.assertRaisesRegex(RuntimeError, 'Refusing to overwrite'):
            helper.configure(self.work, 'desktop')
        self.assertEqual(path.read_text(), edited)
        helper.configure(self.work)
        self.assertEqual(path.read_text(), edited)

    def test_feed_profile_preserves_core_configuration_and_is_separate(self):
        helper.configure(self.work)
        core = self.work/'build/conf/local.conf'
        original = core.read_bytes()
        helper.configure(self.work, 'feed')
        self.assertEqual(core.read_bytes(), original)
        self.assertIn('require conf/distro/include/int-feed-lab.inc',
                      (self.work/'build-feed/conf/local.conf').read_text())

    def test_container_selects_separate_build_directory_and_refuses_unknown_profile(self):
        with mock.patch.object(helper, 'docker') as docker:
            helper.container(self.work, ['bitbake', 'int-image-desktop'], profile='desktop')
        command = docker.call_args.args[0]
        script = command[command.index('-ec')+1]
        self.assertIn('oe-init-build-env /work/build-desktop', script)
        with self.assertRaisesRegex(RuntimeError, 'Unknown build profile'):
            helper.configure(self.work, '../outside')
        self.assertFalse((self.work/'outside').exists())


if __name__ == '__main__':
    unittest.main()
