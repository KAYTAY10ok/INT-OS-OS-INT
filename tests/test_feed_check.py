"""Host-only checks of feed-check.py parsing and validation.

Tool output here is canned text; these tests cannot establish that any RPM or
GnuPG build verifies OpenPGP signatures. That needs the real-tool runs.
"""
import bz2
import contextlib
import gzip
import hashlib
import importlib.util
import io
import lzma
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/feed-check.py"
SPEC = importlib.util.spec_from_file_location("feed_check", SCRIPT)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
AuditError = check.AuditError

FPR = "6CD846D4F989B4FBED99DBF184850C7993212648"
SUBFPR = "0123456789ABCDEF0123456789ABCDEF01234567"
OTHER = "5155F870578DD1C7F4588FC1E852B2F4731B52B7"
NOW = 1793970600
LISTING = f"""tru::1:1793972115:0:3:1:5
pub:-:2048:1:84850C7993212648:1793970587:1794056987::-:::scSC::::::23::0:
fpr:::::::::{FPR}:
uid:-::::1793970587::4C73::INT FEED TEST ONLY trusted <trusted@example.invalid>::::::::::0:
"""
VALID = (f"[GNUPG:] NEWSIG\n[GNUPG:] KEY_CONSIDERED {FPR} 0\n"
         "[GNUPG:] SIG_ID G/gQKLTtvkjv3yFclJzI3dEhsdc 2026-11-06 1793970588\n"
         "[GNUPG:] GOODSIG 84850C7993212648 INT FEED TEST ONLY trusted <trusted@example.invalid>\n"
         f"[GNUPG:] VALIDSIG {FPR} 2026-11-06 1793970588 0 4 0 1 8 00 {FPR}\n"
         "[GNUPG:] TRUST_UNDEFINED 0 pgp\n")
RPM_OK = """{path}:
    Header V4 RSA/SHA256 Signature, key ID 93212648: OK
    Header SHA256 digest: OK
    Header SHA1 digest: OK
    Payload SHA256 digest: OK
    MD5 digest: OK
"""
RPM_UNSIGNED = """{path}:
    Header RSA signature: NOTFOUND
    Header DSA signature: NOTFOUND
    Header SHA256 digest: OK
    Header SHA1 digest: OK
    Payload SHA256 digest: OK
    RSA signature: NOTFOUND
    DSA signature: NOTFOUND
    MD5 digest: OK
"""
RPM_NOKEY = RPM_UNSIGNED.replace("    Header RSA signature: NOTFOUND",
                                 "    Header V4 RSA/SHA256 Signature, key ID 93212648: NOKEY")


class FingerprintAndPathTests(unittest.TestCase):
    def test_fingerprint(self):
        self.assertEqual(check.normalize_fingerprint(FPR.lower()), FPR)
        for value in (FPR[-16:], FPR + "0", FPR[:-1] + "G", "6CD8 46D4 " + FPR[8:], ""):
            with self.subTest(value=value), self.assertRaises(AuditError):
                check.normalize_fingerprint(value)

    def test_package_href(self):
        for href in ("probe-1.0-r0.noarch.rpm", "core2_64/libfoo++-1.0~rc1-r0.core2_64.rpm"):
            self.assertEqual(check.safe_package_href(href), href)
        for href in ("../x.rpm", "/x.rpm", "a/../x.rpm", "./x.rpm", "http://host/x.rpm",
                     "file:///x.rpm", "repodata/x.rpm", "a//x.rpm", "x.txt", "%2e%2e/x.rpm",
                     "a\\x.rpm", "", ".hidden.rpm", "a b.rpm"):
            with self.subTest(href=href), self.assertRaises(AuditError):
                check.safe_package_href(href)

    def test_metadata_href(self):
        check.safe_metadata_href("repodata/abc-primary.xml.gz")
        for href in ("repodata/../x.gz", "other/x.gz", "repodata/a/x.gz", "/repodata/x.gz",
                     "repodata/repomd.xml", "repodata/repomd.xml.asc", "https://x/repodata/y"):
            with self.subTest(href=href), self.assertRaises(AuditError):
                check.safe_metadata_href(href)


class FileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_scan_accepts_regular_tree(self):
        (self.root / "repodata").mkdir()
        (self.root / "repodata" / "repomd.xml").write_text("x")
        (self.root / "a.rpm").write_text("y")
        self.assertEqual(sorted(check.scan_feed(self.root)), ["a.rpm", "repodata/repomd.xml"])

    def test_scan_rejects_symlinks_and_special_files(self):
        (self.root / "a.rpm").symlink_to("/etc/hostname")
        with self.assertRaisesRegex(AuditError, "Symlink"):
            check.scan_feed(self.root)
        (self.root / "a.rpm").unlink()
        (self.root / "dir").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(AuditError, "Symlink"):
            check.scan_feed(self.root)
        (self.root / "dir").unlink()
        os.mkfifo(self.root / "pipe")
        with self.assertRaisesRegex(AuditError, "Special"):
            check.scan_feed(self.root)

    def test_scan_rejects_symlinked_feed_root(self):
        real = self.root / "real"
        real.mkdir()
        (self.root / "alias").symlink_to(real, target_is_directory=True)
        with self.assertRaises(AuditError):
            check.scan_feed(self.root / "alias")

    def test_read_regular_bounds_and_symlinks(self):
        path = self.root / "f"
        path.write_bytes(b"12345")
        self.assertEqual(check.read_regular(path, 5), b"12345")
        with self.assertRaises(AuditError):
            check.read_regular(path, 4)
        (self.root / "link").symlink_to(path)
        with self.assertRaises(AuditError):
            check.read_regular(self.root / "link", 5)
        other = self.root / "g"
        other.write_bytes(b"12345")
        with self.assertRaisesRegex(AuditError, "changed"):
            check.read_regular(path, 5, os.lstat(other))


class XmlAndCompressionTests(unittest.TestCase):
    def test_rejects_dtd_and_entities(self):
        bomb = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
                b'<r xmlns="http://linux.duke.edu/metadata/repo">&b;</r>')
        external = (b'<?xml version="1.0"?><!DOCTYPE r SYSTEM "http://example.invalid/x.dtd">'
                    b'<r xmlns="http://linux.duke.edu/metadata/repo"/>')
        for data in (bomb, external):
            with self.subTest(data=data[:40]), self.assertRaisesRegex(AuditError, "document type"):
                check.parse_xml(data, 4096, check.REPO_NS + "r")

    def test_rejects_malformed_oversize_and_wrong_root(self):
        with self.assertRaises(AuditError):
            check.parse_xml(b"<a>", 100, "a")
        with self.assertRaises(AuditError):
            check.parse_xml(b"<a/>" + b" " * 100, 50, "a")
        with self.assertRaises(AuditError):
            check.parse_xml(b"<b/>", 100, "a")

    def test_compression_detection(self):
        data = b"<x/>"
        self.assertEqual(check.compression_of("repodata/a.xml.gz", gzip.compress(data)), "gz")
        self.assertEqual(check.compression_of("repodata/a.sqlite.bz2", bz2.compress(data)), "bz2")
        self.assertEqual(check.compression_of("repodata/a.xml.xz", lzma.compress(data)), "xz")
        self.assertIsNone(check.compression_of("repodata/a.xml", data))
        for href, payload in (("repodata/a.xml.zst", b"\x28\xb5\x2f\xfd"), ("repodata/a.xml.zck", b"\0ZCK1"),
                              ("repodata/a.xml.gz", b"plain"), ("repodata/a.xml", gzip.compress(data)),
                              ("repodata/a.bin", data)):
            with self.subTest(href=href), self.assertRaises(AuditError):
                check.compression_of(href, payload)

    def test_bounded_decompression(self):
        data = b"a" * 10000
        for name, packed in (("gz", gzip.compress(data)), ("bz2", bz2.compress(data)),
                             ("xz", lzma.compress(data)), (None, data)):
            with self.subTest(name=name):
                size, digest, kept = check.open_content(packed, name, "sha256", 10000, True)
                self.assertEqual((size, digest, kept), (10000, hashlib.sha256(data).hexdigest(), data))
                with self.assertRaisesRegex(AuditError, "exceeds"):
                    check.open_content(packed, name, "sha256", 9999, False)
        with self.assertRaises(AuditError):
            check.open_content(gzip.compress(data)[:-6], "gz", "sha256", 20000, False)


def repomd(entries, extra=""):
    body = "".join(
        f'<data type="{kind}"><checksum type="{ctype}">{value}</checksum>'
        f'<location href="{href}"{extra}/></data>' for kind, ctype, value, href in entries)
    return (f'<?xml version="1.0" encoding="UTF-8"?><repomd xmlns="http://linux.duke.edu/metadata/repo">'
            f'{body}</repomd>').encode()


def primary(packages, count=None):
    body = "".join(
        f'<package type="rpm"><name>{name}</name><arch>noarch</arch>'
        f'<version epoch="0" ver="1.0" rel="r0"/><checksum type="sha256" pkgid="YES">{value}</checksum>'
        f'<size package="{size}"/><location href="{href}"/></package>'
        for name, href, value, size in packages)
    count = len(packages) if count is None else count
    return (f'<?xml version="1.0" encoding="UTF-8"?><metadata xmlns="http://linux.duke.edu/metadata/common" '
            f'packages="{count}">{body}</metadata>').encode()


class MetadataTests(unittest.TestCase):
    def test_repomd(self):
        digest = "a" * 64
        entries = check.parse_repomd(repomd([("primary", "sha256", digest, "repodata/p.xml.gz"),
                                             ("other", "sha512", "b" * 128, "repodata/o.xml.gz")]))
        self.assertEqual([entry["type"] for entry in entries], ["primary", "other"])
        bad = {
            "sha1": repomd([("primary", "sha1", "a" * 40, "repodata/p.xml.gz")]),
            "short": repomd([("primary", "sha256", "a" * 63, "repodata/p.xml.gz")]),
            "no primary": repomd([("other", "sha256", digest, "repodata/p.xml.gz")]),
            "two primary": repomd([("primary", "sha256", digest, "repodata/p.xml.gz"),
                                   ("primary", "sha256", digest, "repodata/q.xml.gz")]),
            "same href": repomd([("primary", "sha256", digest, "repodata/p.xml.gz"),
                                 ("other", "sha256", digest, "repodata/p.xml.gz")]),
            "base": repomd([("primary", "sha256", digest, "repodata/p.xml.gz")],
                           ' xml:base="http://example.invalid/"'),
            "url": repomd([("primary", "sha256", digest, "http://example.invalid/p.xml.gz")]),
        }
        for name, data in bad.items():
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.parse_repomd(data)

    def test_primary(self):
        digest = "c" * 64
        packages = check.parse_primary(primary([("probe", "probe.rpm", digest, 10)]))
        self.assertEqual(packages[0]["href"], "probe.rpm")
        self.assertEqual(packages[0]["nevra"], "probe-0:1.0-r0.noarch")
        for name, data in (("count", primary([("p", "p.rpm", digest, 1)], count=2)),
                           ("empty", primary([])),
                           ("duplicate", primary([("p", "p.rpm", digest, 1), ("q", "p.rpm", digest, 1)])),
                           ("escape", primary([("p", "../p.rpm", digest, 1)])),
                           ("md5", primary([("p", "p.rpm", "d" * 32, 1)]))):
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.parse_primary(data)


class GnupgParsingTests(unittest.TestCase):
    def test_key_listing(self):
        key = check.parse_key_listing(LISTING, FPR, NOW)
        self.assertEqual(key, {"primary": FPR, "signing": [FPR], "expires": 1794056987})

    def test_key_listing_rejections(self):
        two = LISTING + LISTING.split("\n", 1)[1].replace(FPR, OTHER)
        cases = {
            "wrong": (LISTING, OTHER, NOW),
            "two primary": (two, FPR, NOW),
            "secret": (LISTING.replace("pub:", "sec:"), FPR, NOW),
            "revoked": (LISTING.replace("pub:-:", "pub:r:"), FPR, NOW),
            "expired flag": (LISTING.replace("pub:-:", "pub:e:"), FPR, NOW),
            "expired time": (LISTING, FPR, 1794056987),
            "disabled": (LISTING.replace(":scSC:", ":scSCD:"), FPR, NOW),
            "no signing": (LISTING.replace(":scSC:", ":cC:"), FPR, NOW),
            "unknown record": (LISTING + "xyz:1\n", FPR, NOW),
            "no fingerprint": (LISTING.replace(f"fpr:::::::::{FPR}:\n", ""), FPR, NOW),
        }
        for name, (listing, expected, now) in cases.items():
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.parse_key_listing(listing, expected, now)

    def test_signing_subkeys(self):
        listing = (LISTING.replace(":scSC:", ":cSC:") +
                   f"sub:-:2048:1:01234567:1793970587:1794056987:::::s::::::23:\nfpr:::::::::{SUBFPR}:\n" +
                   f"sub:r:2048:1:E852B2F4:1793970587:1794056987:::::s::::::23:\nfpr:::::::::{OTHER}:\n")
        key = check.parse_key_listing(listing, FPR, NOW)
        self.assertEqual(key["signing"], [SUBFPR])

    def test_import_status(self):
        good = (f"[GNUPG:] KEY_CONSIDERED {FPR} 0\n[GNUPG:] IMPORTED 84850C7993212648 INT\n"
                f"[GNUPG:] IMPORT_OK 1 {FPR}\n[GNUPG:] IMPORT_RES 1 0 1 0 0 0 0 0 0 0 0 0 0 0 0\n")
        check.check_import_status(good, FPR)
        for name, output in (("wrong", good.replace(f"IMPORT_OK 1 {FPR}", f"IMPORT_OK 1 {OTHER}")),
                             ("two", good.replace("IMPORT_RES 1 ", "IMPORT_RES 2 ")),
                             ("secret", good.replace("IMPORT_RES 1 0 1 0 0 0 0 0 0 0 ", "IMPORT_RES 1 0 1 0 0 0 0 0 0 1 ")),
                             ("unknown", good + "[GNUPG:] IMPORT_PROBLEM 1\n"),
                             ("text", good + "gpg: imported\n")):
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.check_import_status(output, FPR)

    def test_verify_status(self):
        result = check.check_verify_status(VALID, 0, FPR, [FPR])
        self.assertEqual(result["signing_fingerprint"], FPR)
        self.assertEqual(result["hash_algorithm"], "SHA256")

    def test_verify_status_rejections(self):
        badsig = "[GNUPG:] NEWSIG\n[GNUPG:] BADSIG 84850C7993212648 INT\n[GNUPG:] FAILURE gpg-exit 33554433\n"
        nokey = ("[GNUPG:] NEWSIG\n[GNUPG:] ERRSIG E852B2F4731B52B7 1 8 00 1793970588 9 " + OTHER +
                 "\n[GNUPG:] NO_PUBKEY E852B2F4731B52B7\n")
        cases = {
            "badsig": (badsig, 1, [FPR]),
            "nokey": (nokey, 2, [FPR]),
            "exit": (VALID, 1, [FPR]),
            "goodsig only": (VALID.replace(f"[GNUPG:] VALIDSIG {FPR} 2026-11-06 1793970588 0 4 0 1 8 00 {FPR}\n", ""),
                             0, [FPR]),
            "other primary": (VALID.replace(f"00 {FPR}", f"00 {OTHER}"), 0, [FPR]),
            "unexpected signer": (VALID, 0, [SUBFPR]),
            "sha1": (VALID.replace(" 1 8 00 ", " 1 2 00 "), 0, [FPR]),
            "class": (VALID.replace(" 8 00 ", " 8 01 "), 0, [FPR]),
            "two signatures": (VALID + VALID, 0, [FPR]),
            "expired key": (VALID.replace("GOODSIG", "EXPKEYSIG"), 0, [FPR]),
            "never trusted": (VALID.replace("TRUST_UNDEFINED", "TRUST_NEVER"), 0, [FPR]),
            "free text": (VALID + "gpg: Good signature\n", 0, [FPR]),
        }
        for name, (output, code, signing) in cases.items():
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.check_verify_status(output, code, FPR, signing)


class RpmParsingTests(unittest.TestCase):
    path = "/tmp/feed-check-x/package-0.rpm"

    def test_trusted_signature(self):
        self.assertEqual(check.check_rpm_trusted(RPM_OK.format(path=self.path), 0, self.path, [FPR]),
                         ["93212648"])

    def test_trusted_rejections(self):
        ok = RPM_OK.format(path=self.path)
        cases = {
            "digests only": (RPM_UNSIGNED.replace("NOTFOUND", "OK").replace(
                "    Header RSA signature: OK\n", "").format(path=self.path), 0),
            "unsigned": (RPM_UNSIGNED.format(path=self.path), 1),
            "nokey": (RPM_NOKEY.format(path=self.path), 1),
            "digests only no signature lines": ("".join(
                line + "\n" for line in ok.splitlines() if "Signature" not in line), 0),
            "nonzero exit": (ok, 1),
            "bad digest": (ok.replace("Payload SHA256 digest: OK",
                                      "Payload SHA256 digest: BAD (Expected 00 != 11)"), 1),
            "other key": (ok.replace("93212648", "731b52b7"), 0),
            "nottrusted": (ok.replace("93212648: OK", "93212648: NOTTRUSTED"), 1),
            "unknown line": (ok + "    Mystery check: OK\n", 0),
            "summary form": (f"{self.path}: digests signatures OK\n", 0),
            "other path": (ok.replace(self.path, "/elsewhere.rpm"), 0),
            "empty": ("", 0),
        }
        for name, (output, code) in cases.items():
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.check_rpm_trusted(output, code, self.path, [FPR])

    def test_empty_database_requires_nokey(self):
        check.check_rpm_untrusted(RPM_NOKEY.format(path=self.path), 1, self.path, [FPR])
        for name, (output, code) in {
                "accepted": (RPM_OK.format(path=self.path), 0),
                "accepted nonzero": (RPM_OK.format(path=self.path), 1),
                "zero exit": (RPM_NOKEY.format(path=self.path), 0),
                "unsigned": (RPM_UNSIGNED.format(path=self.path), 1),
                "other key": (RPM_NOKEY.replace("93212648", "731b52b7").format(path=self.path), 1),
                "unknown": (RPM_NOKEY.format(path=self.path) + "error: something\n", 1)}.items():
            with self.subTest(name=name), self.assertRaises(AuditError):
                check.check_rpm_untrusted(output, code, self.path, [FPR])


class FakeAuditTests(unittest.TestCase):
    """Run the whole audit flow with canned tool results on a synthetic feed."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.feed = self.root / "feed"
        (self.feed / "repodata").mkdir(parents=True)
        self.rpm = b"synthetic rpm bytes"
        (self.feed / "probe.rpm").write_bytes(self.rpm)
        xml = primary([("probe", "probe.rpm", hashlib.sha256(self.rpm).hexdigest(), len(self.rpm))])
        packed = gzip.compress(xml)
        href = f"repodata/{hashlib.sha256(packed).hexdigest()}-primary.xml.gz"
        (self.feed / href).write_bytes(packed)
        data = repomd([("primary", "sha256", hashlib.sha256(packed).hexdigest(), href)])
        data = data.replace(b'"/></data>', f'"/><open-checksum type="sha256">'
                            f'{hashlib.sha256(xml).hexdigest()}</open-checksum></data>'.encode())
        (self.feed / "repodata" / "repomd.xml").write_bytes(data)
        (self.feed / "repodata" / "repomd.xml.asc").write_bytes(b"-----BEGIN PGP SIGNATURE-----\nx\n")
        self.key = self.root / "key.asc"
        self.key.write_bytes(b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nx\n")
        self.rpm_trusted = RPM_OK
        self.calls = []

    def fake_split(self, argv, **_kwargs):
        self.calls.append(argv)
        if "--verify" in argv:
            return 0, VALID, ""
        if "--status-fd" in argv:
            return 0, (f"[GNUPG:] IMPORT_OK 1 {FPR}\n"
                       "[GNUPG:] IMPORT_RES 1 0 1 0 0 0 0 0 0 0 0 0 0 0 0\n"), ""
        return 0, LISTING, ""

    def fake_tool(self, argv, **_kwargs):
        self.calls.append(argv)
        argv = [str(argument) for argument in argv]
        if "--version" in argv:
            return 0, "tool 1.0\n"
        if "--import" in argv:
            return 0, ""
        path = argv[-1]
        if "rpmdb-empty" in argv[2]:
            return 1, RPM_NOKEY.format(path=path)
        return 0, self.rpm_trusted.format(path=path)

    def audit(self):
        argv = [str(self.feed), "--rpm-key", str(self.key), "--rpm-fingerprint", FPR,
                "--feed-key", str(self.key), "--feed-fingerprint", FPR,
                "--rpmkeys", sys.executable, "--gpg", sys.executable]
        out = io.StringIO()
        with mock.patch.object(check, "run_split", self.fake_split), \
                mock.patch.object(check, "run_tool", self.fake_tool), \
                mock.patch.object(check.time, "time", return_value=NOW), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = check.main(argv)
        return code, check.json.loads(out.getvalue())

    def test_pass(self):
        code, report = self.audit()
        self.assertEqual((code, report["result"], report["complete"]), (0, "pass", True))
        self.assertEqual(report["packages"][0]["sha256"], hashlib.sha256(self.rpm).hexdigest())
        dbpaths = [argv[2] for argv in self.calls if "--checksig" in argv]
        self.assertTrue(any("rpmdb-trusted" in path for path in dbpaths))
        self.assertTrue(any("rpmdb-empty" in path for path in dbpaths))
        self.assertTrue(all(str(argument) != "--keyserver" for argv in self.calls for argument in argv))

    def expect_failure(self, pattern):
        code, report = self.audit()
        self.assertEqual((code, report["result"], report["complete"]), (1, "fail", False))
        self.assertRegex(report["error"], pattern)

    def test_unindexed_rpm(self):
        (self.feed / "extra.rpm").write_bytes(b"x")
        self.expect_failure("Unindexed")

    def test_stale_rpm(self):
        (self.feed / "probe.rpm").write_bytes(self.rpm + b"\n")
        self.expect_failure("Indexed RPM checksum mismatch")

    def test_altered_metadata(self):
        href = next((self.feed / "repodata").glob("*-primary.xml.gz"))
        href.write_bytes(href.read_bytes() + b"\n")
        self.expect_failure("Metadata checksum mismatch")

    def test_missing_signature(self):
        (self.feed / "repodata" / "repomd.xml.asc").unlink()
        self.expect_failure("Missing repodata/repomd.xml.asc")

    def test_digest_only_rpm(self):
        self.rpm_trusted = RPM_UNSIGNED
        self.expect_failure("RPM verification failed")

    def test_relative_tool_path(self):
        argv = [str(self.feed), "--rpm-key", str(self.key), "--rpm-fingerprint", FPR,
                "--feed-key", str(self.key), "--feed-fingerprint", FPR,
                "--rpmkeys", "rpmkeys", "--gpg", sys.executable]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check.main(argv), 1)
        self.assertIn("absolute", check.json.loads(out.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
