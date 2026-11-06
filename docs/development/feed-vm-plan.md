# Isolated DNF feed VM: test design and procedure

Status (2026-11-06): the experimental image recipe, the test-only guest
service and its QEMU runner exist in the repository, but none of them has been
built, booted or run. The feed-profile image, the OE native laboratory
(`int-feed-lab-native`), the probe packages and a fixture set have not yet been
produced together; no DNF feed, installation, update or rejection test has run
in a guest. The guest's expected DNF diagnostics were derived from a host
rehearsal with Ubuntu 24.04 tools (DNF 4.14, RPM 4.18, createrepo_c 0.17.3,
GnuPG 2.4.4), in which the fixture generator and all eleven guest cases
passed. That rehearsal is not OE or guest evidence: the patterns must be
confirmed with OE's DNF 4.24 and RPM 4.20.1 with Sequoia. The existing core
and desktop image validations do not qualify this plan.
The prerequisites, signing limitations and complete negative-case rationale
are in [signed-feed-plan.md](signed-feed-plan.md). The two small probe recipes
and their proposed build procedure are described in [feed-probe.md](feed-probe.md),
fixture generation in [feed-fixtures.md](feed-fixtures.md) and the fixture disk
in [feed-disk.md](feed-disk.md).

## Experimental image

The separate `int-image-feed-smoke` recipe is based on
`int-image-minimal.bb` and restricted to `qemux86-64`. It selects
`IMAGE_FEATURES += "package-management"`, which is intended to include target
`rpm` and `dnf` and retain their package database, adds 256 MiB of extra
rootfs space, and installs the test-only `int-feed-smoke` package. It contains
no test repository, public key or probe package: those arrive only on the
read-only fixture disk. The minimal image's locked-root policy remains in
place; the image has no login credential and is not an installation image.

`int-feed-smoke` (`meta-int/recipes-test/int-feed-smoke`) installs a oneshot
systemd service that writes to the serial console and powers the VM off in
every outcome. It depends on `rpm`, `dnf`, `gnupg`, Python and the
`util-linux` `blkid` and `mount` tools. It must never be added to the console
or desktop images. In the locked OE source, `rootfs_rpm.bbclass` also adds
100 MiB of extra rootfs space when DNF is installed; verify the actual image
manifest, GnuPG package split and free space after building.

## Guest test service

Each boot runs exactly one case, selected by `int.feed_case=` on the kernel
command line: `valid`, or one of the ten rejection cases `wrong-key-metadata`,
`altered-repomd`, `missing-metadata-signature`, `missing-repo-key`,
`wrong-configured-key`, `altered-primary`, `stale-rpm-checksum`,
`unsigned-rpm`, `wrong-key-rpm` and `corrupt-rpm-indexed`. The service:

1. Reads the expected full 40-digit primary fingerprint from `int.feed_fpr=`,
   never from the fixture disk, and records RPM, DNF and GnuPG versions.
2. Finds the disk labelled `INTFEED`, requires the kernel to report the block
   device read-only, and mounts it with `ro,nosuid,nodev,noexec,noload`.
3. Inspects `trusted-public-key.asc` under an isolated GnuPG home and accepts
   it only if it contains exactly one valid, signing-capable primary key, no
   subkeys and no secret material, with exactly the pinned fingerprint.
4. Checks the RPM OpenPGP backend with isolated databases: `rpmkeys` with
   `_pkgverify_level all` must report a valid signature on the v2 probe after
   importing the pinned key, and must reject it with `NOKEY` from an empty
   trust database.
5. Requires that the system RPM database trusts no key and that the probe is
   absent, then installs `int-feed-probe` 1.0 from `valid-v1` and requires
   that the RPM database trusts exactly the pinned key.
6. Runs the selected case:
   - `valid`: refresh signed v2 metadata, upgrade to 2.0, then repeat the
     upgrade and require `Nothing to do` with the same installed state.
   - a rejection case: try to upgrade from the candidate directory and require
     a nonzero DNF result, every expected diagnostic pattern for that case, an
     unchanged installed version and version file, and an unchanged RPM trust
     database. `missing-repo-key` omits `gpgkey`; `wrong-configured-key`
     configures an unrelated public key generated inside the disposable guest.

Every repository gets a fresh ID, configuration file, `reposdir` and cache.
DNF runs with `-c` pointing at that configuration, `--disablerepo=*` plus the
one test repository, `gpgcheck=1`, `repo_gpgcheck=1`, `localpkg_gpgcheck=1`,
`skip_if_unavailable=0`, `plugins=0` and a `file://` base URL. The service
refuses `--nogpgcheck`. Installed state is checked through both `rpm -q` and
`/usr/share/int-feed-probe/version`.

The guest emits `INT_FEED_BEGIN:CASE`, one `INT_FEED_CHECK:NAME:PASS` per
completed check, bounded `INT_FEED_INFO` and `INT_FEED_DIAG` lines (exit codes,
last 20 lines of each command, fingerprints and artifact hashes), and finally
`INT_FEED_CASE:CASE:PASS` or `INT_FEED_FAIL:REASON`. It installs no
credential, unlocks no account and opens no network service.

## Runner and transport

`scripts/qemu-feed-check.py` reuses the snapshot, process-timeout and evidence
mechanisms of `scripts/qemu-smoke.py`. For each case it boots the feed image
from a fresh copy-on-write root snapshot (`snapshot=on`) with `-nic none`, and
attaches the fixture disk produced by `scripts/feed-disk.py` as a second
virtio disk with `readonly=on`. Before the run it checks that the image
manifest contains `rpm`, `dnf`, `gnupg`, `int-feed-smoke` and `python3-core`.
Before and after each case it hashes `feed.ext4` and requires it to match both
its `report.json` and the independently supplied `--feed-sha256`; it also
rechecks the kernel and root snapshot hashes.

A case passes only if QEMU exits 0 within the timeout (default 1800 s per
case), the guest emits exactly one `INT_FEED_BEGIN` for that case, exactly the
expected ordered list of checks, one final `INT_FEED_CASE:CASE:PASS`, no
`INT_FEED_FAIL` or kernel panic, and a clean power-down. A core or boot smoke
pass is never interpreted as a feed pass.

## Procedure

All steps happen under the separate `feed` profile, whose artifacts live under
`INT_WORKDIR/build-feed`, leaving the validated image profiles untouched.
Laboratory fixture keys expire one day after creation, so the fixtures, the
disk and every VM case must be produced and run within that window; an
expired key is correctly rejected by the guest and does not indicate a DNF
defect.

1. Build the image, then inspect its manifest and free space:

   ```sh
   ./scripts/int --profile feed build int-image-feed-smoke
   ```

2. Build the probe packages and generate a new fixture directory with the
   native laboratory as described in [feed-probe.md](feed-probe.md) and
   [feed-fixtures.md](feed-fixtures.md). Record the full primary fingerprint
   from the host-side generation output before creating the disk.
3. Create the fixture disk as described in [feed-disk.md](feed-disk.md), for
   example under `INT_WORKDIR/feed-disks/NAME`, and record the `feed.ext4`
   SHA-256 from that step.
4. Run all eleven cases, or a subset with repeated `--case`, passing the disk
   directory as seen inside the builder container:

   ```sh
   ./scripts/int --profile feed feed-check /work/feed-disks/NAME \
     --fingerprint FPR --feed-sha256 SHA [--case NAME]...
   ```

Evidence is written to `INT_WORKDIR/evidence/qemu-feed-*/`: a top-level
`result.json` with tool versions, input hashes, the pinned fingerprint and
per-case outcomes, plus one directory per case with `serial.log` and
`result.json`. Image copies are removed after the run; only their hashes are
kept. Failed or incomplete runs remain evidence of failure and must not
replace a known-good image. No private key enters the VM or the evidence.

In this laboratory the fingerprint and disk hash come from the host-side
generation steps, a channel separate from the disk contents. They are test
inputs, not a production trust policy.

## Acceptance and rejection criteria

Successful path, against freshly prepared data:

1. Check the pinned key and signed metadata, then run `dnf makecache`.
2. Install `int-feed-probe` version 1.0 from its signed feed. Check both
   `rpm -q` and `/usr/share/int-feed-probe/version`.
3. Switch to the signed version 2.0 feed and update. Check that the RPM
   database and version file both report 2.0.
4. Repeat the update and require success with the same installed state.

Each negative case uses a fresh QEMU snapshot and isolated cache/trust setup.
It first establishes version 1.0 from a valid feed, then tries the candidate
feed and requires a nonzero DNF result, a relevant failure diagnostic and an
unchanged installed version and file. The cases cover wrong or unknown
metadata signer, altered or missing metadata signature, missing or wrong
configured repository key, altered referenced metadata, a stale RPM checksum,
and unsigned, wrong-key and corrupt RPMs whose metadata was regenerated and
correctly signed so that the RPM signature check is actually reached. The
empty RPM trust database case and a positive backend capability check run in
every boot. The negative cases must reach the intended verification stage
rather than pass because of an unrelated missing file, dependency, cache or
network failure.

Record separate case outcomes, return codes, bounded diagnostics, tool
versions, full verified fingerprints, artifact hashes and installed-state
checks. Require one ordered set of exact guest markers, clean shutdown, and a
successful QEMU exit for a passing run.

## Known gaps

- No case exercises an OpenPGP-disabled RPM backend; only the positive
  capability check and the empty-trust rejection are implemented.
- The expected DNF diagnostics come from a host rehearsal with distribution
  tools, not from OE's DNF; a pattern mismatch in the guest must be diagnosed
  from the retained output, not relaxed blindly.
- The one-day fixture key lifetime constrains when runs can happen.
- Repository freshness and replay protection, key rotation, update
  interruption recovery, network transport and production key custody remain
  out of scope.

## Points to confirm before implementation is considered validated

- The feed-profile image builds with target Sequoia, DNF, suitable GnuPG
  dependencies and enough writable space; its kernel and disk device match the
  runner's assumptions (`CONFIG_VIRTIO_BLK`, `CONFIG_EXT4_FS`, the fixture
  disk appearing as a read-only `/dev/vdb`).
- `mke2fs -d`, the generated EXT4 features, the guest mount options and the
  read-only QEMU attachment work together in the actual test environment.
- GnuPG reports the expected key identity under an isolated home, including
  key validity. The runner's independent expected fingerprint reaches the
  guest without allowing feed contents to define their own trust anchor.
- DNF's metadata and RPM keyrings, `gpgkey` import, cache isolation, `file://`
  behavior and failure diagnostics behave as required in this pinned version.
- Tests prove actual signature enforcement, not merely successful digest
  checks, and each rejection leaves both the RPM database and file unchanged.

These tests would qualify only a disposable local feed and its tested
artifacts. They would not establish production key custody, network delivery,
anti-replay protection, update interruption recovery or release readiness.
