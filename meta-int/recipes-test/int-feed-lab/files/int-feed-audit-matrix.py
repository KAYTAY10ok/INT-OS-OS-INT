#!/usr/bin/env python3
"""Rehearse the read-only feed auditor against disposable laboratory fixtures.

A rejected fixture counts only when its expected verification stage was
reached and its specific failure was reported. Infrastructure failures do not
qualify as signature/checksum rejection. Never signs or installs anything.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

# case: (required last successful stage, expected error fragment)
CASES = {
    "valid-v1": ("rpm_signatures_rejected_empty_db", None),
    "valid-v2": ("rpm_signatures_rejected_empty_db", None),
    "wrong-key-metadata": ("feed_tree_regular_files_only", "NO_PUBKEY"),
    "altered-repomd": ("feed_tree_regular_files_only", "BADSIG"),
    "missing-metadata-signature": ("feed_tree_regular_files_only", "Missing repodata/repomd.xml.asc"),
    "altered-primary": ("repomd_signature_validsig", "Metadata checksum mismatch:"),
    "stale-rpm-checksum": ("rpm_key_imported_isolated_db", "Indexed RPM checksum mismatch:"),
    "unsigned-rpm": ("rpm_key_imported_isolated_db", "NOTFOUND"),
    "wrong-key-rpm": ("rpm_key_imported_isolated_db", "NOKEY"),
    "corrupt-rpm-indexed": ("rpm_key_imported_isolated_db", "digest: BAD"),
}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
PIN = re.compile(r"[0-9A-F]{40}\Z")


def qualifies(case, status, report):
    stage, error = CASES[case]
    checks = report.get("checks_passed", [])
    if not isinstance(checks, list) or not checks or checks[-1] != stage:
        return False
    if error is None:
        return status == 0 and report.get("result") == "pass" and report.get("complete") is True
    return (status == 1 and report.get("result") == "fail" and report.get("complete") is False
            and isinstance(report.get("error"), str) and error in report["error"])


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Fixture tree contains a symlink or special file")
        if path.is_file():
            if len(result) >= 1000 or path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("Laboratory fixtures exceed limits")
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindir", required=True, type=Path)
    args = parser.parse_args()
    name = os.environ.get("INT_FEED_AUDIT_FIXTURES", "")
    output = os.environ.get("INT_FEED_AUDIT_OUTPUT", "")
    pin = os.environ.get("INT_FEED_AUDIT_FINGERPRINT", "")
    if not NAME.fullmatch(name) or not NAME.fullmatch(output) or not PIN.fullmatch(pin):
        raise ValueError("Explicit fixture/output names and full independent fingerprint required")
    root = Path("/work/feed-fixtures") / name
    if root.resolve(strict=True) != root or not root.is_dir():
        raise ValueError("Fixture root must be a real local directory")
    base = Path("/work/feed-audits")
    base.mkdir(mode=0o700, exist_ok=True)
    if base.resolve(strict=True) != base:
        raise ValueError("Audit base must not be a symlink")
    dest = base / output
    dest.mkdir(mode=0o700)  # Never overwrite an earlier result.
    before = snapshot(root)
    results = []
    for case in CASES:
        command = [sys.executable, str(Path(__file__).with_name("feed-check.py")), str(root / case),
                   "--rpm-key", str(root / "trusted-public-key.asc"), "--rpm-fingerprint", pin,
                   "--feed-key", str(root / "trusted-public-key.asc"), "--feed-fingerprint", pin,
                   "--rpmkeys", str(args.bindir / "rpmkeys"), "--gpg", str(args.bindir / "gpg")]
        # Auditor bounds individual tool output/time; additionally bound the
        # whole case and retain stdout/stderr directly in files.
        with (dest / (case + ".json")).open("wb") as out, (dest / (case + ".stderr")).open("wb") as err:
            proc = subprocess.run(command, stdout=out, stderr=err, timeout=180)
        report_path = dest / (case + ".json")
        if report_path.stat().st_size > 1024 * 1024:
            raise ValueError("Audit report exceeds laboratory limit")
        report = json.loads(report_path.read_text())
        results.append({"case": case, "exit": proc.returncode,
                        "qualified": qualifies(case, proc.returncode, report),
                        "error": report.get("error"), "checks_passed": report.get("checks_passed"),
                        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                        "tool_versions": report.get("tool_versions")})
    unchanged = before == snapshot(root)
    passed = unchanged and all(r["qualified"] for r in results)
    summary = {"passed": passed, "fixtures_unchanged": unchanged, "cases": results,
               "fingerprint": pin, "fixture_hashes": before,
               "scope": "disposable native audit regression only; no DNF, transport or publication"}
    (dest / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
