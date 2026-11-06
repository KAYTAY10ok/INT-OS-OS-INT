"""Reject incomplete graphics evidence and exercise local QMP framing."""
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('int_graphics_test', ROOT/'scripts/qemu-graphics-check.py')
graphics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(graphics)
FIXTURE_SPEC = importlib.util.spec_from_file_location('desktop_fixtures', Path(__file__).with_name('test_qemu_desktop_check.py'))
fixtures = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(fixtures)


def frame():
    pixels = bytearray(b'\x00\x00\x00' * 196)
    pixels[97*3:97*3+3] = b'\xff\xff\xff'
    return b'P6\n196 1\n255\n' + pixels


class GraphicsTests(unittest.TestCase):
    def test_rejects_blank_truncated_and_oversized_framebuffers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'screen.ppm'
            path.write_bytes(frame())
            self.assertEqual(graphics.inspect_frame(path)['width'], 196)
            for invalid in (b'P6\n2 1\n255\n'+b'\x00'*6, frame()[:-1], b'P3\n1 1\n255\n0 0 0'):
                path.write_bytes(invalid)
                with self.assertRaises(ValueError):
                    graphics.inspect_frame(path)
            with path.open('wb') as stream:
                stream.truncate(graphics.MAX_FRAME+1)
            with self.assertRaises(ValueError):
                graphics.inspect_frame(path)

    def test_graphics_markers_and_unchanged_frame_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'screen.ppm'
            path.write_bytes(frame())
            process = dict(fixtures.EXIT_OK, graphics_frame=graphics.inspect_frame(path))
            log = fixtures.PASS_LOG.replace('INT_CORE_ROOT_PASS', 'INT_GRAPHICS_READY\nINT_GRAPHICS_EXIT_PASS\nINT_CORE_ROOT_PASS')
            self.assertTrue(graphics.analyze(log, process, path)['passed'])
            for invalid in (log.replace('INT_GRAPHICS_READY\n', ''),
                            log.replace('INT_GRAPHICS_EXIT_PASS\n', ''),
                            log+'INT_GRAPHICS_READY\n'):
                self.assertFalse(graphics.analyze(invalid, process, path)['passed'])
            path.write_bytes(frame()[:-1])
            self.assertFalse(graphics.analyze(log, process, path)['passed'])

    def test_qmp_uses_a_local_socket_and_captures_requested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            sockpath = Path(directory)/'qmp.sock'
            target = Path(directory)/'screen.ppm'
            ready = threading.Event()
            requests = []
            def server():
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                    listener.bind(str(sockpath)); listener.listen(1); ready.set()
                    with listener.accept()[0] as conn:
                        stream = conn.makefile('rwb', buffering=0)
                        stream.write(b'{"QMP":{}}\n')
                        for _ in range(2):
                            request = json.loads(stream.readline()); requests.append(request)
                            if request['execute'] == 'screendump':
                                Path(request['arguments']['filename']).write_bytes(frame())
                            stream.write(b'{"return":{}}\n')
            thread = threading.Thread(target=server, daemon=True)
            thread.start()
            self.assertTrue(ready.wait(2))
            result = graphics.capture(sockpath, target)
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual([item['execute'] for item in requests], ['qmp_capabilities', 'screendump'])
            self.assertEqual(result['snapshot'], str(target))


if __name__ == '__main__':
    unittest.main()
