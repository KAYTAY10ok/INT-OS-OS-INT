#!/usr/bin/env python3
"""Read-only audit of one createrepo_c RPM feed directory and its signatures.

The audit pins two full OpenPGP primary fingerprints (packages and repository
metadata), verifies the detached repomd.xml signature, the metadata checksum
chain, every indexed RPM checksum and every RPM signature in isolated
temporary trust stores. A pass describes only the audited files; it does not
test DNF, a guest, freshness, rollback protection or a publication service.
"""
import argparse
import bz2
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import xml.parsers.expat

MAX_KEY = 1024 * 1024
MAX_SIGNATURE = 64 * 1024
MAX_REPOMD = 1024 * 1024
MAX_METADATA = 256 * 1024 * 1024        # one compressed or decompressed file
MAX_XML = 128 * 1024 * 1024             # decompressed primary held in memory
MAX_RPM = 1024 * 1024 * 1024
MAX_FILES = 20000
MAX_DEPTH = 8
MAX_TOOL_OUTPUT = 1024 * 1024
TOOL_TIMEOUT = 120
CHUNK = 1024 * 1024

REPO_NS = "{http://linux.duke.edu/metadata/repo}"
COMMON_NS = "{http://linux.duke.edu/metadata/common}"
CHECKSUMS = {"sha256": 64, "sha384": 96, "sha512": 128}
GOOD_HASH_ALGOS = {"8": "SHA256", "9": "SHA384", "10": "SHA512", "11": "SHA224"}
FINGERPRINT = re.compile(r"(?:[0-9A-F]{40}|[0-9A-F]{64})\Z")
COMPONENT = re.compile(r"[A-Za-z0-9_+][A-Za-z0-9._+~^-]{0,254}\Z")
METADATA_HREF = re.compile(r"repodata/[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")
# Only key validities that do not state invalid, revoked, expired or never.
ACCEPTED_VALIDITY = {"", "-", "q", "o", "m", "f", "u"}
KEY_RECORDS = {"tru", "pub", "sub", "fpr", "fp2", "grp", "uid", "uat", "rvk"}
VERIFY_STATUS = {"NEWSIG", "KEY_CONSIDERED", "SIG_ID", "GOODSIG", "VALIDSIG",
                 "TRUST_UNDEFINED", "TRUST_MARGINAL", "TRUST_FULLY", "TRUST_ULTIMATE"}
IMPORT_STATUS = {"KEY_CONSIDERED", "IMPORTED", "IMPORT_OK", "IMPORT_RES"}
RPM_RESULT = re.compile(
    r"    (?P<label>(?:Header |Payload )?(?:"
    r"(?P<keyed>V\d+ [A-Za-z0-9]+/[A-Za-z0-9-]+ Signature, key ID (?P<keyid>[0-9a-f]{8,64}))|"
    r"(?P<plain>[A-Z0-9]+ signature)|"
    r"(?P<digest>[A-Z0-9-]+(?: ALT)? digest))): "
    r"(?P<status>OK|BAD|NOKEY|NOTFOUND|NOTTRUSTED)(?: \([^()\n]*\))?\Z")


class AuditError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


# ---------------------------------------------------------------- tools

def tool_env(home):
    """A minimal environment: no personal GnuPG home, RPM macros or locale."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LC_ALL": "C", "LANG": "C", "TZ": "UTC"}


def run_tool(argv, *, env, timeout=TOOL_TIMEOUT, limit=MAX_TOOL_OUTPUT):
    """Run argv (never a shell) with bounded time and captured output size."""
    argv = [str(argument) for argument in argv]
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AuditError(f"Could not run {Path(argv[0]).name}: {error}") from error
        output.seek(0)
        data = output.read(limit + 1)
    require(len(data) <= limit, f"{Path(argv[0]).name} output exceeds limit")
    return result.returncode, data.decode("utf-8", "replace")


def run_split(argv, *, env, timeout=TOOL_TIMEOUT, limit=MAX_TOOL_OUTPUT):
    """Like run_tool, but keeps stdout (machine output) apart from stderr."""
    argv = [str(argument) for argument in argv]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            result = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AuditError(f"Could not run {Path(argv[0]).name}: {error}") from error
        streams = []
        for stream in (out, err):
            stream.seek(0)
            data = stream.read(limit + 1)
            require(len(data) <= limit, f"{Path(argv[0]).name} output exceeds limit")
            streams.append(data.decode("utf-8", "replace"))
    return result.returncode, streams[0], streams[1]


def check_tool(value):
    path = Path(value)
    require(path.is_absolute(), f"Tool path must be absolute: {value}")
    require(path.is_file() and os.access(path, os.X_OK), f"Tool is not an executable file: {value}")
    return path


def normalize_fingerprint(value):
    require(isinstance(value, str) and FINGERPRINT.fullmatch(value.upper()) is not None,
            "Fingerprint must be a full 40 or 64 digit hexadecimal primary fingerprint")
    return value.upper()


# ---------------------------------------------------------------- GnuPG parsing

def gnupg_status(output):
    """Return GnuPG status records; any other stdout content fails closed."""
    records = []
    for line in output.splitlines():
        if not line:
            continue
        fields = line.split()
        require(len(fields) >= 2 and fields[0] == "[GNUPG:]", f"Unrecognized GnuPG output: {line!r}")
        records.append(fields[1:])
    return records


def has_status(output, status, first_argument=None):
    """Match a GnuPG machine-status record, never free-form diagnostics."""
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[:2] == ["[GNUPG:]", status]:
            if first_argument is None or (len(fields) >= 3 and fields[2] == first_argument):
                return True
    return False


def parse_key_listing(listing, expected, now, *, allowed_records=KEY_RECORDS):
    """Validate a --with-colons key listing for exactly one expected primary key.

    Returns the primary fingerprint and the fingerprints of currently valid
    signing-capable keys (primary and/or subkeys) belonging to it.
    """
    records = [line.split(":") for line in listing.splitlines() if line]
    for fields in records:
        require(fields[0] not in ("sec", "ssb"), "Key file contains secret-key material")
        require(fields[0] in allowed_records, f"Unrecognized key listing record: {fields[0]}")
    primaries = [index for index, fields in enumerate(records) if fields[0] == "pub"]
    require(len(primaries) == 1, f"Key file must contain exactly one primary key, found {len(primaries)}")
    keys = []
    current = None
    for fields in records:
        if fields[0] in ("pub", "sub"):
            require(len(fields) >= 12, "Truncated key listing record")
            current = {"type": fields[0], "validity": fields[1], "expires": fields[6],
                       "caps": fields[11], "fpr": None}
            keys.append(current)
        elif fields[0] == "fpr":
            require(current is not None and current["fpr"] is None and len(fields) >= 10,
                    "Unexpected fingerprint record")
            current["fpr"] = fields[9].upper()
    for key in keys:
        require(key["fpr"] is not None and FINGERPRINT.fullmatch(key["fpr"]) is not None,
                "Key without a full fingerprint")
    primary = keys[0]
    require(primary["type"] == "pub", "Key listing does not start with a primary key")
    require(primary["fpr"] == expected,
            f"Primary fingerprint {primary['fpr']} does not match expected {expected}")

    def usable(key):
        if key["validity"] not in ACCEPTED_VALIDITY:
            return False
        if key["expires"]:
            require(key["expires"].isdigit(), "Unrecognized key expiry")
            if int(key["expires"]) <= now:
                return False
        return "D" not in key["caps"]

    require(primary["validity"] not in ("r",), "Primary key is revoked")
    require(primary["validity"] not in ("e",), "Primary key is expired")
    require(usable(primary), f"Primary key is not valid (validity {primary['validity']!r}, "
                             f"expiry {primary['expires'] or 'none'})")
    signing = [key["fpr"] for key in keys if "s" in key["caps"] and usable(key)]
    require(signing, "Key has no valid signing-capable primary key or subkey")
    return {"primary": primary["fpr"], "signing": signing,
            "expires": int(primary["expires"]) if primary["expires"] else None}


def check_import_status(output, expected):
    records = gnupg_status(output)
    for record in records:
        require(record[0] in IMPORT_STATUS, f"Unexpected GnuPG import status: {record[0]}")
    ok = [record for record in records if record[0] == "IMPORT_OK"]
    require(len(ok) == 1 and len(ok[0]) >= 3 and ok[0][2].upper() == expected,
            "Key import did not report exactly the expected fingerprint")
    results = [record for record in records if record[0] == "IMPORT_RES"]
    require(len(results) == 1 and len(results[0]) >= 11 and
            all(field.isdigit() for field in results[0][1:]), "Missing key import result")
    counts = results[0][1:]
    require(counts[0] == "1", "Key import processed an unexpected number of keys")
    require(counts[9] == "0", "Key import read secret-key material")


def check_verify_status(output, returncode, primary, signing):
    """Require one good detached signature by an expected key, by VALIDSIG."""
    records = gnupg_status(output)
    rejected = [record[0] for record in records if record[0] not in VERIFY_STATUS]
    require(not rejected, "Repository signature rejected: GnuPG reported " + ", ".join(rejected))
    require(returncode == 0, f"Repository signature verification failed (exit {returncode})")
    require(sum(record[0] == "NEWSIG" for record in records) == 1, "Expected exactly one signature")
    require(sum(record[0] == "GOODSIG" for record in records) == 1, "Expected exactly one good signature")
    valid = [record for record in records if record[0] == "VALIDSIG"]
    require(len(valid) == 1 and len(valid[0]) >= 11, "Missing full VALIDSIG status")
    fields = valid[0]
    require(fields[10].upper() == primary, "VALIDSIG primary fingerprint is not the expected key")
    require(fields[1].upper() in signing, "VALIDSIG signing key is not a valid key of the expected primary")
    require(fields[8] in GOOD_HASH_ALGOS, f"Unsupported signature hash algorithm {fields[8]}")
    require(fields[9] == "00", f"Unexpected signature class {fields[9]}")
    require(not has_status(output, "TRUST_NEVER"), "Signing key is marked never trusted")
    return {"signing_fingerprint": fields[1].upper(), "primary_fingerprint": fields[10].upper(),
            "hash_algorithm": GOOD_HASH_ALGOS[fields[8]], "signature_timestamp": fields[3]}


# ---------------------------------------------------------------- rpmkeys parsing

def parse_checksig(output, path):
    """Parse `rpmkeys --checksig --verbose` for one file; unknown lines fail."""
    lines = [line for line in output.splitlines() if line]
    require(lines and lines[0] == f"{path}:", f"Unrecognized rpmkeys output: {output!r}")
    entries = []
    for line in lines[1:]:
        match = RPM_RESULT.fullmatch(line)
        require(match is not None, f"Unrecognized rpmkeys output line: {line!r}")
        kind = "digest" if match.group("digest") else "signature"
        entries.append({"label": match.group("label"), "kind": kind,
                        "keyid": match.group("keyid"), "status": match.group("status")})
    require(entries, "rpmkeys reported no checks")
    return entries


def keyid_matches(keyid, fingerprints):
    return keyid is not None and any(fpr.lower().endswith(keyid) for fpr in fingerprints)


def signature_ok(output):
    # Only a cryptographic signature line can qualify; digest lines cannot.
    return any(re.search(r"\bsignature\b.*:\s*OK\s*$", line, re.I)
               for line in output.splitlines())


def check_rpm_trusted(output, returncode, path, signing):
    """Require explicit accepted signature(s) by the expected key and no failure."""
    entries = parse_checksig(output, path)
    bad = [entry["label"] + ": " + entry["status"] for entry in entries if entry["status"] != "OK"]
    require(not bad, "RPM verification failed: " + "; ".join(bad))
    require(returncode == 0, f"rpmkeys exited {returncode} despite OK lines")
    signatures = [entry for entry in entries if entry["kind"] == "signature"]
    require(signatures and all(entry["keyid"] for entry in signatures),
            "RPM has no accepted OpenPGP signature (digests alone are insufficient)")
    for entry in signatures:
        require(keyid_matches(entry["keyid"], signing),
                f"RPM signature key ID {entry['keyid']} is not an expected signing key")
    require(any(entry["kind"] == "digest" for entry in entries), "RPM reported no digests")
    require(signature_ok(output), "No explicit RPM signature OK line")
    return sorted({entry["keyid"] for entry in signatures})


def check_rpm_untrusted(output, returncode, path, signing):
    """With an empty RPM database, require NOKEY for the expected key."""
    entries = parse_checksig(output, path)
    require(returncode != 0, "RPM signature was accepted by an empty trust database")
    require(not any(entry["kind"] == "signature" and entry["status"] == "OK" for entry in entries),
            "RPM signature was accepted by an empty trust database")
    require(not any(entry["status"] in ("BAD", "NOTTRUSTED") for entry in entries),
            "Unexpected RPM failure with an empty trust database")
    nokey = [entry for entry in entries if entry["status"] == "NOKEY"]
    require(nokey and all(keyid_matches(entry["keyid"], signing) for entry in nokey),
            "Empty trust database did not report NOKEY for the expected key")


# ---------------------------------------------------------------- files

def read_regular(path, limit, expected=None):
    """Read a regular file without following symlinks; optionally pin inode."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise AuditError(f"Cannot open {path}: {error}") from error
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), f"Not a regular file: {path}")
        require(info.st_size <= limit, f"File exceeds size limit: {path}")
        if expected is not None:
            require((info.st_dev, info.st_ino) == (expected.st_dev, expected.st_ino),
                    f"File changed during audit: {path}")
        data = stream.read(limit + 1)
    require(len(data) == info.st_size, f"File changed during read: {path}")
    return data


def copy_hashing(path, target, algorithm, limit, expected):
    """Copy a regular file once, hashing exactly the bytes later verified."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise AuditError(f"Cannot open {path}: {error}") from error
    hashes = {algorithm: hashlib.new(algorithm), "sha256": hashlib.sha256()}
    size = 0
    with os.fdopen(fd, "rb") as stream, open(target, "xb") as out:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, f"Invalid RPM file: {path}")
        require((info.st_dev, info.st_ino) == (expected.st_dev, expected.st_ino),
                f"File changed during audit: {path}")
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            require(size <= limit, f"File exceeds size limit: {path}")
            for value in hashes.values():
                value.update(chunk)
            out.write(chunk)
    require(size == info.st_size, f"File changed during read: {path}")
    return size, hashes[algorithm].hexdigest(), hashes["sha256"].hexdigest()


def scan_feed(root):
    """Map every regular file to its lstat; reject symlinks and special files."""
    info = os.lstat(root)
    require(stat.S_ISDIR(info.st_mode), "Feed directory must be a real directory, not a symlink")
    files = {}
    pending = [(root, PurePosixPath(), 0)]
    while pending:
        directory, relative, depth = pending.pop()
        require(depth <= MAX_DEPTH, f"Feed is nested too deeply: {relative}")
        try:
            names = sorted(os.listdir(directory))
        except OSError as error:
            raise AuditError(f"Cannot list {directory}: {error}") from error
        for name in names:
            path = directory / name
            entry = os.lstat(path)
            child = relative / name
            require(not stat.S_ISLNK(entry.st_mode), f"Symlink in feed: {child}")
            if stat.S_ISDIR(entry.st_mode):
                pending.append((path, child, depth + 1))
            elif stat.S_ISREG(entry.st_mode):
                files[str(child)] = entry
                require(len(files) <= MAX_FILES, "Feed has too many files")
            else:
                raise AuditError(f"Special file in feed: {child}")
    return files


def safe_package_href(href):
    """Accept a plain relative path inside the feed; reject URLs and escapes."""
    require(isinstance(href, str) and 0 < len(href) <= 1024, "Missing package location")
    parts = href.split("/")
    require(not href.startswith("/") and all(COMPONENT.fullmatch(part) for part in parts) and
            not any(part in (".", "..") for part in parts),
            f"Unsafe package location: {href!r}")
    require(parts[0] != "repodata" and len(parts) <= MAX_DEPTH and href.endswith(".rpm"),
            f"Unexpected package location: {href!r}")
    return href


def safe_metadata_href(href):
    require(isinstance(href, str) and METADATA_HREF.fullmatch(href) is not None and
            href not in ("repodata/repomd.xml", "repodata/repomd.xml.asc"),
            f"Unsafe metadata location: {href!r}")
    return href


# ---------------------------------------------------------------- XML/compression

def reject_dtd(data):
    """Pre-scan with expat and reject any DOCTYPE or entity declaration."""
    parser = xml.parsers.expat.ParserCreate()

    def forbidden(*_arguments):
        raise AuditError("XML document type or entity declarations are not accepted")

    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.UnparsedEntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(data, True)
    except xml.parsers.expat.ExpatError as error:
        raise AuditError(f"Malformed XML: {error}") from error


def parse_xml(data, limit, root_tag):
    require(len(data) <= limit, "XML document exceeds limit")
    reject_dtd(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise AuditError(f"Malformed XML: {error}") from error
    require(root.tag == root_tag, f"Unexpected XML root {root.tag}")
    return root


def compression_of(href, data):
    """Identify supported compression by name and magic; others fail closed."""
    if href.endswith(".gz"):
        require(data[:2] == b"\x1f\x8b", f"Not gzip data: {href}")
        return "gz"
    if href.endswith(".bz2"):
        require(data[:3] == b"BZh", f"Not bzip2 data: {href}")
        return "bz2"
    if href.endswith(".xz"):
        require(data[:6] == b"\xfd7zXZ\x00", f"Not xz data: {href}")
        return "xz"
    if href.endswith(".xml") or href.endswith(".sqlite"):
        require(data[:2] != b"\x1f\x8b" and data[:3] != b"BZh" and data[:4] != b"\x28\xb5\x2f\xfd",
                f"Compressed data with uncompressed name: {href}")
        return None
    raise AuditError(f"Unsupported metadata compression or format: {href}")


def decompress_stream(data, compression):
    stream = io.BytesIO(data)
    if compression == "gz":
        return gzip.GzipFile(fileobj=stream, mode="rb")
    if compression == "bz2":
        return bz2.BZ2File(stream, mode="rb")
    if compression == "xz":
        return lzma.LZMAFile(stream, mode="rb", format=lzma.FORMAT_XZ)
    return stream


def open_content(data, compression, algorithm, limit, keep):
    """Decompress with a hard output bound; return size, digest and maybe data."""
    digest = hashlib.new(algorithm)
    kept = bytearray()
    size = 0
    try:
        with decompress_stream(data, compression) as stream:
            while True:
                chunk = stream.read(min(CHUNK, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                require(size <= limit, "Decompressed metadata exceeds limit")
                digest.update(chunk)
                if keep:
                    kept.extend(chunk)
    except (OSError, EOFError, lzma.LZMAError, ValueError) as error:
        raise AuditError(f"Cannot decompress metadata: {error}") from error
    return size, digest.hexdigest(), bytes(kept) if keep else None


def checksum_element(parent, tag):
    elements = parent.findall(tag)
    require(len(elements) <= 1, f"Duplicate {tag}")
    if not elements:
        return None
    element = elements[0]
    kind = element.get("type", "")
    value = (element.text or "").strip()
    require(kind in CHECKSUMS, f"Unsupported checksum type {kind!r}")
    require(re.fullmatch(f"[0-9a-f]{{{CHECKSUMS[kind]}}}", value) is not None,
            f"Malformed {kind} checksum")
    return kind, value


def integer_text(parent, tag):
    elements = parent.findall(tag)
    require(len(elements) <= 1, f"Duplicate {tag}")
    if not elements:
        return None
    text = (elements[0].text or "").strip()
    require(text.isdigit(), f"Malformed {tag}")
    return int(text)


def parse_repomd(data):
    root = parse_xml(data, MAX_REPOMD, f"{REPO_NS}repomd")
    entries = []
    types = set()
    hrefs = set()
    for element in root.findall(f"{REPO_NS}data"):
        kind = element.get("type", "")
        require(re.fullmatch(r"[A-Za-z0-9_]{1,64}", kind) is not None and kind not in types,
                f"Invalid or duplicate metadata type {kind!r}")
        types.add(kind)
        locations = element.findall(f"{REPO_NS}location")
        require(len(locations) == 1, f"Metadata {kind} needs exactly one location")
        require(set(locations[0].attrib) == {"href"}, f"Metadata {kind} location has base/URL attributes")
        href = safe_metadata_href(locations[0].get("href"))
        require(href not in hrefs, f"Duplicate metadata location {href}")
        hrefs.add(href)
        checksum = checksum_element(element, f"{REPO_NS}checksum")
        require(checksum is not None, f"Metadata {kind} has no checksum")
        entries.append({"type": kind, "href": href, "checksum": checksum,
                        "open_checksum": checksum_element(element, f"{REPO_NS}open-checksum"),
                        "size": integer_text(element, f"{REPO_NS}size"),
                        "open_size": integer_text(element, f"{REPO_NS}open-size")})
    require(sum(entry["type"] == "primary" for entry in entries) == 1,
            "repomd.xml must reference exactly one primary metadata file")
    return entries


def parse_primary(data):
    root = parse_xml(data, MAX_XML, f"{COMMON_NS}metadata")
    packages = []
    hrefs = set()
    for element in root:
        require(element.tag == f"{COMMON_NS}package", f"Unexpected primary element {element.tag}")
        require(element.get("type") == "rpm", "Unexpected package type")
        locations = element.findall(f"{COMMON_NS}location")
        require(len(locations) == 1 and set(locations[0].attrib) == {"href"},
                "Package needs exactly one plain location (no base/URL)")
        href = safe_package_href(locations[0].get("href"))
        require(href not in hrefs, f"Duplicate package location {href}")
        hrefs.add(href)
        checksum = checksum_element(element, f"{COMMON_NS}checksum")
        require(checksum is not None, f"Package {href} has no checksum")
        sizes = element.findall(f"{COMMON_NS}size")
        require(len(sizes) == 1 and (sizes[0].get("package") or "").isdigit(),
                f"Package {href} has no package size")
        names = element.findall(f"{COMMON_NS}name")
        arches = element.findall(f"{COMMON_NS}arch")
        versions = element.findall(f"{COMMON_NS}version")
        require(len(names) == len(arches) == len(versions) == 1, f"Package {href} identity missing")
        version = versions[0]
        packages.append({"href": href, "checksum": checksum, "size": int(sizes[0].get("package")),
                         "nevra": f"{names[0].text}-{version.get('epoch', '0')}:{version.get('ver')}-"
                                  f"{version.get('rel')}.{arches[0].text}"})
    count = root.get("packages", "")
    require(count.isdigit() and int(count) == len(packages), "Primary package count mismatch")
    require(packages, "Primary metadata indexes no packages")
    return packages


# ---------------------------------------------------------------- audit

class Auditor:
    def __init__(self, args, work):
        self.work = work
        self.env = tool_env(work / "home")
        (work / "home").mkdir(mode=0o700)
        self.gpg_path = check_tool(args.gpg)
        self.rpmkeys_path = check_tool(args.rpmkeys)
        self.feed = Path(os.path.abspath(args.feed))
        self.expected = {"rpm": normalize_fingerprint(args.rpm_fingerprint),
                         "feed": normalize_fingerprint(args.feed_fingerprint)}
        self.key_sources = {"rpm": Path(args.rpm_key), "feed": Path(args.feed_key)}
        self.checks = []
        self.report = {"result": "fail", "complete": False}

    def passed(self, name):
        self.checks.append(name)

    def gpg(self, home, *arguments):
        return run_split([self.gpg_path, "--no-options", "--homedir", home, "--batch", "--no-tty",
                          "--no-autostart", "--no-auto-key-retrieve", "--disable-dirmngr",
                          *arguments], env=self.env)

    def new_home(self, name):
        home = self.work / name
        home.mkdir(mode=0o700)
        return home

    def load_key(self, role):
        source = self.key_sources[role]
        data = read_regular(source, MAX_KEY)
        require(data, f"{role} key file is empty")
        require(b"PRIVATE KEY BLOCK" not in data, f"{role} key file contains secret-key material")
        copy = self.work / f"{role}-key.asc"
        copy.write_bytes(data)
        expected = self.expected[role]
        now = int(time.time())
        listing_args = ("--with-colons", "--fixed-list-mode", "--with-fingerprint", "--with-fingerprint")
        shown = self.new_home(f"{role}-show")
        code, out, err = self.gpg(shown, *listing_args, "--import-options", "show-only",
                                  "--import", copy)
        require(code == 0, f"Cannot read {role} key ({code}): {err.strip()}")
        parse_key_listing(out, expected, now)
        home = self.new_home(f"{role}-gnupg")
        code, out, err = self.gpg(home, "--status-fd", "1", "--import", copy)
        require(code == 0, f"Cannot import {role} key ({code}): {err.strip()}")
        check_import_status(out, expected)
        code, out, err = self.gpg(home, *listing_args, "--list-keys")
        require(code == 0, f"Cannot list imported {role} key ({code}): {err.strip()}")
        key = parse_key_listing(out, expected, now)
        self.passed(f"{role}_key_fingerprint")
        return {"home": home, "file": copy, "sha256": hashlib.sha256(data).hexdigest(), **key}

    def versions(self):
        code, gpg_out = run_tool([self.gpg_path, "--version"], env=self.env)
        require(code == 0 and gpg_out.strip(), "Cannot read gpg version")
        code, rpm_out = run_tool([self.rpmkeys_path, "--version"], env=self.env)
        require(code == 0 and rpm_out.strip(), "Cannot read rpmkeys version")
        return {"gpg": gpg_out.splitlines()[0], "libgcrypt": next(
                    (line for line in gpg_out.splitlines() if line.startswith("libgcrypt")), None),
                "rpmkeys": rpm_out.splitlines()[0], "python": sys.version.split()[0]}

    def rpmkeys(self, db, *arguments):
        return run_tool([self.rpmkeys_path, "--define", f"_dbpath {db}",
                         "--define", "_pkgverify_level all", *arguments], env=self.env)

    def run(self):
        report = self.report
        report["tool_versions"] = self.versions()
        rpm_key = self.load_key("rpm")
        feed_key = self.load_key("feed")
        report["keys"] = {role: {"primary_fingerprint": key["primary"],
                                 "signing_fingerprints": key["signing"],
                                 "expires": key["expires"], "key_file_sha256": key["sha256"]}
                          for role, key in (("rpm", rpm_key), ("feed", feed_key))}

        files = scan_feed(self.feed)
        self.passed("feed_tree_regular_files_only")
        require("repodata/repomd.xml" in files, "Missing repodata/repomd.xml")
        require("repodata/repomd.xml.asc" in files, "Missing repodata/repomd.xml.asc signature")
        repomd = read_regular(self.feed / "repodata/repomd.xml", MAX_REPOMD, files["repodata/repomd.xml"])
        signature = read_regular(self.feed / "repodata/repomd.xml.asc", MAX_SIGNATURE,
                                 files["repodata/repomd.xml.asc"])
        require(signature.startswith(b"-----BEGIN PGP SIGNATURE-----"),
                "repomd.xml.asc is not an ASCII-armored detached signature")
        repomd_copy = self.work / "repomd.xml"
        signature_copy = self.work / "repomd.xml.asc"
        repomd_copy.write_bytes(repomd)
        signature_copy.write_bytes(signature)
        code, out, _err = self.gpg(feed_key["home"], "--status-fd", "1", "--verify",
                                   signature_copy, repomd_copy)
        report["repository_signature"] = check_verify_status(out, code, feed_key["primary"],
                                                             feed_key["signing"])
        self.passed("repomd_signature_validsig")
        report["repomd_sha256"] = hashlib.sha256(repomd).hexdigest()
        report["repomd_signature_sha256"] = hashlib.sha256(signature).hexdigest()

        # Everything below is parsed from the exact bytes whose signature passed.
        entries = parse_repomd(repomd)
        metadata = []
        primary = None
        for entry in entries:
            href = entry["href"]
            require(href in files, f"Referenced metadata file is missing: {href}")
            data = read_regular(self.feed / href, MAX_METADATA, files[href])
            algorithm, value = entry["checksum"]
            require(hashlib.new(algorithm, data).hexdigest() == value, f"Metadata checksum mismatch: {href}")
            require(entry["size"] is None or entry["size"] == len(data), f"Metadata size mismatch: {href}")
            compression = compression_of(href, data)
            keep = entry["type"] == "primary"
            if compression or entry["open_checksum"] or keep:
                open_algorithm = entry["open_checksum"][0] if entry["open_checksum"] else algorithm
                require(entry["open_checksum"] is not None or not compression,
                        f"Compressed metadata lacks open-checksum: {href}")
                size, digest, content = open_content(data, compression, open_algorithm,
                                                     MAX_XML if keep else MAX_METADATA, keep)
                if entry["open_checksum"]:
                    require(digest == entry["open_checksum"][1], f"Metadata open-checksum mismatch: {href}")
                require(entry["open_size"] is None or entry["open_size"] == size,
                        f"Metadata open-size mismatch: {href}")
                if keep:
                    primary = content
            metadata.append({"type": entry["type"], "href": href, "sha256": hashlib.sha256(data).hexdigest()})
        self.passed("metadata_checksums")
        packages = parse_primary(primary)
        self.passed("primary_metadata_parsed")

        indexed = {"repodata/repomd.xml", "repodata/repomd.xml.asc"} | {entry["href"] for entry in entries}
        indexed |= {package["href"] for package in packages}
        unexpected = sorted(set(files) - indexed)
        require(not unexpected, "Unindexed or unexpected files in feed: " + ", ".join(unexpected[:10]))
        self.passed("every_file_accounted_for")

        trusted_db = self.new_home("rpmdb-trusted")
        empty_db = self.new_home("rpmdb-empty")
        code, out = self.rpmkeys(trusted_db, "--import", rpm_key["file"])
        require(code == 0 and not out.strip(), f"rpmkeys --import failed ({code}): {out.strip()}")
        self.passed("rpm_key_imported_isolated_db")
        results = []
        for index, package in enumerate(packages):
            href = package["href"]
            require(href in files, f"Indexed RPM is missing: {href}")
            copy = self.work / f"package-{index}.rpm"
            algorithm, value = package["checksum"]
            size, digest, sha256 = copy_hashing(self.feed / href, copy, algorithm, MAX_RPM, files[href])
            require(digest == value, f"Indexed RPM checksum mismatch: {href}")
            require(size == package["size"], f"Indexed RPM size mismatch: {href}")
            code, out = self.rpmkeys(trusted_db, "--checksig", "--verbose", copy)
            keyids = check_rpm_trusted(out, code, copy, rpm_key["signing"])
            code, out = self.rpmkeys(empty_db, "--checksig", "--verbose", copy)
            check_rpm_untrusted(out, code, copy, rpm_key["signing"])
            copy.unlink()
            results.append({"href": href, "nevra": package["nevra"], "bytes": size,
                            "sha256": sha256, "rpm_signature_key_ids": keyids})
        self.passed("rpm_checksums")
        self.passed("rpm_signatures_trusted_db")
        self.passed("rpm_signatures_rejected_empty_db")
        report.update(result="pass", complete=True, metadata=metadata, packages=results)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed", metavar="FEED_DIRECTORY")
    parser.add_argument("--rpm-key", required=True, help="public key for package signatures")
    parser.add_argument("--rpm-fingerprint", required=True, help="full primary fingerprint")
    parser.add_argument("--feed-key", required=True, help="public key for repomd.xml.asc")
    parser.add_argument("--feed-fingerprint", required=True, help="full primary fingerprint")
    parser.add_argument("--rpmkeys", required=True, help="absolute path to rpmkeys")
    parser.add_argument("--gpg", required=True, help="absolute path to gpg")
    args = parser.parse_args(argv)
    report = {"result": "fail", "complete": False}
    auditor = None
    try:
        # A short private directory keeps any GnuPG socket paths short; it is
        # removed with every temporary keyring, database and file copy.
        with tempfile.TemporaryDirectory(prefix="feed-check-", dir="/tmp") as temporary:
            auditor = Auditor(args, Path(temporary))
            report = auditor.run()
    except (AuditError, OSError) as error:
        report = dict(auditor.report if auditor else report)
        report.update(result="fail", complete=False, error=str(error))
    report["scope"] = ("audited files of one feed directory only; DNF, guests, freshness, "
                       "replay/rollback protection and publication are not tested")
    report["feed"] = os.path.abspath(args.feed)
    report["checks_passed"] = auditor.checks if auditor else []
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["result"] != "pass":
        print(f"FAIL: {report.get('error', 'audit incomplete')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
