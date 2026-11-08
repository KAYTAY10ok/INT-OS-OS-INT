"""Profile selection preserves the console configuration and isolates outputs."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
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
        for profile in ('desktop', 'feed'):
            with self.subTest(profile=profile), mock.patch.object(helper, 'docker') as docker:
                helper.container(self.work, ['bitbake', 'example'], profile=profile)
                command = docker.call_args.args[0]
                script = command[command.index('-ec')+1]
                self.assertIn(f'oe-init-build-env /work/build-{profile}', script)
        with self.assertRaisesRegex(RuntimeError, 'Unknown build profile'):
            helper.configure(self.work, '../outside')
        self.assertFalse((self.work/'outside').exists())

    def test_feed_build_selects_native_rpm_or_explicit_target(self):
        for target, expected in ((None, 'rpm-native'), ('example', 'example')):
            with self.subTest(target=target), mock.patch.object(helper, 'container') as container:
                helper.dispatch(SimpleNamespace(profile='feed', command='build', target=target), self.work)
                container.assert_called_once_with(self.work, ['bitbake', expected], profile='feed')

    def test_host_network_is_explicit_opt_in_only(self):
        for value, expected in ((None, False), ('host', True)):
            environment = {} if value is None else {'INT_DOCKER_NETWORK': value}
            with self.subTest(value=value), mock.patch.dict('os.environ', environment, clear=False), \
                    mock.patch.object(helper, 'docker') as docker:
                if value is None:
                    helper.os.environ.pop('INT_DOCKER_NETWORK', None)
                helper.container(self.work, ['true'], profile='feed')
                command = docker.call_args.args[0]
                self.assertEqual(expected, '--network' in command)
                self.assertNotIn('-p', command)
                self.assertNotIn('--publish', command)
        for value in ('bridge', 'container:other', 'HOST', ' host'):
            with self.subTest(value=value), mock.patch.dict('os.environ', {'INT_DOCKER_NETWORK': value}):
                with self.assertRaisesRegex(RuntimeError, 'accepts only'):
                    helper.network_args()

    def test_options_after_command_keep_profile_and_reject_stray_arguments(self):
        for argv in (['build', '--profile', 'feed'], ['build', 'x', '--profile', 'feed'],
                     ['--profile', 'feed', 'build', 'x']):
            with self.subTest(argv=argv):
                args = helper.parse_arguments(argv)
                self.assertEqual(('feed', 'build', []), (args.profile, args.command, args.extra))
        for argv in (['build', 'x', 'y'], ['smoke', '--fingerprint', 'A'], ['build', '--bogus']):
            with self.subTest(argv=argv), self.assertRaises(SystemExit), mock.patch('sys.stderr'):
                helper.parse_arguments(argv)

    def test_feed_check_forwards_runner_options(self):
        argv = ['--profile', 'feed', 'feed-check', '/work/fixtures', '--fingerprint', 'A' * 40,
                '--feed-sha256', 'b' * 64, '--case', 'valid']
        args = helper.parse_arguments(argv)
        self.assertEqual('/work/fixtures', args.target)
        with mock.patch.object(helper, 'container') as container:
            helper.dispatch(args, self.work)
        command = container.call_args.args[1]
        self.assertEqual(['/work/fixtures', '/work/evidence', *argv[4:]], command[3:])
        self.assertEqual('feed', container.call_args.kwargs['profile'])

    def test_run_launches_host_qemu_helper_without_lock_or_container(self):
        argv = ['int', '--profile', 'desktop', 'run', '--reset']
        with mock.patch('sys.argv', argv), mock.patch.object(helper, 'workdir', return_value=self.work), \
                mock.patch.object(helper, 'operation_lock') as lock, \
                mock.patch.object(helper, 'docker') as docker, \
                mock.patch.object(helper.subprocess, 'run') as run:
            run.return_value.returncode = 0
            with self.assertRaises(SystemExit):
                helper.main()
        command = run.call_args.args[0]
        self.assertTrue(command[1].endswith('scripts/qemu-run.py'))
        self.assertEqual(['--profile', 'desktop', '--workdir', str(self.work), '--reset'], command[2:])
        lock.assert_not_called()
        docker.assert_not_called()

    def test_live_profile_layers_desktop_then_live_in_separate_directory(self):
        helper.configure(self.work, 'live')
        conf = self.work/'build-live/conf'
        local = (conf/'local.conf').read_text()
        self.assertLess(local.index('int-desktop.inc'), local.index('int-live.inc'))
        self.assertIn('/src/meta-int-desktop', (conf/'bblayers.conf').read_text())
        self.assertIn('/meta-openembedded/meta-multimedia ', (conf/'bblayers.conf').read_text())
        self.assertFalse((self.work/'build-desktop/conf/local.conf').exists())
        with mock.patch.object(helper, 'container') as container:
            helper.dispatch(SimpleNamespace(profile='live', command='build', target=None), self.work)
            container.assert_called_once_with(self.work, ['bitbake', 'int-image-live'], profile='live')

    def test_browser_profile_adds_firefox_layer_last_in_separate_directory(self):
        for profile in ('core', 'desktop', 'feed', 'live'):
            helper.configure(self.work, profile)
        before = {path: path.read_bytes() for path in self.work.glob('build*/conf/*')}
        helper.configure(self.work, 'browser')
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        conf = self.work/'build-browser/conf'
        live = self.work/'build-live/conf'
        layers = (conf/'bblayers.conf').read_text()
        self.assertEqual(layers, (live/'bblayers.conf').read_text().replace(
            '/src/meta-int-desktop"', '/src/meta-int-desktop /work/sources/meta-browser/meta-firefox"'))
        order = [layer.rsplit('/', 1)[-1] for layer in
                 layers.split('BBLAYERS = "', 1)[1].split('"', 1)[0].split()]
        self.assertEqual(order, ['meta', 'meta-oe', 'meta-python', 'meta-networking', 'meta-multimedia',
                                 'meta-int', 'meta-wayland', 'meta-int-desktop', 'meta-firefox'])
        self.assertNotIn('meta-clang', layers)
        local = (conf/'local.conf').read_text()
        self.assertEqual(local, (live/'local.conf').read_text().replace(
            'include int-local.conf', 'require conf/distro/include/int-browser.inc\ninclude int-local.conf'))
        self.assertLess(local.index('int-desktop.inc'), local.index('int-live.inc'))
        self.assertLess(local.index('int-live.inc'), local.index('int-browser.inc'))
        self.assertLess(local.index('int-browser.inc'), local.index('include int-local.conf'))
        with mock.patch.object(helper, 'container') as container:
            helper.dispatch(SimpleNamespace(profile='browser', command='build', target=None), self.work)
            container.assert_called_once_with(self.work, ['bitbake', 'int-image-osint-browser'],
                                              profile='browser')
        with mock.patch.object(helper, 'docker') as docker:
            helper.container(self.work, ['bitbake', 'example'], profile='browser')
            command = docker.call_args.args[0]
            self.assertIn('oe-init-build-env /work/build-browser', command[command.index('-ec')+1])
        self.assertEqual('browser', helper.parse_arguments(['--profile', 'browser', 'build']).profile)

    def test_browser_layer_source_is_locked_and_fetched_by_bootstrap(self):
        source = helper.LOCK['sources']['meta-browser']
        self.assertEqual('https://github.com/OSSystems/meta-browser', source['url'])
        self.assertRegex(source['revision'], '^[0-9a-f]{40}$')
        work = self.work/'fresh'
        sources = helper.LOCK['sources']

        def check_output(args, text):
            name = Path(args[2]).name
            return {'remote': sources[name]['url'] + '\n', 'rev-parse': sources[name]['revision'] + '\n',
                    'status': ''}[args[3]]

        with mock.patch.object(helper, 'run') as run, \
                mock.patch.object(helper.subprocess, 'check_output', side_effect=check_output):
            helper.bootstrap(work)
        fetched = [call.args[0][-1] for call in run.call_args_list if 'fetch' in call.args[0]]
        self.assertEqual([entry['revision'] for entry in sources.values()], fetched)
        self.assertTrue((work/'sources/meta-browser').is_dir())
        self.assertEqual(list(sources), [
            'openembedded-core', 'bitbake', 'meta-openembedded', 'meta-wayland', 'meta-browser'])


if __name__ == '__main__':
    unittest.main()
