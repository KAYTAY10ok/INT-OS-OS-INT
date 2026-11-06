#!/usr/bin/env python3
"""Copy a bounded, manifested test fixture tree into a disposable EXT4 image.

This checks file integrity against the supplied manifest, not its authenticity
or any RPM, OpenPGP, repository, or DNF behavior.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

MAX_MANIFEST = 2 * 1024 * 1024
MAX_CONTENT = 100 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_DEPTH = 8
MAX_PATH = 512
COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
DIR_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY


class DiskError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise DiskError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Manifest contains duplicate JSON keys")
        result[key] = value
    return result


def valid_path(value):
    if not isinstance(value, str) or not value or len(value) > MAX_PATH:
        return False
    parts = value.split("/")
    return len(parts) <= MAX_DEPTH and all(COMPONENT.fullmatch(part) and part not in (".", "..") for part in parts)


def read_regular(directory_fd, name, limit):
    fd = os.open(name, READ_FLAGS, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                f"Not a regular file with exactly one hard link: {name}")
        require(0 <= info.st_size <= limit, f"File is too large: {name}")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        require(len(data) == info.st_size and len(data) <= limit,
                f"File changed or exceeded the limit: {name}")
        return data
    finally:
        os.close(fd)


def parse_manifest(raw):
    try:
        report = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise DiskError("Invalid fixture manifest") from error
    require(isinstance(report, dict) and isinstance(report.get("files"), dict), "Missing fixture file list")
    files = report["files"]
    require(0 < len(files) <= MAX_ENTRIES, "Invalid number of fixture files")
    total = 0
    for name, info in files.items():
        require(valid_path(name) and name != "manifest.json", "Unsafe manifest path")
        require(isinstance(info, dict) and type(info.get("bytes")) is int and
                0 <= info["bytes"] <= MAX_CONTENT and
                isinstance(info.get("sha256"), str) and SHA256.fullmatch(info["sha256"]),
                f"Invalid manifest entry: {name}")
        total += info["bytes"]
        require(total <= MAX_CONTENT, "Fixture content exceeds the size limit")
    return files, total


def copy_verified(source_fd, stage):
    raw_manifest = read_regular(source_fd, "manifest.json", MAX_MANIFEST)
    files, total = parse_manifest(raw_manifest)
    expected_dirs = {"/".join(name.split("/")[:i]) for name in files
                     for i in range(1, len(name.split("/")))}
    seen, dirs = set(), set()
    entries = 0

    def visit(fd, parts):
        nonlocal entries
        with os.scandir(fd) as scan:
            names = sorted(entry.name for entry in scan)
        for name in names:
            entries += 1
            require(entries <= MAX_ENTRIES, "Too many fixture entries")
            relative = "/".join((*parts, name))
            require(valid_path(relative), "Unsafe fixture path")
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                require(relative in expected_dirs, f"Unexpected directory: {relative}")
                child = os.open(name, DIR_FLAGS, dir_fd=fd)
                try:
                    actual = os.fstat(child)
                    require((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino),
                            "Directory changed during inspection")
                    (stage / relative).mkdir(mode=0o755)
                    dirs.add(relative)
                    visit(child, (*parts, name))
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                require(relative == "manifest.json" or relative in files, f"Unexpected file: {relative}")
                limit = MAX_MANIFEST if relative == "manifest.json" else files[relative]["bytes"]
                data = read_regular(fd, name, limit)
                if relative == "manifest.json":
                    require(data == raw_manifest, "Manifest changed during inspection")
                else:
                    expected = files[relative]
                    require(len(data) == expected["bytes"] and hashlib.sha256(data).hexdigest() == expected["sha256"],
                            f"Fixture hash or size mismatch: {relative}")
                (stage / relative).write_bytes(data)
                seen.add(relative)
            else:
                raise DiskError(f"Unsupported fixture entry: {relative}")

    visit(source_fd, ())
    require(seen == set(files) | {"manifest.json"} and dirs == expected_dirs, "Fixture tree is incomplete")
    return raw_manifest, files, total


def canonical_existing(path):
    absolute = Path(os.path.abspath(path))
    require(absolute.resolve(strict=True) == absolute, f"Symlink in path: {absolute}")
    require(absolute.is_dir(), f"Not a directory: {absolute}")
    return absolute


def build(source, destination):
    source = canonical_existing(source)
    dest = Path(os.path.abspath(destination))
    parent = canonical_existing(dest.parent)
    require(dest.name not in ("", ".", "..") and COMPONENT.fullmatch(dest.name), "Invalid output directory name")
    require(source != parent and source not in parent.parents, "Output must be outside the fixture tree")
    tool = shutil.which("mke2fs")
    require(tool is not None, "mke2fs is required on PATH")
    version = subprocess.run([tool, "-V"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=15, check=True).stdout.splitlines()[0]
    source_fd = os.open(source, DIR_FLAGS)
    try:
        with tempfile.TemporaryDirectory(prefix=".int-feed-stage-", dir=parent) as temp:
            stage = Path(temp) / "files"
            stage.mkdir(mode=0o700)
            raw_manifest, files, total = copy_verified(source_fd, stage)
            size = ((32 * 1024 * 1024 + 2 * total + 4095) // 4096) * 4096
            dest.mkdir(mode=0o700)  # Exclusive; never replaces an existing path.
            disk = dest / "feed.ext4"
            fd = os.open(disk, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                os.ftruncate(fd, size)
            finally:
                os.close(fd)
            command = [tool, "-q", "-F", "-t", "ext4", "-b", "4096", "-m", "0", "-d", str(stage),
                       "-L", "INTFEED", str(disk)]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=120)
            require(result.returncode == 0, f"mke2fs failed (exit {result.returncode})")
            digest = hashlib.sha256()
            with disk.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            os.chmod(disk, 0o400)
            report = {
                "scope": "Fixture file integrity and EXT4 construction only; no signature or DNF verification",
                "source_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "source_manifest_bytes": len(raw_manifest),
                "files": files,
                "fixture_total_bytes": total,
                "mke2fs_version": version,
                "image": {"name": disk.name, "bytes": size, "sha256": digest.hexdigest()},
                "attachment": "Future QEMU invocation must explicitly attach this image readonly=on",
            }
            report_path = dest / "report.json"
            with report_path.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, sort_keys=True)
                stream.write("\n")
            return report
    finally:
        os.close(source_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="fixture directory containing manifest.json")
    parser.add_argument("output", type=Path, help="new output directory outside the fixture tree")
    args = parser.parse_args()
    try:
        report = build(args.fixtures, args.output)
    except (DiskError, OSError, subprocess.SubprocessError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
