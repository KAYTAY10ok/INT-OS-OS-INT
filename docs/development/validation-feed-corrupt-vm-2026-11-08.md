# Corrupted RPM rejection in QEMU — 2026-11-08 (Europe/Zurich)

The feed guest rejected a deliberately corrupted RPM whose repository metadata
had been regenerated and correctly signed. The VM first installed version 1.0
and verified the trusted version 2.0 RPM. The candidate repository passed
metadata verification and advertised exactly version 2.0. Strict rpmkeys then
reported payload digest BAD; DNF refused the transaction with both
`Problem opening package int-feed-probe-2.0-r0.noarch.rpm` and
`GPG check FAILED`. Both the RPM database and version file remained at 1.0.

The `corrupt-rpm-indexed` case passed all nine ordered markers and powered off
cleanly. QEMU returned 0; no input/snapshot hash changed. This is a local,
offline laboratory test, not a published package service or recovery test.

Evidence directory: `/workspace/int-linux-work/evidence/qemu-smoke-20261107T235616.604154Z-37cfeff22279`.
Result SHA-256: `abf73733473654da3854f8f8e10bee675862d2a2f912a970343e157bec9da069`.
Serial SHA-256: `bb2b02d24faeacb92499cc7a876856f5e3108f58c0b573be36fc6dd79335971d`.
Elapsed: 42.784 seconds; kernel:
`6.18.54-int-core1`.

Fresh fixtures: `/workspace/int-linux-work/feed-fixtures/resume-20261108`;
disposable fingerprint `1D0AFF8CCBA638843082CA48F8737058B8D7FC4F`.
These keys expire after one day and are never release trust anchors.
The independently recorded disk SHA-256 is
`bbfc9304f187dcccf9fbc84b43aefd326d63afedeefc0d90be8c59e2a7a7e642`.

Build log: `/workspace/int-linux-work/feed-corrupt-build-retry.log`.
Runner log: `/workspace/int-linux-work/feed-corrupt-vm-retry.log`.
The preceding run `qemu-smoke-20261107T235414.515228Z-f5a93821a69b`
failed its assertion because DNF emits a package-opening diagnostic instead
of repeating rpmkeys' digest detail. Its evidence remains retained. The retry
requires the observed DNF diagnostics, the separate BAD digest check, and
unchanged installed state; no failed run was counted as a pass.

Host suite: 269 tests, one skipped (EXT4 inspection tools absent on host).
The actual image and this case were built and executed after the local tests.
Remaining work includes other rejection paths, feed key custody/publication,
network delivery, freshness/replay policy and interrupted-update recovery.
`int-ai packages.install` remains disabled until a usable trusted feed exists.
