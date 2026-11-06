#!/usr/bin/env python3
"""Check effective metadata instead of assuming source assignments won overrides."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def value(name, recipe=None):
    args = ["bitbake-getvar", "--value"]
    if recipe:
        args += ["-r", recipe]
    return subprocess.check_output([*args, name], text=True).strip()


def generic_x86_64_flags(raw):
    # security_flags.inc also appends -f/-D/-W hardening flags to TARGET_CC_ARCH.
    # Validate machine flags without rejecting those protections.
    machine_flags = {flag for flag in shlex.split(raw) if flag.startswith("-m")}
    return "-m64" in machine_flags and not machine_flags - {
        "-m64", "-march=x86-64", "-mtune=generic"
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["core", "desktop", "feed"], default="core")
    args = parser.parse_args()
    subprocess.run(["bitbake", "-p"], check=True)
    lock = json.loads(Path("/src/configs/sources.lock.json").read_text())
    kernel = lock["kernel"].copy()
    if args.profile == "desktop":
        kernel["local_version"] = lock["profiles"]["desktop"]["kernel_local_version"]
        kernel["recipe_revision"] = lock["profiles"]["desktop"]["kernel_recipe_revision"]
    expected = {
        "DISTRO": "int-linux", "MACHINE": "qemux86-64", "DEFAULTTUNE": "x86-64",
        "TCLIBC": "glibc", "INIT_MANAGER": "systemd", "PACKAGE_CLASSES": "package_rpm",
    }
    observed = {name: value(name) for name in expected}
    failures = [f"{key}: expected {want!r}, got {observed[key]!r}"
                for key, want in expected.items() if observed[key] != want]
    observed["TUNE_FEATURES"] = value("TUNE_FEATURES")
    observed["TARGET_CC_ARCH"] = value("TARGET_CC_ARCH")
    if set(observed["TUNE_FEATURES"].split()) != {"m64"}:
        failures.append("unexpected CPU features; the foundation must use the m64 baseline")
    # OE's generic m64 tune emits -m64, relying on GCC's x86-64 default.
    # Reject any narrower architecture tuning rather than require a flag OE
    # does not emit. The real guest is also exercised on the qemu64 CPU.
    if not generic_x86_64_flags(observed["TARGET_CC_ARCH"]):
        failures.append("compiler architecture flags do not use the generic x86-64 baseline")
    for name, key in (("SRCREV_machine", "machine_revision"), ("SRCREV_meta", "metadata_revision"),
                      ("LINUX_VERSION_EXTENSION", "local_version"), ("PR", "recipe_revision")):
        observed[name] = value(name, "linux-yocto")
        if observed[name] != kernel[key]:
            failures.append(f"kernel {name} differs from sources.lock.json")
    if args.profile == "desktop":
        observed["DISTRO_FEATURES"] = value("DISTRO_FEATURES")
        if not {"wayland", "opengl"}.issubset(observed["DISTRO_FEATURES"].split()):
            failures.append("desktop profile requires Wayland and OpenGL features")
        desktop = {}
        for recipe, names in {
            "mesa": ("PACKAGECONFIG",),
            "sway-1.11": ("PV", "RRECOMMENDS:sway-1.11"),
            "wlroots-0.19": ("PV",),
            "fuzzel": ("PACKAGECONFIG",),
            "seatd": ("PACKAGECONFIG", "SYSTEMD_AUTO_ENABLE"),
        }.items():
            desktop[recipe] = {name: value(name, recipe) for name in names}
        observed["desktop_packages"] = desktop
        mesa = set(desktop["mesa"]["PACKAGECONFIG"].split())
        if not {"egl", "gles", "gbm", "gallium", "wayland", "virtio"}.issubset(mesa):
            failures.append("desktop QEMU Mesa lacks a required rendering feature")
        if mesa & {"intel", "amd", "nouveau", "svga", "libclc", "gallium-llvm"}:
            failures.append("desktop QEMU prototype unexpectedly enables hardware/LLVM drivers")
        if desktop["sway-1.11"]["PV"] != "1.11" or desktop["wlroots-0.19"]["PV"] != "0.19.3":
            failures.append("desktop compositor recipes differ from the selected stable versions")
        if desktop["sway-1.11"]["RRECOMMENDS:sway-1.11"].strip():
            failures.append("desktop optional Sway applications must be selected explicitly")
        if "librsvg" in desktop["fuzzel"]["PACKAGECONFIG"].split():
            failures.append("desktop prototype unexpectedly enables the librsvg/Rust backend")
        if ("systemd" not in desktop["seatd"]["PACKAGECONFIG"].split()
                or "libseat-builtin" in desktop["seatd"]["PACKAGECONFIG"].split()
                or desktop["seatd"]["SYSTEMD_AUTO_ENABLE"] != "disable"):
            failures.append("desktop seat access must use logind without an enabled seatd daemon")
    if args.profile == "feed":
        observed["rpm_packageconfig"] = {recipe: value("PACKAGECONFIG", recipe)
                                         for recipe in ("rpm-native", "rpm")}
        for recipe, config in observed["rpm_packageconfig"].items():
            if "sequoia" not in config.split():
                failures.append(f"{recipe} lacks the OpenPGP backend required for the feed lab")
    print(json.dumps({"effective_configuration": observed, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
