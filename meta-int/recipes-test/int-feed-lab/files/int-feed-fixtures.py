#!/usr/bin/env python3
"""Generate disposable signed feed fixtures for a future isolated VM test.

This is not a production signer or a DNF test. Only public artifacts are
retained; unprotected laboratory private keys live in a temporary directory.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET

lab = runpy.run_path(str(Path(__file__).with_name("int-feed-lab.py")))
LabError = lab["LabError"]
invoke = lab["invoke"]
require = lab["require"]
signature_ok = lab["signature_ok"]
has_status = lab["has_status"]

MAX_RPM = 10 * 1024 * 1024
MAX_OUTPUT = 100 * 1024 * 1024
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def input_bytes(work, value, version):
    """Read only a regular copied probe under /work/int-feed-probe.*."""
    path = Path(value)
    expected = f"int-feed-probe-{version}-r0.noarch.rpm"
    require(path.is_absolute() and path.name == expected and
            path.parent.parent == work and path.parent.name.startswith("int-feed-probe.") and
            path.parent.name != "int-feed-probe.", f"Invalid probe {version} path")
    require(path.parent.resolve(strict=True) == path.parent, "Probe parent must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            entry = os.fstat(stream.fileno())
            require(stat.S_ISREG(entry.st_mode) and 0 < entry.st_size <= MAX_RPM,
                    f"Probe {version} must be a bounded regular file")
            data = stream.read(MAX_RPM + 1)
    except OSError as error:
        raise LabError(f"Cannot read probe {version}: {error}") from error
    require(len(data) == entry.st_size and len(data) <= MAX_RPM, f"Probe {version} changed during read")
    return data


def create_output(work, name):
    require(NAME.fullmatch(name) is not None, "Invalid output name")
    base = work / "feed-fixtures"
    try:
        base.mkdir(mode=0o700, exist_ok=True)
        require(base.resolve(strict=True) == base and base.is_dir(), "Invalid output base")
        output = base / name
        output.mkdir(mode=0o700)  # Fails if anything already exists, including a symlink.
    except OSError as error:
        raise LabError(f"Cannot create new output: {error}") from error
    return output


def sha(data):
    return hashlib.sha256(data).hexdigest()


def invoke_rpm(tool, database, *arguments, env, ok=True):
    """Keep every RPM tool away from the host or default RPM database."""
    require(Path(database).is_absolute(), "RPM database path must be absolute")
    return invoke([tool, "--define", f"_dbpath {database}", *arguments], env=env, ok=ok)


def validate_probe_files(output):
    """Reject extra paths or non-regular version markers in RPM file metadata."""
    directory = "/usr/share/int-feed-probe"
    version_file = directory + "/version"
    allowed_directories = {"/usr", "/usr/share", directory}
    seen = set()
    for line in output.splitlines():
        fields = line.split("\t")
        require(len(fields) == 2 and fields[0] not in seen, "Unexpected probe file metadata")
        path, mode = fields
        try:
            file_mode = int(mode, 8)
        except ValueError as error:
            raise LabError("Invalid RPM file mode") from error
        require((path in allowed_directories and stat.S_ISDIR(file_mode)) or
                (path == version_file and stat.S_ISREG(file_mode)),
                "Unexpected probe path or file type")
        seen.add(path)
    require(version_file in seen, "Probe version file missing")


def verify_single_package_index(repo, version):
    """Check this generator's limited one-package primary-index format."""
    repomd_path = repo / "repodata" / "repomd.xml"
    require(repomd_path.stat().st_size <= 1024 * 1024, "repomd exceeds limit")
    tree = ET.parse(repomd_path)
    ns = "{http://linux.duke.edu/metadata/repo}"
    entries = tree.findall(f"{ns}data[@type='primary']")
    require(len(entries) == 1, "Expected exactly one primary index")
    location = entries[0].find(f"{ns}location")
    checksum = entries[0].find(f"{ns}checksum")
    require(location is not None and checksum is not None and checksum.get("type") == "sha256",
            "Missing primary location or SHA-256")
    href = location.get("href", "")
    require(re.fullmatch(r"repodata/[A-Za-z0-9_.-]+\.gz", href), "Unsafe primary path")
    primary_path = repo / href
    require(primary_path.stat().st_size <= 1024 * 1024, "Compressed primary exceeds limit")
    require(sha(primary_path.read_bytes()) == checksum.text, "Primary checksum mismatch")
    with gzip.open(primary_path, "rb") as stream:
        primary = stream.read(4 * 1024 * 1024 + 1)
    require(len(primary) <= 4 * 1024 * 1024, "Primary metadata exceeds limit")
    root = ET.fromstring(primary)
    common = "{http://linux.duke.edu/metadata/common}"
    packages = root.findall(f"{common}package")
    require(root.get("packages") == "1" and len(packages) == 1, "Repository must index one RPM")
    package = packages[0]
    name = package.find(f"{common}name")
    arch = package.find(f"{common}arch")
    ver = package.find(f"{common}version")
    location = package.find(f"{common}location")
    checksum = package.find(f"{common}checksum")
    filename = f"int-feed-probe-{version}-r0.noarch.rpm"
    require(name is not None and name.text == "int-feed-probe" and arch is not None and
            arch.text == "noarch" and ver is not None and ver.get("ver") == version and
            ver.get("rel") == "r0" and location is not None and location.get("href") == filename,
            "Indexed RPM identity mismatch")
    require(
            checksum is not None and checksum.get("type") == "sha256" and
            checksum.text == sha((repo / filename).read_bytes()), "Indexed RPM checksum mismatch")
    return primary_path


def expect_index_failure(repo, version, expected):
    """Accept only the particular integrity failure the fixture is meant to test."""
    try:
        verify_single_package_index(repo, version)
    except LabError as error:
        require(str(error) == expected, f"Unexpected index validation failure: {error}")
        return
    raise LabError(f"Expected index validation failure: {expected}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindir", required=True, type=Path)
    args = parser.parse_args()
    work = Path("/work")
    values = [os.environ.get(name, "") for name in ("INT_FEED_V1", "INT_FEED_V2", "INT_FEED_OUTPUT")]
    require(all(values), "Set INT_FEED_V1, INT_FEED_V2 and INT_FEED_OUTPUT")
    inputs = {version: input_bytes(work, value, version)
              for version, value in zip(("1.0", "2.0"), values[:2])}
    require(Path(values[0]).parent == Path(values[1]).parent, "Probe copies must share one directory")
    tools = {name: args.bindir / name for name in ("gpg", "gpgconf", "rpm", "rpmkeys", "rpmsign", "createrepo_c")}
    for tool in tools.values():
        require(tool.is_file() and os.access(tool, os.X_OK), f"Missing native tool: {tool}")
    output = create_output(work, values[2])
    agents = []
    env = os.environ.copy()
    env.update(LC_ALL="C", TZ="UTC")
    env.pop("GNUPGHOME", None)
    env.pop("XDG_CONFIG_HOME", None)

    # Convert ordinary termination into an exception so the temporary GnuPG
    # homes and agents are cleaned up. SIGKILL and machine failure cannot be
    # caught and require subsequent cleanup of an abandoned temporary home.
    def terminate(signum, _frame):
        raise LabError(f"Interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, terminate)

    with tempfile.TemporaryDirectory(prefix="int-feed-fixtures-", dir="/tmp") as temporary:
        root = Path(temporary)
        env["HOME"] = str(root)
        try:
            def gpg(home, *arguments, ok=True):
                return invoke([tools["gpg"], "--no-options", "--homedir", home,
                               "--batch", *arguments], env=env, ok=ok)

            def key(name):
                home = root / name
                home.mkdir(mode=0o700)
                agents.append(home)
                gpg(home, "--pinentry-mode", "loopback", "--passphrase", "",
                    "--quick-generate-key", f"INT FEED TEST ONLY {name} <{name}@example.invalid>",
                    "rsa2048", "sign", "1d")
                lines = gpg(home, "--with-colons", "--fingerprint", "--list-keys").stdout.splitlines()
                fprs = [line.split(":")[9] for line in lines if line.startswith("fpr:")]
                require(sum(line.startswith("pub:") for line in lines) == 1 and len(fprs) == 1 and
                        re.fullmatch(r"[0-9A-F]{40}", fprs[0]), "Unexpected laboratory fingerprint")
                public = root / f"{name}.asc"
                gpg(home, "--armor", "--output", public, "--export", fprs[0])
                require(public.stat().st_size > 0, "Empty public key")
                return home, fprs[0], public

            trusted_home, fingerprint, public = key("trusted")
            wrong_home, wrong_fingerprint, wrong_public = key("wrong")
            verify_home = root / "verify"
            verify_home.mkdir(mode=0o700)
            agents.append(verify_home)
            gpg(verify_home, "--import", public)
            rpmdb = root / "rpmdb"
            rpmdb.mkdir(mode=0o700)
            invoke_rpm(tools["rpmkeys"], rpmdb, "--import", public, env=env)

            unsigned = {}
            for version, data in inputs.items():
                path = root / f"int-feed-probe-{version}-r0.noarch.rpm"
                path.write_bytes(data)
                query = invoke_rpm(tools["rpm"], rpmdb, "-qp", "--qf", "%{NAME}\\t%{VERSION}\\t%{RELEASE}\\t%{ARCH}\\n", path, env=env)
                require(query.stdout == f"int-feed-probe\t{version}\tr0\tnoarch\n", f"Unexpected RPM identity: {query.stdout}")
                scripts = invoke_rpm(tools["rpm"], rpmdb, "-qp", "--scripts", "--triggers", "--filetriggers", path, env=env)
                require(not scripts.stdout.strip(), "Probe unexpectedly has scriptlets or triggers")
                files = invoke_rpm(tools["rpm"], rpmdb, "-qp", "--qf",
                                   "[%{FILENAMES}\\t%{FILEMODES:octal}\\n]", path, env=env)
                validate_probe_files(files.stdout)
                check = invoke_rpm(tools["rpmkeys"], rpmdb, "--checksig", "--verbose", path, env=env)
                require(not re.search(r"\bsignature\b", check.stdout, re.I) and
                        re.search(r"\bdigest\b.*:\s*OK\s*$", check.stdout, re.I | re.M),
                        "Input probe must be unsigned and have valid digests")
                check = invoke_rpm(tools["rpmkeys"], rpmdb, "--define", "_pkgverify_level all",
                                   "--checksig", "--verbose", path, env=env, ok=False)
                require(check.returncode != 0 and
                        re.search(r"\bsignature\b.*:\s*NOTFOUND\s*$", check.stdout, re.I | re.M),
                        "Unsigned input did not fail the strict signature check")
                unsigned[version] = path

            def sign_rpm(source, name, home, fpr):
                target = root / name
                shutil.copyfile(source, target)
                signing_env = dict(env, GNUPGHOME=str(home))
                invoke_rpm(tools["rpmsign"], rpmdb, "--define", f"_gpg_name {fpr}",
                        "--define", f"_gpg_path {home}", "--define", f"__gpg {tools['gpg']}",
                        "--define", "_gpg_digest_algo sha256", "--define",
                        "_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback", "--addsign", target,
                       env=signing_env)
                return target

            signed_v1 = sign_rpm(unsigned["1.0"], "signed-v1.rpm", trusted_home, fingerprint)
            signed_v2 = sign_rpm(unsigned["2.0"], "signed-v2.rpm", trusted_home, fingerprint)
            wrong_v2 = sign_rpm(unsigned["2.0"], "wrong-v2.rpm", wrong_home, wrong_fingerprint)
            for signed in (signed_v1, signed_v2):
                check = invoke_rpm(tools["rpmkeys"], rpmdb, "--define", "_pkgverify_level all",
                                   "--checksig", "--verbose", signed, env=env)
                require(signature_ok(check.stdout), f"No successful RPM signature: {check.stdout}")
            check = invoke_rpm(tools["rpmkeys"], rpmdb, "--define", "_pkgverify_level all",
                               "--checksig", "--verbose", wrong_v2, env=env, ok=False)
            require(check.returncode != 0 and "NOKEY" in check.stdout.upper() and
                    not signature_ok(check.stdout), "Wrong-key RPM did not fail as expected")

            corrupt = root / "corrupt-v2.rpm"
            shutil.copyfile(signed_v2, corrupt)
            with corrupt.open("r+b") as stream:
                stream.seek(-1, os.SEEK_END)
                byte = stream.read(1)
                stream.seek(-1, os.SEEK_END)
                stream.write(bytes([byte[0] ^ 1]))
            check = invoke_rpm(tools["rpmkeys"], rpmdb, "--define", "_pkgverify_level all",
                               "--checksig", "--verbose", corrupt, env=env, ok=False)
            require(check.returncode != 0 and re.search(r"\bdigest\b.*:\s*BAD(?:\s|$)", check.stdout, re.I | re.M),
                    "Corrupt RPM did not fail its digest check")

            def make_repo(name, package, version):
                repo = output / name
                repo.mkdir(mode=0o700)
                shutil.copyfile(package, repo / f"int-feed-probe-{version}-r0.noarch.rpm")
                invoke([tools["createrepo_c"], "--general-compress-type", "gz",
                        "--checksum", "sha256", repo], env=env)
                metadata = repo / "repodata" / "repomd.xml"
                verify_single_package_index(repo, version)
                gpg(trusted_home, "--yes", "--armor", "--digest-algo", "SHA256",
                    "--local-user", fingerprint, "--detach-sign", metadata)
                check = gpg(verify_home, "--status-fd", "1", "--verify", Path(str(metadata) + ".asc"), metadata)
                require(has_status(check.stdout, "VALIDSIG", fingerprint), "Repository signature not verified")
                return repo

            make_repo("valid-v1", signed_v1, "1.0")
            valid = make_repo("valid-v2", signed_v2, "2.0")
            make_repo("unsigned-rpm", unsigned["2.0"], "2.0")
            make_repo("wrong-key-rpm", wrong_v2, "2.0")
            make_repo("corrupt-rpm-indexed", corrupt, "2.0")

            def variant(name):
                target = output / name
                shutil.copytree(valid, target)
                return target

            wrong_meta = variant("wrong-key-metadata") / "repodata" / "repomd.xml"
            gpg(wrong_home, "--yes", "--armor", "--digest-algo", "SHA256", "--local-user",
                wrong_fingerprint, "--detach-sign", wrong_meta)
            check = gpg(verify_home, "--status-fd", "1", "--verify", Path(str(wrong_meta) + ".asc"), wrong_meta, ok=False)
            require(check.returncode != 0 and has_status(check.stdout, "NO_PUBKEY", wrong_fingerprint[-16:]),
                    "Wrong-key metadata did not fail as expected")
            altered_meta = variant("altered-repomd") / "repodata" / "repomd.xml"
            with altered_meta.open("ab") as stream:
                stream.write(b"\n")
            check = gpg(verify_home, "--status-fd", "1", "--verify", Path(str(altered_meta) + ".asc"), altered_meta, ok=False)
            require(check.returncode != 0 and has_status(check.stdout, "BADSIG", fingerprint[-16:]),
                    "Altered repomd did not fail as expected")
            missing_meta = variant("missing-metadata-signature") / "repodata" / "repomd.xml.asc"
            missing_meta.unlink()
            altered_primary = variant("altered-primary")
            tree = ET.parse(altered_primary / "repodata" / "repomd.xml")
            primary = tree.find("{http://linux.duke.edu/metadata/repo}data[@type='primary']/{http://linux.duke.edu/metadata/repo}location")
            require(primary is not None, "Missing primary metadata")
            href = primary.get("href", "")
            require(re.fullmatch(r"repodata/[A-Za-z0-9_.-]+", href), "Unsafe primary metadata path")
            with (altered_primary / href).open("ab") as stream:
                stream.write(b"\n")
            expect_index_failure(altered_primary, "2.0", "Primary checksum mismatch")
            primary_meta = altered_primary / "repodata" / "repomd.xml"
            check = gpg(verify_home, "--status-fd", "1", "--verify",
                        Path(str(primary_meta) + ".asc"), primary_meta)
            require(has_status(check.stdout, "VALIDSIG", fingerprint), "Altered-primary repomd signature invalid")
            stale_rpm = variant("stale-rpm-checksum") / "int-feed-probe-2.0-r0.noarch.rpm"
            with stale_rpm.open("ab") as stream:
                stream.write(b"\n")
            expect_index_failure(stale_rpm.parent, "2.0", "Indexed RPM checksum mismatch")
            stale_meta = stale_rpm.parent / "repodata" / "repomd.xml"
            check = gpg(verify_home, "--status-fd", "1", "--verify",
                        Path(str(stale_meta) + ".asc"), stale_meta)
            require(has_status(check.stdout, "VALIDSIG", fingerprint), "Stale-RPM repomd signature invalid")
            shutil.copyfile(public, output / "trusted-public-key.asc")
            files = {}
            total = 0
            for path in sorted(output.rglob("*")):
                require(not path.is_symlink(), "Output contains a symlink")
                if path.is_file():
                    size = path.stat().st_size
                    require(size <= MAX_OUTPUT and total + size <= MAX_OUTPUT, "Output size limit exceeded")
                    data = path.read_bytes()
                    total += len(data)
                    require(len(data) == size, "Output file changed during hashing")
                    files[str(path.relative_to(output))] = {"sha256": sha(data), "bytes": len(data)}
            versions = {name: invoke([tools[name], "--version"], env=env).stdout.splitlines()[0]
                        for name in ("gpg", "createrepo_c")}
            versions["rpmkeys"] = invoke_rpm(tools["rpmkeys"], rpmdb, "--version", env=env).stdout.splitlines()[0]
            report = {"scope": "generated laboratory fixtures only; DNF and target runtime not tested",
                      "signing_primary_fingerprint": fingerprint, "key_expiration": "1 day from creation",
                      "input_sha256": {version: sha(data) for version, data in inputs.items()},
                      "tool_versions": versions, "files": files}
        finally:
            original = sys.exc_info()[1]
            failures = []
            for home in agents:
                try:
                    stopped = invoke([tools["gpgconf"], "--homedir", home, "--kill", "gpg-agent"],
                                     env=env, ok=False, timeout=15)
                    if stopped.returncode:
                        failures.append(f"{home.name}: exit {stopped.returncode}")
                except LabError as error:
                    failures.append(f"{home.name}: {error}")
            if failures:
                raise LabError("Failed to stop lab agents: " + "; ".join(failures)) from original
    # Success marker is written only after ephemeral private keys are removed.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output,
                                     prefix=".manifest-", delete=False) as file:
        json.dump(report, file, indent=2, sort_keys=True)
        file.write("\n")
        temporary_manifest = file.name
    os.replace(temporary_manifest, output / "manifest.json")
    print(f"Generated disposable fixtures: {output}")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (LabError, OSError, ET.ParseError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
