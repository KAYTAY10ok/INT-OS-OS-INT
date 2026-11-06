#!/usr/bin/env python3
"""Qualify an unprivileged headless Pixman desktop in the disposable INT VM.

Core enrollment/login/sudo/firewall/shutdown checks remain mandatory. This adds
real Sway IPC, Wayland protocol, configured clients, terminal mapping and session
exit checks. It does not qualify a graphical seat, DRM/EGL, input or performance.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import signal
import sys


_SPEC = importlib.util.spec_from_file_location(
    "int_desktop_core", Path(__file__).with_name("qemu-core-check.py")
)
core = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(core)

INPUTS = {
    "kernel": "bzImage",
    "rootfs": "int-image-desktop-smoke-qemux86-64.rootfs.ext4",
    "manifest": "int-image-desktop-smoke-qemux86-64.rootfs.manifest",
}
# This import is private to the desktop runner; do not alter other core users.
core.INPUTS = INPUTS.copy()
core.smoke.INPUTS = INPUTS.copy()
core.FAILURE = re.compile(core.FAILURE.pattern + r"|INT_DESKTOP[^\r\n]*FAIL", re.I)
COMPONENTS = ("output", "protocol", "config", "terminal", "exit")
DEFAULT_TIMEOUT = 600.0


def owner_checks(child, expect, outcome):
    child.sendline("/usr/libexec/int-desktop-user-check")
    expect(r"(?m)(?:^|[\r\n])INT_DESKTOP_USER_PASS\r*(?:\n|$)",
           "unprivileged headless desktop")
    outcome["desktop_user_checked"] = True


def analyze_log(serial: str, process: dict) -> dict:
    result = core.analyze_log(serial, process)
    lines = serial.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    markers = {name: f"INT_DESKTOP_CHECK:{name}:PASS" for name in COMPONENTS}
    markers["desktop"] = "INT_DESKTOP_USER_PASS"
    positions = {name: [index for index, line in enumerate(lines) if line == marker]
                 for name, marker in markers.items()}
    reasons = result["failure_reasons"]
    desktop_ok = True
    for name, found in positions.items():
        valid = len(found) == 1
        result["checks"]["desktop" if name == "desktop" else "desktop-" + name] = valid
        if not valid:
            desktop_ok = False
            reasons.append(f"expected one exact desktop {name} marker, observed {len(found)}")
    if not process.get("desktop_user_checked"):
        desktop_ok = False
        reasons.append("authenticated owner did not complete the desktop interaction")
    if desktop_ok:
        login = [i for i, line in enumerate(lines) if re.fullmatch(r"INT_CORE_LOGIN_UID:[0-9]+", line)]
        sudo = [i for i, line in enumerate(lines) if line == "INT_CORE_ROOT_PASS"]
        ordered = [positions[name][0] for name in (*COMPONENTS, "desktop")]
        if len(login) != 1 or len(sudo) != 1 or not (
                login[0] < ordered[0] and ordered == sorted(ordered)
                and len(set(ordered)) == len(ordered) and ordered[-1] < sudo[0]):
            desktop_ok = False
            reasons.append("desktop assertions did not run in order as the owner before sudo")
    result["checks"]["desktop"] = desktop_ok
    result["passed"] = not reasons
    return result


def run_desktop(deploy: Path, evidence_root: Path, timeout: float) -> tuple[int, Path]:
    return core.run_core(
        deploy, evidence_root, timeout, on_owner=owner_checks, analyzer=analyze_log,
        context={
            "desktop_runner_sha256": core.smoke.sha256(Path(__file__).resolve()),
            "desktop_scope": "unprivileged Sway headless/Pixman, IPC, Wayland, client configuration, terminal and session exit",
            "unqualified": "physical/DRM/EGL rendering, keyboard/launcher selection, hardware compatibility and performance",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deploy_directory", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")

    def request_stop(signum, _frame):
        raise core.smoke.StopRequested(signum)

    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        code, _run = run_desktop(args.deploy_directory, args.evidence_directory, args.timeout)
        return code
    except OSError as error:
        print("cannot create or write desktop evidence: " + type(error).__name__, file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
