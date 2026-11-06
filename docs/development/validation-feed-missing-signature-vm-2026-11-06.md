# Missing repository metadata signature in QEMU — 2026-11-06 UTC

The experimental feed image rejected a local repository whose detached
`repomd.xml.asc` metadata signature was deliberately absent. A valid signed
repository had first installed `int-feed-probe` 1.0. After the rejected
metadata refresh, the guest checked that both the installed RPM database
version and version file still reported 1.0. The test did not attempt an
upgrade using untrusted metadata.

This validates the missing-metadata-signature path for the tested local
fixture and image. It does not validate other metadata or package failures,
network transport, replay prevention, interrupted transactions, production
key custody or release readiness.

## Inputs and evidence

The experimental image rebuild completed 3,963 tasks, of which 3,927 were
already up to date, with no failures. Its log is
`/workspace/int-linux-work/build-image-feed-missing-signature-retry-20261106.log`,
SHA-256 `988a9544deefc79a0080eee9633411f229385bafa2156280e02129466819f74f`.
The target kernel release was `6.18.54-int-core1`. QEMU 8.2.2 ran with TCG
and `qemu64`, a temporary root filesystem snapshot, a separate read-only
virtio fixture disk and no network device.

The independently supplied disposable test-key fingerprint was
`D8F858DAF212985476049E82F0FD22E0B698895A`. This key expires at
2026-11-07 13:19:05 UTC and is not production trust material. The fixture
disk used the earlier isolated set described in
[validation-feed-fixtures-2026-11-06.md](validation-feed-fixtures-2026-11-06.md),
not the later BitBake-generated fixtures. Its SHA-256 is
`392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6`.

The runner was invoked with `--case missing-metadata-signature`; the command
log is `/workspace/int-linux-work/qemu-feed-missing-signature-retry-20261106.log`,
SHA-256 `94bf48e79bc39364292a6c23a6a505f565cded88e49b71f84a1a98dcb7ef87ec`.
Detailed evidence is retained under
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T224158.102257Z-3173b2230c26/`:

| Artifact | SHA-256 |
| --- | --- |
| `result.json` | `77006d5f038e74833882d5f3228992660b975c3abc7ce54c124f8700694a5d4c` |
| `serial.log` | `15047595ee8070d80accdcb723601ab2f2ebfd13e5e018084ad257622ae266e4` |
| Input and snapshot root filesystem | `f25e1f9c6963e5fdb5d2f45b56d3c095f57c2c150385b99ca90619bb8050c1c4` |
| Input and snapshot kernel | `7a2df4e81ed894eee909f600911214b546402b2507bc25dd13c0944b91bbcd1d` |
| Input and snapshot manifest | `466236c761fe34a7078492965ce54d023c912059fc9e680a47aef102cbda02cb` |
| Input and snapshot fixture disk | `392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6` |

The runner reported no input or snapshot hash changes after QEMU exited.

## Observed checks

The guest pinned the public key and installed version 1.0. It then refreshed
the equivalent signed version 2.0 repository and confirmed its candidate as
a positive control. For the negative fixture, the guest verified that
`repomd.xml` and the RPM existed, but `repomd.xml.asc` did not. It also used
the separately supplied signature from the equivalent valid repository to
verify that the negative fixture's `repomd.xml` itself matched the pinned key;
that signature was not provided to DNF for the negative repository.

Using separate metadata cache and trust directories and with
`repo_gpgcheck=1` and `skip_if_unavailable=0`, DNF's metadata refresh returned
nonzero. Its diagnostic contained:

```text
GPG verification is enabled, but GPG signature is not available
.../missing-metadata-signature/repodata/repomd.xml.asc
```

The guest then verified that both installed-state checks still reported 1.0.
The serial transcript contains these eight ordered markers:

```text
INT_FEED_CHECK:pin:PASS
INT_FEED_CHECK:install-v1:PASS
INT_FEED_CHECK:signed-metadata-control:PASS
INT_FEED_CHECK:missing-signature-fixture:PASS
INT_FEED_CHECK:missing-signature-rejected:PASS
INT_FEED_CHECK:unchanged-v1:PASS
INT_FEED_CASE:missing-metadata-signature:PASS
INT_FEED_SHUTDOWN
```

The runner observed `reboot: Power down`, QEMU exit code 0, no timeout or
output limit, and no failure reasons. Elapsed time was 45.703 seconds and
`result.json` recorded `passed`.

## Earlier failed test run

The first attempt is retained at
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T223941.627065Z-7f208d7ca2ff/`.
DNF rejected the missing signature in that attempt too, but its diagnostic
used wording different from the test's overly specific expected text. The
assertion therefore emitted `INT_FEED_FAIL`; the runner correctly reported
`failed` and did not establish the final installed-state check. The check
was corrected to require the observed missing-signature diagnostic and the
specific missing `.asc` path, and the separate retry above passed. The first
attempt's `result.json` SHA-256 is
`0fd4ed57a41c987ab0ec34c0b94aea66521bcb540bdad2439abcd19b67584992` and
its `serial.log` SHA-256 is
`d3524047fdcb92abc619fb147b0fe80001015ce53d67fc703198bab86f0b47f1`.

Separate guest runs cover the [positive update](validation-feed-vm-2026-11-06.md),
[unsigned-package rejection](validation-feed-unsigned-vm-2026-11-06.md) and
[wrong-key RPM rejection](validation-feed-wrong-key-vm-2026-11-06.md).
