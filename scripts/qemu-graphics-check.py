#!/usr/bin/env python3
"""Test the real local logind/DRM seat on a disposable virtio VGA VM.

The owner logs in on serial; a test-only root helper opens a separate PAM
session on tty1. QMP is a private Unix socket, and the retained framebuffers are
from that synthetic session. Physical devices and mouse input remain unqualified.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import signal
import socket
import sys
import time

SPEC = importlib.util.spec_from_file_location('int_graphics_desktop', Path(__file__).with_name('qemu-desktop-check.py'))
desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop)
core = desktop.core
INPUTS = {
    'kernel': 'bzImage',
    'rootfs': 'int-image-graphics-smoke-qemux86-64.rootfs.ext4',
    'manifest': 'int-image-graphics-smoke-qemux86-64.rootfs.manifest',
}
core.smoke.INPUTS = INPUTS.copy()
core.FAILURE = re.compile(core.FAILURE.pattern + r'|INT_GRAPHICS[^\r\n]*FAIL', re.I)
DEFAULT_TIMEOUT = 600.0
MAX_FRAME = 64 * 1024 * 1024


def inspect_frame(path: Path) -> dict:
    """Validate bounded P6 data and reject an entirely uniform framebuffer."""
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_FRAME:
        raise ValueError('invalid framebuffer size')
    data = path.read_bytes()
    match = re.match(rb'\AP6\s+(\d{1,5})\s+(\d{1,5})\s+255\s', data[:256])
    if not match:
        raise ValueError('invalid framebuffer header')
    width, height = map(int, match.groups())
    pixels = data[match.end():]
    if not (1 <= width <= 8192 and 1 <= height <= 8192 and len(pixels) == width * height * 3):
        raise ValueError('invalid framebuffer dimensions')
    stride = 3 * 97
    sampled = set(zip(pixels[0::stride], pixels[1::stride], pixels[2::stride]))
    if len(sampled) < 2:
        raise ValueError('uniform framebuffer')
    return {'snapshot': str(path), 'bytes': len(data), 'sha256': core.smoke.sha256(path),
            'width': width, 'height': height}


def qmp_execute(qmp: Path, requests: list[dict]) -> None:
    """Use QEMU's local QMP protocol; never expose a TCP control port."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(str(qmp))
        stream = connection.makefile('rwb', buffering=0)
        try:
            def read_message():
                raw = stream.readline(65537)
                if not raw or len(raw) > 65536:
                    raise ValueError('invalid QMP message')
                return json.loads(raw)
            if 'QMP' not in read_message():
                raise ValueError('invalid QMP greeting')
            for request in [{'execute': 'qmp_capabilities'}, *requests]:
                stream.write((json.dumps(request) + '\n').encode())
                while True:
                    reply = read_message()
                    if 'error' in reply:
                        raise ValueError('QMP request rejected')
                    if 'return' in reply:
                        break
                # Separate input reports so the guest receives real key transitions.
                if request['execute'] == 'input-send-event':
                    time.sleep(0.05)
        finally:
            stream.close()


def capture(qmp: Path, frame: Path) -> dict:
    qmp_execute(qmp, [{'execute': 'screendump', 'arguments': {'filename': str(frame)}}])
    return inspect_frame(frame)


def shortcut(qmp: Path, key: str) -> None:
    if key not in ('ret', 'd'):
        raise ValueError('unsupported test key')
    transitions = [('meta_l', True), (key, True), (key, False), ('meta_l', False)]
    requests = [{'execute': 'input-send-event', 'arguments': {'events': [
        {'type': 'key', 'data': {'down': down, 'key': {'type': 'qcode', 'data': name}}}]}}
        for name, down in transitions]
    qmp_execute(qmp, requests)


def select_terminal(qmp: Path) -> None:
    # Filter the launcher by its installed Foot desktop entry, then select it.
    requests = [{'execute': 'input-send-event', 'arguments': {'events': [
        {'type': 'key', 'data': {'down': down, 'key': {'type': 'qcode', 'data': name}}}]}}
        for name in ('f', 'o', 'o', 't', 'ret') for down in (True, False)]
    qmp_execute(qmp, requests)


def frame_difference(before: Path, after: Path) -> int:
    left, right = before.read_bytes(), after.read_bytes()
    head = rb'\AP6\s+(\d{1,5})\s+(\d{1,5})\s+255\s'
    lm, rm = re.match(head, left[:256]), re.match(head, right[:256])
    if not lm or not rm or lm.groups() != rm.groups():
        raise ValueError('incompatible framebuffer dimensions')
    left, right = left[lm.end():], right[rm.end():]
    if len(left) != len(right):
        raise ValueError('incompatible framebuffer size')
    return sum(a != b for a, b in zip(left, right))


def analyze(serial: str, process: dict, frame: Path, launcher: Path) -> dict:
    result = desktop.analyze_log(serial, process)
    lines = serial.replace('\r\n', '\n').replace('\r', '\n').splitlines()
    required = ('INT_DESKTOP_USER_PASS', 'INT_GRAPHICS_KEYBOARD_READY', 'INT_GRAPHICS_LAUNCHER_READY',
                'INT_GRAPHICS_LAUNCHER_VISIBLE', 'INT_GRAPHICS_SELECTION_PASS',
                'INT_GRAPHICS_EXIT_PASS', 'INT_CORE_ROOT_PASS')
    positions = [[i for i, line in enumerate(lines) if line == marker] for marker in required]
    ordered = all(len(found) == 1 for found in positions) and [p[0] for p in positions] == sorted(p[0] for p in positions)
    ok = bool(ordered and process.get('graphics_frame') and process.get('launcher_frame'))
    if ok:
        try:
            initial, opened = inspect_frame(frame), inspect_frame(launcher)
            changed = frame_difference(frame, launcher)
            ok = (initial == process['graphics_frame'] and opened == process['launcher_frame']
                  and initial['width'] == opened['width'] and initial['height'] == opened['height']
                  and changed == process.get('launcher_changed_bytes')
                  and changed >= max(1, initial['width'] * initial['height'] // 100))
        except (OSError, ValueError):
            ok = False
    result['checks']['graphics'] = ok
    result['checks']['keyboard-and-launcher'] = ok
    if not ok:
        result['failure_reasons'].append('missing ordered graphics, keyboard/launcher checks, clean exit, or verified framebuffers')
    result['passed'] = not result['failure_reasons']
    return result


def run_graphics(deploy: Path, evidence: Path, timeout: float) -> tuple[int, Path]:
    state = {}
    def transform(command, run):
        qmp = run / 'qmp.sock'
        if len(str(qmp).encode()) >= 104:
            raise ValueError('QMP socket path is too long')
        state['qmp'] = qmp
        state['frame'] = run / 'graphics.ppm'
        state['launcher'] = run / 'launcher.ppm'
        return command + ['-vga', 'virtio', '-device', 'virtio-keyboard-pci',
                          '-qmp', f"unix:{str(qmp).replace(',', ',,')},server=on,wait=off"]
    def on_root(_child, expect, outcome):
        expect(r'(?m)(?:^|[\r\n])INT_GRAPHICS_KEYBOARD_READY\r*(?:\n|$)', 'virtual keyboard')
        try:
            shortcut(state['qmp'], 'ret')
            expect(r'(?m)(?:^|[\r\n])INT_GRAPHICS_LAUNCHER_READY\r*(?:\n|$)', 'terminal keyboard shortcut')
            outcome['graphics_frame'] = capture(state['qmp'], state['frame'])
            shortcut(state['qmp'], 'd')
            expect(r'(?m)(?:^|[\r\n])INT_GRAPHICS_LAUNCHER_VISIBLE\r*(?:\n|$)', 'launcher keyboard shortcut')
            outcome['launcher_frame'] = capture(state['qmp'], state['launcher'])
            outcome['launcher_changed_bytes'] = frame_difference(state['frame'], state['launcher'])
            select_terminal(state['qmp'])
            expect(r'(?m)(?:^|[\r\n])INT_GRAPHICS_SELECTION_PASS\r*(?:\n|$)', 'launcher selection')
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            raise core.ProtocolError('graphical framebuffer capture failed') from None
    def analyzer(serial, process):
        return analyze(serial, process, state['frame'], state['launcher'])
    return core.run_core(
        deploy, evidence, timeout, on_owner=desktop.owner_checks, on_root=on_root,
        root_helper='/usr/libexec/int-graphics-root-check', command_transform=transform,
        analyzer=analyzer, context={'graphics_runner_sha256': core.smoke.sha256(Path(__file__).resolve()),
        'scope': 'local tty1, PAM/logind, virtio VGA/keyboard, Sway Pixman, terminal, launcher selection and framebuffer',
        'unqualified': 'physical hardware, mouse interaction, GPU acceleration and performance'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('deploy_directory', type=Path)
    parser.add_argument('evidence_directory', type=Path)
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()
    if not 0 < args.timeout < float('inf'):
        parser.error('--timeout must be a finite positive number')
    def stop(signum, _frame):
        raise core.smoke.StopRequested(signum)
    previous = signal.signal(signal.SIGTERM, stop)
    try:
        code, _run = run_graphics(args.deploy_directory, args.evidence_directory, args.timeout)
        return code
    except OSError as error:
        print('cannot create graphics evidence: ' + type(error).__name__, file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
