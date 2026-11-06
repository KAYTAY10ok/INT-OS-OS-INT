#!/usr/bin/env python3
"""Exercise native RPM and repomd signatures with disposable laboratory keys.

This checks neither the metadata checksum chain nor DNF or a published feed.
The unprotected keys are strictly ephemeral and must never be used in release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


class LabError(Exception):
    pass


def invoke(argv, *, env, ok=True, timeout=120):
    try:
        result = subprocess.run([str(arg) for arg in argv], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LabError(f"Could not run {Path(argv[0]).name}: {error}") from error
    if ok and result.returncode:
        raise LabError(f"{Path(argv[0]).name} failed ({result.returncode}):\n{result.stdout}")
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise LabError(message)


def signature_ok(output):
    # Only a cryptographic signature line can qualify; digest lines cannot.
    return any(re.search(r"\bsignature\b.*:\s*OK\s*$", line, re.I)
               for line in output.splitlines())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindir", type=Path, required=True,
                        help="complete OE native recipe sysroot's bin directory")
    args = parser.parse_args()
    tools = {name: args.bindir / name for name in
             ("gpg", "gpgconf", "rpmkeys", "rpmbuild", "rpmsign", "createrepo_c")}
    for tool in tools.values():
        require(tool.is_file() and os.access(tool, os.X_OK), f"Missing native tool: {tool}")
    env = os.environ.copy()
    env.update(LC_ALL="C", TZ="UTC")
    results = []
    agents = []

    def record(name, condition, detail=None, returncode=None):
        require(condition, f"Test failed: {name}" + (f"\n{detail}" if detail else ""))
        results.append({"case": name, "exit_code": returncode})
        print(f"PASS {name}", flush=True)

    # A short directory limits GnuPG agent Unix socket path lengths. tempfile
    # creates it mode 0700; both unprotected secret keys disappear on exit.
    with tempfile.TemporaryDirectory(prefix="int-feed-lab-", dir="/tmp") as temporary:
        root = Path(temporary)
        # Avoid inheriting a developer's GnuPG home or RPM user macros.
        env["HOME"] = str(root)
        env.pop("GNUPGHOME", None)
        env.pop("XDG_CONFIG_HOME", None)
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
                listing = gpg(home, "--with-colons", "--fingerprint", "--list-keys").stdout
                lines = listing.splitlines()
                fingerprints = [line.split(":")[9] for line in lines if line.startswith("fpr:")]
                require(sum(line.startswith("pub:") for line in lines) == 1 and
                        len(fingerprints) == 1 and re.fullmatch(r"[0-9A-F]{40}", fingerprints[0]),
                        "Expected one laboratory primary fingerprint")
                public = root / f"{name}.asc"
                gpg(home, "--armor", "--output", public, "--export", fingerprints[0])
                require(public.stat().st_size > 0, "Public key export is empty")
                return home, fingerprints[0], public

            signer_home, fingerprint, public = key("signer")
            wrong_home, _, wrong_public = key("wrong")
            verify_home = root / "verify"
            verify_home.mkdir(mode=0o700)
            agents.append(verify_home)
            gpg(verify_home, "--import", public)

            top = root / "rpmbuild"
            for name in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
                (top / name).mkdir(parents=True, exist_ok=True)
            spec = top / "SPECS" / "int-feed-probe.spec"
            spec.write_text("""Name: int-feed-lab-probe
Version: 1
Release: 1
Summary: Disposable signature laboratory fixture
License: MIT
BuildArch: noarch
AutoReqProv: no
%description
This package is only a temporary laboratory fixture.
%install
mkdir -p %{buildroot}/usr/share/int-feed-lab
printf 'laboratory fixture\\n' > %{buildroot}/usr/share/int-feed-lab/probe
%files
/usr/share/int-feed-lab/probe
""", encoding="utf-8")
            invoke([tools["rpmbuild"], "--define", f"_topdir {top}", "-bb", spec], env=env)
            packages = list((top / "RPMS").rglob("*.rpm"))
            require(len(packages) == 1, "Expected exactly one fixture RPM")
            unsigned = packages[0]
            signed = root / "signed.rpm"
            shutil.copyfile(unsigned, signed)
            signing_env = dict(env, GNUPGHOME=str(signer_home))
            invoke([tools["rpmsign"], "--define", f"_gpg_name {fingerprint}",
                    "--define", f"_gpg_path {signer_home}",
                    "--define", f"__gpg {tools['gpg']}",
                    "--define", "_gpg_digest_algo sha256",
                    "--define", "_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback",
                    "--addsign", signed], env=signing_env)

            def rpm(db, *options, ok=True, strict=False):
                policy = ["--define", "_pkgverify_level all"] if strict else []
                return invoke([tools["rpmkeys"], "--define", f"_dbpath {db}", *policy, *options],
                              env=env, ok=ok)

            trusted, empty, wrong_db = (root / n for n in ("rpm-trusted", "rpm-empty", "rpm-wrong"))
            for db in (trusted, empty, wrong_db):
                db.mkdir(mode=0o700)
            rpm(trusted, "--import", public)
            rpm(wrong_db, "--import", wrong_public)
            verified = rpm(trusted, "--checksig", "--verbose", signed, strict=True)
            record("rpm_signed_trusted", signature_ok(verified.stdout), verified.stdout,
                   verified.returncode)
            for name, db in (("rpm_missing_key", empty), ("rpm_wrong_key", wrong_db)):
                checked = rpm(db, "--checksig", "--verbose", signed, ok=False, strict=True)
                record(name, checked.returncode != 0 and not signature_ok(checked.stdout)
                       and "NOKEY" in checked.stdout.upper(),
                       checked.stdout, checked.returncode)
            checked = rpm(trusted, "--checksig", "--verbose", unsigned, ok=False)
            record("rpm_unsigned_default_digest_only", checked.returncode == 0 and
                   not re.search(r"\bsignature\b", checked.stdout, re.I) and
                   re.search(r"\bdigest\b.*:\s*OK\s*$", checked.stdout, re.I | re.M),
                   checked.stdout, checked.returncode)
            checked = rpm(trusted, "--checksig", "--verbose", unsigned, ok=False, strict=True)
            record("rpm_unsigned_strict_rejected", checked.returncode != 0 and
                   not signature_ok(checked.stdout) and
                   re.search(r"\bsignature\b.*:\s*NOTFOUND\s*$", checked.stdout, re.I | re.M),
                   checked.stdout, checked.returncode)
            corrupt = root / "corrupt.rpm"
            shutil.copyfile(signed, corrupt)
            with corrupt.open("r+b") as stream:
                stream.seek(-1, os.SEEK_END)
                byte = stream.read(1)
                stream.seek(-1, os.SEEK_END)
                stream.write(bytes([byte[0] ^ 1]))
            checked = rpm(trusted, "--checksig", "--verbose", corrupt, ok=False, strict=True)
            record("rpm_corrupt", checked.returncode != 0 and
                   re.search(r"\bdigest\b.*:\s*BAD(?:\s|$)", checked.stdout, re.I | re.M),
                   checked.stdout, checked.returncode)

            feed = root / "feed"
            feed.mkdir()
            shutil.copyfile(signed, feed / "int-feed-lab-probe.rpm")
            invoke([tools["createrepo_c"], feed], env=env)
            metadata = feed / "repodata" / "repomd.xml"
            signature = Path(str(metadata) + ".asc")
            gpg(signer_home, "--yes", "--armor", "--digest-algo", "SHA256",
                "--local-user", fingerprint, "--detach-sign", metadata)
            require(signature.is_file(), "Repository metadata signature missing")

            def verify(home, sig, data):
                return gpg(home, "--status-fd", "1", "--verify", sig, data, ok=False)

            verified = verify(verify_home, signature, metadata)
            valid = f"[GNUPG:] VALIDSIG {fingerprint} "
            record("metadata_signed_trusted", verified.returncode == 0 and valid in verified.stdout,
                   verified.stdout, verified.returncode)
            checked = verify(wrong_home, signature, metadata)
            record("metadata_wrong_key", checked.returncode != 0 and valid not in checked.stdout,
                   checked.stdout, checked.returncode)
            altered = root / "repomd-altered.xml"
            altered.write_bytes(metadata.read_bytes() + b"\n")
            checked = verify(verify_home, signature, altered)
            record("metadata_modified", checked.returncode != 0 and valid not in checked.stdout,
                   checked.stdout, checked.returncode)
            checked = verify(verify_home, root / "missing.asc", metadata)
            record("metadata_missing_signature", checked.returncode != 0 and valid not in checked.stdout,
                   checked.stdout, checked.returncode)
            report = {"scope": "native RPM signatures and detached repomd.xml signature only; "
                               "metadata checksums, DNF and target runtime not tested",
                      "signing_primary_fingerprint": fingerprint,
                      "sha256": {"signed_rpm": digest(signed), "repomd_xml": digest(metadata),
                                 "repomd_signature": digest(signature), "public_key": digest(public)},
                      "versions": {name: invoke([tools[name], "--version"], env=env).stdout.splitlines()[0]
                                   for name in ("gpg", "rpmkeys", "createrepo_c")},
                      "passed": results}
            print(json.dumps(report, sort_keys=True), flush=True)
        finally:
            for home in agents:
                invoke([tools["gpgconf"], "--homedir", home, "--kill", "gpg-agent"],
                       env=env, ok=False, timeout=15)


if __name__ == "__main__":
    try:
        main()
    except LabError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
