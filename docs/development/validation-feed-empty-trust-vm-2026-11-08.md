# Empty RPM trust database in QEMU — 2026-11-08

The `empty-rpm-trust` case passed in a fresh guest. After a normal signed v1
installation, the test created a separate empty RPM database under `/run` and
confirmed it contained no packages/keys. Strict `rpmkeys` verification of the
valid signed v2 artifact failed nonzero with `NOKEY`, valid digest lines and
no accepted signature. After importing only the independently pinned public
key into that same database, the exact same artifact passed with signature
and digests `OK`. The database contained only `gpg-pubkey`. The installed
system's probe RPM version and file remained at 1.0 throughout.

This isolates RPM trust from DNF's configured automatic public-key import;
it does not claim DNF rejects a correctly configured local key source just
because its package trust database starts empty. It also distinguishes a
working OpenPGP backend from one that would reject both checks.

All eight ordered markers, clean kernel poweroff, QEMU return zero and
unchanged input/snapshot hashes were required. Elapsed: 34.471 seconds.
Evidence: `/workspace/int-linux-work/evidence/qemu-smoke-20261108T021200.438108Z-4856017e4f84`.
Result SHA-256: `c6f281e33803f6ab662a5ac9f4a7d307927e3e286ada5c40a8375d8e9729acab`.
Serial SHA-256: `731e8669c5e5d3d40aa5d35696f025b77a87dfd37c2c56d3cd69f17e6dd7c6e6`.
Build: `/workspace/int-linux-work/feed-empty-trust-build.log` (3,963 tasks,
3,927 already satisfied, all passed).
Run: `/workspace/int-linux-work/feed-empty-trust-vm-retry.log`.
An initial runner invocation supplied the disk directory instead of the file;
it failed before starting QEMU and is retained separately at
`qemu-smoke-20261108T021130.840135Z-837f829042a4`.

Disposable one-day test pin: `1D0AFF8CCBA638843082CA48F8737058B8D7FC4F`.
Fixture disk SHA-256:
`bbfc9304f187dcccf9fbc84b43aefd326d63afedeefc0d90be8c59e2a7a7e642`.
No production key, repository, HTTPS transport or interruption recovery is
qualified by this offline test.
