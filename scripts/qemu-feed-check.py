#!/usr/bin/env python3
"""Run an experimental DNF feed scenario in an isolated QEMU VM.

Only an independently pinned test key and fixture-disk hash are accepted.
Only the explicitly selected scenario is tested; network updates and physical
hardware remain outside the scope.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time

SPEC = importlib.util.spec_from_file_location("int_feed_smoke_base", Path(__file__).with_name("qemu-smoke.py"))
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
smoke.INPUTS = {
    "kernel": "bzImage",
    "rootfs": "int-image-feed-smoke-qemux86-64.rootfs.ext4",
    "manifest": "int-image-feed-smoke-qemux86-64.rootfs.manifest",
}
FINGERPRINT = re.compile(r"[0-9A-F]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_DISK = 256 * 1024 * 1024
MAX_SERIAL = 8 * 1024 * 1024
MARKERS = (
    "INT_FEED_CHECK:pin:PASS",
    "INT_FEED_CHECK:install-v1:PASS",
    "INT_FEED_CHECK:update-v2:PASS",
    "INT_FEED_CHECK:repeat-v2:PASS",
    "INT_FEED_CASE:success:PASS",
    "INT_FEED_SHUTDOWN",
)
CASE_MARKERS = {
    "empty-rpm-trust": (
        "INT_FEED_CHECK:pin:PASS", "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:empty-rpm-db:PASS", "INT_FEED_CHECK:empty-rpm-rejected:PASS",
        "INT_FEED_CHECK:imported-rpm-accepted:PASS", "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:empty-rpm-trust:PASS", "INT_FEED_SHUTDOWN",
    ),
    "altered-primary": (
        "INT_FEED_CHECK:pin:PASS", "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:primary-metadata:PASS", "INT_FEED_CHECK:primary-fixture:PASS",
        "INT_FEED_CHECK:primary-dnf-rejected:PASS", "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:altered-primary:PASS", "INT_FEED_SHUTDOWN",
    ),
    "stale-rpm-checksum": (
        "INT_FEED_CHECK:pin:PASS", "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:stale-metadata:PASS", "INT_FEED_CHECK:stale-fixture:PASS",
        "INT_FEED_CHECK:stale-dnf-rejected:PASS", "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:stale-rpm-checksum:PASS", "INT_FEED_SHUTDOWN",
    ),
    "success": MARKERS,
    "unsigned-rpm": (
        "INT_FEED_CHECK:pin:PASS",
        "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:unsigned-metadata:PASS",
        "INT_FEED_CHECK:unsigned-rpmkeys:PASS",
        "INT_FEED_CHECK:unsigned-dnf-rejected:PASS",
        "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:unsigned-rpm:PASS",
        "INT_FEED_SHUTDOWN",
    ),
    "wrong-key-rpm": (
        "INT_FEED_CHECK:pin:PASS",
        "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:wrong-key-metadata:PASS",
        "INT_FEED_CHECK:trusted-rpmkeys:PASS",
        "INT_FEED_CHECK:wrong-key-rpmkeys:PASS",
        "INT_FEED_CHECK:wrong-key-dnf-rejected:PASS",
        "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:wrong-key-rpm:PASS",
        "INT_FEED_SHUTDOWN",
    ),
    "corrupt-rpm-indexed": (
        "INT_FEED_CHECK:pin:PASS",
        "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:corrupt-metadata:PASS",
        "INT_FEED_CHECK:trusted-rpmkeys:PASS",
        "INT_FEED_CHECK:corrupt-rpmkeys:PASS",
        "INT_FEED_CHECK:corrupt-dnf-rejected:PASS",
        "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:corrupt-rpm-indexed:PASS",
        "INT_FEED_SHUTDOWN",
    ),
    "missing-metadata-signature": (
        "INT_FEED_CHECK:pin:PASS",
        "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:signed-metadata-control:PASS",
        "INT_FEED_CHECK:missing-signature-fixture:PASS",
        "INT_FEED_CHECK:missing-signature-rejected:PASS",
        "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:missing-metadata-signature:PASS",
        "INT_FEED_SHUTDOWN",
    ),
    "wrong-key-metadata": (
        "INT_FEED_CHECK:pin:PASS",
        "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:signed-metadata-control:PASS",
        "INT_FEED_CHECK:wrong-key-metadata-fixture:PASS",
        "INT_FEED_CHECK:wrong-key-metadata-rejected:PASS",
        "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:wrong-key-metadata:PASS",
        "INT_FEED_SHUTDOWN",
    ),
    "altered-repomd": (
        "INT_FEED_CHECK:pin:PASS",
        "INT_FEED_CHECK:install-v1:PASS",
        "INT_FEED_CHECK:signed-metadata-control:PASS",
        "INT_FEED_CHECK:altered-repomd-fixture:PASS",
        "INT_FEED_CHECK:altered-repomd-rejected:PASS",
        "INT_FEED_CHECK:unchanged-v1:PASS",
        "INT_FEED_CASE:altered-repomd:PASS",
        "INT_FEED_SHUTDOWN",
    ),
}
REQUIRED_PACKAGES = frozenset({"int-feed-smoke", "dnf", "rpm", "gnupg", "gnupg-gpg"})


def validate_feed_manifest(path: Path) -> None:
    # snapshot_inputs has already validated the file format, size and kernel.
    packages = {line.split()[0] for line in path.read_text(encoding="ascii").splitlines()}
    missing = REQUIRED_PACKAGES - packages
    if missing:
        raise ValueError("feed manifest lacks required packages: " + ", ".join(sorted(missing)))


def snapshot_disk(path: Path, artifacts: Path, expected: str) -> dict:
    if not SHA256.fullmatch(expected):
        raise ValueError("fixture disk SHA-256 must be 64 lowercase hexadecimal characters")
    source = path.resolve(strict=True)
    if not source.is_file() or not 0 < source.stat().st_size <= MAX_DISK:
        raise ValueError("fixture disk must be a nonempty regular file within the size limit")
    if smoke.sha256(source) != expected:
        raise ValueError("fixture disk does not match its independently supplied SHA-256")
    target = artifacts / "feed.ext4"
    shutil.copyfile(source, target)
    if not 0 < target.stat().st_size <= MAX_DISK or smoke.sha256(target) != expected:
        raise ValueError("fixture disk changed while copying")
    target.chmod(0o400)
    return {"source": str(path), "resolved_source": str(source), "snapshot": str(target),
            "bytes": target.stat().st_size, "sha256": expected}


def build_qemu_command(executable: str, artifacts: dict, fingerprint: str,
                       test_case: str = "success") -> list[str]:
    if not FINGERPRINT.fullmatch(fingerprint):
        raise ValueError("expected test-key fingerprint must be 40 uppercase hexadecimal characters")
    if test_case not in CASE_MARKERS:
        raise ValueError("unknown feed test case")
    root = artifacts["rootfs"]["snapshot"].replace(",", ",,")
    disk = artifacts["feed_disk"]["snapshot"].replace(",", ",,")
    return [executable, "-nodefaults", "-no-user-config", "-machine", "q35",
            "-accel", "tcg,thread=multi", "-cpu", "qemu64", "-m", "1024", "-smp", "2",
            "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot",
            "-kernel", artifacts["kernel"]["snapshot"],
            "-append", ("root=/dev/vda rw rootwait console=ttyS0,115200n8 panic=1 "
                        f"int_feed_fingerprint={fingerprint} int_feed_case={test_case}"),
            "-drive", f"file={root},format=raw,if=virtio,snapshot=on",
            "-drive", f"file={disk},format=raw,if=virtio,readonly=on", "-nic", "none"]


def execute_qemu(command: list[str], log_path: Path, timeout: float) -> dict:
    """Capture a bounded serial transcript and stop the entire process group."""
    outcome = {"returncode": None, "timed_out": False, "interrupted_signal": None, "output_limit": False}
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + timeout
    count = 0
    try:
        with log_path.open("wb") as serial, selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    outcome["timed_out"] = True
                    break
                events = selector.select(min(remaining, 0.5))
                if not events:
                    continue
                chunk = os.read(process.stdout.fileno(), min(65536, MAX_SERIAL + 1 - count))
                if not chunk:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        outcome["timed_out"] = True
                    else:
                        try:
                            process.wait(timeout=remaining)
                        except subprocess.TimeoutExpired:
                            outcome["timed_out"] = True
                    break
                if count + len(chunk) > MAX_SERIAL:
                    serial.write(chunk[:MAX_SERIAL - count])
                    outcome["output_limit"] = True
                    break
                serial.write(chunk)
                count += len(chunk)
    except (KeyboardInterrupt, smoke.StopRequested) as error:
        outcome["interrupted_signal"] = getattr(error, "signum", signal.SIGINT)
    finally:
        # Reap QEMU and stop any helper still in its process group, even when
        # QEMU itself exited normally before an inherited descriptor closed.
        smoke.terminate_process_group(process, smoke.TERMINATION_GRACE)
        process.stdout.close()
        outcome["returncode"] = process.returncode
    return outcome


def analyze_log(serial: str, process: dict, test_case: str = "success") -> dict:
    if test_case not in CASE_MARKERS:
        raise ValueError("unknown feed test case")
    markers = CASE_MARKERS[test_case]
    lines = serial.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    positions = {marker: [i for i, line in enumerate(lines) if line == marker] for marker in markers}
    shutdown = [i for i, line in enumerate(lines)
                if re.fullmatch(r"(?:\[\s*[0-9.]+\]\s*)?reboot: Power down", line)]
    reasons = []
    if process.get("returncode") != 0:
        reasons.append("QEMU did not exit successfully")
    for flag in ("timed_out", "interrupted_signal", "output_limit"):
        if process.get(flag):
            reasons.append("QEMU " + flag)
    if re.search(r"INT_FEED_[^\r\n]*FAIL|kernel panic|panic - not syncing", serial, re.I):
        reasons.append("guest failure or kernel panic")
    if any(len(pos) != 1 for pos in positions.values()) or len(shutdown) != 1:
        reasons.append("missing or duplicate feed assertions or poweroff")
    else:
        ordered = [positions[marker][0] for marker in markers] + shutdown
        if ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
            reasons.append("feed assertions or poweroff out of order")
    unknown = [line for line in lines if line.startswith("INT_FEED_") and line not in markers]
    if unknown:
        reasons.append("unexpected feed protocol marker")
    return {"passed": not reasons, "failure_reasons": reasons,
            "checks": {marker: len(pos) == 1 for marker, pos in positions.items()},
            "poweroff": len(shutdown) == 1}


def artifact_failures(artifacts: dict) -> list[str]:
    failures = []
    for kind, artifact in artifacts.items():
        try:
            if smoke.sha256(Path(artifact["snapshot"])) != artifact["sha256"]:
                failures.append(f"{kind} snapshot changed during QEMU")
            source = Path(artifact["source"])
            if (source.resolve(strict=True) != Path(artifact["resolved_source"])
                    or smoke.sha256(source) != artifact["sha256"]):
                failures.append(f"{kind} input changed during QEMU")
        except OSError:
            failures.append(f"{kind} input or snapshot could not be verified")
    return failures


def run_feed(deploy: Path, disk: Path, expected_disk_sha256: str, fingerprint: str,
             evidence_root: Path, timeout: float, test_case: str = "success") -> tuple[int, Path]:
    if (not FINGERPRINT.fullmatch(fingerprint) or not SHA256.fullmatch(expected_disk_sha256)
            or test_case not in CASE_MARKERS):
        raise ValueError("invalid independent fingerprint or disk SHA-256")
    run = smoke.create_run_directory(evidence_root)
    started = time.monotonic()
    result = {"schema_version": 1, "status": "running", "started_at_utc": smoke.utc_now(),
              "scope": f"local DNF VM scenario {test_case} only; other cases and network not tested",
              "case": test_case,
              "expected_test_key_fingerprint": fingerprint,
              "expected_fixture_sha256": expected_disk_sha256, "timeout_seconds": timeout,
              "runner_sha256": smoke.sha256(Path(__file__).resolve()),
              "base_runner_sha256": smoke.sha256(Path(smoke.__file__).resolve()),
              "artifacts": {}, "process": {}, "failure_reasons": [], "serial_log": str(run / "serial.log")}
    smoke.write_json(run / "result.json", result)
    (run / "serial.log").touch(mode=0o600)
    code = 1
    try:
        executable = shutil.which("qemu-system-x86_64")
        if not executable:
            raise FileNotFoundError("qemu-system-x86_64 not found")
        result["qemu_version"] = smoke.qemu_version(executable)
        result["artifacts"] = smoke.snapshot_inputs(deploy, run)
        validate_feed_manifest(Path(result["artifacts"]["manifest"]["snapshot"]))
        result["artifacts"]["feed_disk"] = snapshot_disk(disk, run / "artifacts", expected_disk_sha256)
        command = build_qemu_command(executable, result["artifacts"], fingerprint, test_case)
        result["command"] = command
        smoke.write_json(run / "result.json", result)
        result["process"] = execute_qemu(command, run / "serial.log", timeout)
        analysis = analyze_log((run / "serial.log").read_text(encoding="utf-8", errors="replace"),
                               result["process"], test_case)
        result.update(analysis)
        result["failure_reasons"].extend(artifact_failures(result["artifacts"]))
        if not result["failure_reasons"] and result["passed"]:
            result["status"] = "passed"
            code = 0
        elif result["process"].get("interrupted_signal"):
            code = 128 + result["process"]["interrupted_signal"]
    except (KeyboardInterrupt, smoke.StopRequested) as error:
        signum = getattr(error, "signum", signal.SIGINT)
        result["failure_reasons"].append(f"interrupted by signal {signum}")
        code = 128 + signum
    except Exception as error:
        result["failure_reasons"].append(f"{type(error).__name__}: {error}")
    finally:
        result["finished_at_utc"] = smoke.utc_now()
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if result["status"] != "passed":
            result["status"] = "failed"
            shutil.rmtree(run / "artifacts", ignore_errors=True)
        result["passed"] = result["status"] == "passed"
        smoke.write_json(run / "result.json", result)
    print(f"{result['status'].upper()}: {run / 'result.json'}", flush=True)
    return code, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deploy_directory", type=Path)
    parser.add_argument("fixture_disk", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--fingerprint", required=True, help="independently pinned 40-character uppercase test-key fingerprint")
    parser.add_argument("--disk-sha256", required=True, help="independently recorded lowercase fixture disk SHA-256")
    parser.add_argument("--case", choices=tuple(CASE_MARKERS), default="success")
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    if not FINGERPRINT.fullmatch(args.fingerprint) or not SHA256.fullmatch(args.disk_sha256):
        parser.error("invalid fingerprint or disk SHA-256")
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be finite and positive")
    def request_stop(signum, _frame):
        raise smoke.StopRequested(signum)

    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        code, _ = run_feed(args.deploy_directory, args.fixture_disk, args.disk_sha256,
                           args.fingerprint, args.evidence_directory, args.timeout, args.case)
        return code
    except (OSError, ValueError) as error:
        print(f"feed runner error: {error}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
