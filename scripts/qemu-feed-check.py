#!/usr/bin/env python3
"""Run signed-feed DNF cases in disposable QEMU guests and retain evidence.

Each case boots int-image-feed-smoke from a fresh copy-on-write snapshot with
no network device. The fixture EXT4 disk is attached read-only and its hash is
checked against an independently supplied value before and after every case.
The expected full signing fingerprint is passed on the kernel command line,
not read from the fixture disk. This qualifies only the tested disposable
fixtures; it is not a production feed, key custody or update-recovery test.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import sys
import time

SMOKE_PATH = Path(__file__).with_name("qemu-smoke.py")
_spec = importlib.util.spec_from_file_location("int_qemu_smoke", SMOKE_PATH)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

INPUTS = {
    "kernel": "bzImage",
    "rootfs": "int-image-feed-smoke-qemux86-64.rootfs.ext4",
    "manifest": "int-image-feed-smoke-qemux86-64.rootfs.manifest",
}
COMMON = ("fixture-mounted", "pinned-key", "rpm-signature-backend", "rpm-empty-trust-rejected",
          "clean-initial-state", "metadata-v1", "installed-v1")
VALID = COMMON + ("metadata-v2", "installed-v2", "installed-repeat")
NEGATIVE = COMMON + ("rejected", "installed-unchanged", "trust-unchanged")
CASES = ("valid", "wrong-key-metadata", "altered-repomd", "missing-metadata-signature",
         "missing-repo-key", "wrong-configured-key", "altered-primary", "stale-rpm-checksum",
         "unsigned-rpm", "wrong-key-rpm", "corrupt-rpm-indexed")
REQUIRED_PACKAGES = ("rpm", "dnf", "gnupg", "int-feed-smoke", "python3-core")
DEFAULT_TIMEOUT = 1800.0
FINGERPRINT = re.compile(r"[0-9A-F]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def expected_checks(case: str) -> tuple[str, ...]:
    return VALID if case == "valid" else NEGATIVE


def analyze_log(serial: str, process: dict, case: str) -> dict:
    """Require each exact check once, in order, then one exact case PASS."""
    lines = serial.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    checks = expected_checks(case)
    reasons = []
    if process.get("timed_out"):
        reasons.append("QEMU exceeded the case timeout")
    if process.get("interrupted_signal"):
        reasons.append(f"runner interrupted by signal {process['interrupted_signal']}")
    if process.get("returncode") != 0:
        reasons.append(f"QEMU returned {process.get('returncode')!r}, expected 0")
    if any(line.startswith("INT_FEED_FAIL") for line in lines):
        reasons.append("guest emitted INT_FEED_FAIL")
    if re.search(r"kernel panic|panic - not syncing", serial, re.IGNORECASE):
        reasons.append("kernel panic observed")
    begins = [i for i, line in enumerate(lines) if line == f"INT_FEED_BEGIN:{case}"]
    if len(begins) != 1:
        reasons.append(f"expected one INT_FEED_BEGIN:{case}, observed {len(begins)}")
    observed = [line.split(":")[1] for line in lines
                if line.startswith("INT_FEED_CHECK:") and line.endswith(":PASS") and line.count(":") == 2]
    if observed != list(checks):
        reasons.append(f"guest checks {observed} differ from required {list(checks)}")
    passes = [i for i, line in enumerate(lines) if line.startswith("INT_FEED_CASE:")]
    if [lines[i] for i in passes] != [f"INT_FEED_CASE:{case}:PASS"]:
        reasons.append("expected exactly one final INT_FEED_CASE PASS line for this case")
    else:
        last_check = max((i for i, line in enumerate(lines) if line.startswith("INT_FEED_CHECK:")), default=-1)
        if begins and not begins[0] < last_check < passes[0]:
            reasons.append("case PASS was not preceded by every required check")
    if not re.search(r"reboot: Power down|System halted|Power down", serial):
        reasons.append("no clean power-down observed")
    info = [line for line in lines if line.startswith(("INT_FEED_INFO:", "INT_FEED_DIAG:"))]
    return {"passed": not reasons, "observed_checks": observed, "failure_reasons": reasons,
            "guest_report": info[:400]}


def validate_manifest_packages(manifest: Path) -> list[str]:
    packages = {line.split()[0] for line in manifest.read_text(encoding="ascii").splitlines() if line.strip()}
    missing = [name for name in REQUIRED_PACKAGES if name not in packages]
    if missing:
        raise ValueError("image manifest lacks required packages: " + ", ".join(missing))
    return sorted(name for name in packages if re.match(r"(rpm|dnf|gnupg|librepo|libdnf|rpm-sequoia)", name))


def snapshot_inputs(deploy: Path, run: Path) -> dict:
    original = smoke.INPUTS
    smoke.INPUTS = INPUTS
    try:
        return smoke.snapshot_inputs(deploy, run)
    finally:
        smoke.INPUTS = original


def build_qemu_command(executable: str, artifacts: dict, feed_disk: Path, case: str,
                       fingerprint: str) -> list[str]:
    rootfs = artifacts["rootfs"]["snapshot"].replace(",", ",,")
    disk = str(feed_disk).replace(",", ",,")
    append = (f"root=/dev/vda rw rootwait console=ttyS0,115200n8 panic=1 "
              f"int.feed_case={case} int.feed_fpr={fingerprint}")
    return [
        executable, "-nodefaults", "-no-user-config",
        "-machine", "q35", "-accel", "tcg,thread=multi", "-cpu", "qemu64",
        "-m", "1024", "-smp", "2", "-display", "none", "-serial", "stdio",
        "-monitor", "none", "-no-reboot", "-nic", "none",
        "-kernel", artifacts["kernel"]["snapshot"], "-append", append,
        "-drive", f"file={rootfs},format=raw,if=virtio,snapshot=on",
        "-drive", f"file={disk},format=raw,if=virtio,readonly=on",
    ]


def check_feed_disk(feed: Path, expected: str) -> dict:
    disk = feed / "feed.ext4"
    report = json.loads((feed / "report.json").read_text(encoding="utf-8"))
    actual = smoke.sha256(disk)
    if report.get("image", {}).get("sha256") != actual:
        raise ValueError("feed.ext4 does not match its report.json hash")
    if actual != expected:
        raise ValueError("feed.ext4 does not match the independently supplied --feed-sha256")
    return {"path": str(disk), "sha256": actual, "bytes": disk.stat().st_size,
            "source_manifest_sha256": report.get("source_manifest_sha256")}


def run_case(executable, artifacts, feed, args, case, evidence) -> dict:
    case_dir = evidence / case
    case_dir.mkdir(mode=0o700)
    serial = case_dir / "serial.log"
    before = check_feed_disk(feed, args.feed_sha256)
    command = build_qemu_command(executable, artifacts, Path(before["path"]), case, args.fingerprint)
    started = time.monotonic()
    process = smoke.execute_qemu(command, serial, args.timeout)
    result = analyze_log(serial.read_text(encoding="utf-8", errors="replace"), process, case)
    result.update(case=case, command=command, process=process,
                  elapsed_seconds=round(time.monotonic() - started, 3), serial_log=str(serial))
    try:
        result["feed_disk_after"] = check_feed_disk(feed, args.feed_sha256)
    except (OSError, ValueError) as error:
        result["passed"] = False
        result["failure_reasons"].append(f"fixture disk changed or unreadable after run: {error}")
    for kind, artifact in artifacts.items():
        if smoke.sha256(Path(artifact["snapshot"])) != artifact["sha256"]:
            result["passed"] = False
            result["failure_reasons"].append(f"{kind} snapshot changed during QEMU run")
    smoke.write_json(case_dir / "result.json", result)
    print(f"{'PASS' if result['passed'] else 'FAIL'} {case} ({result['elapsed_seconds']} s)", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deploy_directory", type=Path)
    parser.add_argument("feed_directory", type=Path, help="feed-disk.py output with feed.ext4 and report.json")
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--fingerprint", required=True, help="independently obtained full primary fingerprint")
    parser.add_argument("--feed-sha256", required=True, help="independently recorded feed.ext4 SHA-256")
    parser.add_argument("--case", action="append", choices=CASES, help="repeatable; default: all cases")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    if not FINGERPRINT.fullmatch(args.fingerprint):
        parser.error("--fingerprint must be 40 uppercase hexadecimal digits")
    if not SHA256.fullmatch(args.feed_sha256):
        parser.error("--feed-sha256 must be 64 lowercase hexadecimal digits")
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")
    cases = args.case or list(CASES)

    def request_stop(signum, _frame):
        raise smoke.StopRequested(signum)

    signal.signal(signal.SIGTERM, request_stop)
    run = smoke.create_run_directory(args.evidence_directory)
    run = run.rename(run.with_name(run.name.replace("qemu-smoke-", "qemu-feed-")))
    print(f"QEMU feed evidence: {run}", flush=True)
    metadata = {"schema_version": 1, "status": "running", "started_at_utc": smoke.utc_now(),
                "scope": "disposable file:// signed-feed DNF cases in QEMU TCG; no network, "
                         "production key custody, freshness/replay or recovery claim",
                "fingerprint": args.fingerprint, "feed_sha256": args.feed_sha256, "cases": {},
                "runner_sha256": smoke.sha256(Path(__file__).resolve()),
                "host_platform": platform.platform(), "failure_reasons": []}
    smoke.write_json(run / "result.json", metadata)
    code = 1
    try:
        executable = shutil.which("qemu-system-x86_64")
        if not executable:
            raise FileNotFoundError("qemu-system-x86_64 is not installed or not on PATH")
        metadata["qemu_version"] = smoke.qemu_version(executable)
        artifacts = snapshot_inputs(args.deploy_directory.resolve(), run)
        metadata["artifacts"] = artifacts
        metadata["image_packages"] = validate_manifest_packages(Path(artifacts["manifest"]["snapshot"]))
        metadata["feed_disk"] = check_feed_disk(args.feed_directory.resolve(), args.feed_sha256)
        for case in cases:
            outcome = run_case(executable, artifacts, args.feed_directory.resolve(), args, case, run)
            metadata["cases"][case] = {key: outcome[key] for key in
                                       ("passed", "failure_reasons", "elapsed_seconds", "serial_log")}
            smoke.write_json(run / "result.json", metadata)
        failed = [case for case, outcome in metadata["cases"].items() if not outcome["passed"]]
        if failed:
            metadata["failure_reasons"].append("failed cases: " + ", ".join(failed))
        else:
            metadata["status"] = "passed"
            code = 0
    except smoke.StopRequested as error:
        metadata["failure_reasons"].append(f"runner interrupted by signal {error.signum}")
        code = 128 + error.signum
    except Exception as error:
        metadata["failure_reasons"].append(f"{type(error).__name__}: {error}")
    finally:
        if metadata["status"] != "passed":
            metadata["status"] = "failed"
        metadata["finished_at_utc"] = smoke.utc_now()
        # Retain only hashes; image copies are large and reproducible from the hashes' sources.
        shutil.rmtree(run / "artifacts", ignore_errors=True)
        smoke.write_json(run / "result.json", metadata)
    print(f"{metadata['status'].upper()}: {run / 'result.json'}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
