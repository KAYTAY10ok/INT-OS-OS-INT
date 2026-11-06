# First signed RPM feed: implementation and evidence plan

Status: researched against locked OE-Core revision
`ae5a301091f5b0574ea7444aab40b309b6d9f3f2`. No INT feed, signing key,
signature verification, package update or recovery test is claimed by this
document. The current minimal images do not contain RPM/DNF runtime tools.
The account and firewall milestone takes precedence over this experiment.

## Current prerequisites

The build already contains native `rpm`, `rpmkeys`, `rpmsign`,
`createrepo_c`, `dnf`, `libdnf`, `librepo` and `gpgme` components. It does not
contain `gnupg-native` or `rpm-sequoia-native` in its populated components.
This was established by inspecting files, not by running a signing test.

The current native `librpmio.so.10.2.1` contains the diagnostic
`RPM was compiled without OpenPGP support`; disassembly of
`pgpVerifySignature` shows an unconditional failure return. Digest support is
not proof of OpenPGP verification. OE's signing self-test explicitly enables
the following configuration for RPM 4.20.1:

```bitbake
PACKAGECONFIG:append:pn-rpm-native = " sequoia"
PACKAGECONFIG:append:pn-rpm = " sequoia"
```

These options, GnuPG and their Rust/Sequoia dependencies have not been built
or enabled by this research. Their build cost remains unmeasured. Use native
tools within a correctly populated OE recipe sysroot or a dedicated tool
recipe: concatenating component `usr/bin` directories does not recreate the
native sysroot's libraries, Python paths or RPM configuration.

## Exact OE interfaces

| Purpose | Interface in the locked source |
| --- | --- |
| Sign RPMs during packaging | `INHERIT += "sign_rpm"`; sets `RPM_SIGN_PACKAGES = "1"` |
| RPM signer | Required `RPM_GPG_NAME` and nonempty `RPM_GPG_PASSPHRASE` |
| RPM backend | `RPM_GPG_BACKEND = "local"` is the only implemented backend |
| File digests | `RPM_FILE_CHECKSUM_DIGEST = "8"` means SHA-256; this is not the OpenPGP signature digest |
| Optional file signatures | `RPM_SIGN_FILES` defaults to `0`; enabling it also requires `RPM_FSK_PATH` and `RPM_FSK_PASSWORD`; outside this milestone |
| RPM batching | `RPM_GPG_SIGN_CHUNK` defaults to `BB_NUMBER_THREADS` |
| Sign repository metadata | `INHERIT += "sign_package_feed"`; sets `PACKAGE_FEED_SIGN = "1"` |
| Feed signer | Required `PACKAGE_FEED_GPG_NAME` and `PACKAGE_FEED_GPG_PASSPHRASE_FILE` |
| Feed backend and format | `PACKAGE_FEED_GPG_BACKEND = "local"`, `PACKAGE_FEED_GPG_SIGNATURE_TYPE = "ASC"` |
| GnuPG selection | `GPG_BIN` optionally selects a binary/wrapper; `GPG_PATH` selects its isolated home |
| Runtime package management | `IMAGE_FEATURES += "package-management"` selects `rpm dnf` and preserves packaging data |
| Runtime feed addresses | `PACKAGE_FEED_URIS`, `PACKAGE_FEED_BASE_PATHS`, `PACKAGE_FEED_ARCHS` |
| Rebuild indexes | `bitbake package-index`, after packages have been built; not run during this research |

There are two stale comments in `sign_package_feed.bbclass`. The code
requires **`PACKAGE_FEED_GPG_PASSPHRASE_FILE`**, not the shorter variable
spelled in its header. Its RPM indexer also reads the signature-type variable,
despite the comment claiming that RPM ignores it. Keep `ASC` for
`repodata/repomd.xml.asc`.

`createrepo_c` writes `repomd.xml` and the metadata files it references. OE
creates a detached SHA-256 signature of `repomd.xml`. Its checksums cover the
other metadata files; the primary metadata then references package checksums.
This chain and each RPM signature must both be checked.

`signing-keys-rpm` provides
`/etc/pki/rpm-gpg/RPM-GPG-KEY-${DISTRO}-${DISTRO_CODENAME}`;
`signing-keys-packagefeed` provides
`/etc/pki/packagefeed-gpg/PACKAGEFEED-GPG-KEY-${DISTRO}-${DISTRO_CODENAME}`.
Only public keys belong in the image/feed. `sign_rpm` also imports the RPM
public key into the image's RPM database during rootfs creation.
`sign_package_feed` adds the feed public-key package to the package-management
feature and writes `repo_gpgcheck=1` with that key's local path to generated
repository configuration. Explicitly set `gpgcheck=1`: do not depend on
defaults or confuse it with `repo_gpgcheck`.

For the first lab, a single disposable key can sign packages and metadata.
With separate keys, install both public keys and configure/import both trust
paths explicitly: OE's generated `gpgkey` entry names only the feed key.

## Disposable laboratory signing without a secret in argv

Do not use `sign_rpm` for this first isolated lab. It rejects
`RPM_GPG_PASSPHRASE_FILE`, requires a nonempty `RPM_GPG_PASSPHRASE` and passes
that value through command arguments in `oe/gpg_sign.py`. A real release
secret must not enter BitBake metadata, task logs, process arguments or caches.
Production signing requires a separately reviewed interface and key custody.

Proposed lab interface, not an executed test:

1. Create a temporary directory with mode `0700` outside the checkout and
   persistent evidence directory. Use it as `GNUPGHOME`. Generate a key with
   standard GnuPG, an unmistakable `INT FEED TEST ONLY` identity and a short
   expiry. `gpg --batch --pinentry-mode loopback --passphrase ''
   --quick-generate-key 'INT FEED TEST ONLY <feed-test@example.invalid>'
   rsa3072 sign 1d` requests an **unprotected disposable key**; the empty
   argument is not a real secret. Never use this procedure for production.
2. Read the full primary fingerprint using `--with-colons --list-keys` and
   require exactly one expected primary key. Export only its public key for
   the test client. Record the fingerprint with the evidence.
3. Sign copies of test RPMs, never files in the known-good deployment tree.
   Invoke standard `rpmsign --addsign` with separate argv elements:
   `--define '_gpg_name FULL_FINGERPRINT'`,
   `--define '_gpg_path TEMPORARY_GNUPGHOME'`,
   `--define '__gpg ABSOLUTE_NATIVE_GPG_PATH'`,
   `--define '_gpg_digest_algo sha256'` and
   `--define '_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback'`.
   Set `GNUPGHOME` for the invocation as well. None of these values is a
   passphrase. The no-passphrase key needs no passphrase argument to sign.
4. Run `createrepo_c` on the isolated copy, then use GnuPG
   `--batch --yes --armor --digest-algo SHA256 --local-user FULL_FINGERPRINT
   --detach-sign` on `repodata/repomd.xml`. Use the same temporary home.
5. End only that home's agent with `gpgconf --homedir TEMPORARY_GNUPGHOME
   --kill gpg-agent`, then remove that temporary key directory after testing.
   Preserve public key, fingerprint, signed artifacts, hashes and sanitized
   results. Do not preserve secret keys or share this test trust with users.

Any implementation must construct subprocess argv lists, not interpolate
filenames or identities into a shell. The native `rpmsign` wrapper and RPM
macro paths must be used from the complete native sysroot. The commands above
are a source-based proposal until exercised with OpenPGP-enabled RPM.

## Proposed read-only audit helper

The narrow interface for a later `scripts/feed-check.py` is:

```text
feed-check.py FEED_DIRECTORY
  --rpm-key PUBLIC_KEY --rpm-fingerprint FULL_PRIMARY_FINGERPRINT
  --feed-key PUBLIC_KEY --feed-fingerprint FULL_PRIMARY_FINGERPRINT
  --rpmkeys ABSOLUTE_PATH --gpg ABSOLUTE_PATH
```

It may create temporary verification databases/keyrings, but must not sign,
install packages, modify a feed, read personal keyrings or change the host
RPM database. No external URLs or keyservers should be consulted. A success
result must describe only the audited artifacts, not a working update service.
Do not implement a helper that treats a `digests OK` string as success.

Required behavior before calling the helper useful:

- Validate full primary fingerprints from supplied public-key material with
  GnuPG machine-readable output. Reject extra primary keys, secret-key
  material, expired/revoked keys and unexpected signing keys. Signing subkeys
  must belong to the expected primary key and remain valid.
- Verify `repomd.xml.asc` using an isolated GnuPG home containing only the
  expected public key; require command success and `VALIDSIG` for the expected
  primary/signing-key relationship. Human-readable `GOODSIG` alone is not a
  full-fingerprint identity check. Do not retrieve missing keys automatically.
- Check every metadata checksum referenced by the signed `repomd.xml` and
  every RPM checksum referenced by primary metadata. Reject absent files,
  unsafe relative paths, URLs, symlinks, unsupported compression/checksum
  formats and unbounded decompression/XML expansion. Account for every RPM
  in the directory so an unindexed extra RPM does not silently pass an audit.
- Use an isolated RPM database containing only the expected package key.
  Require successful import and actual signature verification from
  `rpmkeys --checksig --verbose`, with an explicit accepted signature and no
  failed digests/signatures. Zero exit status or correct digests alone is
  insufficient. Unrecognized output fails closed until reviewed.
- Repeat a signature check with an empty isolated RPM database; require
  rejection for a missing trusted key. This and the positive signed fixture
  distinguish a usable OpenPGP backend from the current unsupported build.
  Unit mocks cannot establish that capability.
- Bound subprocess runtime and data sizes, and emit a concise JSON report
  with artifact hashes, verified fingerprints and tool versions. Capture
  errors without claiming partial checks are a complete feed audit.

Start with either a genuinely complete audit of this narrow feed format or
name a smaller tool `rpm-signature-check` and state that it does not audit
repository metadata. Avoid a broad helper name with incomplete verification.
An XML/decompression parser should use established libraries with bounded
input rather than add a custom package manager or crypto implementation.

## Real guest acceptance and rejection tests

Create a tiny no-scriptlet package `int-feed-probe`, versions `1` and `2`,
installing only its own version file. Use a separate experimental image/build
configuration and feed directory so global signing inheritance does not
replace the foundation's unsigned, known-good artifacts. Do not run two
BitBake servers/containers against the same build directory.

In a disposable VM, use an explicit `file://` feed first. Set
`gpgcheck=1`, `repo_gpgcheck=1`, `localpkg_gpgcheck=1` and
`skip_if_unavailable=0`; keep other repositories disabled. With a public key
whose full fingerprint is pinned by the test, require `makecache`, install
version `1`, update to version `2`, correct RPM database state and correct
installed file contents. Repeat the successful operation to check idempotence.

Use fresh caches and isolated trust for each negative case. Require nonzero
exit status and an unchanged installed version/file:

| Case | Required distinction |
| --- | --- |
| Unknown/wrong feed key | Reject metadata signature; no automatic trust of another key |
| Altered `repomd.xml` | Reject detached signature |
| Missing metadata signature | Fail; do not fall back to unsigned metadata |
| Altered referenced metadata | Reject checksum or parsing failure |
| Altered RPM | Reject referenced checksum; also run the isolated signature case below |
| Wrong-key or modified RPM with freshly indexed, correctly signed metadata | Reach and reject RPM signature verification rather than stop only at a stale metadata checksum |
| Unsigned RPM in correctly signed metadata | Reject; valid package digests are insufficient |
| OpenPGP-disabled RPM tool | Fail capability/positive verification checks; never report a successful signature audit |
| Empty RPM trust database | Reject a correctly signed package until the pinned key is imported |

Record individual expectations, exit status, actual installed versions,
artifact hashes, fingerprints and tool versions. Source review and mocked
unit tests do not replace these guest tests. OE's generic DNF repository
tests use `--nogpgcheck` in some paths; their success alone is not INT signing
evidence.

## Update and recovery limits

A valid signature authenticates an artifact; it does not prove that a feed is
fresh or prevent replay of an older correctly signed feed. Release sequence,
expiry, reliable time, key rotation/revocation and downgrade policy need an
explicit design and tests. A later HTTPS feed must also retain TLS validation;
the initial `file://` experiment does not qualify network transport or mirrors.

DNF history/undo is not an atomic filesystem or boot rollback mechanism.
Retain prior packages and a known-good boot image. First test interruption
during download, then transaction interruption on a disposable guest disk;
inspect RPM database/files, retry behavior and recovery evidence. Do not
claim rollback until a chosen filesystem/image mechanism and boot recovery
have been implemented and exercised. Package updates and kernel/image updates
also need an explicit compatibility boundary.

No production key custody, feed publication, mirror operation, automated
security-update service, anti-rollback protection or interrupted-transaction
recovery has been implemented or qualified here.

## Official source references

The links below identify the locked source reviewed locally; no external
service access was required for this research.

- [RPM signing class](https://git.openembedded.org/openembedded-core/tree/meta/classes/sign_rpm.bbclass?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [Feed signing class](https://git.openembedded.org/openembedded-core/tree/meta/classes/sign_package_feed.bbclass?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [RPM package/index manager and generated trust configuration](https://git.openembedded.org/openembedded-core/tree/meta/lib/oe/package_manager/rpm/__init__.py?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [GPG invocation implementation](https://git.openembedded.org/openembedded-core/tree/meta/lib/oe/gpg_sign.py?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [Public-key packaging](https://git.openembedded.org/openembedded-core/tree/meta/recipes-core/meta/signing-keys.bb?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [RPM signing self-test and explicit Sequoia options](https://git.openembedded.org/openembedded-core/tree/meta/lib/oeqa/selftest/cases/signing.py?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [RPM recipe](https://git.openembedded.org/openembedded-core/tree/meta/recipes-devtools/rpm/rpm_4.20.1.bb?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [DNF recipe and disabled automatic timers](https://git.openembedded.org/openembedded-core/tree/meta/recipes-devtools/dnf/dnf_4.24.0.bb?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [DNF guest tests, including checks disabled in generic paths](https://git.openembedded.org/openembedded-core/tree/meta/lib/oeqa/runtime/cases/dnf.py?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2)
- [RPM 4.20.1 source selected by the recipe](https://github.com/rpm-software-management/rpm/tree/c8dc5ea575a2e9c1488036d12f4b75f6a5a49120)
