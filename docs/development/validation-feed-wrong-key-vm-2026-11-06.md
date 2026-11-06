# Wrong-key RPM rejection in QEMU — 2026-11-06 UTC

The experimental feed image rejected an RPM signed by a different test key
in a real QEMU guest. Version 1.0 had first been installed from a valid
signed local repository. The version 2.0 candidate was signed with another
key, while its repository was freshly indexed and its metadata signed by the
trusted test key. After DNF rejected the upgrade, the guest verified that the
RPM database and installed version file both still reported version 1.0.

This covers one wrong-key package rejection path for the tested local
fixtures and image. Other metadata and package failures, network updates,
interrupted transactions and production trust remain separate work.

## Inputs and evidence

The image rebuild completed 3,963 tasks, of which 3,927 were already up to
date, without failure. The retained build log is
`/workspace/int-linux-work/build-image-feed-wrong-key-20261106.log`, SHA-256
`cda764584b341fb96d347ada95b4c682d0b832bdec9cbe54ec8f99f4209cc42a`.
The kernel release was `6.18.54-int-core1`. QEMU 8.2.2 ran with TCG and
`qemu64`, a temporary root filesystem snapshot, a separate read-only virtio
fixture disk and no network device.

The independently supplied trusted test-key primary fingerprint was
`D8F858DAF212985476049E82F0FD22E0B698895A`. This disposable key expires at
2026-11-07 13:19:05 UTC and is not production trust material. The fixture
disk was the earlier isolated set described in
[validation-feed-fixtures-2026-11-06.md](validation-feed-fixtures-2026-11-06.md),
not the later BitBake-generated fixture set. Its SHA-256 is
`392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6`.

The runner was invoked with `--case wrong-key-rpm`; its command log is
`/workspace/int-linux-work/qemu-feed-wrong-key-20261106.log`, SHA-256
`044675eb6279620db2eed66fd87e58d2bd9af046ba4ceaf7b27269c9bb679ad8`.
Detailed evidence is retained in
`/workspace/int-linux-work/evidence/qemu-smoke-20261106T223510.707245Z-8c015a3c926f/`:

| Artifact | SHA-256 |
| --- | --- |
| `result.json` | `14c6bc0601747032f8eb421f488c086a1da061cf9f1a43f6cf0c8b38153f25ab` |
| `serial.log` | `e8db9b9893d6005ee9cc3960615c4913c985a0d81b6b1e03c111c656aded286d` |
| Input and snapshot root filesystem | `d08329eb36db7d1e2c452c028ba936222d8c3e68c6d37e61dc7e6d56b5bcce79` |
| Input and snapshot kernel | `7a2df4e81ed894eee909f600911214b546402b2507bc25dd13c0944b91bbcd1d` |
| Input and snapshot manifest | `466236c761fe34a7078492965ce54d023c912059fc9e680a47aef102cbda02cb` |
| Input and snapshot fixture disk | `392ba78e1841ed300ee24e69ed6f8856eecc2df146798e821330db6361ac34f6` |

The runner reported no input or snapshot hash changes after QEMU exited.

## Observed result

The guest verified the pinned key and installed version 1.0. DNF then created
the wrong-key candidate repository's metadata cache with signature checking
enabled, and the test required the advertised version 2.0 candidate. As a
positive control, the guest's strict `rpmkeys` check accepted a correctly
signed version 2.0 RPM with the trusted key. A strict check of the wrong-key
candidate returned nonzero and showed `NOKEY`, while its digests were `OK`.

The DNF upgrade returned nonzero. Its serial output included:

```text
The GPG keys listed for the "INT disposable wrong-key package feed" repository are already installed but they are not correct for this package.
Error: GPG check FAILED
```

The guest confirmed the installed RPM database version and version file were
still 1.0. The serial transcript contains these nine ordered markers:

```text
INT_FEED_CHECK:pin:PASS
INT_FEED_CHECK:install-v1:PASS
INT_FEED_CHECK:wrong-key-metadata:PASS
INT_FEED_CHECK:trusted-rpmkeys:PASS
INT_FEED_CHECK:wrong-key-rpmkeys:PASS
INT_FEED_CHECK:wrong-key-dnf-rejected:PASS
INT_FEED_CHECK:unchanged-v1:PASS
INT_FEED_CASE:wrong-key-rpm:PASS
INT_FEED_SHUTDOWN
```

The runner observed `reboot: Power down`, QEMU exit code 0, no timeout or
output limit, and no failure reasons. Elapsed time was 51.169 seconds and
`result.json` recorded `passed`. Earlier separate guest runs covered the
[positive update](validation-feed-vm-2026-11-06.md) and
[unsigned-package rejection](validation-feed-unsigned-vm-2026-11-06.md).
