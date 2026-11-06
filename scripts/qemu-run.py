#!/usr/bin/env python3
"""Boot a built INT image in QEMU for hands-on testing.

This is a developer convenience, not a test: it records no evidence and
proves nothing about the image. It never modifies the deployed build
artifacts. The first run copies the kernel and root filesystem into a private
state directory, so first-owner enrollment and files persist across boots of
that copy; --reset starts again from the deployed image. The guest gets
outbound user-mode networking only; no host port is forwarded.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

_spec = importlib.util.spec_from_file_location("int_qemu_smoke", Path(__file__).with_name("qemu-smoke.py"))
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

PROFILES = {
    "core": {"build": "build", "image": "int-image-core", "memory": "1024"},
    "desktop": {"build": "build-desktop", "image": "int-image-desktop", "memory": "2048"},
}


def artifacts(deploy: Path, image: str) -> dict[str, Path]:
    names = {
        "kernel": "bzImage",
        "rootfs": f"{image}-qemux86-64.rootfs.ext4",
        "manifest": f"{image}-qemux86-64.rootfs.manifest",
    }
    found = {}
    for kind, name in names.items():
        path = (deploy / name).resolve(strict=False)
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"{kind} not found: {deploy / name}; build {image} first")
        found[kind] = path
    smoke.validate_kernel_manifest(found["kernel"], found["manifest"])
    return found


def prepare_state(sources: dict[str, Path], state: Path, reset: bool) -> dict[str, Path]:
    """Copy the deployed kernel/rootfs once; reuse that writable copy later."""
    record = state / "source.json"
    if reset and state.exists():
        shutil.rmtree(state)
    if not record.is_file():
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        copied = {}
        for kind in ("kernel", "rootfs"):
            target = state / sources[kind].name
            shutil.copyfile(sources[kind], target)
            copied[kind] = {"source": str(sources[kind]), "sha256": smoke.sha256(sources[kind])}
        smoke.write_json(record, copied)
    else:
        copied = json.loads(record.read_text())
        current = smoke.sha256(sources["rootfs"])
        if copied["rootfs"]["sha256"] != current:
            print("note: the deployed image changed since this state was created; "
                  "use --reset to test the new build", file=sys.stderr)
    return {kind: state / Path(copied[kind]["source"]).name for kind in ("kernel", "rootfs")}


def accelerator() -> list[str]:
    if os.access("/dev/kvm", os.R_OK | os.W_OK):
        return ["-accel", "kvm", "-cpu", "host"]
    return ["-accel", "tcg,thread=multi", "-cpu", "qemu64"]


def qemu_command(executable: str, files: dict[str, Path], profile: str, display: str) -> list[str]:
    rootfs = str(files["rootfs"]).replace(",", ",,")
    command = [executable, "-nodefaults", "-no-user-config", "-machine", "q35", *accelerator(),
               "-m", PROFILES[profile]["memory"], "-smp", "2",
               "-kernel", str(files["kernel"]),
               "-drive", f"file={rootfs},format=raw,if=virtio",
               "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0"]
    if profile == "desktop":
        # The last console= becomes /dev/console, where owner enrollment runs.
        append = "root=/dev/vda rw rootwait console=ttyS0,115200n8 console=tty0"
        command += ["-vga", "virtio", "-device", "virtio-keyboard-pci", "-device", "virtio-tablet-pci",
                    "-display", display, "-serial", "file:" + str(files["rootfs"].parent / "serial.log"),
                    "-monitor", "none"]
    else:
        append = "root=/dev/vda rw rootwait console=ttyS0,115200n8"
        command += ["-display", "none", "-serial", "mon:stdio"]
    return command + ["-append", append]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="core")
    parser.add_argument("--workdir", type=Path, required=True, help="INT work directory")
    parser.add_argument("--image", help="image recipe name (default depends on profile)")
    parser.add_argument("--reset", action="store_true", help="discard the saved test state first")
    parser.add_argument("--display", default="gtk", help="QEMU display for the desktop (gtk, sdl)")
    parser.add_argument("--dry-run", action="store_true", help="print the QEMU command only")
    args = parser.parse_args(argv)
    settings = PROFILES[args.profile]
    image = args.image or settings["image"]
    deploy = args.workdir / settings["build"] / "tmp/deploy/images/qemux86-64"
    try:
        sources = artifacts(deploy, image)
        files = prepare_state(sources, args.workdir / "run" / image, args.reset)
        executable = shutil.which("qemu-system-x86_64")
        if not executable:
            raise FileNotFoundError("qemu-system-x86_64 is not installed on this machine "
                                    "(Debian/Ubuntu: apt install qemu-system-x86)")
        command = qemu_command(executable, files, args.profile, args.display)
    except (OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(" ".join(command))
        return 0
    if args.profile == "core":
        print("Serial console follows. On first boot, create the owner account. "
              "Quit QEMU with Ctrl-A then X.", flush=True)
    else:
        print("A QEMU window opens. On first boot, create the owner account there, log in, "
              "then run start-int-desktop. Serial log: " + str(files["rootfs"].parent / "serial.log"),
              flush=True)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
