"""Exercise enrollment failure/recovery using a disposable fake account backend.

The production shell is copied with only PATH/state redirected. Account commands
are fixtures; these tests never change host accounts, homes, groups or passwords.
Real passwd/PAM/login/sudo integration belongs to the disposable QEMU test.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "meta-int/recipes-core/int-firstboot/files/int-firstboot"
DISPATCH = r'''
import json, os, pathlib, signal, sys
root = pathlib.Path(os.environ['FIRSTBOOT_FIXTURE'])
dbpath = root/'accounts.json'
db = json.loads(dbpath.read_text())
cmd, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
name = args[-1] if args else ''
def save(event):
    db['events'].append(event)
    dbpath.write_text(json.dumps(db))
if cmd == 'id':
    if args == ['-u']: print(0)
    elif name in db['users']:
        user = db['users'][name]
        print(user['uid'] if args[0] == '-u' else ' '.join(user['groups']))
    else: sys.exit(1)
elif cmd == 'stat':
    path = pathlib.Path(name)
    print('0:%o' % (path.stat().st_mode & 0o777))
elif cmd == 'getent':
    kind = args[0]
    if kind == 'shadow' and name == 'root': print('root:'+('opaque-test-hash' if db.get('root_unlocked') else '!')+':1:0:99999:7:::')
    elif kind == 'group':
        if name == 'wheel' or name in db['users']: print(name+':x:1000:')
        else: sys.exit(2)
    elif name in db['users']:
        u = db['users'][name]
        if kind == 'passwd': print(f"{name}:x:{u['uid']}:1000::/home/{name}:{u['shell']}")
        elif kind == 'shadow': print(f"{name}:{'opaque-test-hash' if u['password'] else '!'}:1:0:99999:7::{u['expiry']}:")
        else: sys.exit(2)
    else: sys.exit(2)
elif cmd == 'useradd':
    if name in db['users']: sys.exit(1)
    db['users'][name] = {'uid': 1000, 'groups':[name], 'shell':'/usr/sbin/nologin', 'expiry':'1', 'password':False}
    save('useradd:'+name)
    if db.get('interrupt_useradd'): os.kill(os.getppid(), signal.SIGTERM); sys.exit(1)
elif cmd == 'passwd':
    save('passwd:'+name)
    if db.get('interrupt_passwd'): os.kill(os.getppid(), signal.SIGTERM); sys.exit(1)
    db['users'][name]['password'] = True
    save('password-set:'+name)
elif cmd == 'usermod':
    # This assertion is independent of the shell's implementation order.
    if not (root/'state/committed').is_file(): sys.exit(99)
    if db.get('interrupt_activation'): sys.exit(1)
    db['users'][name].update(shell='/bin/sh', expiry='', groups=[name, 'wheel'])
    save('activated:'+name)
elif cmd == 'sync': pass
else: sys.exit(90)
'''


class FirstbootTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        dispatcher = self.bin / 'dispatcher'
        dispatcher.write_text(f'#!{sys.executable}\n' + DISPATCH)
        dispatcher.chmod(0o755)
        for command in ('id', 'stat', 'getent', 'useradd', 'passwd', 'usermod', 'sync'):
            (self.bin / command).symlink_to(dispatcher)
        self.script = self.root / 'firstboot'
        source = SOURCE.read_text().replace('state=/var/lib/int-firstboot', f'state={self.state}')
        source = source.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin', f'PATH={self.bin}:/usr/bin:/bin')
        self.script.write_text(source)
        self.dbpath = self.root / 'accounts.json'
        self.store({'users': {}, 'events': []})

    def store(self, data):
        self.dbpath.write_text(json.dumps(data))

    def data(self):
        return json.loads(self.dbpath.read_text())

    def run_enrollment(self, text='intfixtureowner\n', timeout=5):
        return subprocess.run(['sh', str(self.script)], input=text, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              env={**os.environ, 'FIRSTBOOT_FIXTURE':str(self.root)}, timeout=timeout)

    def record(self, kind, text='intfixtureowner 1000\n', mode=0o600):
        path = self.state / kind
        path.write_text(text)
        path.chmod(mode)

    def pending_account(self):
        self.store({'users': {'intfixtureowner': {'uid':1000, 'groups':['intfixtureowner'],
                    'shell':'/usr/sbin/nologin', 'expiry':'1', 'password':False}}, 'events':[]})

    def test_new_account_commits_before_activation_and_repeat_preserves_accounts(self):
        result = self.run_enrollment('Root\n-invalid\nintfixtureowner\n')
        self.assertEqual(result.returncode, 0, result.stdout)
        data = self.data()
        self.assertEqual(data['events'], ['useradd:intfixtureowner', 'passwd:intfixtureowner',
                         'password-set:intfixtureowner', 'activated:intfixtureowner'])
        self.assertEqual((self.state/'complete').read_text(), 'intfixtureowner 1000\n')
        self.assertEqual((self.state/'complete').stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.state/'pending').exists())
        self.assertEqual(self.run_enrollment('').returncode, 0)
        self.assertEqual(self.data(), data)

    def test_existing_account_is_preserved_and_never_adopted(self):
        self.pending_account()
        original = self.data()['users']['intfixtureowner']
        result = self.run_enrollment('intfixtureowner\nnewfixtureowner\n')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.data()['users']['intfixtureowner'], original)
        self.assertNotIn('passwd:intfixtureowner', self.data()['events'])

    def test_pending_resume_requires_password_and_never_creates_second_account(self):
        self.pending_account()
        self.record('pending')
        result = self.run_enrollment('')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.data()['events'][0], 'passwd:intfixtureowner')
        self.assertNotIn('useradd:intfixtureowner', self.data()['events'])

    def test_interrupted_activation_resumes_committed_without_password_reset(self):
        self.pending_account()
        self.record('pending')
        db = self.data()
        db['interrupt_activation'] = True
        self.store(db)
        self.assertNotEqual(self.run_enrollment('').returncode, 0)
        self.assertTrue((self.state/'committed').is_file())
        self.assertFalse((self.state/'complete').exists())
        db = self.data()
        self.assertEqual(db['users']['intfixtureowner']['shell'], '/usr/sbin/nologin')
        db['interrupt_activation'] = False
        self.store(db)
        self.assertEqual(self.run_enrollment('').returncode, 0)
        self.assertEqual(self.data()['events'].count('passwd:intfixtureowner'), 1)

    def test_unsafe_record_and_symlink_are_rejected_without_account_changes(self):
        for mode in (0o644, 0o666):
            with self.subTest(mode=mode):
                self.record('complete', mode=mode)
                self.assertNotEqual(self.run_enrollment('').returncode, 0)
                self.assertEqual(self.data()['events'], [])
        (self.state/'complete').unlink()
        target = self.root/'elsewhere'
        target.write_text('intfixtureowner 1000\n')
        target.chmod(0o600)
        (self.state/'complete').symlink_to(target)
        self.assertNotEqual(self.run_enrollment('').returncode, 0)
        self.assertEqual(self.data()['events'], [])

    def test_corrupt_or_privileged_record_is_rejected(self):
        for text in ('root 0\n', 'intfixtureowner 1000 extra\n', 'intfixtureowner 1000\nsecond 1001\n'):
            with self.subTest(text=text):
                self.record('committed', text)
                self.assertNotEqual(self.run_enrollment('').returncode, 0)
                self.assertEqual(self.data()['events'], [])

    def test_pending_account_unexpectedly_privileged_fails_closed(self):
        self.pending_account()
        self.record('pending')
        db = self.data()
        db['users']['intfixtureowner']['groups'].append('wheel')
        self.store(db)
        self.assertNotEqual(self.run_enrollment('').returncode, 0)
        self.assertEqual(self.data()['events'], [])

    def test_interrupted_password_entry_leaves_account_quarantined_until_retry(self):
        db = self.data()
        db['interrupt_passwd'] = True
        self.store(db)
        self.assertNotEqual(self.run_enrollment().returncode, 0)
        db = self.data()
        account = db['users']['intfixtureowner']
        self.assertEqual(account['shell'], '/usr/sbin/nologin')
        self.assertEqual(account['expiry'], '1')
        self.assertFalse(account['password'])
        self.assertNotIn('wheel', account['groups'])
        self.assertTrue((self.state/'pending').is_file())
        self.assertFalse((self.state/'committed').exists())
        db['interrupt_passwd'] = False
        self.store(db)
        self.assertEqual(self.run_enrollment('').returncode, 0)
        self.assertTrue((self.state/'complete').is_file())

    def test_creation_interrupted_before_record_does_not_adopt_or_delete_orphan(self):
        db = self.data()
        db['interrupt_useradd'] = True
        self.store(db)
        self.assertNotEqual(self.run_enrollment().returncode, 0)
        self.assertFalse((self.state/'pending').exists())
        db = self.data()
        original = db['users']['intfixtureowner'].copy()
        db['interrupt_useradd'] = False
        self.store(db)
        # The existing orphan collides; EOF then fails without changing it.
        self.assertNotEqual(self.run_enrollment().returncode, 0)
        self.assertEqual(self.data()['users']['intfixtureowner'], original)
        self.assertEqual(self.data()['events'], ['useradd:intfixtureowner'])

    def test_unlocked_root_is_rejected_before_creating_owner(self):
        db = self.data()
        db['root_unlocked'] = True
        self.store(db)
        self.assertNotEqual(self.run_enrollment().returncode, 0)
        self.assertEqual(self.data()['users'], {})
        self.assertEqual(self.data()['events'], [])


if __name__ == '__main__':
    unittest.main()
