#!/usr/bin/env python3
"""Exercise first-owner provisioning, login, sudo and firewall in a disposable VM.

The random owner credential stays in memory. Only guest output is captured,
and a credential echo fails the run before a redacted transcript is written.
Passing evidence preserves the original, unprovisioned snapshot, not guest
changes made through QEMU's temporary disk overlay.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import sys
import time

import pexpect


_SPEC = importlib.util.spec_from_file_location(
    "int_core_smoke_base", Path(__file__).with_name("qemu-smoke.py")
)
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)

INPUTS = {
    "kernel": "bzImage",
    "rootfs": "int-image-core-smoke-qemux86-64.rootfs.ext4",
    "manifest": "int-image-core-smoke-qemux86-64.rootfs.manifest",
}
# This private import instance is used only by this runner. Reuse the original
# copying/hash/validation implementation with the core image's input names.
smoke.INPUTS = INPUTS.copy()
CHECKS = ("owner", "network", "firewall", "ready", "login", "sudo", "shutdown")
OWNER = "intowner"
DEFAULT_TIMEOUT = 420.0
TRANSCRIPT_LIMIT = 8 * 1024 * 1024
FAILURE = re.compile(r"INT_(?:CORE|FIRSTBOOT|OWNER)[^\r\n]*FAIL|kernel panic|panic - not syncing", re.I)


class ProtocolError(Exception):
    """A fixed diagnostic, deliberately excluding pexpect's buffer repr."""


class Transcript(io.StringIO):
    """Capture reads only, in bounded memory; never attach this to sends."""

    def write(self, value: str) -> int:
        if self.tell() + len(value) > TRANSCRIPT_LIMIT:
            raise ProtocolError("guest transcript exceeded its size limit")
        return super().write(value)


def redact(value: str, password: str) -> str:
    return value.replace(password, "[REDACTED]") if password else value


def generate_password() -> str:
    # Fixed character classes plus 256 random bits satisfy ordinary passwd
    # strength checks without shell quoting, whitespace or terminal controls.
    return "Int9!" + secrets.token_hex(32)


def terminate_child(child, grace: float) -> None:
    """Reap the PTY child and stop its process group, including orphan helpers."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace
    while child.isalive() and time.monotonic() < deadline:
        time.sleep(min(0.02, max(0, deadline - time.monotonic())))
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.close(force=True)


def execute_interactive(command: list[str], log_path: Path, timeout: float,
                        termination_grace: float = smoke.TERMINATION_GRACE,
                        on_owner=None) -> dict:
    outcome = {
        "returncode": None, "timed_out": False, "interrupted_signal": None,
        "stage": "spawn", "protocol_error": None, "credential_echoed": False,
        "owner_password_prompts": 0, "login_password_prompt": False,
        "sudo_password_prompt": False, "sudo_rejected_wrong_password": False,
        "login_uid": None,
    }
    password = generate_password()
    transcript = Transcript()
    child = None
    deadline = time.monotonic() + timeout

    def expect(pattern, stage: str):
        outcome["stage"] = stage
        # Only fixed protocol-stage names leave memory while the VM runs.
        print(f"QEMU core stage: {stage}", flush=True)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise pexpect.TIMEOUT("total interaction deadline")
        found = child.expect([pattern, FAILURE, pexpect.EOF, pexpect.TIMEOUT], timeout=remaining)
        if found == 1:
            raise ProtocolError("guest emitted a failure or kernel panic")
        if found == 2:
            if pattern is pexpect.EOF:
                return
            raise ProtocolError("guest exited before the expected interaction")
        if found == 3:
            raise pexpect.TIMEOUT("total interaction deadline")

    try:
        # forkpty creates a session/process group for the child. Disable local
        # PTY echo as well as relying on guest passwd/login/sudo to hide input.
        child = pexpect.spawn(command[0], command[1:], encoding="utf-8",
                              codec_errors="replace", echo=False, timeout=timeout)
        child.logfile_read = transcript
        child.logfile_send = None
        child.logfile = None
        expect(r"INT_OWNER_USERNAME: *", "owner username")
        child.sendline(OWNER)
        expect(r"New password: *", "owner password")
        outcome["owner_password_prompts"] += 1
        child.sendline(password)
        expect(r"Retype new password: *", "owner password confirmation")
        outcome["owner_password_prompts"] += 1
        child.sendline(password)
        expect(r"(?m)(?:^|[\r\n])INT_CORE_READY\r*(?:\n|$)", "core assertions")
        expect(r"(?m)(?:^|[\r\n])[^\r\n:]*login: *", "login username")
        child.sendline(OWNER)
        expect(r"Password: *", "login password")
        outcome["login_password_prompt"] = True
        child.sendline(password)
        expect(r"(?m)(?:^|[\r\n])[^\r\n]*[$#] +", "owner shell")
        child.sendline("printf '\\nINT_CORE_LOGIN_UID:%s\\n' \"$(id -u)\"")
        expect(r"(?m)(?:^|[\r\n])INT_CORE_LOGIN_UID:([0-9]+)\r*\n", "login identity")
        outcome["login_uid"] = int(child.match.group(1))
        if outcome["login_uid"] < 1000:
            raise ProtocolError("owner login did not use an unprivileged UID")
        if on_owner is not None:
            # Extension checks run as the authenticated owner, before sudo.
            # The callback receives no credential or raw transcript object.
            on_owner(child, expect, outcome)
        child.sendline("LC_ALL=C sudo -k && LC_ALL=C sudo -p 'INT_SUDO_PASSWORD: ' /usr/libexec/int-core-root-check")
        # The shell echoes the command containing this marker. Only a prompt
        # beginning a fresh line proves sudo actually requested the password.
        expect(r"(?m)(?:^|[\r\n])INT_SUDO_PASSWORD: *", "sudo password")
        outcome["sudo_password_prompt"] = True
        # A prompt alone does not establish that PAM verifies the credential.
        # Prefixing the real random value keeps accidental echoes covered by
        # the same redaction/echo check without persisting another credential.
        child.sendline("Wrong_" + password)
        expect(r"(?m)(?:^|[\r\n])Sorry, try again\.\r*(?:\n|$)",
               "sudo wrong-password rejection")
        expect(r"(?m)(?:^|[\r\n])INT_SUDO_PASSWORD: *", "sudo password retry")
        outcome["sudo_rejected_wrong_password"] = True
        child.sendline(password)
        expect(r"(?m)(?:^|[\r\n])INT_CORE_ROOT_PASS\r*(?:\n|$)", "privileged guest checks")
        expect(pexpect.EOF, "guest poweroff")
    except pexpect.TIMEOUT:
        outcome["timed_out"] = True
    except (KeyboardInterrupt, smoke.StopRequested) as error:
        outcome["interrupted_signal"] = getattr(error, "signum", signal.SIGINT)
    except ProtocolError as error:
        # These exceptions are our fixed strings, never raw pexpect errors.
        outcome["protocol_error"] = str(error)
    except Exception as error:
        outcome["protocol_error"] = "interaction failed: " + type(error).__name__
    finally:
        try:
            if child is not None:
                # Keep a bounded tail of guest diagnostics after its failure
                # marker. All reads still use the same in-memory redaction.
                if outcome["protocol_error"] and child.isalive():
                    remaining = min(2.0, max(0.0, deadline - time.monotonic()))
                    if remaining:
                        try:
                            child.expect(pexpect.EOF, timeout=remaining)
                        except (pexpect.TIMEOUT, pexpect.EOF, ProtocolError):
                            pass
                terminate_child(child, termination_grace)
                outcome["returncode"] = (
                    child.exitstatus if child.exitstatus is not None
                    else -child.signalstatus if child.signalstatus is not None else None
                )
        finally:
            raw = transcript.getvalue()
            outcome["credential_echoed"] = password in raw
            safe = redact(raw, password)
            # No raw transcript, send log, exception buffer or credential is
            # ever persisted, even when authentication/cleanup fails.
            with log_path.open("w", encoding="utf-8") as stream:
                stream.write(safe)
            transcript.close()
            password = ""
    return outcome


def analyze_log(serial: str, process: dict) -> dict:
    lines = serial.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    markers = {"owner": "INT_CORE_CHECK:owner:PASS",
               "network": "INT_CORE_CHECK:network:PASS",
               "firewall": "INT_CORE_CHECK:firewall:PASS", "ready": "INT_CORE_READY",
               "sudo": "INT_CORE_ROOT_PASS"}
    positions = {name: [i for i, line in enumerate(lines) if line == marker]
                 for name, marker in markers.items()}
    positions["login"] = [i for i, line in enumerate(lines)
                          if re.fullmatch(r"INT_CORE_LOGIN_UID:[0-9]+", line)]
    positions["shutdown"] = [i for i, line in enumerate(lines)
                             if re.fullmatch(r"(?:\[\s*[0-9.]+\]\s*)?reboot: Power down", line)]
    checks = {name: len(positions[name]) == 1 for name in CHECKS}
    reasons = []
    if process.get("timed_out"):
        reasons.append("QEMU exceeded the total interaction/shutdown timeout")
    if process.get("interrupted_signal"):
        reasons.append(f"runner interrupted by signal {process['interrupted_signal']}")
    if process.get("returncode") != 0:
        reasons.append(f"QEMU returned {process.get('returncode')!r}, expected 0")
    if process.get("protocol_error"):
        reasons.append(process["protocol_error"])
    if process.get("credential_echoed"):
        reasons.append("guest echoed a credential; serial evidence was redacted")
    if FAILURE.search(serial):
        reasons.append("guest emitted a failure or kernel panic")
    for name in CHECKS:
        if not checks[name]:
            reasons.append(f"expected one exact {name} marker, observed {len(positions[name])}")
    if all(checks.values()):
        first = {name: found[0] for name, found in positions.items()}
        if not (max(first["owner"], first["network"], first["firewall"]) < first["ready"]
                < first["login"] < first["sudo"] < first["shutdown"]):
            reasons.append("guest assertions, login, sudo and shutdown were out of order")
        uid = int(lines[first["login"]].split(":")[-1])
        if uid < 1000 or uid != process.get("login_uid"):
            checks["login"] = False
            reasons.append("recorded login UID was not the authenticated unprivileged owner")
    if process.get("owner_password_prompts") != 2:
        checks["owner"] = False
        reasons.append("owner enrollment did not request password and confirmation")
    if not process.get("login_password_prompt"):
        checks["login"] = False
        reasons.append("login did not request a password")
    if not process.get("sudo_password_prompt"):
        checks["sudo"] = False
        reasons.append("sudo did not request fresh authentication")
    if not process.get("sudo_rejected_wrong_password"):
        checks["sudo"] = False
        reasons.append("sudo did not reject the incorrect password and request a retry")
    return {"passed": not reasons, "checks": checks, "failure_reasons": reasons}


def run_core(deploy: Path, evidence_root: Path, timeout: float, *,
             on_owner=None, analyzer=None, context: dict | None = None) -> tuple[int, Path]:
    run = smoke.create_run_directory(evidence_root)
    print(f"QEMU core evidence: {run}", flush=True)
    started = time.monotonic()
    metadata = {
        "schema_version": 1, "status": "running", "started_at_utc": smoke.utc_now(),
        "deploy_directory": str(deploy.resolve()), "timeout_seconds": timeout,
        "termination_grace_seconds": smoke.TERMINATION_GRACE,
        "python_version": sys.version, "host_platform": platform.platform(),
        "emulation": "QEMU TCG, qemu64, 512 MiB RAM, 2 virtual CPUs",
        "measurement_scope": "functional VM provisioning/login/sudo/firewall; not physical performance",
        "runner_sha256": smoke.sha256(Path(__file__).resolve()),
        "base_runner_sha256": smoke.sha256(Path(smoke.__file__).resolve()),
        "command": None, "artifacts": {}, "checks": {name: False for name in CHECKS},
        "failure_reasons": [], "process": {}, "serial_log": str(run / "serial.log"),
        "credential_policy": "random in-memory test credential; echo fails; transcript redacted before writing",
    }
    if context is not None:
        metadata["context"] = dict(context)
    (run / "serial.log").touch(mode=0o600)
    smoke.write_json(run / "result.json", metadata)
    code = 1
    try:
        executable = shutil.which("qemu-system-x86_64")
        if not executable:
            raise FileNotFoundError("qemu-system-x86_64 is not installed or not on PATH")
        metadata["qemu_version"] = smoke.qemu_version(executable)
        metadata["artifacts"] = smoke.snapshot_inputs(deploy.resolve(), run)
        command = smoke.build_qemu_command(executable, metadata["artifacts"])
        metadata["command"] = command
        smoke.write_json(run / "result.json", metadata)
        if on_owner is None:
            metadata["process"] = execute_interactive(command, run / "serial.log", timeout)
        else:
            metadata["process"] = execute_interactive(command, run / "serial.log", timeout,
                                                      on_owner=on_owner)
        analyze = analyze_log if analyzer is None else analyzer
        analysis = analyze((run / "serial.log").read_text(encoding="utf-8"), metadata["process"])
        metadata["checks"] = analysis["checks"]
        metadata["failure_reasons"] = analysis["failure_reasons"]
        if (not analysis.get("passed")
                or any(metadata["checks"].get(name) is not True for name in CHECKS)
                or any(value is not True for value in metadata["checks"].values())):
            if not metadata["failure_reasons"]:
                metadata["failure_reasons"].append("guest analyzer rejected required checks")
        for kind, artifact in metadata["artifacts"].items():
            if smoke.sha256(Path(artifact["snapshot"])) != artifact["sha256"]:
                metadata["failure_reasons"].append(f"{kind} snapshot changed during QEMU run")
        if not metadata["failure_reasons"]:
            metadata["status"] = "passed"
            code = 0
        if metadata["process"].get("interrupted_signal"):
            code = 128 + metadata["process"]["interrupted_signal"]
    except (KeyboardInterrupt, smoke.StopRequested) as error:
        signum = getattr(error, "signum", signal.SIGINT)
        metadata["failure_reasons"].append(f"runner interrupted by signal {signum}")
        code = 128 + signum
    except Exception as error:
        # The interaction owns credential redaction and returns fixed errors.
        # Avoid serializing arbitrary exception reprs from external libraries.
        metadata["failure_reasons"].append("runner failed: " + type(error).__name__)
    finally:
        metadata["finished_at_utc"] = smoke.utc_now()
        metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if metadata["status"] != "passed":
            metadata["status"] = "failed"
            shutil.rmtree(run / "artifacts", ignore_errors=True)
            metadata["artifact_copies_retained"] = False
        else:
            metadata["artifact_copies_retained"] = True
        smoke.write_json(run / "result.json", metadata)
        if metadata["status"] == "passed":
            smoke.write_json(run / "known-good.json", {
                "schema_version": 1, "result": str(run / "result.json"),
                "artifacts": metadata["artifacts"],
                "verified_at_utc": metadata["finished_at_utc"],
                "snapshot_scope": "original unprovisioned image; guest writes discarded",
            })
    print(f"{metadata['status'].upper()}: {run / 'result.json'}", flush=True)
    return code, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deploy_directory", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")

    def request_stop(signum, _frame):
        raise smoke.StopRequested(signum)

    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        code, _run = run_core(args.deploy_directory, args.evidence_directory, args.timeout)
        return code
    except OSError as error:
        print("cannot create or write core evidence: " + type(error).__name__, file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
