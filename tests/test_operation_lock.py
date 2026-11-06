"""Real advisory locks prevent cross-process access to one build workdir."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/int'
LOADER = importlib.machinery.SourceFileLoader('int_operation_test', str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class OperationLockTests(unittest.TestCase):
    def test_second_process_is_rejected_then_can_acquire_after_release(self):
        program = '''import importlib.machinery,importlib.util,pathlib,sys
loader=importlib.machinery.SourceFileLoader('fixture',sys.argv[1])
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec)
loader.exec_module(module)
try:
    with module.operation_lock(pathlib.Path(sys.argv[2])): pass
except RuntimeError:
    sys.exit(42)
'''
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with helper.operation_lock(work):
                result = subprocess.run([sys.executable, '-c', program, str(SCRIPT), directory], timeout=5)
                self.assertEqual(result.returncode, 42)
            result = subprocess.run([sys.executable, '-c', program, str(SCRIPT), directory], timeout=5)
            self.assertEqual(result.returncode, 0)

    def test_exception_releases_lock_without_blocking_other_workdirs(self):
        with tempfile.TemporaryDirectory() as directory:
            one, two = Path(directory)/'one', Path(directory)/'two'
            one.mkdir()
            two.mkdir()
            with self.assertRaises(ValueError):
                with helper.operation_lock(one), helper.operation_lock(two):
                    raise ValueError('fixture')
            with helper.operation_lock(one), helper.operation_lock(two):
                pass


if __name__ == '__main__':
    unittest.main()
