# Isolated DNF feed VM: proposed test plan

Status: the experimental image and guest helper have passed a positive local
DNF install/update test and separate unsigned-package, wrong-key package and
missing metadata signature rejection tests in QEMU; see
[positive validation](validation-feed-vm-2026-11-06.md),
[unsigned-package validation](validation-feed-unsigned-vm-2026-11-06.md) and
[wrong-key validation](validation-feed-wrong-key-vm-2026-11-06.md), and
[missing-signature validation](validation-feed-missing-signature-vm-2026-11-06.md).
Other DNF rejection cases have not yet been run. The existing core and desktop
image validations do not qualify this plan.
The prerequisites, signing limitations and complete negative-case rationale
are in [signed-feed-plan.md](signed-feed-plan.md). The two small probe recipes
and their proposed build procedure are described in [feed-probe.md](feed-probe.md).

## Experimental image and transport

The separate `int-image-feed-smoke` recipe is based on
`int-image-minimal.bb` and restricted to `qemux86-64`. It selects
`IMAGE_FEATURES += "package-management"`, which is intended to include target
`rpm` and `dnf` and retain their package database. It adds a test-only service
and GnuPG; it does not include a repository, public key or probe package.
The minimal image's locked-root policy remains in place. This experimental
image passed the positive QEMU test and is not an installation image.

When the current operation has finished, build it using the separate profile:

```sh
./scripts/int --profile feed build int-image-feed-smoke
```

This selects the isolated RPM Sequoia configuration and writes artifacts
under `INT_WORKDIR/build-feed`, leaving the already validated image profiles
untouched. A successful image build alone would not prove signature
enforcement, a working feed, or a successful guest boot. In the locked OE
source, `rootfs_rpm.bbclass` also adds 100 MiB of extra rootfs space when DNF
is installed. Verify the actual image manifest and free space after building.

The test-only `int-feed-smoke` package depends on `dnf`, `rpm`, `gnupg` and
`gnupg-gpg`; verify the actual manifest and test dependencies rather than
assuming this is sufficient.

The test-only oneshot service runs as root on the serial console, then shuts
down the disposable VM. It requires a read-only `/dev/vdb`, a single
`int_feed_fingerprint=FULL_40_HEX` and an `int_feed_case` of `success`,
`unsigned-rpm`, `wrong-key-rpm` or `missing-metadata-signature` on the kernel
command line. It checks the independent pin
before importing a key, installs
version 1.0, updates to 2.0 and repeats the update, checking the RPM version
and installed file each time. It emits ordered `INT_FEED_CHECK` markers, a
single `INT_FEED_CASE:success:PASS`, and `INT_FEED_SHUTDOWN`; failures emit
`INT_FEED_FAIL`. The service and its positive DNF commands were tested in the
guest. For the separate unsigned and wrong-key cases it checks signed metadata
and candidate, requires strict `rpmkeys` and DNF rejection, and confirms
version 1.0 remains installed. The wrong-key case also verifies a trusted RPM
as a positive `rpmkeys` control. The missing-signature case checks a valid
signed metadata control, then requires DNF to refuse the absent detached
signature and confirms version 1.0 remains installed. Other negative cases still need to be implemented and
must never be inferred from the success path. Do not unlock root, install a reusable credential,
enable a remote login, or include this test service in normal images.

Use a separate runner based on the existing `scripts/qemu-smoke.py` snapshot,
kernel/manifest consistency, process timeout, strict marker and evidence
mechanisms. `scripts/qemu-core-check.py` is the interactive owner-enrollment
test; the proposed autonomous feed service does not need its login or sudo
protocol. The runner must select the new image and its own assertion markers,
not interpret a core or boot smoke pass as a feed pass. Keep QEMU's root disk
on a temporary snapshot and hash the preserved input artifacts before and
after each run. Disable guest networking for the file-only experiment.

The runner can construct a second, read-only virtual block disk from the
prepared test repositories and public keys. `mke2fs -d` can populate an EXT4
image without a privileged host mount; `mke2fs 1.47.0` is present in the
current builder image. Bound the input and disk size, keep the generated disk
outside the checkout, hash it, and attach it read-only as a second virtio
device. The guest should identify that expected disk and mount it read-only
with `nosuid,nodev,noexec`; it should not receive a host directory or a
private signing key. The previously validated core kernel has
`CONFIG_VIRTIO_BLK=y` and `CONFIG_EXT4_FS=y`; confirm those settings and the
device naming in the actual feed-profile kernel before relying on them. Check
the second disk's hash after the test as well.

## Trust and repository setup

Prepare the RPMs, public keys, detached metadata signatures and separately
indexed feed variants outside the image, using only the disposable lab key
process in the signing plan. Never sign deployment artifacts in place. Verify
and record the full expected primary fingerprint and public-key hash on the
host. The runner must convey the expected identity independently of the
repository contents and require the guest to confirm the full fingerprint
before importing or trusting the key. Isolate GnuPG's home and reject extra,
unexpected, expired or revoked primary keys. A guest comparing a key with a
fingerprint supplied only by the same untrusted feed would not establish a
pin. The pinned identity is a test input, not a production trust policy.

Use a dedicated DNF configuration and local `file://` base URLs. Explicitly
disable all other repositories and set `gpgcheck=1`, `repo_gpgcheck=1`,
`localpkg_gpgcheck=1` and `skip_if_unavailable=0`. Use separate repository IDs,
caches and trust state for each case. Never pass `--nogpgcheck`: some generic
OE DNF tests do so and therefore do not establish signature enforcement.
Confirm DNF/librepo's actual metadata-key import and keyring locations in the
guest; ensure automatic confirmation can import only the pinned public key.

## Acceptance and rejection

Run the successful path against freshly prepared data:

1. Check the pinned key and signed metadata, then run `dnf makecache`.
2. Install `int-feed-probe` version 1.0 from its signed feed. Check both
   `rpm -q` and `/usr/share/int-feed-probe/version`.
3. Switch to the signed version 2.0 feed and update. Check that the RPM
   database and version file both report 2.0.
4. Repeat the update and require success with the same installed state.

Use a fresh QEMU snapshot and isolated cache/trust setup for each negative
case. First establish version 1.0 from a valid feed, then try the candidate
feed and require a nonzero DNF result, a relevant failure diagnostic and an
unchanged installed version and file. Exercise wrong or unknown metadata
signer, altered or missing metadata signature, altered referenced metadata,
and altered RPM. For unsigned and wrong-key or modified RPM cases, regenerate
and correctly sign the metadata around the candidate RPM: otherwise a stale
metadata checksum can fail before RPM signature verification is reached.
Include an empty RPM trust database case and an OpenPGP-disabled RPM backend
capability check as described in the signing plan. Validate that the negative
cases reach the intended verification stage rather than passing because of an
unrelated missing file, dependency, cache or network failure.

Record separate case outcomes, return codes, bounded diagnostics, tool
versions, full verified fingerprints, artifact hashes and installed-state
checks. Require one ordered set of exact guest markers, clean shutdown, and a
successful QEMU exit for a passing run. Failed or incomplete runs remain
evidence of failure and must not replace a known-good image. Keep temporary
private keys out of the VM and retained evidence.

## Diagnostics to confirm in the guest

The following expectations are derived from the locked source, not observed
VM output. The access path, wrapper errors, locale and automatic key-import
attempts can affect what DNF actually prints. Capture the complete bounded
diagnostic and confirm the relevant stage in a real VM before fixing an
assertion to a particular string. Set `LC_ALL=C` for test commands, and require
a nonzero exit, the expected failure reason and unchanged RPM version and
installed file. Use an independent positive control for the same operation,
fresh cache and trust state for each case, and `skip_if_unavailable=0`.

| Case | Source-derived diagnostic or behavior to investigate |
| --- | --- |
| Metadata signature missing | `librepo/yum.c` reports `GPG verification is enabled, but GPG signature ... not available`; the exact wording differs between the local-repository and download paths. |
| Metadata signed by the wrong key or altered after signing | `librepo/yum.c` prefixes a failure with `repomd.xml GPG signature verification`; the GPGME backend can report `Bad GPG signature`. DNF may wrap or retry the error after importing the configured key. |
| Referenced primary metadata altered | `librepo/yum.c` reports `Checksum mismatch` followed by the affected path when it reaches the checksum check. |
| RPM changed after indexing | `libdnf/dnf-package.cpp` reports `Checksum mismatch in local repository` for a local package checksum mismatch; confirm the actual DNF path reaches this check. |
| Unsigned RPM in freshly signed metadata | `dnf/base.py` can report `Package ... is not signed`, followed by `GPG check FAILED` from `dnf/cli/cli.py`. |
| RPM signed by an untrusted key in freshly signed metadata | `dnf/base.py` detects a missing or untrusted public key; after the configured-key import attempt it may report that the repository keys are already installed but are not correct for the package. |
| Corrupt RPM in freshly signed metadata | DNF's RPM output parser treats a `BAD` line as a fatal verification error, which can surface as a package-opening or GPG-check failure. Verify the reported cause and do not count an unrelated parse or missing-file failure as the intended rejection. |

`dnf/rpm/miscutils.py` invokes `rpmkeys --checksig --verbose` with
`_pkgverify_level signature` and `_pkgverify_flags 0x0`; this source path
requires signatures rather than accepting a digest alone. The metadata and
package keyrings are distinct, so importing the pinned package key into the
RPM database does not itself establish metadata trust. Use correctly signed,
freshly indexed metadata for the unsigned, wrong-key and corrupt RPM cases so
that a stale repository checksum does not reject the fixture before the
package check. No source inspection or synthetic test substitutes for proving
the intended rejection path with the actual target tools.

Source references: locked librepo `363cb70c6548be900832bc9b18ced3e7569da15a`
(`librepo/yum.c`, `librepo/gpg_gpgme.c`), libdnf
`d39573195e24b43687587a8d83b9f6ac274e2412` (`libdnf/dnf-package.cpp`), and
DNF `e47634fbe3565d0580e89ec21adb7c1b308642ce` (`dnf/base.py`,
`dnf/cli/cli.py`, `dnf/rpm/miscutils.py`).

## Points to confirm before implementation is considered validated

- The feed-profile image builds with target Sequoia, DNF, suitable GnuPG
  dependencies and enough writable space; its kernel and disk device match the
  runner's assumptions.
- `mke2fs -d`, the generated EXT4 features, the guest mount options and the
  read-only QEMU attachment work together in the actual test environment.
- GnuPG reports the expected key identity under an isolated home, including
  signing-subkey relationships and key validity. The runner's independent
  expected fingerprint reaches the guest without allowing feed contents to
  define their own trust anchor.
- DNF's metadata and RPM keyrings, `gpgkey` import, cache isolation, `file://`
  behavior and failure diagnostics behave as required in this pinned version.
- Tests prove actual signature enforcement, not merely successful digest
  checks, and each rejection leaves both the RPM database and file unchanged.

These tests would qualify only a disposable local feed and its tested
artifacts. They would not establish production key custody, network delivery,
anti-replay protection, update interruption recovery or release readiness.
