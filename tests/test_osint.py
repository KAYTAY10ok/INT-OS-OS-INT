"""Host checks for the OS-INT Tor recipe, hardening sysctl and int-privacy.

int-privacy runs under /bin/sh with fake systemctl/id/exiftool commands placed
first in PATH; the fakes only record their arguments. No host service, file
outside a temporary directory or account is touched.
"""
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / 'meta-int/recipes-security'
TOR_DIR = SECURITY / 'tor'
TORRC = TOR_DIR / 'files/torrc'
TOR_SERVICE = TOR_DIR / 'files/tor.service'
HARDENING = SECURITY / 'int-osint-hardening'
SYSCTL = HARDENING / 'files/90-int-osint.conf'
INT_PRIVACY = HARDENING / 'files/int-privacy'
PACKAGEGROUP = ROOT / 'meta-int/recipes-core/packagegroups/packagegroup-int-osint.bb'

LOOPBACK = {'127.0.0.1', 'localhost', '[::1]'}


def tor_recipe():
    recipes = sorted(TOR_DIR.glob('tor_*.bb'))
    if len(recipes) != 1:
        raise AssertionError('expected exactly one tor recipe, found %s' % recipes)
    return recipes[0]


def torrc_options():
    """Active (non-comment) torrc lines as (keyword lowercased, value)."""
    options = []
    for line in TORRC.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, _, value = line.partition(' ')
        options.append((key.lower(), value.strip()))
    return options


def listen_host(value):
    """Address of a *Port value: '0' (disabled), 'unix', a host, or None for a
    bare port number (which would listen beyond loopback for some options)."""
    first = value.split()[0] if value else ''
    if first == '0' or first.startswith('unix:'):
        return first.split(':')[0]
    if first.isdigit() or first == 'auto':
        return None
    if first.startswith('['):
        return first[:first.index(']') + 1]
    return first.rsplit(':', 1)[0]


class TorrcTests(unittest.TestCase):
    def test_socks_only_on_loopback(self):
        options = torrc_options()
        socks = [value for key, value in options if key == 'socksport']
        self.assertEqual(socks, ['127.0.0.1:9050'])
        for key, value in options:
            if key.endswith('port') and key != 'socksport':
                host = listen_host(value)
                self.assertIn(host, LOOPBACK | {'0', 'unix'}, '%s %s' % (key, value))

    def test_no_relay_bridge_or_exit_settings(self):
        options = dict(torrc_options())
        for key in ('orport', 'dirport', 'bridgerelay', 'dircache', 'exitpolicy',
                    'publishserverdescriptor', 'extorport', 'servertransportplugin'):
            self.assertNotIn(key, options)
        self.assertEqual(options.get('clientonly'), '1')
        self.assertEqual(options.get('exitrelay'), '0')
        self.assertIn('--disable-module-relay', tor_recipe().read_text())

    def test_control_port_absent_or_local_cookie_only(self):
        options = torrc_options()
        controls = [value for key, value in options if key == 'controlport']
        keys = {key for key, _ in options}
        self.assertNotIn('hashedcontrolpassword', keys)
        for value in controls:
            self.assertIn(listen_host(value), LOOPBACK | {'unix'})
            self.assertIn(('cookieauthentication', '1'), options)

    def test_no_user_option_since_systemd_starts_tor_unprivileged(self):
        self.assertNotIn('user', dict(torrc_options()))


class TorRecipeTests(unittest.TestCase):
    def test_source_is_official_and_pinned(self):
        text = tor_recipe().read_text()
        self.assertIn('https://dist.torproject.org/${BP}.tar.gz', text)
        self.assertRegex(text, r'SRC_URI\[sha256sum\] = "[0-9a-f]{64}"')
        self.assertRegex(text, r'LIC_FILES_CHKSUM = "file://LICENSE;md5=[0-9a-f]{32}"')
        self.assertNotIn('AUTOREV', text)

    def test_service_is_not_enabled_by_default(self):
        text = tor_recipe().read_text()
        self.assertIn('SYSTEMD_SERVICE:${PN} = "tor.service"', text)
        self.assertRegex(text, r'(?m)^SYSTEMD_AUTO_ENABLE:\$\{PN\} = "disable"$')
        # No hand-made enablement symlinks.
        self.assertEqual(re.findall(r'SYSTEMD_AUTO_ENABLE\S* = "(\w+)"', text), ['disable'])
        self.assertNotRegex(text, r'\.wants|ln -s')

    def test_service_runs_as_dedicated_unprivileged_user(self):
        text = tor_recipe().read_text()
        self.assertIn('inherit autotools pkgconfig systemd useradd', text)
        self.assertRegex(text, r'USERADD_PARAM:\$\{PN\} = "--system[^"]*--user-group tor"')
        unit = TOR_SERVICE.read_text()
        for line in ('User=tor', 'Group=tor', 'NoNewPrivileges=yes', 'CapabilityBoundingSet=',
                     'ProtectSystem=strict', 'StateDirectory=tor', 'StateDirectoryMode=0700'):
            self.assertRegex(unit, r'(?m)^%s$' % re.escape(line))
        self.assertIn('-f @SYSCONFDIR@/tor/torrc', unit)

    def test_dependencies_come_from_pinned_layers(self):
        text = tor_recipe().read_text()
        depends = re.search(r'^DEPENDS = "([^"]*)"', text, re.M).group(1).split()
        self.assertEqual(sorted(depends), ['libcap', 'libevent', 'openssl', 'zlib'])
        self.assertIn('PACKAGECONFIG[systemd]', text)

    def test_packagegroup_ships_tor_and_hardening(self):
        text = PACKAGEGROUP.read_text()
        for package in ('tor', 'int-osint-hardening'):
            self.assertRegex(text, r'(?m)^\s+%s \\$' % re.escape(package))


class SysctlTests(unittest.TestCase):
    def values(self):
        result = {}
        for line in SYSCTL.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith(('#', ';')):
                continue
            key, _, value = line.partition('=')
            result[key.strip()] = value.strip()
        return result

    def test_required_values(self):
        values = self.values()
        expected = {
            'kernel.kptr_restrict': '2',
            'kernel.dmesg_restrict': '1',
            'net.ipv4.conf.all.rp_filter': '1',
            'net.ipv4.conf.default.rp_filter': '1',
            'net.ipv4.conf.*.rp_filter': '1',
            'net.ipv4.conf.all.accept_redirects': '0',
            'net.ipv4.conf.default.accept_redirects': '0',
            'net.ipv6.conf.all.accept_redirects': '0',
            'net.ipv6.conf.default.accept_redirects': '0',
            'net.ipv4.conf.all.send_redirects': '0',
            'net.ipv4.conf.default.send_redirects': '0',
            'net.ipv4.tcp_syncookies': '1',
        }
        for key, value in expected.items():
            self.assertEqual(values.get(key), value, key)

    def test_yama_is_optional_until_the_kernel_enables_it(self):
        values = self.values()
        self.assertEqual(values.get('-kernel.yama.ptrace_scope'), '1')
        fragments = ''.join(p.read_text() for p in (ROOT / 'meta-int/recipes-kernel/linux/files').glob('*.cfg'))
        if 'CONFIG_SECURITY_YAMA=y' in fragments:
            self.fail('Yama is now enabled: drop the "-" so a failure is reported')

    def test_recipe_installs_drop_in_and_no_service(self):
        text = (HARDENING / 'int-osint-hardening.bb').read_text()
        self.assertIn('${nonarch_libdir}/sysctl.d/90-int-osint.conf', text)
        self.assertNotIn('SYSTEMD_SERVICE', text)
        self.assertNotIn('inherit allarch systemd', text)


FAKE = r'''#!/bin/sh
printf '%s' "$(basename "$0")" >> "$FAKE_LOG"
for arg in "$@"; do printf ' [%s]' "$arg" >> "$FAKE_LOG"; done
printf '\n' >> "$FAKE_LOG"
case "$(basename "$0")" in
    id) echo "${FAKE_UID:-0}" ;;
    systemctl)
        case "$1" in
            is-enabled) echo disabled ;;
            is-active) echo inactive; exit 3 ;;
        esac ;;
esac
exit 0
'''


class IntPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bin = self.dir / 'bin'
        self.bin.mkdir()
        for name in ('id', 'systemctl', 'exiftool'):
            path = self.bin / name
            path.write_text(FAKE)
            path.chmod(0o755)
        self.log = self.dir / 'calls.log'
        self.work = self.dir / 'work'
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, uid='0'):
        env = {
            'PATH': '%s:/usr/bin:/bin' % self.bin,
            'FAKE_LOG': str(self.log),
            'FAKE_UID': uid,
            'LC_ALL': 'C',
        }
        return subprocess.run(['/bin/sh', str(INT_PRIVACY), *args], cwd=self.work, env=env,
                              capture_output=True, text=True, timeout=30)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_script_never_evaluates_user_input(self):
        text = INT_PRIVACY.read_text()
        code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertNotRegex(code, r'\beval\b')
        self.assertNotRegex(code, r'\bsh -c\b|\bbash -c\b|`')
        self.assertNotIn('shell=True', text)
        self.assertTrue(INT_PRIVACY.stat().st_mode & stat.S_IXUSR)
        subprocess.run(['/bin/sh', '-n', str(INT_PRIVACY)], check=True)

    def test_usage_errors(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli('frobnicate').returncode, 2)
        self.assertEqual(self.run_cli('tor').returncode, 2)
        self.assertEqual(self.run_cli('tor', 'maybe').returncode, 2)
        self.assertEqual(self.run_cli('tor', 'on', 'extra').returncode, 2)
        self.assertEqual(self.run_cli('clean-metadata').returncode, 2)
        self.assertEqual(self.run_cli('help').returncode, 0)
        self.assertNotIn('systemctl', ' '.join(self.calls()))
        self.assertNotIn('exiftool', ' '.join(self.calls()))

    def test_status_reports_mac_tor_and_firewall(self):
        result = self.run_cli('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MAC randomisation:', result.stdout)
        self.assertIn('Tor service: disabled, inactive', result.stdout)
        self.assertIn('Firewall (nftables): disabled, inactive', result.stdout)
        self.assertIn('10-int-mac-random.link', result.stdout)

    def test_tor_requires_root(self):
        result = self.run_cli('tor', 'on', uid='1000')
        self.assertEqual(result.returncode, 1)
        self.assertIn('needs root', result.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith('systemctl')])

    def test_tor_on_and_off_as_root(self):
        self.assertEqual(self.run_cli('tor', 'on').returncode, 0)
        self.assertEqual(self.run_cli('tor', 'off').returncode, 0)
        systemctl = [c for c in self.calls() if c.startswith('systemctl')]
        self.assertEqual(systemctl, ['systemctl [enable] [--now] [tor.service]',
                                     'systemctl [disable] [--now] [tor.service]'])

    def test_clean_metadata_refuses_symlinks_directories_and_missing(self):
        target = self.work / 'photo.jpg'
        target.write_bytes(b'not really a jpeg')
        (self.work / 'link.jpg').symlink_to(target)
        (self.work / 'folder').mkdir()
        (self.work / 'dangling').symlink_to(self.work / 'absent')
        for bad in ('link.jpg', 'folder', 'absent', 'dangling', '/dev/null'):
            result = self.run_cli('clean-metadata', 'photo.jpg', bad)
            self.assertEqual(result.returncode, 2, bad)
            self.assertIn('nothing was changed', result.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith('exiftool')])

    def test_clean_metadata_passes_names_as_plain_arguments(self):
        names = ['photo.jpg', '-dash.jpg', 'space name.jpg', '$(touch pwned).jpg', 'semi;colon.jpg']
        for name in names:
            (self.work / name).write_bytes(b'x')
        result = self.run_cli('clean-metadata', *names)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = ['-all=', '-overwrite_original', 'photo.jpg', './-dash.jpg', 'space name.jpg',
                    '$(touch pwned).jpg', 'semi;colon.jpg']
        self.assertEqual(self.calls(), ['exiftool ' + ' '.join('[%s]' % a for a in expected)])
        self.assertFalse((self.work / 'pwned').exists())


if __name__ == '__main__':
    unittest.main()
