# Altered repository metadata rejection in QEMU — 2026-11-06 UTC

The experimental feed guest rejected modified `repomd.xml` metadata in a real
QEMU run. Version 1.0 of `int-feed-probe` was first installed from a valid
signed local repository. A separate correctly signed version 2.0 repository
provided a positive metadata and candidate control. The guest then checked
that the candidate signature authenticated the original `repomd.xml` under
the pinned test key but returned `BADSIG` for the modified file. DNF rejected
the altered repository, and both the installed RPM version and its version
file remained at 1.0.

This validates one altered-metadata rejection path for these local fixtures
and this image. It does not qualify other negative cases, network delivery,
production key custody, anti-replay or interrupted-update recovery.

## Inputs and evidence

The image rebuild completed 3,963 tasks, of which 3,927 were already up to
date, without failure. The build log is
`/workspace/int-linux-work/build-image-feed-altered-repomd-20261106.log`,
SHA-256 `7791d8221d2ce8421da90baa26ef8e0e3404963cba92824a3bb4f8fd66ce0580`.
The kernel release was `6.18.54-int-core1`. QEMU 8.2.2 used TCG and `qemu64`,
a temporary root filesystem snapshot, a separate read-only virtio fixture
disk, and no network device.

The independently supplied test-key fingerprint was
`D8F858DAF212985476049E82F0FD22E0B698895A`. This disposable key expired on
2026-11-07 at 13:19:05 UTC and is not release trust material. The fixture
disk used the isolated set described in
[fixture validation](validation-feed-fixtures-2026-11-06.md), not the later
BitBake-generated set. Its SHA-256 is
`392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6`.
New fixtures and an independently recorded new fingerprint are required to
repeat the test after expiry.

The runner was invoked with `--case altered-repomd`; its command log is
`/workspace/int-linux-work/qemu-feed-altered-repomd-20261106.log`, SHA-256
`b0157c6c50e2be3059a1d45fcb9c8991f688590c45ee6628d186c4fcdd1796fc`.
Detailed evidence is retained under
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T224627.972401Z-df13756e4b1f/`:

| Artifact | SHA-256 |
| --- | --- |
| `result.json` | `b4f1be3ea3e1780691db590676087e4a134db7c1352d93aab7b793928213139f` |
| `serial.log` | `6fef4229478480d677395fd1d126ee2cbbeaecdd5edaa37795aef937a0e979f4` |
| Input and snapshot root filesystem | `b6326ec38f6f939a363b46d9f1cd66e2339d4e7100d498f77f42de0888760e57` |
| Input and snapshot kernel | `7a2df4e81ed894eee909f600911214b546402b2507bc25dd13c0944b91bbcd1d` |
| Input and snapshot manifest | `466236c761fe34a7078492965ce54d023c912059fc9e680a47aef102cbda02cb` |
| Input and snapshot fixture disk | `392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6` |

The runner reported no input or snapshot hash changes after QEMU exited.

## Observed result

After the trusted key was pinned and version 1.0 installed, DNF successfully
refreshed the signed control repository and found its version 2.0 candidate.
GnuPG reported `VALIDSIG` for the pinned key when the candidate signature was
checked against the original metadata, then `BADSIG F0FD22E0B698895A` against
the altered metadata. The separate candidate repository used fresh cache and
trust state; its DNF `makecache` failed with:

```text
repomd.xml GPG signature verification error: Bad GPG signature
```

The transcript contains these eight ordered markers:

```text
INT_FEED_CHECK:pin:PASS
INT_FEED_CHECK:install-v1:PASS
INT_FEED_CHECK:signed-metadata-control:PASS
INT_FEED_CHECK:altered-repomd-fixture:PASS
INT_FEED_CHECK:altered-repomd-rejected:PASS
INT_FEED_CHECK:unchanged-v1:PASS
INT_FEED_CASE:altered-repomd:PASS
INT_FEED_SHUTDOWN
```

The runner observed `reboot: Power down`, QEMU exit code 0, no timeout or
output limit, and no failure reasons. Elapsed time was 47.61 seconds;
`result.json` recorded `passed`. Separate runs covered the
[positive update](validation-feed-vm-2026-11-06.md),
[unsigned-package rejection](validation-feed-unsigned-vm-2026-11-06.md),
[wrong-key RPM rejection](validation-feed-wrong-key-vm-2026-11-06.md) and
[missing-signature rejection](validation-feed-missing-signature-vm-2026-11-06.md).
