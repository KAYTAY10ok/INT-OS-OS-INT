#!/usr/bin/env python3
"""Boot the INT development smoke image under QEMU TCG and retain evidence.

This verifies guest assertions and shutdown, not hardware compatibility or
physical performance. Only a complete, failure-free run may create known-good
evidence. No KVM device, host port forwarding, or guest login is required.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
import uuid


CHECKS = (
    "arch",
    "init",
    "identity",
    "libc",
    "filesystems",
    "root-locked",
    "network",
)
INPUTS = {
    "kernel": "bzImage",
    "rootfs": "int-image-smoke-qemux86-64.rootfs.ext4",
    "manifest": "int-image-smoke-qemux86-64.rootfs.manifest",
}
DEFAULT_TIMEOUT = 300.0
TERMINATION_GRACE = 5.0
MAX_KERNEL_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024


class StopRequested(KeyboardInterrupt):
    """Deliver a termination request through the same process cleanup path."""

    def __init__(self, signum: int):
        self.signum = signum


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    """Replace a single run's metadata atomically; never reuse a run directory."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def create_run_directory(evidence_root: Path) -> Path:
    evidence_root = evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run = evidence_root / f"qemu-smoke-{stamp}-{uuid.uuid4().hex[:12]}"
    run.mkdir(mode=0o700)
    return run


def read_kernel_release(path: Path) -> str:
    """Read only the bounded x86 boot-header version, not arbitrary strings."""
    size = path.stat().st_size
    if not 0x210 <= size <= MAX_KERNEL_BYTES:
        raise ValueError("kernel size is outside the supported bzImage bounds")
    with path.open("rb") as stream:
        header = stream.read(0x210)
        if len(header) != 0x210 or header[0x202:0x206] != b"HdrS":
            raise ValueError("kernel has no valid x86 HdrS boot header")
        offset = 0x200 + struct.unpack_from("<H", header, 0x20e)[0]
        if not 0x210 <= offset < size:
            raise ValueError("kernel version pointer is outside the supported image data")
        stream.seek(offset)
        raw = stream.read(min(256, size - offset))
    end = raw.find(b"\0")
    if end <= 0:
        raise ValueError("kernel version is empty or not terminated within 256 bytes")
    try:
        version = raw[:end].decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("kernel version is not ASCII") from None
    if any(ord(character) < 32 or ord(character) > 126 for character in version):
        raise ValueError("kernel version contains control characters")
    tokens = version.split()
    release = tokens[0] if tokens else ""
    if version[0].isspace() or not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]{0,63}", release):
        raise ValueError("kernel release is not a supported Linux release token")
    return release


def validate_kernel_manifest(kernel: Path, manifest: Path) -> str:
    """Reject a deployment alias pointing at a different kernel ABI release.

    This matches release/package names, not kernel configuration or module
    content. Identical release names do not establish identical build hashes.
    """
    release = read_kernel_release(kernel)
    if not 0 < manifest.stat().st_size <= MAX_MANIFEST_BYTES:
        raise ValueError("package manifest size is outside supported bounds")
    with manifest.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("package manifest exceeded the size limit while reading")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("package manifest is not ASCII") from None
    if any(ord(character) < 32 and character not in "\r\n" for character in text):
        raise ValueError("package manifest contains unsupported control characters")
    lines = text.splitlines()
    packages = set()
    for number, line in enumerate(lines, 1):
        fields = line.split()
        if len(fields) != 3 or any(ord(character) < 32 or ord(character) > 126
                                   for character in line):
            raise ValueError(f"malformed package manifest line {number}")
        name = fields[0]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]*", name):
            raise ValueError(f"invalid package name on manifest line {number}")
        if name in packages:
            raise ValueError(f"ambiguous duplicate package on manifest line {number}")
        packages.add(name)
    expected = "kernel-" + release
    kernel_packages = {name for name in packages if re.match(r"kernel-[0-9]", name)}
    if kernel_packages != {expected}:
        raise ValueError(f"manifest must contain exactly the kernel package {expected}")
    incompatible = sorted(name for name in packages
                          if name.startswith("kernel-module-") and not name.endswith("-" + release))
    if incompatible:
        raise ValueError("kernel module package release differs from the bzImage release")
    return release


def snapshot_inputs(deploy: Path, run: Path) -> dict:
    sources = {}
    for kind, filename in INPUTS.items():
        source = deploy / filename
        resolved = source.resolve(strict=True)
        if not resolved.is_file() or resolved.stat().st_size == 0:
            raise ValueError(f"required {kind} is not a nonempty file: {source}")
        sources[kind] = (source, resolved)
    # Reject bad/sparse oversized headers and mismatched manifests before
    # copying any large disk image or launching a guest.
    validate_kernel_manifest(sources["kernel"][1], sources["manifest"][1])
    artifacts = run / "artifacts"
    artifacts.mkdir(mode=0o700)
    copied = {}
    for kind, filename in INPUTS.items():
        source, resolved = sources[kind]
        destination = artifacts / filename
        shutil.copyfile(resolved, destination)
        copied[kind] = {
            "source": str(source),
            "resolved_source": str(resolved),
            "snapshot": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
        }
    # Validate the exact copies too, so a deployment update during copying
    # cannot make the preflight check apply to different bytes.
    release = validate_kernel_manifest(Path(copied["kernel"]["snapshot"]),
                                       Path(copied["manifest"]["snapshot"]))
    copied["kernel"]["kernel_release"] = release
    copied["manifest"]["kernel_release"] = release
    return copied


def qemu_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def build_qemu_command(executable: str, artifacts: dict) -> list[str]:
    # QEMU's comma-delimited drive syntax escapes a literal comma by doubling it.
    rootfs = artifacts["rootfs"]["snapshot"].replace(",", ",,")
    return [
        executable,
        "-nodefaults",
        "-no-user-config",
        "-machine", "q35",
        "-accel", "tcg,thread=multi",
        "-cpu", "qemu64",
        "-m", "512",
        "-smp", "2",
        "-display", "none",
        "-serial", "stdio",
        "-monitor", "none",
        "-no-reboot",
        "-kernel", artifacts["kernel"]["snapshot"],
        "-append", "root=/dev/vda rw rootwait console=ttyS0,115200n8 panic=1",
        "-drive", f"file={rootfs},format=raw,if=virtio,snapshot=on",
        "-netdev", "user,id=net0,restrict=on",
        "-device", "virtio-net-pci,netdev=net0",
    ]


def terminate_process_group(process: subprocess.Popen, grace: float) -> None:
    """Stop QEMU and any child helpers, then reap the direct child."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # A helper can outlive the parent after SIGTERM. Kill the entire group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def execute_qemu(
    command: list[str], log_path: Path, timeout: float,
    termination_grace: float = TERMINATION_GRACE,
) -> dict:
    outcome = {"returncode": None, "timed_out": False, "interrupted_signal": None}
    with log_path.open("wb") as serial:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=serial,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            outcome["timed_out"] = True
            terminate_process_group(process, termination_grace)
        except (KeyboardInterrupt, StopRequested) as error:
            outcome["interrupted_signal"] = getattr(error, "signum", signal.SIGINT)
            terminate_process_group(process, termination_grace)
        except BaseException:
            terminate_process_group(process, termination_grace)
            raise
        outcome["returncode"] = process.returncode
    return outcome


def analyze_log(serial: str, process: dict) -> dict:
    """Require every exact assertion before a single terminal PASS marker."""
    lines = serial.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    positions = {
        name: [i for i, line in enumerate(lines) if line == f"INT_CHECK:{name}:PASS"]
        for name in CHECKS
    }
    checks = {name: bool(found) for name, found in positions.items()}
    passes = [i for i, line in enumerate(lines) if line == "INT_SMOKE_PASS"]
    reasons = []
    if process.get("timed_out"):
        reasons.append("QEMU exceeded the boot/shutdown timeout")
    if process.get("interrupted_signal"):
        reasons.append(f"runner interrupted by signal {process['interrupted_signal']}")
    if process.get("returncode") != 0:
        reasons.append(f"QEMU returned {process.get('returncode')!r}, expected 0")
    if "INT_SMOKE_FAIL" in serial:
        reasons.append("guest emitted INT_SMOKE_FAIL")
    if re.search(r"kernel panic|panic - not syncing", serial, re.IGNORECASE):
        reasons.append("kernel panic observed")
    if re.search(r"^INT_CHECK:[^:\r\n]+:FAIL(?:\b|$)", serial, re.MULTILINE):
        reasons.append("guest emitted a failed assertion")
    missing = [name for name, passed in checks.items() if not passed]
    if missing:
        reasons.append("missing guest assertions: " + ", ".join(missing))
    if len(passes) != 1:
        reasons.append(f"expected one exact INT_SMOKE_PASS line, observed {len(passes)}")
    elif not missing and any(found[0] >= passes[0] for found in positions.values()):
        reasons.append("INT_SMOKE_PASS preceded a required assertion")
    return {"passed": not reasons, "checks": checks, "failure_reasons": reasons}


def run_smoke(deploy: Path, evidence_root: Path, timeout: float) -> tuple[int, Path]:
    run = create_run_directory(evidence_root)
    print(f"QEMU smoke evidence: {run}", flush=True)
    started = time.monotonic()
    metadata = {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": utc_now(),
        "deploy_directory": str(deploy.resolve()),
        "timeout_seconds": timeout,
        "termination_grace_seconds": TERMINATION_GRACE,
        "python_version": sys.version,
        "host_platform": platform.platform(),
        "emulation": "QEMU TCG, qemu64, 512 MiB RAM, 2 virtual CPUs",
        "measurement_scope": "functional virtual-machine smoke test; not physical performance",
        "runner_sha256": sha256(Path(__file__).resolve()),
        "command": None,
        "artifacts": {},
        "checks": {name: False for name in CHECKS},
        "failure_reasons": [],
        "process": {"returncode": None, "timed_out": False, "interrupted_signal": None},
        "serial_log": str(run / "serial.log"),
    }
    write_json(run / "result.json", metadata)
    (run / "serial.log").touch()
    exit_code = 1
    try:
        executable = shutil.which("qemu-system-x86_64")
        if not executable:
            raise FileNotFoundError("qemu-system-x86_64 is not installed or not on PATH")
        metadata["qemu_version"] = qemu_version(executable)
        metadata["artifacts"] = snapshot_inputs(deploy.resolve(), run)
        command = build_qemu_command(executable, metadata["artifacts"])
        metadata["command"] = command
        write_json(run / "result.json", metadata)
        metadata["process"] = execute_qemu(command, run / "serial.log", timeout)
        analysis = analyze_log(
            (run / "serial.log").read_text(encoding="utf-8", errors="replace"),
            metadata["process"],
        )
        metadata["checks"] = analysis["checks"]
        metadata["failure_reasons"] = analysis["failure_reasons"]
        for kind, artifact in metadata["artifacts"].items():
            if sha256(Path(artifact["snapshot"])) != artifact["sha256"]:
                metadata["failure_reasons"].append(f"{kind} snapshot changed during QEMU run")
        if not metadata["failure_reasons"]:
            metadata["status"] = "passed"
            exit_code = 0
        interrupted = metadata["process"].get("interrupted_signal")
        if interrupted:
            exit_code = 128 + interrupted
    except (KeyboardInterrupt, StopRequested) as error:
        signum = getattr(error, "signum", signal.SIGINT)
        metadata["process"]["interrupted_signal"] = signum
        metadata["failure_reasons"].append(f"runner interrupted by signal {signum}")
        exit_code = 128 + signum
    except Exception as error:
        metadata["failure_reasons"].append(f"{type(error).__name__}: {error}")
    finally:
        metadata["finished_at_utc"] = utc_now()
        metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if metadata["status"] != "passed":
            metadata["status"] = "failed"
            shutil.rmtree(run / "artifacts", ignore_errors=True)
            metadata["artifact_copies_retained"] = False
        else:
            metadata["artifact_copies_retained"] = True
        write_json(run / "result.json", metadata)
        if metadata["status"] == "passed":
            write_json(run / "known-good.json", {
                "schema_version": 1,
                "result": str(run / "result.json"),
                "artifacts": metadata["artifacts"],
                "verified_at_utc": metadata["finished_at_utc"],
            })
    print(f"{metadata['status'].upper()}: {run / 'result.json'}", flush=True)
    return exit_code, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deploy_directory", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="boot and shutdown deadline in seconds (default: 300)")
    args = parser.parse_args(argv)
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")

    def request_stop(signum, _frame):
        raise StopRequested(signum)

    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        code, _run = run_smoke(args.deploy_directory, args.evidence_directory, args.timeout)
        return code
    except OSError as error:
        print(f"cannot create or write smoke evidence: {error}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
