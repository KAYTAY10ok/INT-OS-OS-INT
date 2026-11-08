# Read-only signed-feed audit

`scripts/feed-check.py` audits one local `createrepo_c` RPM feed directory
against two pinned full OpenPGP primary fingerprints: one for package
signatures and one for the detached `repodata/repomd.xml.asc` signature. It
implements the interface proposed in
[the signed-feed plan](signed-feed-plan.md#proposed-read-only-audit-helper):

```sh
python3 scripts/feed-check.py FEED_DIRECTORY \
  --rpm-key RPM_PUBLIC_KEY --rpm-fingerprint FULL_PRIMARY_FINGERPRINT \
  --feed-key FEED_PUBLIC_KEY --feed-fingerprint FULL_PRIMARY_FINGERPRINT \
  --rpmkeys /ABSOLUTE/PATH/rpmkeys --gpg /ABSOLUTE/PATH/gpg
```

It prints one JSON report to standard output and exits `0` only when every
check passes. Any failure, unrecognized tool output or unsupported format
exits `1` with `"result": "fail"`, `"complete": false`, the error and the
checks that had passed before it; that partial report is not a feed audit.

## What it checks

- **Keys.** Each key file is read (bounded, no symlinks), listed with
  `--import-options show-only` and then imported into its own temporary
  GnuPG home. The machine-readable `--with-colons` listing must contain
  exactly one primary key whose full fingerprint equals the argument, no
  secret-key records, and a primary that is not revoked, expired, invalid or
  disabled. Allowed signing keys are the primary and/or signing subkeys of
  that primary that are currently valid. The import status must report that
  one fingerprint and zero secret keys read.
- **Repository signature.** `gpg --status-fd 1 --verify` runs in the feed
  key's temporary home with `--no-autostart`, `--no-auto-key-retrieve` and
  `--disable-dirmngr`. It requires exit `0`, exactly one signature, one
  `GOODSIG` and one `VALIDSIG` whose primary fingerprint is the pinned one and
  whose signing key is an allowed signing key, signature class `00` and a
  SHA-2 hash. Any other status keyword (for example `BADSIG`, `ERRSIG`,
  `NO_PUBKEY`, `EXPKEYSIG`, `REVKEYSIG`) fails.
- **Metadata chain.** The bytes that passed the signature check are parsed.
  `repomd.xml` and the primary metadata are pre-scanned with expat and any
  DOCTYPE or entity declaration is rejected. Each referenced file must be a
  plain `repodata/NAME` location without `xml:base`, exist as a regular file
  and match its `sha256`, `sha384` or `sha512` checksum and size.
  Compressed files (`.gz`, `.bz2`, `.xz`, checked by magic bytes) are
  decompressed with a hard output limit and must match `open-checksum` and
  `open-size`. Uncompressed `.xml`/`.sqlite` is accepted; `zstd`, `zck` and
  any other format fail closed.
- **Packages.** Every primary entry must have a safe relative `.rpm` location
  (no URL, `xml:base`, absolute path, `..` or `repodata/`), a supported
  checksum and a size. Each RPM is copied once into the temporary directory
  while hashing, so the checksum and signature checks see the same bytes.
- **Completeness.** The directory is walked without following symlinks;
  any symlink, special file, unreferenced metadata file, unindexed RPM or
  other unexpected file fails the audit.
- **RPM signatures.** The RPM key is imported into a new temporary RPM
  database (`--define '_dbpath ...'`). Each package is checked with
  `rpmkeys --define '_pkgverify_level all' --checksig --verbose`. Every output
  line must match the reviewed grammar; all results must be `OK`, the exit
  status must be `0`, and at least one `Signature, key ID ...: OK` line must
  name a key ID of an allowed signing key. Digest lines alone never pass. The
  same check against a second, empty database must exit nonzero with `NOKEY`
  for the expected key and no accepted signature.
- **Report.** Tool versions, key fingerprints and key-file hashes,
  repository signature details, and SHA-256 of `repomd.xml`, its signature,
  each metadata file and each RPM.

Tools run from argv lists with a minimal environment (`HOME` in the
temporary directory, no `GNUPGHOME`, `LC_ALL=C`, `TZ=UTC`), a 120 second
timeout and a 1 MiB output limit. The temporary directory, keyrings and RPM
databases are removed on exit. The feed, key files and host RPM database are
only read.

## Evidence so far

Host unit tests in `tests/test_feed_check.py` cover path, XML,
compression, checksum and completeness checks and the parsers, using canned
GnuPG and `rpmkeys` text. They cannot show that any RPM build verifies
OpenPGP signatures.

**Host rehearsal with Ubuntu tools only (2026-11-06).** In the
`int-feed-rehearsal` container (Ubuntu 24.04: GnuPG 2.4.4, libgcrypt 1.10.3,
RPM 4.18.2, Python 3.12.3), run with `--network none` and the fixtures
mounted read-only, against fixtures produced by `int-feed-fixtures.py` with
the same Ubuntu tools:

| Variant | Exit | Reason reported |
| --- | --- | --- |
| `valid-v1`, `valid-v2` | 0 | all checks passed |
| `wrong-key-metadata` | 1 | `ERRSIG`, `NO_PUBKEY` on `repomd.xml.asc` |
| `altered-repomd` | 1 | `BADSIG` |
| `missing-metadata-signature` | 1 | missing `repodata/repomd.xml.asc` |
| `altered-primary` | 1 | primary metadata checksum mismatch |
| `stale-rpm-checksum` | 1 | indexed RPM checksum mismatch |
| `unsigned-rpm` | 1 | RPM signatures `NOTFOUND` |
| `wrong-key-rpm` | 1 | RPM signature `NOKEY` (key `731b52b7`) |
| `corrupt-rpm-indexed` | 1 | RPM payload digests `BAD` |

Additional cases built inside the container's `/tmp` also failed as
intended: wrong fingerprint argument, other feed key, other RPM key, a key
file with two primaries, armored and binary secret keys, a revoked key, an
expired key, a shortened fingerprint, an extra unindexed RPM and a symlink in
the feed; an unmodified copy of `valid-v2` passed. No GnuPG agent, keyboxd or
dirmngr process remained afterwards.

**OE native validation (2026-11-08).** The dedicated opt-in BitBake task
`audit_feed_fixtures` has now passed all ten cases with OE-built RPM 4.20.1,
GnuPG 2.5.17 and Python 3.14.7, without changing the auditor grammar. Both
valid feeds passed the trusted/empty RPM database controls; the eight invalid
variants failed at their expected verification stages. See
[the native evidence and repeat procedure](validation-feed-audit-native-2026-11-08.md).

## Limits

- It audits files in one directory at one moment; it does not test DNF, a
  guest, `file://` or HTTPS transport, freshness, replay or downgrade
  protection, key rotation or revocation distribution.
- The fixture key expires one day after generation; the rehearsal fixtures
  will then correctly fail as expired.
- Only the narrow `createrepo_c` format is accepted. `zstd`/`zck` metadata
  (newer `createrepo_c` defaults), `xml:base`, remote locations, delta RPMs
  and extra files such as `repomd.xml.key` are rejected rather than audited.
- Short RPM key IDs are matched as fingerprint suffixes; the isolated
  database holds only the pinned key, so acceptance still relies on that key.
- A feed modified while the audit runs is detected only for inode
  replacement of scanned files; audit a static copy.
- Metadata other than primary is only checksum-verified, not parsed.
