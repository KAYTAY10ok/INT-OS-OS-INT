# Referenced primary metadata rejection in QEMU — 2026-11-08

A fresh guest installed version 1.0, then successfully cached and queried a
valid signed version 2.0 repository. The candidate repomd matched that control
and its detached signature verified against the pinned primary key, but the
referenced compressed primary metadata bytes differed. DNF makecache refused
it with `Downloading successful, but checksum doesn't match.` and named the
primary.xml.gz file for repository intfeed-primary. The installed RPM version
and version file both remained at 1.0.

All eight ordered markers, clean shutdown, QEMU return 0 and unchanged source
and snapshot hashes were required. Elapsed: 43.64 seconds.
Evidence: `/workspace/int-linux-work/evidence/qemu-smoke-20261108T020223.796294Z-9724100a4d40`.
Result SHA-256: `dbac62e74698b38210562ca78e80c0c3849af7a864ee8bc071efe9317f5191d6`.
Serial SHA-256: `452169603714190d37c2b03fd1ce3c6d83087f30dfd70edb29dc84edf1074e9c`.
Build: `/workspace/int-linux-work/feed-primary-build-retry.log`.
Run: `/workspace/int-linux-work/feed-primary-vm-retry.log`.

Fixtures: `/workspace/int-linux-work/feed-fixtures/resume-20261108`; disposable
fingerprint `1D0AFF8CCBA638843082CA48F8737058B8D7FC4F` (one-day key).
Disk SHA-256: `bbfc9304f187dcccf9fbc84b43aefd326d63afedeefc0d90be8c59e2a7a7e642`.
No guest network was provided; fixtures were read-only and the rootfs used a
throwaway overlay. This proves the tested local metadata checksum path, not
production key custody, HTTPS distribution, replay protection or recovery.

The first run `qemu-smoke-20261108T020022.978384Z-8abce39c08d7`
observed the intended refusal but failed an expected-message assertion.
Its evidence remains retained. The retry requires the actual checksum text,
primary filename, repository-specific error and unchanged installed state.
