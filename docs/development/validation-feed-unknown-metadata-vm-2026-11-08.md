# Untrusted metadata signer rejection in QEMU — 2026-11-08

A fresh guest installed version 1.0 and successfully cached/queried the valid
signed version 2.0 repository. Candidate repomd bytes matched the valid
control. GnuPG verified the control under the pinned key, then rejected the
candidate detached signature with NO_PUBKEY and no VALIDSIG in an isolated
keyring containing only the pinned public key (automatic retrieval disabled).
DNF makecache refused the candidate repository with:

```text
repomd.xml GPG signature verification error: Bad GPG signature
```

Both RPM database and installed file remained at 1.0. All eight ordered
markers, clean poweroff, QEMU return 0 and unchanged input/snapshot hashes
were required. Elapsed: 44.613 seconds.
Evidence: `/workspace/int-linux-work/evidence/qemu-smoke-20261108T020539.110806Z-64f5c9e91ec6`.
Result SHA-256: `44701be93811f352952f27cf6332fe47e1f8b6700f73b6f55b55dd7d966b7f62`.
Serial SHA-256: `cb04fb9e8ef5e45cdd7894b6709ac8150553265e1d927d80bef67a5847d2092f`.
Build: `/workspace/int-linux-work/feed-unknown-meta-build.log`.
Run: `/workspace/int-linux-work/feed-unknown-meta-vm.log`.

The fresh disposable key was `1D0AFF8CCBA638843082CA48F8737058B8D7FC4F`
(one-day laboratory key). Disk SHA-256:
`bbfc9304f187dcccf9fbc84b43aefd326d63afedeefc0d90be8c59e2a7a7e642`.
This is one offline file:// trust test, not HTTPS transport, a production
feed, key rotation, replay prevention or interrupted-update recovery.
